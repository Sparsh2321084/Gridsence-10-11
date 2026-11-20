import datetime
import hashlib
from pathlib import Path
import struct
import time
import numpy as np
import openpyxl
import pandas as pd
import xlrd
import xlrd.compdoc as compdoc

from paths import EXTRACTED_DIR, REPORTS_DIR

# ==============================================================================
# 1. EXACT DIRECTORY PATHS
# ==============================================================================
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

UTILITY_CONFIG = {
    "brpl": {
        "prefixes": ("BRPL",),
        "sheet_hints": ("BILL BRPL", "BRPL"),
        "aa_keywords": ("RAJDHANI", "BRPL"),
    },
    "tpddl": {
        "prefixes": ("NDPL", "TPDDL"),
        "sheet_hints": ("BILL NDPL", "BILL TPDDL", "NDPL", "TPDDL"),
        "aa_keywords": ("TPDDL", "N.D.P.L", "NDPL"),
    },
    "bypl": {
        "prefixes": ("BYPL",),
        "sheet_hints": ("BILL BYPL", "BYPL"),
        "aa_keywords": ("YAMUNA", "BYPL"),
    },
    "ndmc": {
        "prefixes": ("NDMC",),
        "sheet_hints": ("BILL NDMC", "NDMC"),
        "aa_keywords": ("NDMC",),
    },
    "mes": {
        "prefixes": ("MES",),
        "sheet_hints": ("MES", "BILL MES"),
        "aa_keywords": ("MES",),
    },
    "railways": {
        "prefixes": ("NORTHERN RAILWAY", "N.RLY", "NRLY", "RAILWAY"),
        "sheet_hints": ("NORTHERN RAILWAY", "RAILWAY"),
        "aa_keywords": ("RAILWAY",),
    },
}

KNOWN_OTHER_PREFIXES = (
    "AMOUNT ACCOUNT",
    "11KV",
    "ASSESSMENT",
    "BTPS",
    "COMPANY WISE",
    "EAST DELHI",
    "GT STN",
    "IP STN",
    "MSW",
    "PPCL",
    "PRAGATI",
    "RPH",
    "TEHKHAND",
)


# ==============================================================================
# 2. FAST SELECTIVE BIFF8 DECRYPTOR & LIGHTWEIGHT SHEET INSPECTOR
# ==============================================================================
def _rc4_block_keystream(h1: bytes, block_num: int) -> bytes:
    """Generates the 1024-byte RC4 keystream for one BIFF8 1024-byte block."""
    key = hashlib.md5(h1 + struct.pack("<I", block_num)).digest()
    S = bytearray(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + key[i & 15]) & 0xFF
        S[i], S[j] = S[j], S[i]
    i = j = 0
    ks = bytearray(1024)
    for idx in range(1024):
        i = (i + 1) & 0xFF
        j = (j + S[i]) & 0xFF
        si = S[i]
        sj = S[j]
        S[i] = sj
        S[j] = si
        ks[idx] = S[(si + sj) & 0xFF]
    return bytes(ks)


def decrypt_biff8_selective(
    raw_bytes: bytes,
    target_hints: tuple[str, ...],
    fallback_idx: int = 3,
    password: str = "VelvetSweatshop",
) -> bytes:
    cd = compdoc.CompDoc(raw_bytes)
    wb_stream, wb_base, wb_len = cd.locate_named_stream("Workbook")
    if wb_stream is None:
        wb_stream, wb_base, wb_len = cd.locate_named_stream("Book")

    stream = bytearray(wb_stream[wb_base : wb_base + wb_len])
    UNENCRYPTED_RECS = {0x0809, 0x002F, 0x00E1, 0x0086, 0x005B, 0x0042, 0x0161, 0x013D}
    ks_cache: dict[int, bytes] = {}

    def decrypt_slice(start: int, end: int, h1_key: bytes) -> bytes:
        n = end - start
        if n <= 0:
            return b""
        ks_parts = bytearray()
        cur = start
        while cur < end:
            bnum = cur // 1024
            boff = cur % 1024
            take = min(1024 - boff, end - cur)
            ks = ks_cache.get(bnum)
            if ks is None:
                ks = _rc4_block_keystream(h1_key, bnum)
                ks_cache[bnum] = ks
            ks_parts.extend(ks[boff : boff + take])
            cur += take
        data_bytes = bytes(stream[start:end])
        return (
            int.from_bytes(data_bytes, "little") ^ int.from_bytes(ks_parts, "little")
        ).to_bytes(n, "little")

    pos = 0
    h1 = None
    sheets: list[tuple[str, int]] = []
    while pos + 4 <= len(stream):
        rec_id, rec_len = struct.unpack_from("<HH", stream, pos)
        rec_start = pos + 4
        rec_end = rec_start + rec_len
        if rec_end > len(stream):
            break

        if rec_id == 0x002F:
            enc_type, v_maj, v_min = struct.unpack_from("<HHH", stream, rec_start)
            if enc_type == 1 and v_maj == 1 and v_min == 1:
                salt = bytes(stream[rec_start + 6 : rec_start + 22])
                pw_utf16 = password[:15].encode("utf-16le")
                h0 = hashlib.md5(pw_utf16).digest()[:5]
                h1 = hashlib.md5((h0 + salt) * 16).digest()[:5]
                struct.pack_into("<H", stream, pos, 0x004D)
        elif h1 is not None and rec_id not in UNENCRYPTED_RECS and rec_len > 0:
            dec_chunk = decrypt_slice(rec_start, rec_end, h1)
            if rec_id == 0x0085:
                lbPlyPos = struct.unpack_from("<I", stream, rec_start)[0]
                stream[rec_start + 4 : rec_end] = dec_chunk[4:]
                cch = dec_chunk[6]
                flags = dec_chunk[7]
                if flags & 0x01:
                    sname = dec_chunk[8 : 8 + 2 * cch].decode("utf-16le", errors="replace")
                else:
                    sname = dec_chunk[8 : 8 + cch].decode("latin1", errors="replace")
                sheets.append((sname, lbPlyPos))
            else:
                stream[rec_start:rec_end] = dec_chunk

        pos = rec_end
        if rec_id == 0x000A:
            break

    if h1 is not None and sheets:
        sheets_sorted = sorted(sheets, key=lambda x: x[1])
        target_range = None
        for idx_s, (sname, s_start) in enumerate(sheets_sorted):
            if any(sname.strip().upper() == h for h in target_hints):
                s_end = (
                    sheets_sorted[idx_s + 1][1]
                    if idx_s + 1 < len(sheets_sorted)
                    else len(stream)
                )
                target_range = (s_start, s_end)
                break
        if target_range is None and len(sheets_sorted) > fallback_idx:
            s_start = sheets_sorted[fallback_idx][1]
            s_end = (
                sheets_sorted[fallback_idx + 1][1]
                if fallback_idx + 1 < len(sheets_sorted)
                else len(stream)
            )
            target_range = (s_start, s_end)
        if target_range is None:
            target_range = (pos, len(stream))

        pos, limit = target_range
        while pos + 4 <= limit:
            rec_id, rec_len = struct.unpack_from("<HH", stream, pos)
            rec_start = pos + 4
            rec_end = rec_start + rec_len
            if rec_end > limit:
                break
            if rec_id not in UNENCRYPTED_RECS and rec_len > 0:
                stream[rec_start:rec_end] = decrypt_slice(rec_start, rec_end, h1)
            pos = rec_end
            if rec_id == 0x000A:
                break

    out_bytes = bytearray(raw_bytes)
    for d in cd.dirlist:
        if d.name in ("Workbook", "Book") and d.etype == 2:
            sec = d.first_SID
            written = 0
            sec_size = cd.sec_size
            while sec >= 0 and written < len(stream):
                offset = 512 + sec * sec_size
                take = min(sec_size, len(stream) - written)
                out_bytes[offset : offset + take] = stream[written : written + take]
                written += take
                sec = cd.SAT[sec]
            break

    return bytes(out_bytes)


def pick_sheet_name(sheet_names: list[str], hints: tuple[str, ...], fallback_idx: int) -> str:
    for hint in hints:
        for s in sheet_names:
            if s.strip().upper() == hint:
                return s
    idx = fallback_idx if len(sheet_names) > fallback_idx else 0
    return sheet_names[idx]


def load_sheet_rows(
    filepath: Path, sheet_hints: tuple[str, ...], fallback_idx: int = 3
) -> tuple[list[list], list[str], str, bool]:
    """Returns (rows_2d, all_sheet_names, matched_sheet_name, was_encrypted)."""
    ext = filepath.suffix.lower()
    if ext in (".xlsx", ".xlsm"):
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        sheet_names = list(wb.sheetnames)
        target_sheet = pick_sheet_name(sheet_names, sheet_hints, fallback_idx)
        ws = wb[target_sheet]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()
        return rows, sheet_names, target_sheet, False

    raw_bytes = filepath.read_bytes()
    was_encrypted = False
    try:
        wb = xlrd.open_workbook(
            file_contents=raw_bytes, on_demand=True, encoding_override="cp1252"
        )
    except xlrd.biffh.XLRDError as e:
        if "encrypted" in str(e).lower():
            was_encrypted = True
            dec_bytes = decrypt_biff8_selective(
                raw_bytes, sheet_hints, fallback_idx=fallback_idx
            )
            wb = xlrd.open_workbook(
                file_contents=dec_bytes, on_demand=True, encoding_override="cp1252"
            )
        else:
            raise

    sheet_names = list(wb.sheet_names())
    target_sheet = pick_sheet_name(sheet_names, sheet_hints, fallback_idx)
    sh = wb.sheet_by_name(target_sheet)
    rows = []
    for r in range(sh.nrows):
        row_vals = []
        for c in range(sh.ncols):
            ctype = sh.cell_type(r, c)
            cval = sh.cell_value(r, c)
            if ctype == xlrd.XL_CELL_DATE:
                dt = xlrd.xldate_as_datetime(cval, wb.datemode)
                row_vals.append(dt.time() if dt.year <= 1900 else dt)
            elif ctype == xlrd.XL_CELL_EMPTY:
                row_vals.append(None)
            else:
                row_vals.append(cval)
        rows.append(row_vals)
    wb.release_resources()
    return rows, sheet_names, target_sheet, was_encrypted


# ==============================================================================
# 3. CELL & HEADER AUDIT HELPERS
# ==============================================================================
def parse_date_cell(val) -> datetime.date | None:
    if isinstance(val, (datetime.datetime, pd.Timestamp)):
        return val.date()
    if isinstance(val, str):
        s = val.strip()
        if ":" not in s and len(s) >= 8:
            dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
            if pd.notna(dt) and 2018 <= dt.year <= 2030:
                return dt.date()
    return None


def parse_time_cell(val) -> datetime.time | None:
    if isinstance(val, datetime.time):
        return val
    if isinstance(val, datetime.datetime):
        if val.year <= 1900:
            return val.time()
    if isinstance(val, str) and ":" in val:
        parts = val.strip().split(":")
        try:
            hh, mm = int(parts[0]), int(parts[1])
            ss = int(parts[2]) if len(parts) > 2 else 0
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                return datetime.time(hh, mm, ss)
        except ValueError:
            return None
    return None


def match_energy_column(row: list) -> tuple[int, str, str]:
    """Returns (col_idx, normalized_header, unit_str)."""
    headers = {
        c: " ".join(str(val).upper().split())
        for c, val in enumerate(row)
        if c > 0 and val is not None and str(val).strip() != ""
    }
    for priority_terms in (
        ("TOTAL ENERGY IN MUS", "TOTAL ENERGY IN MW"),
        ("ACTUAL ENERGY IN MUS", "ACTUAL ENERGY IN MW"),
        ("ENERGY DRAWL IN MUS", "ENERGY GRAWL IN MUS", "ENERGY DRAWL IN MW"),
    ):
        for c, h in headers.items():
            if any(term in h for term in priority_terms):
                unit = "MW" if "MW" in h else "Mus"
                return c, h, unit

    raise ValueError(f"Header mismatch: {list(headers.values())[:5]}")


def audit_utility_file(filepath: Path, sheet_hints: tuple[str, ...]) -> dict:
    rows, sheet_names, matched_sheet, was_enc = load_sheet_rows(
        filepath, sheet_hints, fallback_idx=3
    )

    dates_seen = []
    time_rows = 0
    total_mu = 0.0
    selected_col = None
    selected_header = ""
    unit = ""

    for row in rows:
        if not row:
            continue
        val0 = row[0]
        dt_val = parse_date_cell(val0)
        if dt_val is not None:
            dates_seen.append(dt_val)
            col_idx, norm_hdr, u = match_energy_column(row)
            selected_col = col_idx
            selected_header = norm_hdr
            unit = u
            continue

        t_val = parse_time_cell(val0)
        if t_val is not None and dates_seen and selected_col is not None:
            if selected_col < len(row) and row[selected_col] is not None:
                num = pd.to_numeric(row[selected_col], errors="coerce")
                if pd.notna(num):
                    time_rows += 1
                    total_mu += float(num) if unit == "Mus" else float(num) / 4000.0

    return {
        "encrypted": was_enc,
        "sheet_names": " | ".join(sheet_names),
        "matched_sheet": matched_sheet,
        "date_blocks": len(dates_seen),
        "time_rows": time_rows,
        "min_date": str(min(dates_seen)) if dates_seen else "",
        "max_date": str(max(dates_seen)) if dates_seen else "",
        "selected_col_idx": selected_col if selected_col is not None else -1,
        "selected_header": selected_header,
        "unit": unit,
        "extracted_mu": round(total_mu, 6),
    }


def audit_amount_account(filepath: Path) -> tuple[dict[str, float], str]:
    rows, sheet_names, matched_sheet, _ = load_sheet_rows(
        filepath, ("NEW FORMAT",), fallback_idx=0
    )
    expected = {}
    for row in rows:
        label_col = None
        row_text = ""
        for c, v in enumerate(row):
            if v is not None and "ACCOUNT OF" in " ".join(str(v).upper().split()):
                label_col = c
                row_text = " ".join(str(v).upper().split())
                break
        if label_col is None:
            continue

        nums = []
        for v in row[label_col + 1 :]:
            if v is not None:
                n = pd.to_numeric(v, errors="coerce")
                if pd.notna(n):
                    nums.append(float(n))
        if not nums:
            continue

        for entity, cfg in UTILITY_CONFIG.items():
            if any(k in row_text for k in cfg["aa_keywords"]):
                expected[entity] = nums[0]
                break

    return expected, f"{matched_sheet} (sheets: {' | '.join(sheet_names)})"


# ==============================================================================
# 4. MAIN DIRECTORY & SCHEMA AUDITOR
# ==============================================================================
def run_audit():
    t0 = time.perf_counter()
    if not EXTRACTED_DIR.exists():
        raise FileNotFoundError(f"Directory not found: {EXTRACTED_DIR}")

    fy_folders = sorted(d for d in EXTRACTED_DIR.iterdir() if d.is_dir())
    week_inventory_rows = []
    file_detail_rows = []

    print(f"Starting read-only audit of: {EXTRACTED_DIR}")
    print(f"Found {len(fy_folders)} financial year folders.\n")

    for fy_dir in fy_folders:
        t_fy = time.perf_counter()
        fy = fy_dir.name
        week_folders = sorted(w for w in fy_dir.iterdir() if w.is_dir())
        fy_ok = 0
        fy_issues = 0

        for week_dir in week_folders:
            week_name = week_dir.name
            all_files = [
                p for p in week_dir.rglob("*")
                if p.is_file() and not p.name.startswith("~$")
            ]
            archive_files = [
                p.name for p in all_files
                if p.suffix.lower() in (".zip", ".rar", ".7z")
            ]
            excel_files = sorted(
                p for p in all_files
                if p.suffix.lower() in (".xls", ".xlsx", ".xlsm")
            )

            aa_matches = sorted(
                (f for f in excel_files if f.stem.strip().upper().startswith("AMOUNT ACCOUNT")),
                key=lambda p: (0 if p.suffix.lower() == ".xls" else 1, p.name),
            )
            expected_mus = {}
            aa_info = "MISSING"
            if aa_matches:
                try:
                    expected_mus, aa_info = audit_amount_account(aa_matches[0])
                except Exception as e:
                    aa_info = f"ERROR: {e}"
                    file_detail_rows.append({
                        "fy": fy, "week": week_name, "entity": "amount_account",
                        "status": f"AA_ERROR: {e}", "file_ext": aa_matches[0].suffix,
                        "encrypted": False, "sheet_names": "", "matched_sheet": "",
                        "date_blocks": 0, "time_rows": 0, "min_date": "", "max_date": "",
                        "selected_col_idx": -1, "selected_header": "", "unit": "",
                        "extracted_mu": np.nan, "expected_mu": np.nan, "diff_mu": np.nan,
                        "source_file": str(aa_matches[0]),
                    })

            matched_paths = set(aa_matches)
            entity_counts = {}
            week_has_issue = bool(archive_files) or (not aa_matches)

            for entity, cfg in UTILITY_CONFIG.items():
                matches = sorted(
                    (f for f in excel_files if f.stem.strip().upper().startswith(cfg["prefixes"])),
                    key=lambda p: (0 if p.suffix.lower() == ".xls" else 1, p.name),
                )
                if not matches:
                    matches = sorted(
                        (
                            f for f in excel_files
                            if any(p in f.stem.strip().upper() for p in cfg["prefixes"])
                        ),
                        key=lambda p: (0 if p.suffix.lower() == ".xls" else 1, p.name),
                    )
                entity_counts[entity] = len(matches)
                matched_paths.update(matches)

                if not matches:
                    week_has_issue = True
                    fy_issues += 1
                    file_detail_rows.append({
                        "fy": fy, "week": week_name, "entity": entity,
                        "status": "MISSING_FILE", "file_ext": "",
                        "encrypted": False, "sheet_names": "", "matched_sheet": "",
                        "date_blocks": 0, "time_rows": 0, "min_date": "", "max_date": "",
                        "selected_col_idx": -1, "selected_header": "", "unit": "",
                        "extracted_mu": np.nan,
                        "expected_mu": expected_mus.get(entity, np.nan),
                        "diff_mu": np.nan,
                        "source_file": "",
                    })
                    continue

                target_file = matches[0]
                try:
                    info = audit_utility_file(target_file, cfg["sheet_hints"])
                    exp_mu = expected_mus.get(entity, np.nan)
                    diff_mu = info["extracted_mu"] - exp_mu if pd.notna(exp_mu) else np.nan

                    if info["time_rows"] == 0:
                        status = "EMPTY_ROWS"
                    elif pd.notna(diff_mu) and abs(diff_mu) >= 0.005:
                        status = "MU_MISMATCH"
                    elif info["time_rows"] != 672:
                        status = f"NON_672_ROWS ({info['time_rows']})"
                    elif len(matches) > 1:
                        status = f"OK_DUPLICATE_FILES ({len(matches)})"
                    else:
                        status = "OK"

                    if status.startswith("OK"):
                        fy_ok += 1
                    else:
                        fy_issues += 1
                        week_has_issue = True

                    file_detail_rows.append({
                        "fy": fy, "week": week_name, "entity": entity,
                        "status": status, "file_ext": target_file.suffix,
                        **info,
                        "expected_mu": round(exp_mu, 6) if pd.notna(exp_mu) else np.nan,
                        "diff_mu": round(diff_mu, 6) if pd.notna(diff_mu) else np.nan,
                        "source_file": str(target_file),
                    })
                except Exception as e:
                    fy_issues += 1
                    week_has_issue = True
                    file_detail_rows.append({
                        "fy": fy, "week": week_name, "entity": entity,
                        "status": f"OPEN_OR_PARSE_ERROR: {e}", "file_ext": target_file.suffix,
                        "encrypted": False, "sheet_names": "", "matched_sheet": "",
                        "date_blocks": 0, "time_rows": 0, "min_date": "", "max_date": "",
                        "selected_col_idx": -1, "selected_header": "", "unit": "",
                        "extracted_mu": np.nan,
                        "expected_mu": expected_mus.get(entity, np.nan),
                        "diff_mu": np.nan,
                        "source_file": str(target_file),
                    })

            unmatched_unknown = [
                f.name for f in excel_files
                if f not in matched_paths
                and not f.stem.strip().upper().startswith(KNOWN_OTHER_PREFIXES)
            ]

            week_inventory_rows.append({
                "fy": fy,
                "week": week_name,
                "excel_files_count": len(excel_files),
                "archives_found": " | ".join(archive_files),
                "aa_count": len(aa_matches),
                "aa_sheet_info": aa_info,
                **{f"{k}_count": v for k, v in entity_counts.items()},
                "unrecognized_excel_files": " | ".join(unmatched_unknown),
                "week_status": "REVIEW_NEEDED" if week_has_issue else "CLEAN",
            })

        print(
            f"[{fy}] Weeks: {len(week_folders):2d} | Entity checks OK: {fy_ok:3d} | "
            f"Issues: {fy_issues:2d} | Time: {time.perf_counter() - t_fy:.1f}s"
        )

    df_inv = pd.DataFrame(week_inventory_rows)
    df_det = pd.DataFrame(file_detail_rows)

    inv_path = REPORTS_DIR / "audit_week_inventory.csv"
    det_path = REPORTS_DIR / "audit_file_details.csv"
    df_inv.to_csv(inv_path, index=False)
    df_det.to_csv(det_path, index=False)

    lines = []
    lines.append("=" * 80)
    lines.append(f"DELHI LOAD DATA AUDIT SUMMARY  (Completed in {time.perf_counter() - t0:.1f}s)")
    lines.append("=" * 80)
    lines.append(f"Total Financial Years : {df_inv['fy'].nunique()}")
    lines.append(f"Total Week Folders    : {len(df_inv)}")
    lines.append(f"Clean Weeks           : {(df_inv['week_status'] == 'CLEAN').sum()}")
    lines.append(f"Weeks Needing Review  : {(df_inv['week_status'] != 'CLEAN').sum()}")
    lines.append("\n--- ENTITY-WEEK STATUS BREAKDOWN ---")
    lines.append(df_det["status"].value_counts().to_string())

    lines.append("\n--- UNIQUE MATCHED SHEETS PER ENTITY ---")
    for ent, grp in df_det[df_det["matched_sheet"] != ""].groupby("entity"):
        lines.append(f"  {ent:10s}: {sorted(grp['matched_sheet'].unique())}")

    lines.append("\n--- UNIQUE SELECTED HEADERS PER ENTITY ---")
    for ent, grp in df_det[df_det["selected_header"] != ""].groupby("entity"):
        lines.append(f"  {ent:10s}: {sorted(grp['selected_header'].unique())}")

    archives = df_inv[df_inv["archives_found"] != ""]
    lines.append(f"\n--- UNEXTRACTED ARCHIVES FOUND ({len(archives)} weeks) ---")
    if not archives.empty:
        lines.append(archives[["fy", "week", "archives_found"]].to_string(index=False))

    unknowns = df_inv[df_inv["unrecognized_excel_files"] != ""]
    lines.append(f"\n--- UNRECOGNIZED EXCEL FILENAMES ({len(unknowns)} weeks) ---")
    if not unknowns.empty:
        lines.append(unknowns[["fy", "week", "unrecognized_excel_files"]].head(30).to_string(index=False))

    non_ok = df_det[~df_det["status"].str.startswith("OK")]
    lines.append(f"\n--- NON-OK FILE DETAILS ({len(non_ok)} total, showing first 40) ---")
    if not non_ok.empty:
        lines.append(
            non_ok[["fy", "week", "entity", "status", "time_rows", "diff_mu", "source_file"]]
            .head(40)
            .to_string(index=False)
        )

    overview_text = "\n".join(lines)
    overview_path = REPORTS_DIR / "audit_overview.txt"
    overview_path.write_text(overview_text, encoding="utf-8")

    print("\n" + overview_text)
    print("\nSaved reports to:")
    print(f"  1. {overview_path}")
    print(f"  2. {inv_path}")
    print(f"  3. {det_path}")


if __name__ == "__main__":
    run_audit()
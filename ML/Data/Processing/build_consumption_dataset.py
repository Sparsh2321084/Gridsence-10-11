import datetime
import hashlib
import importlib.util
from pathlib import Path
import struct
import time
import numpy as np
import openpyxl
import pandas as pd
import xlrd
import xlrd.compdoc as compdoc

from paths import (
    DATASET_DIR,
    EXTRACTED_DIR,
    PROCESSING_DIR,
    REPORTS_DIR,
    YEARLY_DIR,
)

# ==============================================================================
# 1. EXACT DIRECTORY PATHS
# ==============================================================================

for folder in (PROCESSING_DIR, REPORTS_DIR, DATASET_DIR, YEARLY_DIR):
    folder.mkdir(parents=True, exist_ok=True)

HAS_PARQUET = (
    importlib.util.find_spec("pyarrow") is not None
    or importlib.util.find_spec("fastparquet") is not None
)

UTILITY_CONFIG = {
    "brpl_mw": {
        "prefixes": ("BRPL",),
        "sheet_hints": ("BILL BRPL", "BRPL"),
        "aa_keywords": ("RAJDHANI", "BRPL"),
    },
    "tpddl_mw": {
        "prefixes": ("NDPL", "TPDDL"),
        "sheet_hints": ("BILL NDPL", "BILL TPDDL", "NDPL", "TPDDL"),
        "aa_keywords": ("TPDDL", "N.D.P.L", "NDPL"),
    },
    "bypl_mw": {
        "prefixes": ("BYPL",),
        "sheet_hints": ("BILL BYPL", "BYPL"),
        "aa_keywords": ("YAMUNA", "BYPL"),
    },
    "ndmc_mw": {
        "prefixes": ("NDMC",),
        "sheet_hints": ("BILL NDMC", "NDMC"),
        "aa_keywords": ("NDMC",),
    },
    "mes_mw": {
        "prefixes": ("MES",),
        "sheet_hints": ("MES", "BILL MES"),
        "aa_keywords": ("MES",),
    },
    "railways_mw": {
        "prefixes": ("NORTHERN RAILWAY", "N.RLY", "NRLY", "RAILWAY"),
        "sheet_hints": ("NORTHERN RAILWAY", "RAILWAY"),
        "aa_keywords": ("RAILWAY",),
    },
}


# ==============================================================================
# 2. FAST SELECTIVE BIFF8 DECRYPTOR & DIRECT SHEET READER
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
    """Decrypts ONLY workbook globals and the target billing tab."""
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
) -> tuple[list[list], str]:
    ext = filepath.suffix.lower()
    if ext in (".xlsx", ".xlsm"):
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        sheet_names = list(wb.sheetnames)
        target_sheet = pick_sheet_name(sheet_names, sheet_hints, fallback_idx)
        ws = wb[target_sheet]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()
        return rows, target_sheet

    raw_bytes = filepath.read_bytes()
    try:
        wb = xlrd.open_workbook(
            file_contents=raw_bytes, on_demand=True, encoding_override="cp1252"
        )
    except xlrd.biffh.XLRDError as e:
        if "encrypted" in str(e).lower():
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
    return rows, target_sheet


# ==============================================================================
# 3. UTILITY BILLING TAB & AMOUNT ACCOUNT PARSERS
# ==============================================================================
def select_target_column(row: list) -> tuple[int, bool]:
    """Returns (column_index, is_in_mus) across all utility sheet layouts."""
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
                is_mus = "MW" not in h
                return c, is_mus

    raise ValueError(f"Unrecognized headers: {list(headers.values())[:5]}")


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
    if isinstance(val, datetime.datetime) and val.year <= 1900:
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


def parse_utility_workbook(
    filepath: Path, sheet_hints: tuple[str, ...]
) -> tuple[pd.DataFrame, str]:
    """
    Extracts 672 15-min intervals (MU & MW) and automatically repairs single-day
    SLDC date-header typos (such as 2019-2020 Week_19 where 2019-08-05 was typed
    as 2019-05-06 in US date format).
    """
    rows, target_sheet = load_sheet_rows(filepath, sheet_hints, fallback_idx=3)
    day_blocks: list[dict] = []
    current_block: dict | None = None

    for row in rows:
        if not row:
            continue
        val0 = row[0]
        dt_val = parse_date_cell(val0)
        if dt_val is not None:
            col_idx, is_mus = select_target_column(row)
            current_block = {
                "raw_date": dt_val,
                "col_idx": col_idx,
                "is_mus": is_mus,
                "entries": [],
            }
            day_blocks.append(current_block)
            continue

        t_val = parse_time_cell(val0)
        if t_val is not None and current_block is not None:
            col_idx = current_block["col_idx"]
            if col_idx < len(row) and row[col_idx] is not None:
                raw_num = pd.to_numeric(row[col_idx], errors="coerce")
                if pd.notna(raw_num):
                    is_mus = current_block["is_mus"]
                    mu_val = float(raw_num) if is_mus else float(raw_num) / 4000.0
                    mw_val = float(raw_num) * 4000.0 if is_mus else float(raw_num)
                    current_block["entries"].append((t_val, mu_val, mw_val))

    day_blocks = [b for b in day_blocks if b["entries"]]
    if not day_blocks:
        raise ValueError(f"Zero 15-min rows extracted from {filepath.name} [{target_sheet}]")

    note = ""
    raw_dates = [b["raw_date"] for b in day_blocks]
    if len(day_blocks) == 7 and (max(raw_dates) - min(raw_dates)).days != 6:
        # Snap sequential 7-day block to contiguous 7 days ending on max_date
        anchor_end = max(raw_dates)
        expected_dates = [anchor_end - datetime.timedelta(days=6 - i) for i in range(7)]
        # Verify at least 5 of the 7 dates already match the expected week
        matches = sum(1 for d in raw_dates if d in expected_dates)
        if matches >= 5:
            note = f"DATE_TYPO_FIXED ({min(raw_dates)} -> {expected_dates[0]})"
            for b, fixed_d in zip(day_blocks, expected_dates):
                b["raw_date"] = fixed_d

    records = []
    for b in day_blocks:
        d = b["raw_date"]
        for t_val, mu_val, mw_val in b["entries"]:
            records.append({
                "timestamp": pd.Timestamp.combine(d, t_val),
                "mu": mu_val,
                "mw": mw_val,
            })

    return pd.DataFrame(records), note


def parse_amount_account(filepath: Path) -> dict[str, float]:
    """Extracts official weekly MU totals per utility from AMOUNT ACCOUNT.xls."""
    rows, _ = load_sheet_rows(filepath, ("NEW FORMAT",), fallback_idx=0)
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

        for col_name, cfg in UTILITY_CONFIG.items():
            if any(k in row_text for k in cfg["aa_keywords"]):
                expected[col_name] = nums[0]
                break

    return expected


def find_utility_file(xls_files: list[Path], prefixes: tuple[str, ...]) -> Path | None:
    """Matches utility files by prefix first, preferring original .xls over duplicate .xlsx."""
    ordered = sorted(xls_files, key=lambda p: (0 if p.suffix.lower() == ".xls" else 1, p.name))
    for f in ordered:
        if f.stem.strip().upper().startswith(prefixes):
            return f
    for f in ordered:
        stem_upper = f.stem.strip().upper()
        if any(p in stem_upper for p in prefixes):
            return f
    return None


# ==============================================================================
# 4. MAIN EXTRACTION & AUDIT PIPELINE
# ==============================================================================
def run_extraction():
    t_start = time.perf_counter()
    audit_rows = []
    yearly_frames = []

    fy_folders = sorted(d for d in EXTRACTED_DIR.iterdir() if d.is_dir())
    if not fy_folders:
        raise FileNotFoundError(f"No financial year folders found in {EXTRACTED_DIR}")

    for fy_dir in fy_folders:
        t_fy = time.perf_counter()
        fy = fy_dir.name
        week_folders = sorted(w for w in fy_dir.iterdir() if w.is_dir())
        print(f"[{fy}] Processing {len(week_folders):2d} weeks...", end=" ", flush=True)
        fy_buckets = {col: [] for col in UTILITY_CONFIG}

        for week_dir in week_folders:
            week_name = week_dir.name
            xls_files = sorted(
                p
                for p in week_dir.rglob("*")
                if p.is_file()
                and p.suffix.lower() in (".xls", ".xlsx", ".xlsm")
                and not p.name.startswith("~$")
            )

            aa_files = sorted(
                (f for f in xls_files if f.stem.strip().upper().startswith("AMOUNT ACCOUNT")),
                key=lambda p: (0 if p.suffix.lower() == ".xls" else 1, p.name),
            )
            expected_mus = {}
            if aa_files:
                try:
                    expected_mus = parse_amount_account(aa_files[0])
                except Exception as e:
                    audit_rows.append({
                        "fy": fy,
                        "week": week_name,
                        "entity": "AMOUNT_ACCOUNT",
                        "status": f"PARSE_ERROR: {e}",
                        "rows": 0,
                        "extracted_mu": np.nan,
                        "expected_mu": np.nan,
                        "diff_mu": np.nan,
                        "source_file": str(aa_files[0]),
                    })

            for col_name, cfg in UTILITY_CONFIG.items():
                target_file = find_utility_file(xls_files, cfg["prefixes"])
                if target_file is None:
                    audit_rows.append({
                        "fy": fy,
                        "week": week_name,
                        "entity": col_name,
                        "status": "MISSING_FILE",
                        "rows": 0,
                        "extracted_mu": np.nan,
                        "expected_mu": expected_mus.get(col_name, np.nan),
                        "diff_mu": np.nan,
                        "source_file": "",
                    })
                    continue

                try:
                    df_u, fix_note = parse_utility_workbook(target_file, cfg["sheet_hints"])
                    fy_buckets[col_name].append(df_u[["timestamp", "mw"]])

                    ext_mu = df_u["mu"].sum()
                    exp_mu = expected_mus.get(col_name, np.nan)
                    diff_mu = ext_mu - exp_mu if pd.notna(exp_mu) else np.nan
                    if fix_note:
                        status = fix_note
                    elif pd.isna(diff_mu) or abs(diff_mu) < 0.005:
                        status = "OK"
                    else:
                        status = "FEEDER_BOUNDARY_DIFF"

                    audit_rows.append({
                        "fy": fy,
                        "week": week_name,
                        "entity": col_name,
                        "status": status,
                        "rows": len(df_u),
                        "extracted_mu": round(ext_mu, 6),
                        "expected_mu": round(exp_mu, 6) if pd.notna(exp_mu) else np.nan,
                        "diff_mu": round(diff_mu, 6) if pd.notna(diff_mu) else np.nan,
                        "source_file": str(target_file),
                    })
                except Exception as e:
                    audit_rows.append({
                        "fy": fy,
                        "week": week_name,
                        "entity": col_name,
                        "status": f"ERROR: {e}",
                        "rows": 0,
                        "extracted_mu": np.nan,
                        "expected_mu": expected_mus.get(col_name, np.nan),
                        "diff_mu": np.nan,
                        "source_file": str(target_file),
                    })

        merged_cols = []
        for col_name, parts in fy_buckets.items():
            if parts:
                s = (
                    pd.concat(parts, ignore_index=True)
                    .drop_duplicates(subset=["timestamp"], keep="last")
                    .sort_values("timestamp")
                    .set_index("timestamp")["mw"]
                    .rename(col_name)
                )
                merged_cols.append(s)

        if merged_cols:
            df_fy = pd.concat(merged_cols, axis=1).sort_index()
            df_fy.to_csv(YEARLY_DIR / f"delhi_consumption_{fy}.csv")
            if HAS_PARQUET:
                df_fy.to_parquet(YEARLY_DIR / f"delhi_consumption_{fy}.parquet")
            yearly_frames.append(df_fy)
            print(f"Done ({len(df_fy):6,} rows in {time.perf_counter() - t_fy:4.1f}s)")
        else:
            print(f"No rows extracted ({time.perf_counter() - t_fy:.1f}s)")

    df_audit = pd.DataFrame(audit_rows)
    audit_csv = REPORTS_DIR / "weekly_audit_report.csv"
    df_audit.to_csv(audit_csv, index=False)

    if not yearly_frames:
        raise RuntimeError(f"No data extracted. Check {audit_csv} for details.")

    # Combine all financial years onto a strict 15-minute continuous timeline
    master = pd.concat(yearly_frames).sort_index()
    master = master[~master.index.duplicated(keep="last")]
    full_idx = pd.date_range(master.index.min(), master.index.max(), freq="15min")
    master = master.reindex(full_idx)
    master.index.name = "timestamp"

    utility_cols = list(UTILITY_CONFIG.keys())
    master = master.reindex(columns=utility_cols)
    master["delhi_total_mw"] = master[utility_cols].sum(axis=1, min_count=len(utility_cols))

    final_df = master.reset_index()

    out_csv = DATASET_DIR / "delhi_consumption_2019_2026.csv"
    final_df.to_csv(out_csv, index=False)
    if HAS_PARQUET:
        final_df.to_parquet(DATASET_DIR / "delhi_consumption_2019_2026.parquet", index=False)

    summary_rows = []
    for col in utility_cols + ["delhi_total_mw"]:
        s = final_df[col]
        summary_rows.append({
            "column": col,
            "valid_blocks": int(s.notna().sum()),
            "missing_blocks": int(s.isna().sum()),
            "missing_pct": round(s.isna().mean() * 100, 3),
            "mean_mw": round(s.mean(), 2),
            "std_mw": round(s.std(), 2),
            "min_mw": round(s.min(), 2),
            "median_mw": round(s.median(), 2),
            "max_mw": round(s.max(), 2),
        })
    df_summary = pd.DataFrame(summary_rows)
    summary_csv = REPORTS_DIR / "dataset_summary_report.csv"
    df_summary.to_csv(summary_csv, index=False)

    print("\n" + "=" * 75)
    print(f"COMPLETED IN  : {time.perf_counter() - t_start:.1f}s")
    print(f"DATASET SAVED : {out_csv}")
    print(f"DATE RANGE    : {final_df['timestamp'].min()}  -->  {final_df['timestamp'].max()}")
    print(f"TOTAL ROWS    : {len(final_df):,} (15-min intervals)")
    print(f"AUDIT LOG     : {audit_csv}")
    print("=" * 75)
    print("\nAUDIT STATUS COUNTS:")
    print(df_audit["status"].value_counts().to_string())
    print("\nCOLUMN SUMMARY (MW):")
    print(df_summary.to_string(index=False))


if __name__ == "__main__":
    run_extraction()
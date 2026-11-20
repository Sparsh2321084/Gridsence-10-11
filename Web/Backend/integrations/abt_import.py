import argparse
import hashlib
import logging
import math
import re
import time
import zipfile
from datetime import datetime, time as clock_time
from pathlib import Path
from typing import Any

import pandas as pd
from xlrd.biffh import XLRDError

from Web.Backend.core.settings import Settings
from Web.Backend.storage.actuals_store import ActualLoadStore

logger = logging.getLogger(__name__)

ABT_ENTITY_HEADERS = {
    "BILL BRPL": "brpl_mw",
    "BRPL": "brpl_mw",
    "BILL TPDDL NDPL": "tpddl_mw",
    "TPDDL NDPL": "tpddl_mw",
    "BILL TPDDL": "tpddl_mw",
    "TPDDL": "tpddl_mw",
    "BILL BYPL": "bypl_mw",
    "BYPL": "bypl_mw",
    "BILL NDMC": "ndmc_mw",
    "NDMC": "ndmc_mw",
    "MES": "mes_mw",
    "NORTHERN RAILWAY": "railways_mw",
    "NORTHERN RAILWAYS": "railways_mw",
    "RAILWAY": "railways_mw",
    "RAILWAYS": "railways_mw",
}
REQUIRED_ENTITIES = (
    "brpl_mw",
    "tpddl_mw",
    "bypl_mw",
    "ndmc_mw",
    "mes_mw",
    "railways_mw",
)
TIMESTAMP_HEADERS = {
    "TIMESTAMP",
    "TIME STAMP",
    "DATETIME",
    "DATE TIME",
    "DATE TIME STAMP",
    "DATE AND TIME",
}
DATE_HEADERS = {"DATE", "SUPPLY DATE", "DATE OF SUPPLY"}
TIME_HEADERS = {
    "TIME",
    "TIME BLOCK",
    "TIMEBLOCK",
    "BLOCK",
    "BLOCK NO",
    "BLOCK NUMBER",
    "INTERVAL",
}


def _normalize_header(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip().upper()
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", text).split())


def _parse_block_time(value: Any, is_block_number: bool) -> pd.Timedelta:
    if value is None or pd.isna(value):
        raise ValueError("ABT workbook contains a missing time/block value")
    if isinstance(value, pd.Timestamp):
        return pd.Timedelta(
            hours=value.hour,
            minutes=value.minute,
            seconds=value.second,
        )
    if isinstance(value, (datetime, clock_time)):
        return pd.Timedelta(
            hours=value.hour,
            minutes=value.minute,
            seconds=value.second,
        )
    if isinstance(value, (int, float)):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError("ABT workbook contains a non-finite time/block value")
        if 0 <= numeric < 1:
            return pd.to_timedelta(numeric, unit="D")
        if is_block_number and numeric.is_integer() and 1 <= numeric <= 96:
            return pd.Timedelta(minutes=(int(numeric) - 1) * 15)
        raise ValueError(f"Unsupported numeric ABT time/block value: {value}")

    text = str(value).strip()
    if is_block_number and text.isdigit() and 1 <= int(text) <= 96:
        return pd.Timedelta(minutes=(int(text) - 1) * 15)
    clock_match = re.match(r"^(\d{1,2}:\d{2}(?::\d{2})?)", text)
    parsed = pd.to_timedelta(clock_match.group(1) if clock_match else text, errors="coerce")
    if pd.isna(parsed) or parsed < pd.Timedelta(0) or parsed >= pd.Timedelta(days=1):
        raise ValueError(f"Unsupported ABT time/block value: {value}")
    return parsed


def _sheet_rows_to_frame(rows: pd.DataFrame, sheet_name: str) -> pd.DataFrame | None:
    header_row: int | None = None
    header_map: dict[str, int] = {}
    detected_entity_columns: dict[str, int] = {}

    for row_index in range(min(len(rows), 30)):
        values = [_normalize_header(value) for value in rows.iloc[row_index].tolist()]
        detected: dict[str, int] = {}
        for column_index, value in enumerate(values):
            entity = ABT_ENTITY_HEADERS.get(value)
            if entity is not None:
                if entity in detected:
                    raise ValueError(
                        f"ABT sheet {sheet_name!r} has duplicate columns for {entity}"
                    )
                detected[entity] = column_index
        if len(detected) == len(REQUIRED_ENTITIES):
            header_row = row_index
            detected_entity_columns = detected
            header_map = {value: index for index, value in enumerate(values) if value}
            break
        if detected:
            detected_entity_columns = detected

    if header_row is None:
        if detected_entity_columns:
            missing = sorted(set(REQUIRED_ENTITIES) - detected_entity_columns.keys())
            raise ValueError(
                f"ABT sheet {sheet_name!r} is missing meter columns: {', '.join(missing)}"
            )
        return None

    timestamp_column = next(
        (header_map[name] for name in TIMESTAMP_HEADERS if name in header_map),
        None,
    )
    date_column = next(
        (header_map[name] for name in DATE_HEADERS if name in header_map),
        None,
    )
    time_column = next(
        (header_map[name] for name in TIME_HEADERS if name in header_map),
        None,
    )
    data = rows.iloc[header_row + 1 :].copy()
    if data.empty:
        return pd.DataFrame(columns=["timestamp", *REQUIRED_ENTITIES])
    meter_values: dict[str, pd.Series] = {}
    for entity, column_index in detected_entity_columns.items():
        values = (
            data.iloc[:, column_index]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        values = values.mask(
            values.isin({"", "-", "nan", "None", "<NA>", "NA", "N/A"})
        )
        meter_values[entity] = pd.to_numeric(values, errors="raise")

    if timestamp_column is not None:
        timestamps = pd.to_datetime(data.iloc[:, timestamp_column], errors="coerce")
    elif date_column is not None and time_column is not None:
        dates = pd.to_datetime(data.iloc[:, date_column], errors="coerce").ffill()
        block_header = _normalize_header(rows.iloc[header_row, time_column])
        is_block_number = "BLOCK" in block_header or block_header in {"INTERVAL"}
        timestamps = []
        for date_value, time_value in zip(dates, data.iloc[:, time_column]):
            if pd.isna(date_value):
                timestamps.append(pd.NaT)
                continue
            day = pd.Timestamp(date_value).normalize()
            timestamps.append(day + _parse_block_time(time_value, is_block_number))
        timestamps = pd.to_datetime(timestamps, errors="coerce")
    else:
        raise ValueError(
            f"ABT sheet {sheet_name!r} must include a timestamp or date plus time/block column"
        )

    frame = pd.DataFrame(meter_values)
    frame["timestamp"] = timestamps
    frame = frame.dropna(subset=["timestamp"])
    if frame.empty:
        return pd.DataFrame(columns=["timestamp", *REQUIRED_ENTITIES])
    return frame[["timestamp", *REQUIRED_ENTITIES]]


def read_abt_week(workbook_path: Path | str) -> pd.DataFrame:
    path = Path(workbook_path)
    if path.suffix.lower() not in {".xls", ".xlsx"}:
        raise ValueError(f"Unsupported ABT workbook extension: {path.suffix}")
    sheets = pd.read_excel(path, sheet_name=None, header=None)
    parsed_sheets = [
        parsed
        for sheet_name, rows in sheets.items()
        if (parsed := _sheet_rows_to_frame(rows, str(sheet_name))) is not None
    ]
    if not parsed_sheets:
        raise ValueError(f"No ABT meter table found in workbook: {path.name}")

    frame = pd.concat(parsed_sheets, ignore_index=True)
    frame = frame.sort_values("timestamp", kind="stable")
    if frame.empty:
        raise ValueError(f"ABT workbook contains no timestamped meter readings: {path.name}")
    timestamps = pd.DatetimeIndex(frame["timestamp"].drop_duplicates())
    week_start = timestamps.min().normalize()
    expected = pd.date_range(week_start, periods=672, freq="15min")
    if timestamps.max().normalize() != week_start + pd.Timedelta(days=6):
        raise ValueError(
            "ABT workbook must cover exactly seven local dates"
        )
    if not timestamps.isin(expected).all():
        raise ValueError("ABT workbook contains timestamps outside its seven-day window")
    absent_timestamps = expected.difference(timestamps)
    if len(absent_timestamps):
        absent = pd.DataFrame(
            {
                "timestamp": absent_timestamps,
                **{entity: float("nan") for entity in REQUIRED_ENTITIES},
            }
        )
        frame = pd.concat([frame, absent], ignore_index=True).sort_values(
            "timestamp",
            kind="stable",
        )
    frame["delhi_total_mw"] = frame[list(REQUIRED_ENTITIES)].sum(
        axis=1,
        min_count=6,
    )
    return frame[["timestamp", *REQUIRED_ENTITIES, "delhi_total_mw"]].reset_index(drop=True)


def ingest_abt_week(store: ActualLoadStore, workbook_path: Path | str) -> int:
    frame = read_abt_week(workbook_path)
    latest = store.latest_complete_valid_timestamp()
    first = pd.Timestamp(frame["timestamp"].min())
    if latest is not None and first > latest + pd.Timedelta(minutes=15):
        store.record_missing(
            latest + pd.Timedelta(minutes=15),
            first - pd.Timedelta(minutes=15),
            source="sldc_abt_weekly",
        )
    store.ingest_frame(frame, source="sldc_abt_weekly", unit="MU")
    return int(frame["timestamp"].nunique())


def scan_abt_folder(
    store: ActualLoadStore,
    folder_path: Path | str,
) -> tuple[list[Path], list[str]]:
    folder = Path(folder_path)
    if not folder.exists():
        return [], []
    if not folder.is_dir():
        raise NotADirectoryError(f"ABT import path is not a directory: {folder}")

    imported: list[Path] = []
    failures: list[str] = []
    try:
        paths = sorted(folder.iterdir())
    except OSError as error:
        message = f"{folder}: {error}"
        logger.error("Could not scan ABT inbox %s", message)
        return imported, [message]
    for path in paths:
        if path.name.startswith("~$") or path.suffix.lower() not in {".xls", ".xlsx"}:
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            message = f"{path.name}: {error}"
            logger.error("Could not read ABT workbook %s", message)
            failures.append(message)
            continue
        metadata_key = f"abt_workbook:{path.resolve()}"
        if store.get_metadata(metadata_key) == digest:
            continue
        try:
            ingest_abt_week(store, path)
        except (OSError, ValueError, ImportError, zipfile.BadZipFile, XLRDError) as error:
            message = f"{path.name}: {error}"
            logger.error("Could not import ABT workbook %s", message)
            failures.append(message)
            continue
        store.set_metadata(metadata_key, digest)
        imported.append(path)
        logger.info("Imported ABT workbook %s", path)
    return imported, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Delhi weekly ABT workbooks")
    settings = Settings.from_env()
    parser.add_argument(
        "--folder",
        default=str(settings.abt_inbox_path),
        help="Folder containing weekly .xls/.xlsx workbooks",
    )
    parser.add_argument("--watch", action="store_true", help="Rescan the folder continuously")
    parser.add_argument("--interval-seconds", type=int, default=60)
    args = parser.parse_args()
    if args.interval_seconds < 1:
        parser.error("--interval-seconds must be positive")

    store = ActualLoadStore(settings.actuals_db_path)
    while True:
        imported, failures = scan_abt_folder(store, args.folder)
        print(f"Imported {len(imported)} workbook(s); {len(failures)} failure(s).")
        if failures and not args.watch:
            return 1
        if not args.watch:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())

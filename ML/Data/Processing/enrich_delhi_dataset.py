import datetime
import importlib.util
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request
import numpy as np
import pandas as pd

from paths import DATASET_DIR, PROCESSING_DIR, REPORTS_DIR

# ==============================================================================
# 1. EXACT DIRECTORY PATHS
# ==============================================================================
WEATHER_CACHE_DIR = PROCESSING_DIR / "weather_cache"

for folder in (PROCESSING_DIR, REPORTS_DIR, DATASET_DIR, WEATHER_CACHE_DIR):
    folder.mkdir(parents=True, exist_ok=True)

HAS_PARQUET = (
    importlib.util.find_spec("pyarrow") is not None
    or importlib.util.find_spec("fastparquet") is not None
)

UTILITY_COLS = [
    "brpl_mw",
    "tpddl_mw",
    "bypl_mw",
    "ndmc_mw",
    "mes_mw",
    "railways_mw",
]

# Delhi grid center (Safdarjung / Palam reference)
DELHI_LAT = 28.58
DELHI_LON = 77.20
DELHI_TZ = "Asia/Kolkata"

HOURLY_WEATHER_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "cloud_cover",
    "wind_speed_10m",
    "shortwave_radiation",
]

# Major Delhi & Indian Gazetted / Festival Holidays (2019–2026)
DELHI_MOVABLE_HOLIDAYS = {
    # 2019
    "2019-04-13", "2019-04-17", "2019-04-19", "2019-05-18", "2019-06-05",
    "2019-08-12", "2019-08-24", "2019-09-10", "2019-10-08", "2019-10-27",
    "2019-10-28", "2019-11-10", "2019-11-12",
    # 2020
    "2020-02-21", "2020-03-10", "2020-04-02", "2020-04-06", "2020-04-10",
    "2020-05-07", "2020-05-25", "2020-08-01", "2020-08-12", "2020-08-30",
    "2020-10-25", "2020-11-14", "2020-11-30",
    # 2021
    "2021-03-11", "2021-03-29", "2021-04-02", "2021-04-21", "2021-05-14",
    "2021-05-26", "2021-07-21", "2021-08-19", "2021-08-30", "2021-10-15",
    "2021-10-19", "2021-11-04", "2021-11-19",
    # 2022
    "2022-03-01", "2022-03-18", "2022-04-15", "2022-05-03", "2022-05-16",
    "2022-07-10", "2022-08-09", "2022-08-19", "2022-10-05", "2022-10-24",
    "2022-11-08",
    # 2023
    "2023-02-18", "2023-03-08", "2023-03-30", "2023-04-04", "2023-04-07",
    "2023-04-22", "2023-05-05", "2023-06-29", "2023-07-29", "2023-09-07",
    "2023-09-28", "2023-10-24", "2023-11-12", "2023-11-27",
    # 2024
    "2024-03-08", "2024-03-25", "2024-03-29", "2024-04-11", "2024-04-17",
    "2024-04-21", "2024-05-23", "2024-06-17", "2024-07-17", "2024-08-26",
    "2024-09-16", "2024-10-12", "2024-10-31", "2024-11-15",
    # 2025
    "2025-02-26", "2025-03-14", "2025-03-31", "2025-04-10", "2025-04-18",
    "2025-05-12", "2025-06-07", "2025-07-06", "2025-08-16", "2025-09-05",
    "2025-10-02", "2025-10-20", "2025-11-05",
    # 2026
    "2026-02-15", "2026-03-04", "2026-03-21", "2026-03-26", "2026-04-03",
    "2026-05-01", "2026-05-27", "2026-06-26", "2026-08-26", "2026-09-04",
}

FIXED_MONTH_DAY_HOLIDAYS = {
    (1, 26),   # Republic Day
    (4, 14),   # Ambedkar Jayanti
    (8, 15),   # Independence Day
    (10, 2),   # Gandhi Jayanti
    (12, 25),  # Christmas Day
}


# ==============================================================================
# 2. METER SPIKE AUDIT & CLEANER
# ==============================================================================
def clean_consumption_anomalies(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Detects and repairs isolated single-block meter spikes or negative readings
    while keeping multi-week missing gaps strictly as NaN.
    """
    df = df_raw.copy().sort_values("timestamp").reset_index(drop=True)
    anomaly_logs = []

    for col in UTILITY_COLS:
        s = df[col].astype(float)
        # 6-hour centered rolling median (25 intervals) to spot isolated spikes
        roll_med = s.rolling(window=25, center=True, min_periods=5).median()

        bad_neg = s < 0
        bad_spike = (roll_med > 1.0) & (s > roll_med * 3.0)
        bad_drop = (roll_med > 20.0) & (s < roll_med * 0.15)
        bad_mask = bad_neg | bad_spike | bad_drop

        if bad_mask.any():
            for idx in df.index[bad_mask]:
                raw_val = s.loc[idx]
                med_val = roll_med.loc[idx]
                reason = (
                    "NEGATIVE_VALUE"
                    if bad_neg.loc[idx]
                    else ("EXTREME_SPIKE" if bad_spike.loc[idx] else "NEAR_ZERO_DROP")
                )
                anomaly_logs.append({
                    "timestamp": df.loc[idx, "timestamp"],
                    "utility": col,
                    "reason": reason,
                    "raw_mw": round(float(raw_val), 4),
                    "local_6h_median_mw": round(float(med_val), 4) if pd.notna(med_val) else np.nan,
                })
            df.loc[bad_mask, col] = np.nan

        # Interpolate ONLY isolated gaps <= 4 consecutive intervals (<= 1 hour)
        s_clean = df[col].interpolate(method="linear", limit=4, limit_area="inside")
        if bad_mask.any():
            for entry in anomaly_logs:
                if entry["utility"] == col:
                    ts = entry["timestamp"]
                    rep_val = s_clean.loc[df["timestamp"] == ts].iloc[0]
                    entry["repaired_mw"] = round(float(rep_val), 4) if pd.notna(rep_val) else np.nan
        df[col] = s_clean

    # Recompute exact Delhi total (NaN whenever any utility is missing)
    df["delhi_total_mw"] = df[UTILITY_COLS].sum(axis=1, min_count=len(UTILITY_COLS))

    df_anom = pd.DataFrame(anomaly_logs)
    anom_path = REPORTS_DIR / "anomaly_cleaning_report.csv"
    df_anom.to_csv(anom_path, index=False)
    print(f"[Step 2A] Logged & repaired {len(df_anom)} isolated meter anomalies -> {anom_path}")
    if not df_anom.empty:
        print(df_anom.to_string(index=False))

    return df


# ==============================================================================
# 3. OPEN-METEO HISTORICAL WEATHER FETCHER & 15-MIN ALIGNER
# ==============================================================================
def fetch_open_meteo_hourly(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetches hourly historical weather for New Delhi in yearly chunks from
    Open-Meteo Archive API and caches locally for fast offline re-runs.
    """
    cache_file = WEATHER_CACHE_DIR / f"delhi_openmeteo_hourly_{start_date}_to_{end_date}.csv"
    if cache_file.exists():
        print(f"[Step 2B] Loading cached hourly weather -> {cache_file}")
        df_w = pd.read_csv(cache_file)
        df_w["timestamp"] = pd.to_datetime(df_w["timestamp"])
        return df_w

    start_dt = datetime.date.fromisoformat(start_date)
    end_dt = datetime.date.fromisoformat(end_date)
    yearly_chunks = []

    print(f"[Step 2B] Fetching Open-Meteo hourly weather for Delhi ({start_date} to {end_date})...")
    for yr in range(start_dt.year, end_dt.year + 1):
        chunk_start = max(start_dt, datetime.date(yr, 1, 1)).isoformat()
        chunk_end = min(end_dt, datetime.date(yr, 12, 31)).isoformat()

        params = {
            "latitude": DELHI_LAT,
            "longitude": DELHI_LON,
            "start_date": chunk_start,
            "end_date": chunk_end,
            "hourly": ",".join(HOURLY_WEATHER_VARS),
            "timezone": DELHI_TZ,
        }
        url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(params)

        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "GridSense-Delhi-ETL/1.0"})
                with urllib.request.urlopen(req, timeout=45) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                df_yr = pd.DataFrame(payload["hourly"])
                df_yr["timestamp"] = pd.to_datetime(df_yr["time"])
                df_yr = df_yr.drop(columns=["time"])
                yearly_chunks.append(df_yr)
                print(f"  Fetched {chunk_start} .. {chunk_end} ({len(df_yr):,} hourly rows)")
                break
            except Exception as e:
                if attempt == 2:
                    raise RuntimeError(f"Failed fetching Open-Meteo weather for {yr}: {e}") from e
                time.sleep(2.0 * (attempt + 1))

    df_weather = (
        pd.concat(yearly_chunks, ignore_index=True)
        .drop_duplicates(subset=["timestamp"], keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    df_weather.to_csv(cache_file, index=False)
    print(f"  Cached raw hourly weather -> {cache_file}")
    return df_weather


def align_weather_to_15min(df_weather_hr: pd.DataFrame, target_index: pd.DatetimeIndex) -> pd.DataFrame:
    """
    Upsamples hourly weather to exact 15-minute intervals:
    - Continuous states (temp, humidity, dew point, radiation, wind, cloud): linear time interpolation
    - Hourly accumulated rainfall (precipitation, rain): divided equally by 4 per 15-min interval
    """
    w = df_weather_hr.set_index("timestamp").sort_index()
    w = w[~w.index.duplicated(keep="last")]

    step_cols = ["precipitation", "rain"]
    cont_cols = [c for c in HOURLY_WEATHER_VARS if c not in step_cols]

    union_idx = w.index.union(target_index)
    w_cont = w[cont_cols].reindex(union_idx).interpolate(method="time").reindex(target_index)
    w_step = (w[step_cols] / 4.0).reindex(target_index, method="ffill").fillna(0.0)

    out = pd.concat([w_cont, w_step], axis=1)
    out.index.name = "timestamp"
    return out.reset_index()


# ==============================================================================
# 4. THERMAL INERTIA, CALENDAR, HOLIDAYS & COVID FEATURE ENGINEERING
# ==============================================================================
def add_domain_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adds thermal inertia, cyclical time, Delhi holidays, and COVID lockdown flags."""
    out = df.copy()
    ts = out["timestamp"]

    # 1. Thermal comfort & building thermal inertia (15-min blocks: 12=3h, 96=24h, 288=72h)
    out["cdd_24"] = np.maximum(0.0, out["temperature_2m"] - 24.0)
    out["hdd_18"] = np.maximum(0.0, 18.0 - out["temperature_2m"])
    out["temp_roll_3h"] = out["temperature_2m"].rolling(12, min_periods=1).mean()
    out["temp_roll_24h"] = out["temperature_2m"].rolling(96, min_periods=1).mean()
    out["temp_roll_72h"] = out["temperature_2m"].rolling(288, min_periods=1).mean()
    out["temp_max_24h"] = out["temperature_2m"].rolling(96, min_periods=1).max()
    out["temp_min_24h"] = out["temperature_2m"].rolling(96, min_periods=1).min()
    out["apparent_temp_roll_24h"] = out["apparent_temperature"].rolling(96, min_periods=1).mean()

    # 2. Calendar & cyclical encodings
    out["year"] = ts.dt.year
    out["month"] = ts.dt.month
    out["day"] = ts.dt.day
    out["hour"] = ts.dt.hour
    out["minute"] = ts.dt.minute
    out["block_of_day"] = ts.dt.hour * 4 + ts.dt.minute // 15
    out["day_of_week"] = ts.dt.dayofweek
    out["day_of_year"] = ts.dt.dayofyear
    out["is_weekend"] = (out["day_of_week"] >= 5).astype(np.int8)

    out["sin_block"] = np.sin(2.0 * np.pi * out["block_of_day"] / 96.0)
    out["cos_block"] = np.cos(2.0 * np.pi * out["block_of_day"] / 96.0)
    out["sin_dow"] = np.sin(2.0 * np.pi * out["day_of_week"] / 7.0)
    out["cos_dow"] = np.cos(2.0 * np.pi * out["day_of_week"] / 7.0)
    out["sin_doy"] = np.sin(2.0 * np.pi * out["day_of_year"] / 365.25)
    out["cos_doy"] = np.cos(2.0 * np.pi * out["day_of_year"] / 365.25)

    # 3. Delhi holidays & non-working day indicator
    date_strs = ts.dt.strftime("%Y-%m-%d")
    fixed_mask = pd.Series(
        list(zip(ts.dt.month, ts.dt.day)), index=out.index
    ).isin(FIXED_MONTH_DAY_HOLIDAYS)
    movable_mask = date_strs.isin(DELHI_MOVABLE_HOLIDAYS)
    out["is_holiday"] = (fixed_mask | movable_mask).astype(np.int8)
    out["is_non_working_day"] = ((out["is_weekend"] == 1) | (out["is_holiday"] == 1)).astype(np.int8)

    # 4. COVID-19 lockdown windows in Delhi
    lockdown_w1 = (ts >= "2020-03-25 00:00:00") & (ts <= "2020-06-07 23:45:00")
    lockdown_w2 = (ts >= "2021-04-19 00:00:00") & (ts <= "2021-05-31 23:45:00")
    out["is_lockdown"] = (lockdown_w1 | lockdown_w2).astype(np.int8)

    # Round weather & engineered float columns cleanly
    float_cols = [
        c for c in out.columns
        if c not in (["timestamp"] + UTILITY_COLS + ["delhi_total_mw"])
        and pd.api.types.is_float_dtype(out[c])
    ]
    out[float_cols] = out[float_cols].round(4)
    return out


# ==============================================================================
# 5. MAIN PIPELINE
# ==============================================================================
def run_enrichment():
    t0 = time.perf_counter()
    raw_parquet = DATASET_DIR / "delhi_consumption_2019_2026.parquet"
    raw_csv = DATASET_DIR / "delhi_consumption_2019_2026.csv"

    if raw_parquet.exists():
        df_raw = pd.read_parquet(raw_parquet)
    elif raw_csv.exists():
        df_raw = pd.read_csv(raw_csv)
    else:
        raise FileNotFoundError(f"Step 1 dataset not found in {DATASET_DIR}")

    df_raw["timestamp"] = pd.to_datetime(df_raw["timestamp"])
    print(f"Loaded raw consumption dataset: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")

    # Step 2A: Clean isolated meter anomalies & save clean consumption file
    df_clean = clean_consumption_anomalies(df_raw)
    clean_csv = DATASET_DIR / "delhi_consumption_clean_2019_2026.csv"
    df_clean.to_csv(clean_csv, index=False)
    if HAS_PARQUET:
        df_clean.to_parquet(DATASET_DIR / "delhi_consumption_clean_2019_2026.parquet", index=False)

    # Step 2B: Fetch & align Delhi hourly weather to 15-min blocks
    start_date = df_clean["timestamp"].min().strftime("%Y-%m-%d")
    end_date = df_clean["timestamp"].max().strftime("%Y-%m-%d")
    df_weather_hr = fetch_open_meteo_hourly(start_date, end_date)
    target_idx = pd.DatetimeIndex(df_clean["timestamp"])
    df_weather_15m = align_weather_to_15min(df_weather_hr, target_idx)

    # Step 2C: Merge & build domain features
    df_merged = pd.merge(df_clean, df_weather_15m, on="timestamp", how="left")
    df_final = add_domain_features(df_merged)

    ml_csv = DATASET_DIR / "delhi_ml_dataset_2019_2026.csv"
    df_final.to_csv(ml_csv, index=False)
    if HAS_PARQUET:
        df_final.to_parquet(DATASET_DIR / "delhi_ml_dataset_2019_2026.parquet", index=False)

    # Save enriched dataset summary report
    summary_rows = []
    for col in df_final.columns:
        if col == "timestamp":
            continue
        s = df_final[col]
        summary_rows.append({
            "column": col,
            "dtype": str(s.dtype),
            "valid_count": int(s.notna().sum()),
            "missing_count": int(s.isna().sum()),
            "mean": round(float(s.mean()), 3),
            "std": round(float(s.std()), 3),
            "min": round(float(s.min()), 3),
            "median": round(float(s.median()), 3),
            "max": round(float(s.max()), 3),
        })
    df_sum = pd.DataFrame(summary_rows)
    sum_path = REPORTS_DIR / "enriched_dataset_summary.csv"
    df_sum.to_csv(sum_path, index=False)

    print("\n" + "=" * 78)
    print(f"STEP 2 COMPLETED IN : {time.perf_counter() - t0:.1f}s")
    print(f"CLEAN LOAD DATASET  : {clean_csv}")
    print(f"FINAL ML DATASET    : {ml_csv}")
    print(f"SHAPE               : {df_final.shape[0]:,} rows x {df_final.shape[1]} columns")
    print(f"SUMMARY REPORT      : {sum_path}")
    print("=" * 78)
    print("\nKEY COLUMNS SUMMARY:")
    key_cols = [
        "brpl_mw", "tpddl_mw", "bypl_mw", "ndmc_mw", "mes_mw", "railways_mw",
        "delhi_total_mw", "temperature_2m", "relative_humidity_2m",
        "apparent_temperature", "shortwave_radiation", "is_holiday", "is_lockdown",
    ]
    print(df_sum[df_sum["column"].isin(key_cols)].to_string(index=False))


if __name__ == "__main__":
    run_enrichment()
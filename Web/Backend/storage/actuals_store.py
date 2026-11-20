import logging
import math
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Literal
from zoneinfo import ZoneInfo

import pandas as pd

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
ENTITIES = (
    "brpl_mw",
    "tpddl_mw",
    "bypl_mw",
    "ndmc_mw",
    "mes_mw",
    "railways_mw",
    "delhi_total_mw",
)
UTILITY_ENTITIES = ENTITIES[:-1]
ENTITY_BOUNDS = {
    "delhi_total_mw": (1_000.0, 10_500.0),
    "brpl_mw": (400.0, 4_500.0),
    "tpddl_mw": (250.0, 3_200.0),
    "bypl_mw": (200.0, 2_400.0),
    "ndmc_mw": (35.0, 550.0),
    "mes_mw": (2.0, 90.0),
    "railways_mw": (0.2, 75.0),
}
AUTO_MU_THRESHOLDS = {
    "delhi_total_mw": 2.0,
    "brpl_mw": 2.0,
    "tpddl_mw": 2.0,
    "bypl_mw": 2.0,
    "ndmc_mw": 2.0,
    "mes_mw": 0.05,
    "railways_mw": 0.05,
}

Unit = Literal["MW", "MU", "AUTO"]
TimestampInput = str | datetime | pd.Timestamp


class InferenceHistoryError(ValueError):
    pass


class ActualLoadStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seed_lock = threading.Lock()
        self._initialize()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS actual_load_15m (
                    timestamp TEXT NOT NULL,
                    entity TEXT NOT NULL CHECK (
                        entity IN (
                            'brpl_mw', 'tpddl_mw', 'bypl_mw', 'ndmc_mw',
                            'mes_mw', 'railways_mw', 'delhi_total_mw'
                        )
                    ),
                    mw REAL,
                    source TEXT NOT NULL,
                    quality_flag TEXT NOT NULL
                        CHECK (quality_flag IN ('VALID', 'SUSPECT_SPIKE', 'MISMATCH_SUM', 'MISSING')),
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY (timestamp, entity)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_actual_load_quality_timestamp "
                "ON actual_load_15m(quality_flag, timestamp)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS actual_load_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS forecast_predictions_15m (
                    timestamp TEXT NOT NULL,
                    entity TEXT NOT NULL CHECK (
                        entity IN (
                            'brpl_mw', 'tpddl_mw', 'bypl_mw', 'ndmc_mw',
                            'mes_mw', 'railways_mw', 'delhi_total_mw'
                        )
                    ),
                    predicted_mw REAL NOT NULL,
                    issued_at TEXT NOT NULL,
                    PRIMARY KEY (timestamp, entity, issued_at)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_forecast_predictions_timestamp "
                "ON forecast_predictions_15m(timestamp, entity, issued_at)"
            )

    @staticmethod
    def _timestamp(value: object) -> pd.Timestamp:
        if not isinstance(value, (str, datetime, pd.Timestamp)):
            raise ValueError(f"Unsupported actual reading timestamp: {value!r}")
        timestamp = pd.Timestamp(value)
        if pd.isna(timestamp):
            raise ValueError("Actual reading timestamp cannot be missing")
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_convert(IST).tz_localize(None)
        if (
            timestamp.minute % 15 != 0
            or timestamp.second != 0
            or timestamp.microsecond != 0
            or timestamp.nanosecond != 0
        ):
            raise ValueError(f"Timestamp is not aligned to a 15-minute IST block: {value}")
        return timestamp

    @staticmethod
    def _timestamp_text(timestamp: pd.Timestamp) -> str:
        return timestamp.strftime("%Y-%m-%dT%H:%M:%S")

    @staticmethod
    def _write_batch(connection: sqlite3.Connection, rows: list[tuple]) -> None:
        if not rows:
            return
        connection.executemany(
            """
            INSERT INTO actual_load_15m
                (timestamp, entity, mw, source, quality_flag, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(timestamp, entity) DO UPDATE SET
                mw = excluded.mw,
                source = excluded.source,
                quality_flag = excluded.quality_flag,
                recorded_at = excluded.recorded_at
            WHERE
                CASE actual_load_15m.quality_flag
                    WHEN 'VALID' THEN 4
                    WHEN 'MISMATCH_SUM' THEN 3
                    WHEN 'SUSPECT_SPIKE' THEN 2
                    ELSE 1
                END
                <=
                CASE excluded.quality_flag
                    WHEN 'VALID' THEN 4
                    WHEN 'MISMATCH_SUM' THEN 3
                    WHEN 'SUSPECT_SPIKE' THEN 2
                    ELSE 1
                END
            """,
            rows,
        )

    def _prepare_frame(self, frame: pd.DataFrame, unit: Unit) -> pd.DataFrame:
        if "timestamp" not in frame.columns:
            raise ValueError("Actual readings must include a timestamp column")
        if unit not in ("MW", "MU", "AUTO"):
            raise ValueError(f"Unsupported unit: {unit}")
        prepared = frame.copy()
        prepared["_timestamp"] = [self._timestamp(value) for value in prepared["timestamp"]]
        for entity in ENTITIES:
            if entity not in prepared.columns:
                prepared[entity] = None
            try:
                prepared[entity] = pd.to_numeric(prepared[entity], errors="raise")
            except (TypeError, ValueError) as error:
                raise ValueError(f"Non-numeric reading for {entity}") from error

        if unit == "MU":
            prepared.loc[:, ENTITIES] = prepared.loc[:, ENTITIES] * 4_000.0
            logger.info("Converted %s MU entity readings to MW", len(prepared) * len(ENTITIES))
        elif unit == "AUTO":
            for entity, threshold in AUTO_MU_THRESHOLDS.items():
                values = prepared[entity].dropna()
                positive = values[values > 0]
                if len(positive) >= 4 and bool((positive < threshold).all()):
                    prepared[entity] = prepared[entity] * 4_000.0
                    logger.info("Auto-detected %s values in MU and converted them to MW", entity)
        return prepared

    def ingest_frame(self, frame: pd.DataFrame, source: str, unit: Unit = "MW") -> None:
        if not source.strip():
            raise ValueError("Actual reading source cannot be empty")
        if frame.empty:
            return
        prepared = self._prepare_frame(frame, unit)
        timestamps = prepared["_timestamp"].tolist()
        present_timestamps = set(timestamps)
        start = min(timestamps)
        end = max(timestamps)
        recorded_at = datetime.now(IST).isoformat()
        rows: list[tuple] = []

        with self._connect() as connection:
            for values in prepared[["_timestamp", *ENTITIES]].itertuples(index=False, name=None):
                timestamp = values[0]
                readings = dict(zip(ENTITIES, values[1:]))
                flags: dict[str, str] = {}
                mw_values: dict[str, float | None] = {}
                for entity, raw_value in readings.items():
                    if pd.isna(raw_value):
                        flags[entity] = "MISSING"
                        mw_values[entity] = None
                        continue
                    value = float(raw_value)
                    if not math.isfinite(value):
                        flags[entity] = "SUSPECT_SPIKE"
                        mw_values[entity] = None
                        continue
                    lower, upper = ENTITY_BOUNDS[entity]
                    flags[entity] = "VALID" if lower <= value <= upper else "SUSPECT_SPIKE"
                    mw_values[entity] = value

                if all(flags[entity] == "VALID" for entity in ENTITIES):
                    utility_values = []
                    for entity in UTILITY_ENTITIES:
                        value = mw_values[entity]
                        if value is None:
                            break
                        utility_values.append(value)
                    total = mw_values["delhi_total_mw"]
                    utility_sum = sum(utility_values) if len(utility_values) == len(UTILITY_ENTITIES) else None
                    if total is not None and utility_sum is not None and abs(utility_sum - total) / total > 0.02:
                        for entity in ENTITIES:
                            flags[entity] = "MISMATCH_SUM"

                timestamp_text = self._timestamp_text(timestamp)
                for entity in ENTITIES:
                    rows.append(
                        (
                            timestamp_text,
                            entity,
                            mw_values[entity],
                            source,
                            flags[entity],
                            recorded_at,
                        )
                    )
                if len(rows) >= 10_000:
                    self._write_batch(connection, rows)
                    rows.clear()

            expected = pd.date_range(start, end, freq="15min")
            for timestamp in expected:
                if timestamp in present_timestamps:
                    continue
                timestamp_text = self._timestamp_text(timestamp)
                for entity in ENTITIES:
                    rows.append((timestamp_text, entity, None, source, "MISSING", recorded_at))
                if len(rows) >= 10_000:
                    self._write_batch(connection, rows)
                    rows.clear()
            self._write_batch(connection, rows)

    def record_missing(self, start: TimestampInput, end: TimestampInput, source: str) -> None:
        if not source.strip():
            raise ValueError("Missing reading source cannot be empty")
        first = self._timestamp(start)
        last = self._timestamp(end)
        if last < first:
            raise ValueError("Missing range end must not precede its start")
        recorded_at = datetime.now(IST).isoformat()
        rows = []
        with self._connect() as connection:
            for timestamp in pd.date_range(first, last, freq="15min"):
                timestamp_text = self._timestamp_text(timestamp)
                for entity in ENTITIES:
                    rows.append((timestamp_text, entity, None, source, "MISSING", recorded_at))
                if len(rows) >= 10_000:
                    self._write_batch(connection, rows)
                    rows.clear()
            self._write_batch(connection, rows)

    def seed_historical(self, frame: pd.DataFrame, fingerprint: str) -> None:
        with self._seed_lock:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT value FROM actual_load_metadata WHERE key = 'historical_fingerprint'"
                ).fetchone()
                if row is not None and row["value"] == fingerprint:
                    return
            self.ingest_frame(frame, source="historical_parquet", unit="MW")
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO actual_load_metadata(key, value)
                    VALUES ('historical_fingerprint', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (fingerprint,),
                )

    def latest_complete_valid_timestamp(self) -> pd.Timestamp | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT timestamp
                FROM actual_load_15m
                GROUP BY timestamp
                HAVING COUNT(*) = ? AND SUM(CASE WHEN quality_flag = 'VALID' THEN 1 ELSE 0 END) = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (len(ENTITIES), len(ENTITIES)),
            ).fetchone()
        return pd.Timestamp(row["timestamp"]) if row else None

    def valid_block_count(self, start: pd.Timestamp, end: pd.Timestamp) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM (
                    SELECT timestamp
                    FROM actual_load_15m
                    WHERE timestamp >= ? AND timestamp <= ?
                    GROUP BY timestamp
                    HAVING COUNT(*) = ?
                        AND SUM(CASE WHEN quality_flag = 'VALID' THEN 1 ELSE 0 END) = ?
                )
                """,
                (
                    self._timestamp_text(start),
                    self._timestamp_text(end),
                    len(ENTITIES),
                    len(ENTITIES),
                ),
            ).fetchone()
        return int(row["count"])

    def get_valid_values_for_timestamps(
        self,
        timestamps: list[TimestampInput] | pd.DatetimeIndex,
    ) -> list[dict[str, float | None]]:
        normalized = [self._timestamp_text(self._timestamp(value)) for value in timestamps]
        if not normalized:
            return []
        positions = {timestamp: position for position, timestamp in enumerate(normalized)}
        values: list[dict[str, float | None]] = [
            {entity: None for entity in ENTITIES} for _ in normalized
        ]
        placeholders = ",".join("?" for _ in normalized)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT timestamp, entity, mw
                FROM actual_load_15m
                WHERE timestamp IN ({placeholders}) AND quality_flag = 'VALID'
                """,
                normalized,
            ).fetchall()
        for row in rows:
            position = positions[row["timestamp"]]
            values[position][row["entity"]] = float(row["mw"]) if row["mw"] is not None else None
        return values

    def get_valid_values(self, timestamp: TimestampInput) -> dict[str, float | None]:
        return self.get_valid_values_for_timestamps([timestamp])[0]

    def get_metadata(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM actual_load_metadata WHERE key = ?", (key,)
            ).fetchone()
        return str(row["value"]) if row else None

    def set_metadata(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO actual_load_metadata(key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def record_predictions(
        self,
        predictions: pd.DataFrame,
        issued_at: TimestampInput | None = None,
    ) -> None:
        if predictions.empty:
            return
        missing_entities = [entity for entity in ENTITIES if entity not in predictions.columns]
        if missing_entities:
            raise ValueError(
                f"Forecast predictions are missing entities: {', '.join(missing_entities)}"
            )
        issued = pd.Timestamp(issued_at or datetime.now(IST))
        if issued.tzinfo is None:
            issued = issued.tz_localize(IST)
        else:
            issued = issued.tz_convert(IST)
        issued_text = issued.tz_localize(None).isoformat(timespec="microseconds")
        rows: list[tuple[str, str, float, str]] = []
        for timestamp, values in predictions.loc[:, list(ENTITIES)].iterrows():
            timestamp_text = self._timestamp_text(self._timestamp(timestamp))
            if issued.tz_localize(None) >= pd.Timestamp(timestamp_text):
                raise ValueError("A forecast must be recorded before its target timestamp")
            for entity in ENTITIES:
                raw_value = values[entity]
                value = float(raw_value)
                if not math.isfinite(value):
                    raise ValueError(f"Non-finite forecast prediction for {entity}")
                rows.append((timestamp_text, entity, value, issued_text))
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO forecast_predictions_15m
                    (timestamp, entity, predicted_mw, issued_at)
                VALUES (?, ?, ?, ?)
                """,
                rows,
            )

    def recent_14d_block_bias(
        self,
        future_timestamps: list[TimestampInput] | pd.DatetimeIndex,
        now: datetime | pd.Timestamp | None = None,
        min_valid_days: int = 5,
    ) -> pd.DataFrame | None:
        if min_valid_days < 1:
            raise ValueError("Minimum valid calibration days must be positive")
        normalized_future = [self._timestamp(value) for value in future_timestamps]
        if not normalized_future:
            return None

        current = pd.Timestamp(now or datetime.now(IST))
        if current.tzinfo is None:
            current = current.tz_localize(IST)
        else:
            current = current.tz_convert(IST)
        today = current.tz_localize(None).normalize()
        window_start = self._timestamp_text(today - pd.Timedelta(days=14))
        window_end = self._timestamp_text(today - pd.Timedelta(minutes=15))

        with self._connect() as connection:
            rows = connection.execute(
                """
                WITH ranked_residuals AS (
                    SELECT
                        actual.timestamp,
                        actual.entity,
                        actual.mw - prediction.predicted_mw AS residual_mw,
                        ROW_NUMBER() OVER (
                            PARTITION BY actual.timestamp, actual.entity
                            ORDER BY prediction.issued_at DESC
                        ) AS prediction_rank
                    FROM actual_load_15m AS actual
                    JOIN forecast_predictions_15m AS prediction
                        ON prediction.timestamp = actual.timestamp
                        AND prediction.entity = actual.entity
                    WHERE actual.timestamp >= ?
                        AND actual.timestamp <= ?
                        AND actual.quality_flag = 'VALID'
                        AND actual.mw IS NOT NULL
                        AND prediction.issued_at < prediction.timestamp
                )
                SELECT timestamp, entity, residual_mw
                FROM ranked_residuals
                WHERE prediction_rank = 1
                """,
                (window_start, window_end),
            ).fetchall()

        if not rows:
            return None
        residuals = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp(row["timestamp"]),
                    "entity": row["entity"],
                    "residual_mw": float(row["residual_mw"]),
                }
                for row in rows
            ]
        )
        if residuals["timestamp"].dt.normalize().nunique() < min_valid_days:
            return None

        residuals["block_of_day"] = (
            residuals["timestamp"].dt.hour * 4 + residuals["timestamp"].dt.minute // 15
        )
        residuals["day"] = residuals["timestamp"].dt.normalize()
        summary = residuals.groupby(["block_of_day", "entity"]).agg(
            bias_mw=("residual_mw", "mean"),
            valid_days=("day", "nunique"),
        )
        bias_by_block = {
            key: float(row["bias_mw"])
            for key, row in summary.iterrows()
            if int(row["valid_days"]) >= min_valid_days
        }

        index = pd.DatetimeIndex(normalized_future)
        bias = pd.DataFrame(0.0, index=index, columns=ENTITIES, dtype="float64")
        for timestamp in index:
            block = timestamp.hour * 4 + timestamp.minute // 15
            for entity in ENTITIES:
                bias.at[timestamp, entity] = bias_by_block.get((block, entity), 0.0)
        return bias

    def inference_input(self, start: TimestampInput, periods: int) -> tuple[pd.DataFrame, int]:
        first = self._timestamp(start)
        if periods <= 0:
            raise ValueError("Inference history periods must be positive")
        index = pd.date_range(first, periods=periods, freq="15min")
        start_text = self._timestamp_text(first)
        end_text = self._timestamp_text(index[-1])
        values = pd.DataFrame(index=index, columns=ENTITIES, dtype="float64")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT timestamp, entity, mw
                FROM actual_load_15m
                WHERE timestamp >= ? AND timestamp <= ? AND quality_flag = 'VALID'
                """,
                (start_text, end_text),
            ).fetchall()
        positions = {self._timestamp_text(timestamp): timestamp for timestamp in index}
        for row in rows:
            timestamp = positions.get(row["timestamp"])
            if timestamp is not None and row["mw"] is not None:
                values.at[timestamp, row["entity"]] = float(row["mw"])

        filled_positions: set[int] = set()
        for entity in ENTITIES:
            column = values[entity]
            missing = column.isna().to_numpy()
            position = 0
            while position < periods:
                if not missing[position]:
                    position += 1
                    continue
                run_start = position
                while position < periods and missing[position]:
                    position += 1
                run_end = position
                run_length = run_end - run_start
                if run_length > 4 or run_start == 0 or run_end == periods:
                    continue
                left = float(column.iloc[run_start - 1])
                right = float(column.iloc[run_end])
                for offset in range(run_length):
                    fraction = (offset + 1) / (run_length + 1)
                    values.at[index[run_start + offset], entity] = (
                        left + (right - left) * fraction
                    )
                    filled_positions.add(run_start + offset)

        if values.isna().any().any():
            raise InferenceHistoryError(
                "Inference history contains a gap longer than four blocks or an unbounded gap"
            )
        return values, len(filled_positions)

    def data_freshness(
        self,
        now: datetime | pd.Timestamp | None = None,
        filled_blocks: int = 0,
        inference_available: bool = True,
    ) -> dict[str, object]:
        current = pd.Timestamp(now or datetime.now(IST))
        if current.tzinfo is None:
            current = current.tz_localize(IST)
        else:
            current = current.tz_convert(IST)
        latest = self.latest_complete_valid_timestamp()
        window_end = current.tz_localize(None).floor("15min") - pd.Timedelta(minutes=15)
        window_start = window_end - pd.Timedelta(minutes=15 * 671)
        valid_blocks = self.valid_block_count(window_start, window_end)
        valid_percent = round(valid_blocks / 672 * 100, 2)

        if latest is None:
            mode = "UNAVAILABLE"
            lag_minutes = None
            latest_text = None
        else:
            latest_ist = latest.tz_localize(IST)
            lag_minutes = int((current - latest_ist).total_seconds() // 60)
            latest_text = latest_ist.isoformat()
            if not inference_available:
                mode = "UNAVAILABLE"
            elif lag_minutes > 7 * 24 * 60:
                mode = "REPLAYED"
            elif 0 <= lag_minutes <= 60 and valid_percent >= 95:
                mode = "LIVE"
            else:
                mode = "STALE"

        return {
            "latest_actual_timestamp": latest_text,
            "lag_minutes": lag_minutes,
            "forecast_mode": mode,
            "valid_blocks_percent": valid_percent,
            "filled_blocks": filled_blocks,
        }

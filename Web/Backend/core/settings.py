"""Environment-backed settings for the GridSense backend."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Settings:
    project_root: Path
    model_path: Path
    dataset_path: Path
    actuals_db_path: Path
    abt_inbox_path: Path
    cors_origins: tuple[str, ...]
    enable_sldc_polling: bool

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        project_root: Path | None = None,
    ) -> "Settings":
        env = os.environ if environ is None else environ
        root_value = env.get("GRIDSENSE_PROJECT_ROOT")
        root = Path(root_value).expanduser() if root_value else (
            project_root or Path(__file__).resolve().parents[3]
        )
        root = root.resolve()

        origins_value = env.get("GRIDSENSE_CORS_ORIGINS")
        origins = (
            tuple(origin.strip() for origin in origins_value.split(",") if origin.strip())
            if origins_value is not None
            else ("http://localhost:5173", "http://127.0.0.1:5173")
        )
        polling_value = env.get("GRIDSENSE_ENABLE_SLDC_POLLING", "true").strip().lower()
        if polling_value not in {"true", "false", "1", "0", "yes", "no"}:
            raise ValueError(
                "GRIDSENSE_ENABLE_SLDC_POLLING must be true/false, 1/0, or yes/no"
            )

        return cls(
            project_root=root,
            model_path=_configured_path(
                env,
                "GRIDSENSE_MODEL_PATH",
                root / "ML" / "Model" / "gridsence_production_bundle.joblib",
                root,
            ),
            dataset_path=_configured_path(
                env,
                "GRIDSENSE_DATASET_PATH",
                root / "ML" / "Data" / "Dataset" / "delhi_ml_dataset_2019_2026.parquet",
                root,
            ),
            actuals_db_path=_configured_path(
                env,
                "GRIDSENSE_ACTUALS_DB_PATH",
                root / "Web" / "Backend" / "data" / "actual_load_15m.sqlite3",
                root,
            ),
            abt_inbox_path=_configured_path(
                env,
                "GRIDSENSE_ABT_INBOX_PATH",
                root / "Web" / "Backend" / "data" / "abt_inbox",
                root,
            ),
            cors_origins=origins,
            enable_sldc_polling=polling_value in {"true", "1", "yes"},
        )


def _configured_path(
    environ: Mapping[str, str],
    key: str,
    default: Path,
    root: Path,
) -> Path:
    value = environ.get(key)
    if value is None or not value.strip():
        return default.resolve()
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


settings = Settings.from_env()

"""Shared, portable paths for the GridSense ML data pipeline."""

import os
from pathlib import Path


_PROCESSING_DIR = Path(__file__).resolve().parent
_DEFAULT_PROJECT_ROOT = _PROCESSING_DIR.parents[2]

PROJECT_ROOT = Path(
    os.environ.get("GRIDSENSE_PROJECT_ROOT", _DEFAULT_PROJECT_ROOT)
).expanduser().resolve()
DATA_DIR = Path(
    os.environ.get("GRIDSENSE_DATA_DIR", PROJECT_ROOT / "ML" / "Data")
).expanduser().resolve()

SOURCE_DIR = DATA_DIR / "Data"
EXTRACTED_DIR = DATA_DIR / "Extracted"
PROCESSING_DIR = DATA_DIR / "Processing"
REPORTS_DIR = DATA_DIR / "Reports"
DATASET_DIR = DATA_DIR / "Dataset"
YEARLY_DIR = PROCESSING_DIR / "yearly_cleaned"

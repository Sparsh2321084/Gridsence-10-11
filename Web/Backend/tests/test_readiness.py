import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from Web.Backend import main


class ReadinessTests(unittest.TestCase):
    def test_readiness_reports_missing_model_and_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with (
                patch.object(main, "MODEL_PATH", root / "missing-model.joblib"),
                patch.object(main, "DATASET_PATH", root / "missing-dataset.parquet"),
            ):
                with self.assertRaises(HTTPException) as raised:
                    main.readiness()

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail["missing_artifacts"],
            ["missing-model.joblib", "missing-dataset.parquet"],
        )

    def test_readiness_succeeds_when_model_and_dataset_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            model_path = root / "model.joblib"
            dataset_path = root / "dataset.parquet"
            model_path.touch()
            dataset_path.touch()
            with (
                patch.object(main, "MODEL_PATH", model_path),
                patch.object(main, "DATASET_PATH", dataset_path),
            ):
                response = main.readiness()

        self.assertEqual(response["status"], "ready")
        self.assertEqual(response["model"], "model.joblib")
        self.assertEqual(response["dataset"], "dataset.parquet")

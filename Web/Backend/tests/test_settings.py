import unittest
from pathlib import Path

from Web.Backend.core.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_defaults_are_repository_relative(self) -> None:
        root = Path("C:/grid-sense").resolve()
        settings = Settings.from_env({}, project_root=root)

        self.assertEqual(settings.project_root, root)
        self.assertEqual(
            settings.model_path,
            root / "ML" / "Model" / "gridsence_production_bundle.joblib",
        )
        self.assertEqual(
            settings.dataset_path,
            root / "ML" / "Data" / "Dataset" / "delhi_ml_dataset_2019_2026.parquet",
        )
        self.assertTrue(settings.enable_sldc_polling)

    def test_environment_overrides_paths_cors_and_poller(self) -> None:
        root = Path("C:/grid-sense").resolve()
        settings = Settings.from_env(
            {
                "GRIDSENSE_PROJECT_ROOT": str(root),
                "GRIDSENSE_MODEL_PATH": "artifacts/model.joblib",
                "GRIDSENSE_DATASET_PATH": "artifacts/dataset.parquet",
                "GRIDSENSE_ACTUALS_DB_PATH": "runtime/actuals.sqlite3",
                "GRIDSENSE_ABT_INBOX_PATH": "runtime/inbox",
                "GRIDSENSE_CORS_ORIGINS": "https://grid.example, https://admin.example ",
                "GRIDSENSE_ENABLE_SLDC_POLLING": "false",
            }
        )

        self.assertEqual(settings.model_path, root / "artifacts" / "model.joblib")
        self.assertEqual(settings.dataset_path, root / "artifacts" / "dataset.parquet")
        self.assertEqual(
            settings.actuals_db_path,
            root / "runtime" / "actuals.sqlite3",
        )
        self.assertEqual(settings.abt_inbox_path, root / "runtime" / "inbox")
        self.assertEqual(
            settings.cors_origins,
            ("https://grid.example", "https://admin.example"),
        )
        self.assertFalse(settings.enable_sldc_polling)

    def test_invalid_poller_setting_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "GRIDSENSE_ENABLE_SLDC_POLLING"):
            Settings.from_env({"GRIDSENSE_ENABLE_SLDC_POLLING": "sometimes"})

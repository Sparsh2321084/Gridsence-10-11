# GridSense ML

This folder contains the data-processing code, generated datasets and reports,
and the forecast model. The pipeline is designed to be run as individual,
understandable stages; it does not silently train or replace the production
model.

## Folder map

| Location | Purpose |
| --- | --- |
| `Data/Data/` | Original source archives. Keep these unchanged. |
| `Data/Extracted/` | Extracted ABT workbooks, organized by financial year and week. |
| `Data/Processing/` | Data pipeline scripts, intermediate yearly data, and weather cache. |
| `Data/Dataset/` | Combined, cleaned, and feature-enriched datasets. |
| `Data/Reports/` | Audit, cleaning, and dataset summary reports. |
| `Model/` | Forecast inference code and the current model bundle. |

Generated data files are intentionally kept separate from the scripts. Do not
edit generated datasets by hand; make corrections in the source or processing
logic, then rerun the relevant stage.

## Pipeline order

Run commands from the repository root in PowerShell:

1. `python ML\Data\Processing\01_archive_inventory.py` — inventory source archives.
2. Extract the source archives into the matching financial-year folders under
   `ML\Data\Extracted\`.
3. `python ML\Data\Processing\audit_extracted_files.py` — report workbook and
   utility-week issues for review.
4. `python ML\Data\Processing\build_consumption_dataset.py` — build yearly and
   combined consumption datasets.
5. `python ML\Data\Processing\enrich_delhi_dataset.py` — clean anomalies, add
   weather and calendar features, and write the ML dataset.

Review the reports in `ML\Data\Reports\` before using a regenerated dataset.
Enrichment may fetch weather data when its cache does not contain the requested
period. These scripts do not train a model; a documented training and
evaluation workflow remains future work.

## Choose data and project locations

By default, paths are resolved from this file's location, so cloning or moving
the repository does not require editing Python source.

Set either environment variable before running a script to customize locations:

```powershell
$env:GRIDSENSE_PROJECT_ROOT = "E:\work\GridSense"
$env:GRIDSENSE_DATA_DIR = "F:\GridSenseData"
```

`GRIDSENSE_DATA_DIR` points to the directory containing `Data`, `Extracted`,
`Processing`, `Dataset`, and `Reports`. If it is not set, those folders live
under `<project>\ML\Data`. `GRIDSENSE_PROJECT_ROOT` is optional and is only
needed when the repository root cannot be inferred. The shared definitions are
in `Data\Processing\paths.py`.

The pipeline currently uses the Python packages listed in
`Web\Backend\requirements.txt`; run it in an environment where those
dependencies are installed.

## Editing safely

- Start with one processing script and read its inputs and outputs before
  changing it.
- Keep original archives unchanged and inspect audit reports rather than
  assuming every flagged mismatch is bad data.
- Preserve the current model bundle until a separate training/evaluation
  process can demonstrate that a replacement is better.
- Put changeable data paths in environment variables, not machine-specific
  absolute paths in code.

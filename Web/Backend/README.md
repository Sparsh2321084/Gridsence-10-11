# GridSense Backend

FastAPI service for Delhi load forecasts, actual-load ingestion, grid metrics,
and planning-only asset simulations.

## Code layout

```text
Web/Backend/
├── core/                 # Environment-backed settings
├── domain/               # Forecast metrics and asset simulation rules
├── integrations/         # SLDC and ABT data-source adapters
├── storage/              # SQLite actual-load and forecast persistence
├── config/               # Editable simulator defaults
├── tests/                # Unit and API integration tests
├── main.py               # ASGI app, API routes, and startup orchestration
├── requirements.txt      # Pinned runtime dependencies
├── Dockerfile            # Portable API image
└── compose.yaml          # Local/self-hosted API deployment
```

The small Python modules at the backend root (`actuals_store.py`,
`asset_simulators.py`, `grid_metrics.py`, `abt_import.py`, and `sldc_source.py`)
are compatibility exports for existing imports and commands. New code should
import the implementation from the corresponding layer package.

## Run locally

From the repository root, use an environment with the pinned Python dependencies:

```powershell
python -m pip install -r Web\Backend\requirements.txt
python -m uvicorn Web.Backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation.
The frontend's Vite development server proxies `/api` to this local API.

Run the backend tests from the repository root:

```powershell
python -m unittest discover -s Web\Backend\tests
```

The same test command runs in the backend GitHub Actions workflow.

## Configuration

Settings are resolved in `core/settings.py` from environment variables, with
repository-relative defaults. Relative path values are resolved from
`GRIDSENSE_PROJECT_ROOT`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `GRIDSENSE_PROJECT_ROOT` | Repository root | Base for relative artifact and runtime paths. |
| `GRIDSENSE_MODEL_PATH` | `ML/Model/gridsence_production_bundle.joblib` | Forecast model bundle. |
| `GRIDSENSE_DATASET_PATH` | `ML/Data/Dataset/delhi_ml_dataset_2019_2026.parquet` | Enriched historical model inputs. |
| `GRIDSENSE_ACTUALS_DB_PATH` | `Web/Backend/data/actual_load_15m.sqlite3` | Persistent SQLite actuals and prediction store. |
| `GRIDSENSE_ABT_INBOX_PATH` | `Web/Backend/data/abt_inbox` | Directory scanned for weekly ABT workbooks. |
| `GRIDSENSE_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated browser origins allowed by CORS. |
| `GRIDSENSE_ENABLE_SLDC_POLLING` | `true` | Start the background 15-minute SLDC polling task. |

Use `.env.example` as the environment template for Compose. For local Python
commands, set variables in the current shell or use the repository defaults.
Never put credentials or private keys in the example file.

## Health and readiness

- `GET /api/health` is a liveness check; it reports that the process is serving.
- `GET /api/ready` returns `200` only when the model and dataset files exist;
  otherwise it returns `503` and names the missing artifacts.

Readiness checks file presence, not model deserialization, dataset quality, live
feed availability, or forecast accuracy. Use the forecast endpoint and
operational monitoring for those checks.

## Docker Compose

The API container intentionally does not bake the model, dataset, or SQLite
runtime state into the image. Keep the model bundle and dataset in the expected
host directories, then run from `Web/Backend`:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Compose mounts `ML/Model/` and `ML/Data/Dataset/` read-only, and persists the
SQLite database and ABT inbox under `Web/Backend/data/`. The API listens on
port 8000; readiness is available at `/api/ready`. Run one API container/worker
per SQLite database because each API process starts its own SLDC poller.

This provides a portable API container, not a complete public deployment. The
frontend still needs a production API URL or reverse proxy, and the deployed
frontend origin must be added to `GRIDSENSE_CORS_ORIGINS`. Hosting, TLS,
backups, and monitoring are deployment-specific.

### Railway free-tier evaluation

Railway can build this Dockerfile from the repository root. For a demo, mount a
volume at `/data`, place the model and dataset under `/data/artifacts/`, and set
`GRIDSENSE_MODEL_PATH`, `GRIDSENSE_DATASET_PATH`,
`GRIDSENSE_ACTUALS_DB_PATH`, and `GRIDSENSE_ABT_INBOX_PATH` to those mounted
paths. Set `GRIDSENSE_CORS_ORIGINS` to the deployed frontend origin, and set
`VITE_API_BASE_URL` in the frontend host to the Railway service's HTTPS origin.

The Railway Free plan is not suitable for dependable operations: it has a
512-MB service memory limit, limited monthly usage credits, and a 500-MB volume
limit. The current local actuals database is already about 336 MiB, before
including the model and dataset if placed on the same volume. Monitor volume
usage closely or use a paid/external persistent store before relying on the
service.

## Data and operating limitations

- The model and dataset are required local artifacts and are not downloaded by
  the API.
- SLDC values are monitoring data, not ABT settlement data. ABT workbooks can
  be placed in the configured inbox for backfill.
- Stale actuals, weather-provider failures, or missing history can prevent
  live-input forecasting; the response identifies the selected input source.
- Asset outputs are configurable planning simulations. They do not connect to
  SCADA, asset telemetry, or dispatch controls.

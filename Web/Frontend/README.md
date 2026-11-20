# GridSense Frontend

GridSense is a responsive electricity forecasting website for Delhi, built with React, TypeScript, and Vite. It includes a marketing home page and a forecast dashboard connected to the FastAPI forecast endpoint.

## Project structure

```text
src/
├── assets/                 # Images and other frontend assets
├── components/
│   └── layout/             # Shared site header, footer, and layout
├── pages/
│   ├── home/
│   │   ├── HomePage.tsx    # Composes the home page sections
│   │   └── sections/       # Independently editable home page sections
│   └── dashboard/
│       ├── DashboardPage.tsx
│       └── sections/
│           ├── DashboardForecastSection.tsx  # Fetches data and composes dashboard blocks
│           ├── MainGridDashboard.tsx
│           ├── AreaGridDashboard.tsx
│           ├── analytics.ts
│           ├── types.ts
│           └── blocks/                      # Independent cards and visualizations
├── App.tsx                 # Selects the page for the current URL
├── App.css                 # Application styles
├── index.css               # Global styles
└── main.tsx                # Application entry point
```

The shared `SiteLayout` wraps each page with the same header and footer. Page-specific content stays inside its page folder. To change the order of home page sections, rearrange their component entries in `pages/home/HomePage.tsx`; each section can otherwise be edited independently.

The dashboard composes independent blocks from `pages/dashboard/sections/blocks/`. Choose `All Delhi` or a utility in the area switcher. Add, remove, or reorder blocks in `MainGridDashboard.tsx` or `AreaGridDashboard.tsx`; each block owns its own display and styling hooks.

Forecast KPIs, 15-minute energy, ramps, area shares, and P05/P50/P95 curves are derived from the API response. Yesterday comparisons appear only when aligned historical values are available. Asset simulators use forecast inputs and editable example profiles; they are not live SCADA/asset telemetry and never issue control or dispatch commands. The PPA calculator is a planning comparison only and does not submit market bids.

## Actual-load freshness

The backend seeds the `actual_load_15m` SQLite store from the historical Parquet dataset, then polls the Delhi SLDC real-time page every 15 minutes while the API process is running. It reads the **Drawl** values (not Schedule) for BRPL, BYPL, TPDDL, NDMC, MES, Railways, and Total, and aligns the page's timestamp to its 15-minute block. The API reports `LIVE`, `STALE`, `REPLAYED`, or `UNAVAILABLE` in the forecast response. Actual rows retain their source and quality flag; missing rows remain `NULL`. Interpolation of up to four consecutive missing blocks is limited to the separate model inference window and is reported in the freshness metadata.

The SLDC page labels these figures as monitoring data and warns that communication failures can affect readings; range and sum checks are applied, but this feed is not ABT settlement data. The separate dated load-curve page is not used as a substitute for missing entities. Run a single API worker to avoid redundant polling. The SQLite database is local runtime state under `Web/Backend/data/` by default; set `GRIDSENSE_ACTUALS_DB_PATH` to choose another location.

### ABT backfill, weather, and drift calibration

Drop weekly `.xls` or `.xlsx` ABT workbooks into `Web/Backend/data/abt_inbox/` (or set `GRIDSENSE_ABT_INBOX_PATH`). The API scans this folder on its 15-minute ingestion cycle. The importer accepts the six named billing columns plus either a timestamp or a date and time/block column; numeric blocks are treated as 1–96, where block 1 starts at 00:00. It requires the workbook to cover seven local dates, records absent intervals and gaps since the last verified reading as `MISSING`, converts the six 15-minute MU readings to MW using `× 4000`, and derives Delhi total from the six entities. For a one-time scan or a continuously running folder importer, use:

```powershell
python -m Web.Backend.abt_import --folder Web/Backend/data/abt_inbox
python -m Web.Backend.abt_import --folder Web/Backend/data/abt_inbox --watch
```

When recent actuals meet the `LIVE` freshness threshold and form a usable 672-block inference window, the forecast uses those load values and requests hourly weather from Open-Meteo with `past_days=8` and `forecast_days=2`; weather is aligned to 15-minute blocks and expanded to the model's 29 features. In `STALE` or `REPLAYED` mode, the forecast stays on the historical load baseline and the last historical weather-day profile. Open-Meteo failures also fall back to that baseline and are logged.

Served forecasts are retained in `forecast_predictions_15m`. Once at least five prior days have valid actual/prediction pairs, the API calculates trailing 14-day block-of-day residual means from completed local days only (excluding the current day) and passes the bias to inference. This updates forecast values only; it does not retrain model weights.

### Configurable asset simulators

The forecast response includes default simulator schedules, and the dashboard exposes editable profiles behind the **Configurable Simulator** label. Defaults are stored in `Web/Backend/config/assets_config.json`. The corridor panel applies the configured 0.8%/°C ambient derating above 40°C to its nominal capacity and classifies forecast P95 utilization. BESS, EV valley-fill, and demand-response outputs are greedy planning simulations based on forecast P50/P95; the DR trigger uses its configured threshold, enrolled MW, and curtailable fraction.

To run the simulators with edited values, send `POST /api/v1/simulate-assets` with a target and optional profile overrides. For example:

```json
{
  "target": "delhi_total_mw",
  "corridor_capacity_mw": 8600,
  "bess": {
    "power_mw": 20,
    "energy_mwh": 40,
    "min_soc_pct": 15,
    "initial_soc_pct": 50,
    "max_soc_pct": 95,
    "round_trip_efficiency": 0.88
  },
  "ev_fleet": {
    "bus_count": 500,
    "charger_kw_per_bus": 180,
    "target_energy_mwh": 65
  },
  "demand_response": {
    "threshold_mw": 7800,
    "enrolled_capacity_mw": 150,
    "curtailable_fraction": 0.15,
    "event_duration_hours": 2
  }
}
```

These are configurable examples only. Corridor results do not include conductor temperature, topology, or N-1 contingencies; battery SOC, fleet availability, and customer response are not connected. Do not treat simulator outputs as validated operating limits, dispatch instructions, IEX bids, or real-world asset schedules.

## Development

Start the forecast API from the repository root:

```powershell
python -m pip install -r Web/Backend/requirements.txt
python -m uvicorn Web.Backend.main:app --app-dir . --reload --host 127.0.0.1 --port 8000
```

Then run the frontend from `Web/Frontend`:

```powershell
npm install
npm run dev
```

The dashboard fetches live model output from `http://localhost:8000/api/forecast`.
The API origin is configurable with `VITE_API_BASE_URL`. Leave it empty in
development to use the Vite `/api` proxy; set it to the deployed API origin in
the Vercel project environment for production.

## Checks

```powershell
npm run build
npm run lint
```

## Deployment

For Vercel, set the project root directory to `Web/Frontend`. The Vercel
configuration rewrites `/dashboard` to the app entry point so the client-side
dashboard route works on direct visits and refreshes. Set `VITE_API_BASE_URL`
to the backend service's HTTPS origin and allow the deployed Vercel origin in
the backend's `GRIDSENSE_CORS_ORIGINS`.

# GridSense Project Status

**Last reviewed:** 2026-11-20
**Overall progress:** Deliverables 1–4 implemented locally; overall release percentage not recalculated.

This is the living progress log for the GridSense website and its forecasting stack. Update the checklist and append to the progress log as work is completed. “Present” means the implementation or artifact exists in this repository; it does not imply production readiness.

## Daily Progress Report — 2026-11-20 (IST)

### Summary

Completed the first four implementation deliverables: actual-load storage/freshness, ABT/weather/drift integration, calibrated forecast metrics, and configurable forecast-based asset simulators. The model weights were not changed. The application and simulator outputs remain a local planning prototype, not an operational dispatch system.

### Work completed today

1. **Actual-load source and freshness**
   - Confirmed the supplied Delhi SLDC monitoring page contains the seven Drawl entities, including Railways.
   - Added SQLite quality-aware actual storage, timestamp/unit/range/reconciliation checks, duplicate precedence, explicit missing rows, and inference-only short-gap interpolation.
   - Added the SLDC poller and dashboard `LIVE`, `STALE`, `REPLAYED`, and `UNAVAILABLE` freshness states. The source is monitoring data, not ABT settlement data.
   - Fixed a timezone-aware/naive timestamp comparison in the poller and added a regression test.

2. **ABT backfill, weather, and causal calibration**
   - Added the weekly ABT workbook importer and inbox scanner/CLI; 15-minute MU values convert to MW and missing intervals remain explicitly missing.
   - Added the Open-Meteo lookback/forecast feature assembly for the model’s 672 × 29 history and 96 × 29 future inputs when freshness/coverage permits. Stale/replayed operation uses the documented historical fallback.
   - Added stored forecast predictions and the trailing, completed-day 14-day block-of-day bias calculation. This adjusts inference values without retraining weights.

3. **Forecast metrics and PPA planning**
   - Added `config/grid_norms.json` with the user-specified 0.65 t/MWh coal factor, 0.68 default thermal share, 0.80 August–October share, the configured 5% reserve floor, and empirical P75/P95 ramp thresholds for all seven entities.
   - Added per-block and daily maximum ramp severity, thermal coal estimates, reserve calculations, and optional scalar/96-value PPA calculations to the forecast API.
   - Updated the dashboard’s ramp, coal, reserve, and PPA displays. The coal and reserve assumptions are labeled as planning estimates; they were not independently verified as plant-specific or official dispatch rules.

4. **Configurable asset simulators**
   - Added editable defaults in `Web/Backend/config/assets_config.json` and `POST /api/v1/simulate-assets`.
   - Added forecast-P95 corridor stress with the requested 0.8%/°C ambient multiplier above 40°C, the `NORMAL`/`ELEVATED_SAG`/`N1_THERMAL_RISK` classifications, and overnight blocks below 55% utilization.
   - Added a 20 MW / 40 MWh BESS greedy schedule with bounded SOC and charge/discharge efficiency; a 500-bus, 90 MW maximum EV water-fill schedule targeting 65 MWh; and a DR trigger with configured city/NDMC thresholds, a two-hour lead window, and a 22.5 MW default maximum shave.
   - Added editable dashboard controls and default simulator outputs in the forecast response. All four cards say **Configurable Simulator** and disclose that no live SCADA, asset SOC, vehicle availability, or customer-response telemetry is connected. They do not issue commands.
   - Documented profiles, endpoint, and limitations in `Web/Frontend/README.md`. No PyTorch model weights were touched.

### Verification completed today

- `python -m unittest discover -s Web\Backend\tests` — **37 tests passed**, including unit conversion/quality/freshness, weather and drift behavior, coal/ramp/reserve/PPA math, corridor derating/severity boundaries, BESS SOC bounds, EV energy conservation, DR trigger boundaries, and simulator API overrides.
- `npm run build` and `npm run lint` from `Web/Frontend` — passed.
- `git diff --check` — passed; Git printed only existing LF/CRLF normalization notices.
- Local API smoke checks returned health `ok`, 96 forecast intervals, default simulator output, and a successful custom EV target via `POST /api/v1/simulate-assets`.
- Browser check confirmed all four simulator cards render; changing the EV target from 65 MWh to 30 MWh and applying it updated the displayed server result.
- Pylance MCP diagnostics timed out during the session; backend unit/runtime checks and frontend build/lint completed successfully.

### Current limitations and next work

- Freshness was still **STALE** during verification. The latest displayed SLDC actual was 2026-11-20 04:30 IST, but the rolling seven-day coverage was insufficient; the forecast continued to use the historical feature baseline ending 2026-09-27. No ABT workbook was available to backfill the intervening period.
- Therefore, live actuals are not yet a complete model input window; live weather assembly and causal calibration activate only when the required coverage/data is present.
- The corridor multiplier is the requested configurable approximation, not a complete IEEE 738 conductor-rating study; topology, contingency data, conductor temperatures, and approved line ratings are absent.
- BESS/EV/DR profiles are illustrative heuristics. Production deployment, live asset feeds, operator validation, and external market/dispatch integrations remain out of scope.
- Local API and Vite processes used for verification were stopped afterward. No background PowerShell sessions remain.

## Aim

Deliver a reliable, deployable Delhi electricity-demand forecasting website that presents a 24-hour forecast in 15-minute intervals, backed by a tested API and reproducible, documented data/model pipeline.

## Current snapshot

| Area | Status |
| --- | --- |
| Marketing site | Home page sections, shared header/footer, and responsive styling are present. |
| Dashboard | City and utility-area views include freshness states, probabilistic charts, PPA planning, ramp severity, coal/reserve estimates, and four editable configurable-simulator cards. |
| Backend | FastAPI health/forecast endpoints and `POST /api/v1/simulate-assets` are present. Forecasts include freshness, weather, ramp, coal, reserve/PPA, and default simulator outputs. |
| Operational data | SLDC monitoring snapshots and optional ABT workbooks feed the actuals store. Live SCADA, corridor topology/ratings, BESS/EV telemetry, customer response, and market feeds are not connected; simulator cards are explicitly planning-only. |
| Data and model artifacts | Consumption/enriched datasets, data audit reports, and a production model bundle are present. |
| End-to-end operation | Local API/model, simulator endpoint, Vite flow, and browser parameter update verified. Production deployment remains unverified. Model feature baseline ends on 2026-09-27 23:45 IST; latest SLDC samples alone do not provide the required recent coverage. |

## Progress recorded

### Present in the repository

- [x] React/TypeScript/Vite frontend with shared site layout and composed home page sections.
- [x] `/dashboard` route and dashboard UI wired to the forecast API contract.
- [x] City dashboard calculates P50 peak, P95 ceiling/spread, 24-hour energy, ramp, prior-day comparison when available, area shares, and weather overlays.
- [x] Utility switcher opens area views with area KPIs, a PPA-vs-forecast planning comparison, and downloadable CSV ledger.
- [x] Asset cards are labeled as configurable simulators and disclose missing live SCADA/asset telemetry; their example outputs are not presented as live instructions.
- [x] PPA-vs-P50 ledger calculates per-block deficit/surplus comparison and provides a CSV download action.
- [x] Vite development proxy for `/api` to `http://localhost:8000`.
- [x] FastAPI `/api/health` and `/api/forecast` endpoints.
- [x] Forecast serving code for 24 hours at 15-minute intervals, with utility outputs, prediction bounds, weather drivers, aligned prior-day values, and dataset cutoff.
- [x] SQLite actual-load quality store, SLDC polling, freshness metadata, and short-gap inference-only interpolation.
- [x] ABT weekly workbook import, Open-Meteo feature assembly, stored predictions, and causal block-of-day drift calibration.
- [x] Configured coal/ramp/reserve/PPA forecast metrics and the `POST /api/v1/simulate-assets` corridor/BESS/EV/DR endpoint.
- [x] Data extraction, anomaly cleaning, weather enrichment, and domain-feature scripts.
- [x] Delhi consumption and enriched dataset files, data audit reports, and a saved model bundle.

### Prior verification completed on 2026-11-19

- [x] `npm run build` from `Web/Frontend` — passed.
- [x] `npm run lint` from `Web/Frontend` — passed.
- [x] Backend syntax check — `python -m py_compile Web/Backend/main.py` passed.
- [x] Browser check with a mocked payload — city blocks, area switching, PPA input, and 96 ledger rows rendered.
- [x] Local backend/model and Vite proxy — health passed; forecast returned 96 rows, Open-Meteo weather source, weather values, and dataset cutoff.
- [x] Forced an expected weather-fetch failure — logged fallback source and returned 96 feature rows under the installed pandas version.
- [x] Browser check with the live local API — city dashboard, weather strips, utility selector, area view, PPA input, and 96 rows rendered.
- [ ] Downloaded CSV file contents — not independently verified in the browser harness.
- [ ] Production deployment and live forecast delivery — not exercised.

## Remaining work

### P0 — Make the forecast work end to end

- [x] Run the backend against the checked-in model and dataset; health passed and 96 forecast intervals plus weather fields returned.
- [x] Run frontend and backend together; live local forecast rendering and area view passed.
- [ ] Verify refresh, API-down, missing-artifact behavior, aligned actual values, and all numerical invariants.
- [ ] Backfill recent actuals and refresh/rebuild the historical feature dataset: the checked-in model baseline still ends at 2026-09-27 23:45 IST; isolated recent SLDC samples do not meet the seven-day coverage requirement.
- [ ] Decide and configure the production API URL/routing. The frontend calls the relative `/api/forecast`; Vite proxies it only in development, while the current Vercel config only rewrites `/dashboard`.
- [ ] Confirm deployed backend CORS settings match the actual frontend origin; current allowed origins are localhost-only.

### P1 — Improve reliability and user-facing forecast clarity

- [x] Log expected weather-fetch failures and include the selected weather source in the API response/dashboard.
- [x] Display the forecast as future estimates rather than labeling the first forecast point as a measured live load.
- [x] Display P05–P50–P95 forecast curves and weather-driver strips when those fields are available.
- [ ] Add focused API/model tests for missing artifacts, weather API failure, feature shape/columns, timestamps, and forecast response schema.
- [ ] Add frontend tests for key loading/error/success states, metrics, area switching, and PPA calculations.
- [x] Configure user-specified coal, empirical ramp, and reserve assumptions before displaying their planning labels; independent regulatory/plant validation remains outstanding.

### P2 — Make data and model work reproducible

- [ ] Review the existing data audit findings: 25 of 388 weeks need review, and the audit reports 52 utility-week mismatch rows. Resolve or document accepted exceptions.
- [x] Add the requested coal factor, empirical ramp thresholds, and reserve policy to configuration; source validation/citations and plant-specific verification remain outstanding.
- [ ] Document how to obtain/extract source data, run each processing stage, and regenerate datasets and reports.
- [x] Remove machine-specific absolute paths from ML data scripts; paths now resolve from the repository or `GRIDSENSE_PROJECT_ROOT` / `GRIDSENSE_DATA_DIR`.
- [ ] Document model provenance, training/evaluation procedure, validation period, and accuracy metrics. A production model artifact is present, but a model training script was not found in the inspected `ML/Model` files.
- [ ] Record model/data versions and define a repeatable model refresh procedure.

### P3 — Release readiness

- [ ] Verify responsive behavior, accessibility basics, chart labeling, and behavior on direct `/dashboard` visits and refresh.
- [ ] Define deployment environments, runtime/dependency setup, secrets/configuration policy, and operational health checks.
- [ ] Add a release checklist and record a successful deployed smoke test.

## Review notes and known risks

- The frontend README now describes the city/area dashboards and their data-backed limitations.
- The Vercel config currently handles the dashboard SPA route only; it does not provide a production backend route.
- Future weather acquisition falls back to recent historical weather after an expected fetch failure; the backend logs that fallback and the API/dashboard identify the selected source.
- Local smoke test on 2026-11-19 used Open-Meteo weather; historical demand ended on 2026-09-27 23:45 IST and no yesterday-aligned actual values were present.
- The audit summary is evidence of data review still needed, not proof that all reported mismatches are bad data; investigate and document the cause before changing records.
- Backend tests are present and 37 passed on 2026-11-20. A repeatable PyTorch training script/model-refresh procedure is still not established.

## Suggested acceptance criteria

1. A clean setup can start the API and frontend using documented commands.
2. The API health check and forecast endpoint pass automated tests with the checked-in model/data artifacts.
3. The dashboard renders 96 correctly ordered 15-minute points and understandable units, and handles unavailable services without appearing to have fresh data.
4. Production routing and CORS are configured for the chosen hosting setup and a deployed smoke test succeeds.
5. Data and model provenance, evaluation metrics, and known data exceptions are documented and reproducible.

## Progress log

| Date | Progress | Evidence / notes |
| --- | --- | --- |
| 2026-11-19 | ~30% (team estimate) | Initial whole-project inventory recorded. |
| 2026-11-19 | ~30% (estimate unchanged) | Added city/area forecast blocks and API weather/prior-day fields. Build, lint, and backend syntax check passed; live API and browser flow returned 96 intervals. Dataset is stale and production delivery remains unverified. |
| 2026-11-20 | Deliverables 1–4 implemented locally; overall percentage not recalculated. | Added quality-aware actuals/freshness, SLDC polling, ABT import, weather/drift integration, coal/ramp/reserve/PPA metrics, and configurable corridor/BESS/EV/DR simulators. 37 backend tests, frontend build/lint, local API smoke checks, and browser EV-override interaction passed. Forecast remains STALE on the historical feature baseline; production/live-asset readiness remains incomplete. |
| 2026-11-20 | Backend foundation structured; production remains unverified. | Grouped backend code by core/domain/integrations/storage, centralized environment settings, added readiness checks and backend setup/deployment docs, Docker Compose, and backend CI. 42 backend tests passed and local health/readiness endpoints responded; Docker CLI was unavailable, so the image and deployment were not exercised. |

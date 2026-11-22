# Run GridSense locally

These instructions are for Windows PowerShell. Start the backend and frontend
in separate terminals from the repository root.

## Prerequisites

- Python and Node.js/npm installed.
- The model and dataset files are present:
  - `ML/Model/gridsence_production_bundle.joblib`
  - `ML/Data/Dataset/delhi_ml_dataset_2019_2026.parquet`

## 1. Start the backend

In the first PowerShell terminal:

```powershell
cd D:\GridSence-10-11
python -m pip install -r Web\Backend\requirements.txt
python -m uvicorn Web.Backend.main:app --host 127.0.0.1 --port 8000
```

The API is available at `http://127.0.0.1:8000`. Check that it is ready at
`http://127.0.0.1:8000/api/ready`, or open the API docs at
`http://127.0.0.1:8000/docs`.

## 2. Start the frontend

In a second PowerShell terminal:

```powershell
cd D:\GridSence-10-11\Web\Frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open the local address printed by Vite, normally
`http://127.0.0.1:5173/`. The development environment is configured to connect
to the API at `http://localhost:8000`.

## Stop the project

Press `Ctrl+C` in each terminal running a server.

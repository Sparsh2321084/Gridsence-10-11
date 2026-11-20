FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRIDSENSE_PROJECT_ROOT=/app

WORKDIR /app

COPY Web/Backend/requirements.txt /app/Web/Backend/requirements.txt
RUN python -m pip install --no-cache-dir -r Web/Backend/requirements.txt

COPY Web/Backend /app/Web/Backend
COPY ML/Model/predict_delhi_load.py /app/ML/Model/predict_delhi_load.py
COPY ML/Data/Processing/enrich_delhi_dataset.py /app/ML/Data/Processing/enrich_delhi_dataset.py
COPY ML/Data/Processing/paths.py /app/ML/Data/Processing/paths.py
COPY config/grid_norms.json /app/config/grid_norms.json

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn Web.Backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

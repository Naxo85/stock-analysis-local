FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STOCK_ANALYSIS_ROOT=/app

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config

RUN pip install --no-cache-dir .

CMD exec gunicorn --bind :${PORT:-8080} --workers 1 --threads 4 --timeout 180 stock_analysis.controller.cloud_app:app

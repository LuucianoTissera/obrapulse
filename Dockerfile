FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLBACKEND=Agg

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install .

# Usuario sin privilegios
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data /app/models /app/reports \
    && chown -R appuser:appuser /app
USER appuser

# Datos y modelo DEMO (sintéticos). En producción se montan volúmenes con datos reales.
RUN python -m obrapulse.cli generate-data && python -m obrapulse.cli train \
    && python -m obrapulse.cli run > /dev/null

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["python", "-m", "obrapulse.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]

# Arquitectura y flujo de datos

## Flujo del pipeline (`pipeline.py`)

1. **Ingesta** (`ingestion.py`): lee `partes_diarios.csv`. Valida fechas, numéricos, cantidades, duplicados.
   Los inválidos van a `cuarentena_partes` con la columna `motivo`.
2. **KPIs base** (`kpis.enrich`): marca cada tarea como cumplida (≥ 95 % de lo planificado) y calcula
   valor planificado/ejecutado/perdido y horas-hombre perdidas.
3. **Clasificación** (`classifier/service.py`), solo para tareas **no cumplidas con observación**:
   - ML clasifica todo el lote en una llamada vectorizada.
   - Casos con `confianza < CONFIDENCE_THRESHOLD` se escalan al LLM (tope `LLM_MAX_CALLS`, caché por texto).
   - Si sigue bajo el umbral → `requiere_revision = True`.
   - Desvíos sin observación → `SIN_CAUSA` por regla (nunca se envían a la IA).
4. **Agregados** (`kpis.py`): PPC global/obra/semana, SPI, curvas S, Pareto de causas, productividad.
5. **Alertas** (`anomalies.py`): test binomial unilateral por obra (última semana vs línea base) + causa dominante.
6. **Causa raíz** (`rca.py`): top 3 combinaciones causa+obra por valor no ejecutado → 5 Porqués + acciones (LLM o playbook).
7. **Persistencia** (`storage.py`): SQLite (`partes`, `desvios`, `cuarentena_partes`, `corridas`).
8. **Reporte** (`reporting.py`): HTML autocontenido + `resumen_latest.json`.

## Fórmulas

- PPC = tareas cumplidas / tareas planificadas
- SPI = Σ(cantidad ejecutada × precio) / Σ(cantidad planificada × precio), acumulado
- Valor no ejecutado = (planificado − ejecutado) × precio, solo en tareas no cumplidas
- Test de alerta: p0 = (fallas_base + 1) / (tareas_base + 2) (suavizado de Laplace);
  p-valor = P(X ≥ k | n, p0) con X ~ Binomial; alerta si p < 0,01

## Seguridad

- Secretos solo por variables de entorno; `.env` ignorado por git.
- API opcionalmente protegida con `X-API-Key` (comparación en tiempo constante).
- Contenedor sin root; entradas de la API con límites de longitud y patrones validados.
- Observaciones enviadas al LLM como dato delimitado, con límite de caracteres. Si la política de la empresa
  prohíbe enviar datos a terceros, usar `CLASSIFIER_MODE=ml` (100 % local).

## Escalar a producción real

| Hoy | Producción |
|---|---|
| CSV | Formulario móvil / ERP / sistema de gestión de obras |
| SQLite | PostgreSQL |
| `cron` de GitHub Actions | Scheduler corporativo (cron / Airflow / Task Scheduler) |
| Reporte HTML | Power BI sobre la API |

# Integración de ObraPulse con Power Query y Power BI

Esta carpeta contiene consultas M listas para importar en Power BI Desktop. Power BI se usa como capa de visualización; la validación, los cálculos de KPIs y la clasificación siguen ejecutándose en ObraPulse (Python/FastAPI).

## 1. Levantar ObraPulse

Desde la carpeta raíz del repositorio:

```bash
pip install -e ".[dev]"
obrapulse run
obrapulse serve
```

La API queda disponible en `http://127.0.0.1:8000`. Verificá `http://127.0.0.1:8000/health` y ejecutá `obrapulse run` cada vez que quieras actualizar los datos procesados.

Si configuraste `API_KEY` en el archivo `.env`, creá el parámetro `pApiKey` en Power Query con ese mismo valor. Si no configuraste `API_KEY`, dejá `pApiKey` vacío. No publiques ni compartas un archivo PBIX que contenga una clave real.

## 2. Crear las consultas en Power BI Desktop

1. Abrí Power BI Desktop y seleccioná **Transformar datos** → **Nueva fuente** → **Consulta en blanco**.
2. En el Editor avanzado, pegá el contenido de `queries/fnObraPulseGet.m`. Nombrá la consulta `fnObraPulseGet` y dejala como función (no hace falta cargarla al modelo).
3. Creá dos parámetros en **Administrar parámetros**:
   - `pBaseUrl`: tipo Texto; valor actual `http://127.0.0.1:8000`.
   - `pApiKey`: tipo Texto; valor actual vacío si la API no usa clave.
4. Para cada archivo `.m` restante de `queries/`, creá una consulta en blanco, pegá el contenido en el Editor avanzado y asignale el nombre indicado por el archivo: `Partes`, `ResumenObras`, `CurvaS`, `ParetoCausas`, `Anomalias` y `CalidadDatos`.
5. Seleccioná **Cerrar y aplicar**. En la primera conexión, aceptá el nivel de privacidad que corresponda a tu entorno local.
6. Configurá `Partes[fecha]` y `CurvaS[fecha]` como tipo Fecha si Power Query no lo detectó automáticamente.

`Partes.m` consulta el endpoint paginando en bloques de hasta 50.000 registros. Los endpoints de resumen devuelven el resultado de la última corrida procesada, no vuelven a ejecutar la IA desde Power BI.

## 3. Modelo de datos

Tablas principales:

- `Partes`: granularidad por registro/actividad/fecha. Incluye cantidades planificadas y ejecutadas, cumplimiento, valores, pérdidas estimadas y categoría del desvío.
- `ResumenObras`: indicadores agregados por obra.
- `CurvaS`: valor planificado y ejecutado por fecha y obra, con acumulados.
- `ParetoCausas`: causas ordenadas por valor perdido.
- `Anomalias`: anomalías detectadas por ObraPulse en la última corrida.
- `CalidadDatos`: cantidad de partes válidos/rechazados y registros que requieren revisión.

Relaciones recomendadas: `Partes[obra]` → `ResumenObras[obra]` (muchos a uno, filtro desde ResumenObras hacia Partes si se usa como dimensión). `CurvaS` es una tabla agregada independiente; para filtrar ambas tablas con una dimensión de obras, creá una tabla `DimObra` con DAX y relacioná `DimObra[obra]` con `Partes[obra]`, `ResumenObras[obra]` y `CurvaS[obra]`. Evitá relaciones directas muchos-a-muchos.

Para crear la dimensión de obras en **Modelado → Nueva tabla**:

```DAX
DimObra = DISTINCT(Partes[obra])
```

## 4. Medidas DAX sugeridas

Crealas en la tabla `Partes` desde **Modelado → Nueva medida**:

```DAX
Registros = COUNTROWS(Partes)

Actividades cumplidas =
CALCULATE(COUNTROWS(Partes), Partes[cumplida] = TRUE())

PPC = DIVIDE([Actividades cumplidas], [Registros], 0)

Desvíos =
CALCULATE(COUNTROWS(Partes), Partes[cumplida] = FALSE())

Valor planificado = SUM(Partes[valor_plan])

Valor ejecutado = SUM(Partes[valor_ejec])

SPI = DIVIDE([Valor ejecutado], [Valor planificado], 0)

Valor perdido = SUM(Partes[valor_perdido])

Horas-hombre perdidas = SUM(Partes[hh_perdidas])

% de ejecución = DIVIDE(SUM(Partes[cantidad_ejecutada]), SUM(Partes[cantidad_planificada]), 0)
```

Formato sugerido: PPC y % de ejecución como porcentaje; SPI con dos decimales; valores monetarios según la moneda real de los datos. El proyecto de ejemplo usa datos sintéticos, por lo que no deben presentarse como métricas de una obra real.

## 5. Diseño del informe recomendado

### Página 1 — Resumen ejecutivo

- Tarjetas: PPC, SPI, valor perdido, horas-hombre perdidas y cantidad de desvíos.
- Gráfico de líneas: PPC por semana, usando `Partes[semana]` y una medida de PPC que respete el filtro de fecha.
- Barras: valor perdido por obra.
- Segmentadores: obra, fecha y categoría.

### Página 2 — Planificación y avance

- Gráfico de líneas con `CurvaS[fecha]`, `CurvaS[pv_acum]` y `CurvaS[ev_acum]`.
- Barras agrupadas: valor planificado vs. ejecutado por obra.
- Tabla por actividad con cantidad planificada, ejecutada y cumplimiento.

### Página 3 — Causas de incumplimiento

- Barras horizontales: `ParetoCausas[categoria]` por `ParetoCausas[valor_perdido]`.
- Tabla con cantidad de desvíos, valor perdido y horas-hombre perdidas.
- Segmentador por categoría para explorar patrones.

### Página 4 — Alertas y calidad de datos

- Tabla de `Anomalias` para revisar caídas inusuales del PPC.
- Tarjetas con partes válidos, rechazados y registros a revisión, desde `CalidadDatos`.
- Tabla de detalle de `Partes`, filtrable por `cumplida = FALSE()` y por categoría `SIN_CAUSA`.

## 6. Actualización y límites

- Para actualizar en Desktop, primero volvé a ejecutar `obrapulse run` y luego **Actualizar** en Power BI.
- La API está pensada para una integración local de demostración. Power BI Service no puede acceder directamente a `127.0.0.1` de tu PC. Para actualización en la nube, la API debe estar desplegada en un host accesible y protegido, o configurarse un gateway de datos local administrado.
- Si `API_KEY` está activa, la función `fnObraPulseGet` envía `X-API-Key`. Usá una clave de solo lectura para BI en un entorno productivo y no expongas la API sin autenticación.
- Los endpoints `/datos` y `/curva-s` leen la base procesada; no disparan procesamiento ni llamadas al proveedor de IA.
- `valor_plan` y `valor_ejec` se calculan con `precio_unitario`; el proyecto no modela impuestos, presupuesto total ni CPI. No interpretes SPI como CPI.

## Endpoints utilizados

| Consulta Power BI | Endpoint |
|---|---|
| `Partes` | `GET /datos` |
| `ResumenObras` | `GET /obras` |
| `CurvaS` | `GET /curva-s` |
| `ParetoCausas` | `GET /pareto?por=categoria` |
| `Anomalias` | `GET /anomalies` |
| `CalidadDatos` | `GET /calidad-datos` |

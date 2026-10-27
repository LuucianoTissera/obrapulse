"""Detección de caídas anómalas del PPC por obra con un TEST BINOMIAL unilateral.

Por qué binomial y no un z-score diario: cada tarea es un resultado discreto (cumple / no
cumple) y hay pocas por día (~3 por obra). Un z-score diario no tiene potencia estadística;
en cambio, el test binomial acumula la evidencia de toda la ventana reciente y responde
exactamente la pregunta de negocio: ¿la tasa de incumplimiento de la última semana es
significativamente mayor que la histórica de ESA obra?
"""

from __future__ import annotations

import pandas as pd
from scipy.stats import binomtest

COLUMNS = [
    "obra",
    "ppc_base",
    "ppc_reciente",
    "tareas_recientes",
    "desvios_recientes",
    "p_value",
    "valor_perdido_reciente",
    "causa_dominante",
    "pct_causa",
]


def _dominant_cause(desvios: pd.DataFrame, obra: str, cutoff: pd.Timestamp) -> tuple[str, float]:
    rec = desvios[
        (desvios["obra"] == obra)
        & (pd.to_datetime(desvios["fecha"]) >= cutoff)
        & (desvios["categoria"] != "SIN_CAUSA")
    ]
    # Por frecuencia (como en el CNC de Last Planner): estable con pocos eventos
    by = rec.groupby("categoria")["registro_id"].count().sort_values(ascending=False)
    if by.empty:
        return "SIN_CAUSA", 0.0
    return str(by.index[0]), round(float(by.iloc[0] / by.sum() * 100), 0)


def detect_ppc_drops(
    partes: pd.DataFrame,
    desvios: pd.DataFrame,
    recent_days: int = 7,
    alpha: float = 0.01,
    min_recent_tasks: int = 8,
    min_baseline_tasks: int = 30,
) -> pd.DataFrame:
    """Obras cuyo incumplimiento reciente supera significativamente su línea base.

    - Línea base: tareas anteriores a la ventana reciente, con suavizado de Laplace para no
      tener p0 = 0 cuando todavía no hubo incumplimientos.
    - alpha = 0.01 (exigente) porque se testean varias obras a la vez.
    - Se atribuye la causa dominante de la ventana reciente para que la alerta sea accionable.
    """
    if partes.empty:
        return pd.DataFrame(columns=COLUMNS)
    dt = pd.to_datetime(partes["fecha"])
    cutoff = dt.max() - pd.Timedelta(days=recent_days - 1)
    rows = []
    for obra, g in partes.groupby("obra"):
        gdt = dt.loc[g.index]
        base, rec = g[gdt < cutoff], g[gdt >= cutoff]
        if len(base) < min_baseline_tasks or len(rec) < min_recent_tasks:
            continue
        fails_base = int((~base["cumplida"].astype(bool)).sum())
        p0 = (fails_base + 1) / (len(base) + 2)
        k, n = int((~rec["cumplida"].astype(bool)).sum()), len(rec)
        p_value = float(binomtest(k, n, p0, alternative="greater").pvalue)
        if p_value < alpha:
            causa, pct = _dominant_cause(desvios, str(obra), cutoff)
            rows.append(
                {
                    "obra": obra,
                    "ppc_base": round(1 - fails_base / len(base), 3),
                    "ppc_reciente": round(1 - k / n, 3),
                    "tareas_recientes": n,
                    "desvios_recientes": k,
                    "p_value": round(p_value, 5),
                    "valor_perdido_reciente": round(float(rec["valor_perdido"].sum()), 0),
                    "causa_dominante": causa,
                    "pct_causa": pct,
                }
            )
    return pd.DataFrame(rows, columns=COLUMNS).sort_values("p_value").reset_index(drop=True)

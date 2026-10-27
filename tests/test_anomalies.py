import numpy as np
import pandas as pd

from obrapulse.anomalies import detect_ppc_drops


def _build(days=40, recent_fail_rate=0.3, base_fail_rate=0.3, seed=3):
    """Partes sintéticos de 1 obra, 3 tareas por día; la última semana con otra tasa de falla."""
    rng = np.random.default_rng(seed)
    rows = []
    start = pd.Timestamp("2026-09-01")
    n_recent_days = 7
    for d in range(days):
        fecha = (start + pd.Timedelta(days=d)).strftime("%Y-%m-%d")
        rate = recent_fail_rate if d >= days - n_recent_days else base_fail_rate
        for t in range(3):
            fail = rng.random() < rate
            rows.append(
                {
                    "registro_id": f"R{d}-{t}",
                    "fecha": fecha,
                    "obra": "O1",
                    "cumplida": not fail,
                    "valor_perdido": 1000.0 if fail else 0.0,
                    "categoria": "MATERIALES" if fail else None,
                }
            )
    partes = pd.DataFrame(rows)
    desvios = partes[~partes["cumplida"]].copy()
    return partes, desvios


def test_detects_sustained_ppc_collapse_and_attributes_cause():
    partes, desvios = _build(recent_fail_rate=0.95)
    out = detect_ppc_drops(partes, desvios)
    assert len(out) == 1 and out.iloc[0]["obra"] == "O1"
    assert out.iloc[0]["causa_dominante"] == "MATERIALES"
    assert out.iloc[0]["ppc_reciente"] < out.iloc[0]["ppc_base"]


def test_stable_series_not_flagged():
    partes, desvios = _build(recent_fail_rate=0.3, base_fail_rate=0.3)
    assert detect_ppc_drops(partes, desvios).empty


def test_improvement_is_not_flagged():
    """El test es unilateral: una MEJORA del PPC no es una alerta."""
    partes, desvios = _build(recent_fail_rate=0.0, base_fail_rate=0.5)
    assert detect_ppc_drops(partes, desvios).empty


def test_insufficient_data_is_skipped():
    partes, desvios = _build(days=8, recent_fail_rate=1.0)
    assert detect_ppc_drops(partes, desvios).empty  # sin línea base suficiente


def test_empty_input():
    assert detect_ppc_drops(pd.DataFrame(columns=["fecha"]), pd.DataFrame()).empty

"""Análisis de causa raíz asistido (5 Porqués + acciones) para los principales problemas.

Con LLM: genera hipótesis contextualizadas con ejemplos reales de los partes.
Sin LLM: usa el playbook de la taxonomía (determinista). Siempre se etiqueta la fuente,
y siempre son HIPÓTESIS a validar en obra (gemba), nunca conclusiones."""

from __future__ import annotations

import pandas as pd

from .classifier.llm import LLMClassifier
from .taxonomy import CATEGORIES, PLAYBOOK


def analyze_top_problems(
    desvios: pd.DataFrame, llm: LLMClassifier | None = None, top_n: int = 3
) -> list[dict]:
    """Top problemas por valor no ejecutado (obra + causa). SIN_CAUSA es un KPI de datos, no de RCA."""
    d = desvios[desvios["categoria"] != "SIN_CAUSA"]
    if d.empty:
        return []
    g = (
        d.groupby(["categoria", "obra"])
        .agg(
            desvios=("registro_id", "count"),
            valor=("valor_perdido", "sum"),
            hh=("hh_perdidas", "sum"),
        )
        .reset_index()
        .sort_values("valor", ascending=False)
        .head(top_n)
    )
    results = []
    for _, r in g.iterrows():
        mask = (d["categoria"] == r["categoria"]) & (d["obra"] == r["obra"])
        ejemplos = d.loc[mask, "observacion"].drop_duplicates().head(8).tolist()
        analisis, fuente = None, "playbook"
        if llm is not None:
            analisis = llm.suggest_rca(r["categoria"], r["obra"], ejemplos)
            if analisis:
                fuente = "llm"
        if not analisis:
            analisis = PLAYBOOK.get(r["categoria"], PLAYBOOK["OTROS"])
        results.append(
            {
                "categoria": r["categoria"],
                "categoria_nombre": CATEGORIES.get(r["categoria"], r["categoria"]),
                "obra": r["obra"],
                "desvios": int(r["desvios"]),
                "valor_perdido": round(float(r["valor"]), 0),
                "hh_perdidas": round(float(r["hh"]), 1),
                "ejemplos": ejemplos[:3],
                "porques": analisis["porques"],
                "acciones": analisis["acciones"],
                "fuente": fuente,
            }
        )
    return results

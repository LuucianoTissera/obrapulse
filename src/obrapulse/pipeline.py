"""Pipeline end-to-end: ingesta -> validación -> KPIs -> clasificación IA de causas ->
anomalías -> causa raíz -> persistencia -> reporte. Un solo comando, sin intervención."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import kpis, storage
from .anomalies import detect_ppc_drops
from .classifier.llm import LLMClassifier
from .classifier.service import ClassificationService
from .config import Settings
from .ingestion import load_partes
from .rca import analyze_top_problems
from .reporting import chart_curva_s, chart_pareto, chart_ppc, render_report
from .taxonomy import CATEGORIES

log = logging.getLogger(__name__)


def classify_desvios(service: ClassificationService, desvios):
    """Clasifica los desvíos. Los que no tienen texto NO se mandan a la IA: son SIN_CAUSA."""
    d = desvios.copy()
    d["descripcion"] = d["observacion"]
    has_text = d["descripcion"].str.strip() != ""
    classified = service.classify_dataframe(d[has_text]) if has_text.any() else d[has_text]
    sin = d[~has_text].copy()
    sin["categoria"] = "SIN_CAUSA"
    sin["confianza"] = 1.0
    sin["metodo"] = "regla"
    sin["justificacion"] = "Desvío sin observación en el parte"
    sin["requiere_revision"] = True
    out = pd.concat([classified, sin]).sort_values("registro_id").reset_index(drop=True)
    return out


def run_pipeline(
    settings: Settings,
    partes_csv: str | Path | None = None,
    service: ClassificationService | None = None,
    llm: LLMClassifier | None = None,
) -> dict:
    t0 = time.perf_counter()
    partes_csv = Path(partes_csv or settings.data_dir / "partes_diarios.csv")

    # 1. Ingesta + validación (con cuarentena)
    partes, rechazados = load_partes(partes_csv)
    if partes.empty:
        raise ValueError("No hay partes válidos para procesar")

    # 2. KPIs base
    partes = kpis.enrich(partes)
    desvios = partes[~partes["cumplida"]]

    # 3. Clasificación con IA (híbrida, con fallbacks) de las causas de los desvíos
    service = service or ClassificationService(settings, llm=llm)
    desvios = classify_desvios(service, desvios)
    partes = partes.merge(desvios[["registro_id", "categoria"]], on="registro_id", how="left")

    total = kpis.totales(partes)
    por_obra = kpis.resumen_obras(partes)
    par = kpis.pareto(desvios)
    prod = kpis.productividad(partes)
    ppc_sem = kpis.ppc(partes, by=["semana", "obra"])
    ppc_tot = kpis.ppc(partes, by=["semana"])
    curva = kpis.curva_s(partes)

    # 4. Anomalías y causa raíz
    anomalias = detect_ppc_drops(partes, desvios)
    rca = analyze_top_problems(desvios, llm=service.llm, top_n=3)

    # 5. Persistencia
    metodos = desvios["metodo"].value_counts().to_dict()
    summary = {
        "ejecutado": datetime.now().isoformat(timespec="seconds"),
        "partes_validos": len(partes),
        "partes_rechazados": len(rechazados),
        "ppc": round(total["ppc"], 4),
        "spi": round(total["spi"], 4),
        "valor_perdido": round(total["valor_perdido"], 0),
        "hh_perdidas": round(total["hh_perdidas"], 1),
        "desvios": total["desvios"],
        "desvios_sin_causa": total["desvios_sin_causa"],
        "llm_calls": service.llm_calls,
        "a_revision": int(desvios["requiere_revision"].sum()),
        "anomalias": len(anomalias),
    }
    storage.save_run(settings.db_path, partes, desvios, rechazados, summary)

    # 6. Reporte
    par_view = par.assign(nombre=par["categoria"].map(CATEGORIES))
    context = {
        "periodo": {"desde": partes["fecha"].min(), "hasta": partes["fecha"].max()},
        "kpi": total,
        "obras": por_obra.to_dict("records"),
        "pareto": par_view.to_dict("records"),
        "productividad": prod.head(8).to_dict("records"),
        "anomalias": anomalias.to_dict("records"),
        "rca": rca,
        "chart_pareto": chart_pareto(par),
        "chart_ppc": chart_ppc(ppc_sem, ppc_tot),
        "chart_curva_s": chart_curva_s(curva),
        "calidad_datos": {
            "partes_validos": len(partes),
            "partes_rechazados": len(rechazados),
            "desvios": total["desvios"],
            "sin_causa": total["desvios_sin_causa"],
            "metodos": metodos,
            "llm_calls": service.llm_calls,
            "a_revision": summary["a_revision"],
            "umbral": settings.confidence_threshold,
        },
    }
    report = render_report(context, settings.reports_dir / "reporte_latest.html")
    (settings.reports_dir / "resumen_latest.json").write_text(
        json.dumps({**summary, "metodos": metodos}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("pipeline OK en %.1fs -> %s", time.perf_counter() - t0, report)
    return {**summary, "metodos": metodos, "reporte": str(report)}

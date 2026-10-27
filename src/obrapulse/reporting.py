"""Generación del reporte HTML autocontenido (gráficos embebidos en base64)."""

from __future__ import annotations

import base64
import io
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: E402

from .taxonomy import CATEGORIES  # noqa: E402

TEMPLATES_DIR = Path(__file__).parent / "templates"
PALETTE = ["#1f6feb", "#12b76a", "#f79009", "#7a5af8", "#d92d20"]
PPC_TARGET = 0.80  # objetivo de referencia habitual en Last Planner


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def chart_pareto(par: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9, 3.8))
    labels = [CATEGORIES.get(c, c) for c in par["categoria"]]
    ax.bar(range(len(par)), par["valor_perdido"] / 1e6, color="#1f6feb")
    ax.set_xticks(range(len(par)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Valor no ejecutado (millones $)")
    ax2 = ax.twinx()
    ax2.plot(range(len(par)), par["pct_acum"], color="#d92d20", marker="o")
    ax2.axhline(80, color="#98a2b3", linestyle="--", linewidth=0.8)
    ax2.set_ylim(0, 105)
    ax2.set_ylabel("% acumulado")
    ax.set_title("Pareto de causas de no cumplimiento")
    return _fig_to_b64(fig)


def chart_ppc(ppc_sem: pd.DataFrame, ppc_tot: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9, 3.6))
    for i, (obra, g) in enumerate(ppc_sem.groupby("obra")):
        g = g.sort_values("semana")
        ax.plot(
            pd.to_datetime(g["semana"]),
            g["ppc"] * 100,
            label=obra,
            color=PALETTE[i % len(PALETTE)],
            alpha=0.65,
            linewidth=1.4,
        )
    t = ppc_tot.sort_values("semana")
    ax.plot(
        pd.to_datetime(t["semana"]), t["ppc"] * 100, label="Total", color="black", linewidth=2.4
    )
    ax.axhline(PPC_TARGET * 100, color="#98a2b3", linestyle="--", linewidth=0.8)
    ax.text(
        pd.to_datetime(t["semana"]).iloc[-1],
        PPC_TARGET * 100 + 1,
        "objetivo de referencia 80%",
        fontsize=7,
        color="#667085",
        ha="right",
    )
    ax.set_ylabel("PPC (%)")
    ax.set_ylim(0, 100)
    ax.legend(fontsize=8, ncol=5, loc="lower left")
    ax.set_title("PPC semanal (Percent Plan Complete)")
    fig.autofmt_xdate()
    return _fig_to_b64(fig)


def chart_curva_s(curva: pd.DataFrame) -> str:
    obras = sorted(curva["obra"].unique())
    cols = 2
    rows = (len(obras) + 1) // 2
    fig, axes = plt.subplots(rows, cols, figsize=(9, 2.9 * rows), squeeze=False)
    for ax, obra in zip(axes.flat, obras, strict=False):
        g = curva[curva["obra"] == obra]
        x = pd.to_datetime(g["fecha"])
        ax.plot(x, g["pv_acum"] / 1e6, "--", color="#98a2b3", label="Planificado")
        ax.plot(x, g["ev_acum"] / 1e6, color="#1f6feb", linewidth=2, label="Ejecutado")
        ax.set_title(obra, fontsize=9)
        ax.tick_params(labelsize=7)
        ax.set_ylabel("millones $", fontsize=7)
    for ax in list(axes.flat)[len(obras) :]:
        ax.axis("off")
    axes.flat[0].legend(fontsize=7, loc="upper left")
    fig.suptitle("Curvas S: avance en valor acumulado", fontsize=10)
    fig.autofmt_xdate()
    return _fig_to_b64(fig)


def render_report(context: dict, out_path: str | Path) -> Path:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "j2"]),
    )
    html = env.get_template("report.html.j2").render(
        generado=datetime.now().strftime("%Y-%m-%d %H:%M"), **context
    )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out

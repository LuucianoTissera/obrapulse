"""Indicadores de gestión de obra.

- PPC (Percent Plan Complete, Lean Construction / Last Planner): % de actividades planificadas
  que se cumplieron. Es el indicador de confiabilidad de la planificación.
- Avance en valor (EV vs PV) y SPI = EV / PV (>1 adelantado, <1 atrasado), curva S.
- Pareto de causas de no cumplimiento (CNC) por valor no ejecutado y horas-hombre perdidas.
- Productividad por actividad (unidades por hora-hombre).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

COMPLETION_TOLERANCE = 0.95  # una tarea se considera "cumplida" si ejecuta >= 95% de lo planificado


def enrich(partes: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas derivadas. Devuelve una copia."""
    df = partes.copy()
    plan = df["cantidad_planificada"]
    ejec = df["cantidad_ejecutada"]
    fecha = pd.to_datetime(df["fecha"])
    df["semana"] = (fecha - pd.to_timedelta(fecha.dt.weekday, unit="D")).dt.strftime("%Y-%m-%d")
    df["cumplida"] = ejec >= plan * COMPLETION_TOLERANCE
    df["valor_plan"] = plan * df["precio_unitario"]
    df["valor_ejec"] = ejec * df["precio_unitario"]
    # Solo los DESVÍOS (tareas no cumplidas) cuentan como pérdida: así el total del KPI
    # coincide exactamente con la suma del Pareto.
    df["valor_perdido"] = ((plan - ejec).clip(lower=0) * df["precio_unitario"]).where(
        ~df["cumplida"], 0.0
    )
    df["hh_perdidas"] = (df["horas_hombre"] * (1 - ejec / plan).clip(lower=0, upper=1)).where(
        ~df["cumplida"], 0.0
    )
    return df


def _ratio(a: float, b: float) -> float:
    return float(a / b) if b else 0.0


def ppc(df: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    """PPC = tareas cumplidas / tareas planificadas."""
    work = df.assign(_c=df["cumplida"].astype(int), _n=1)
    if by:
        g = work.groupby(by, as_index=False)
    else:
        g = work.assign(_all="total").groupby("_all", as_index=False)
    out = g.agg(planificadas=("_n", "sum"), cumplidas=("_c", "sum"))
    out["ppc"] = np.where(out["planificadas"] > 0, out["cumplidas"] / out["planificadas"], 0.0)
    return out.drop(columns=["_all"], errors="ignore")


def curva_s(df: pd.DataFrame) -> pd.DataFrame:
    """Valor planificado (PV) y ejecutado (EV) acumulados por obra y fecha."""
    daily = (
        df.groupby(["obra", "fecha"], as_index=False)
        .agg(pv=("valor_plan", "sum"), ev=("valor_ejec", "sum"))
        .sort_values(["obra", "fecha"])
    )
    daily["pv_acum"] = daily.groupby("obra")["pv"].cumsum()
    daily["ev_acum"] = daily.groupby("obra")["ev"].cumsum()
    return daily


def resumen_obras(df: pd.DataFrame) -> pd.DataFrame:
    """Tabla resumen por obra: PPC, SPI, valor y horas-hombre perdidas."""
    g = df.groupby("obra", as_index=False).agg(
        tareas=("registro_id", "count"),
        cumplidas=("cumplida", "sum"),
        pv=("valor_plan", "sum"),
        ev=("valor_ejec", "sum"),
        valor_perdido=("valor_perdido", "sum"),
        hh_perdidas=("hh_perdidas", "sum"),
        hh_totales=("horas_hombre", "sum"),
    )
    g["ppc"] = g["cumplidas"] / g["tareas"]
    g["spi"] = g["ev"] / g["pv"]
    g["pct_hh_perdidas"] = g["hh_perdidas"] / g["hh_totales"]
    return g.drop(columns=["cumplidas"])


def totales(df: pd.DataFrame) -> dict:
    pv, ev = float(df["valor_plan"].sum()), float(df["valor_ejec"].sum())
    desv = df[~df["cumplida"]]
    sin_causa = int((desv["categoria"] == "SIN_CAUSA").sum()) if "categoria" in desv else 0
    return {
        "tareas": int(len(df)),
        "ppc": _ratio(df["cumplida"].sum(), len(df)),
        "spi": _ratio(ev, pv),
        "valor_perdido": float(df["valor_perdido"].sum()),
        "hh_perdidas": float(df["hh_perdidas"].sum()),
        "desvios": int(len(desv)),
        "desvios_sin_causa": sin_causa,
    }


def pareto(desvios: pd.DataFrame, by: str = "categoria") -> pd.DataFrame:
    """Pareto del valor no ejecutado por causa (u otra dimensión)."""
    p = (
        desvios.groupby(by)
        .agg(
            desvios=("registro_id", "count"),
            valor_perdido=("valor_perdido", "sum"),
            hh_perdidas=("hh_perdidas", "sum"),
        )
        .sort_values("valor_perdido", ascending=False)
        .reset_index()
    )
    total = p["valor_perdido"].sum()
    if total:
        pct = p["valor_perdido"] / total * 100
        p["pct_acum"] = pct.cumsum().round(2)
        p["pct"] = pct.round(2)
    else:
        p["pct"] = 0.0
        p["pct_acum"] = 0.0
    p["valor_perdido"] = p["valor_perdido"].round(0)
    p["hh_perdidas"] = p["hh_perdidas"].round(1)
    return p


def productividad(df: pd.DataFrame) -> pd.DataFrame:
    """Unidades ejecutadas por hora-hombre y % de cumplimiento, por obra y actividad."""
    g = df.groupby(["obra", "actividad", "unidad"], as_index=False).agg(
        ejecutado=("cantidad_ejecutada", "sum"),
        planificado=("cantidad_planificada", "sum"),
        hh=("horas_hombre", "sum"),
    )
    g["u_por_hh"] = (g["ejecutado"] / g["hh"]).round(3)
    g["cumplimiento"] = (g["ejecutado"] / g["planificado"]).round(3)
    return g.drop(columns=["ejecutado", "planificado", "hh"]).sort_values("cumplimiento")

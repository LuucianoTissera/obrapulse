"""Ingesta y validación de partes diarios. Las filas inválidas NO se descartan en silencio:
van a una tabla de cuarentena con el motivo, para que el área pueda corregirlas."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

REQUIRED = [
    "registro_id",
    "fecha",
    "obra",
    "actividad",
    "unidad",
    "cantidad_planificada",
    "cantidad_ejecutada",
    "horas_hombre",
    "precio_unitario",
]
NUMERIC = ["cantidad_planificada", "cantidad_ejecutada", "horas_hombre", "precio_unitario"]
MAX_OVERRUN = 10.0  # ejecutado > 10x lo planificado se considera error de carga


def validate_partes(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (válidos, rechazados). Rechazados incluye la columna `motivo`."""
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"partes_diarios: faltan columnas obligatorias {missing}")
    df = df.copy()
    if "observacion" not in df.columns:
        df["observacion"] = ""
    df["observacion"] = df["observacion"].fillna("").astype(str).str.strip()
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.strftime("%Y-%m-%d")
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    reasons = pd.Series("", index=df.index, dtype="object")

    def flag(mask: pd.Series, msg: str) -> None:
        nonlocal reasons
        mask = mask.fillna(False).astype(bool)
        reasons = reasons.where(~mask | (reasons != ""), msg)

    flag(df["fecha"].isna(), "fecha inválida")
    flag(df[NUMERIC].isna().any(axis=1), "valor numérico faltante o inválido")
    flag(df["cantidad_planificada"] <= 0, "cantidad planificada <= 0")
    flag(df["cantidad_ejecutada"] < 0, "cantidad ejecutada negativa")
    flag(df["horas_hombre"] < 0, "horas hombre negativas")
    flag(df["precio_unitario"] < 0, "precio unitario negativo")
    flag(
        df["cantidad_ejecutada"] > df["cantidad_planificada"] * MAX_OVERRUN,
        "ejecutado implausible (>10x lo planificado)",
    )
    flag(df["obra"].isna() | df["actividad"].isna(), "obra o actividad vacía")
    flag(df.duplicated("registro_id", keep="first"), "registro_id duplicado")

    bad = reasons != ""
    rejected = df[bad].assign(motivo=reasons[bad]).reset_index(drop=True)
    clean = df[~bad].reset_index(drop=True)
    log.info("partes válidos=%d rechazados=%d", len(clean), len(rejected))
    return clean, rejected


def load_partes(path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    return validate_partes(pd.read_csv(path))

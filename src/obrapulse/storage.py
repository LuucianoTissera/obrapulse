"""Persistencia en SQLite (sin servidor, ideal para el alcance). Reemplazable por
PostgreSQL cambiando solo esta capa."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd


@contextmanager
def connect(db_path: str | Path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_run(
    db_path: str | Path,
    partes: pd.DataFrame,
    desvios: pd.DataFrame,
    rechazados: pd.DataFrame,
    summary: dict,
) -> None:
    with connect(db_path) as conn:
        partes.to_sql("partes", conn, if_exists="replace", index=False)
        desvios.to_sql("desvios", conn, if_exists="replace", index=False)
        rechazados.to_sql("cuarentena_partes", conn, if_exists="replace", index=False)
        pd.DataFrame([summary]).to_sql("corridas", conn, if_exists="append", index=False)


def table_exists(db_path: str | Path, table: str) -> bool:
    if not Path(db_path).exists():
        return False
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
    return row is not None


def read_table(db_path: str | Path, table: str) -> pd.DataFrame:
    with connect(db_path) as conn:
        return pd.read_sql_query(f"SELECT * FROM {table}", conn)  # noqa: S608 - nombre fijo interno

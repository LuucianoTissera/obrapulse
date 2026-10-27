import pandas as pd
import pytest

from obrapulse.ingestion import validate_partes


def _row(**over):
    base = {
        "registro_id": "P1",
        "fecha": "2026-09-01",
        "obra": "VIAL-01",
        "actividad": "Base granular",
        "unidad": "m3",
        "cantidad_planificada": 100,
        "cantidad_ejecutada": 80,
        "horas_hombre": 64,
        "precio_unitario": 9500,
        "observacion": "no llegó el hormigón",
    }
    return {**base, **over}


def test_valid_row_passes():
    clean, rej = validate_partes(pd.DataFrame([_row()]))
    assert len(clean) == 1 and rej.empty


def test_missing_observation_column_is_created():
    row = _row()
    row.pop("observacion")
    clean, _ = validate_partes(pd.DataFrame([row]))
    assert clean.loc[0, "observacion"] == ""


@pytest.mark.parametrize(
    "override,reason",
    [
        ({"fecha": "no-es-fecha"}, "fecha inválida"),
        ({"cantidad_planificada": 0}, "cantidad planificada <= 0"),
        ({"cantidad_ejecutada": -5}, "negativa"),
        ({"horas_hombre": -1}, "horas hombre negativas"),
        ({"precio_unitario": "abc"}, "valor numérico faltante"),
        ({"cantidad_ejecutada": 5000}, "implausible"),
    ],
)
def test_invalid_rows_go_to_quarantine_with_reason(override, reason):
    clean, rej = validate_partes(pd.DataFrame([_row(**override)]))
    assert clean.empty and len(rej) == 1
    assert reason in rej.loc[0, "motivo"]


def test_duplicate_ids_rejected():
    clean, rej = validate_partes(pd.DataFrame([_row(), _row()]))
    assert len(clean) == 1 and rej.loc[0, "motivo"] == "registro_id duplicado"


def test_missing_columns_raise():
    with pytest.raises(ValueError, match="faltan columnas"):
        validate_partes(pd.DataFrame([{"registro_id": "P1"}]))

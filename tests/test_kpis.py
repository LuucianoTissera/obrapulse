import pandas as pd
import pytest

from obrapulse import kpis


def _partes():
    rows = [
        # cumplida (100%)
        ("A", "2026-09-01", "O1", "Act1", "m3", 100, 100, 80, 10, "", None),
        # desvío al 50%
        ("B", "2026-09-01", "O1", "Act2", "m3", 100, 50, 80, 20, "lluvia", "CLIMA"),
        # cumplida justo en la tolerancia del 95%
        ("C", "2026-09-02", "O2", "Act1", "m3", 200, 190, 160, 10, "", None),
        # desvío total
        ("D", "2026-09-02", "O2", "Act3", "m3", 10, 0, 40, 100, "sin material", "MATERIALES"),
    ]
    cols = [
        "registro_id",
        "fecha",
        "obra",
        "actividad",
        "unidad",
        "cantidad_planificada",
        "cantidad_ejecutada",
        "horas_hombre",
        "precio_unitario",
        "observacion",
        "categoria",
    ]
    return kpis.enrich(pd.DataFrame(rows, columns=cols))


def test_enrich_values_calculated_by_hand():
    df = _partes().set_index("registro_id")
    assert bool(df.loc["A", "cumplida"]) and bool(df.loc["C", "cumplida"])  # 95% cuenta
    assert not df.loc["B", "cumplida"] and not df.loc["D", "cumplida"]
    assert df.loc["B", "valor_perdido"] == 50 * 20
    assert df.loc["B", "hh_perdidas"] == pytest.approx(80 * 0.5)
    assert df.loc["D", "hh_perdidas"] == pytest.approx(40)  # ejecutó 0 -> pierde todas
    assert df.loc["A", "valor_perdido"] == 0
    assert df.loc["A", "semana"] == "2026-08-31"  # lunes de esa semana


def test_ppc_global_and_by_obra():
    df = _partes()
    assert kpis.ppc(df).iloc[0]["ppc"] == pytest.approx(0.5)
    by = kpis.ppc(df, by=["obra"]).set_index("obra")
    assert by.loc["O1", "ppc"] == pytest.approx(0.5) and by.loc["O2", "ppc"] == pytest.approx(0.5)


def test_totals_and_spi():
    t = kpis.totales(_partes())
    pv = 100 * 10 + 100 * 20 + 200 * 10 + 10 * 100
    ev = 100 * 10 + 50 * 20 + 190 * 10 + 0
    assert t["spi"] == pytest.approx(ev / pv)
    assert t["valor_perdido"] == pytest.approx(50 * 20 + 10 * 100 + 10 * 200 * 0)
    assert t["desvios"] == 2


def test_pareto_sorted_and_sums_to_100():
    df = _partes()
    p = kpis.pareto(df[~df["cumplida"]])
    assert set(p["categoria"]) == {"CLIMA", "MATERIALES"}
    assert p["valor_perdido"].is_monotonic_decreasing
    assert p["pct_acum"].iloc[-1] == pytest.approx(100.0)


def test_curva_s_is_cumulative_and_monotonic():
    c = kpis.curva_s(_partes())
    o1 = c[c["obra"] == "O1"]
    assert o1["pv_acum"].is_monotonic_increasing
    assert o1["pv_acum"].iloc[-1] == pytest.approx(100 * 10 + 100 * 20)


def test_productividad_units_per_hh():
    p = kpis.productividad(_partes()).set_index("actividad")
    assert p.loc["Act2", "u_por_hh"] == pytest.approx(50 / 80, abs=1e-3)
    assert p.loc["Act2", "cumplimiento"] == pytest.approx(0.5)


def test_total_loss_matches_pareto_sum():
    df = _partes()
    assert kpis.totales(df)["valor_perdido"] == pytest.approx(
        kpis.pareto(df[~df["cumplida"]])["valor_perdido"].sum()
    )

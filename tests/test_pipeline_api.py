import json

import pandas as pd
from fastapi.testclient import TestClient

from obrapulse.api import create_app
from obrapulse.classifier import ClassificationService
from obrapulse.classifier.ml import MLClassifier
from obrapulse.pipeline import run_pipeline

from .conftest import FakeLLM


def _train(settings):
    hist = pd.read_csv(settings.data_dir / "historico_etiquetado.csv")
    model, metrics = MLClassifier.train(hist)
    model.save(settings.model_path, metrics)
    return model


def test_pipeline_end_to_end(settings):
    _train(settings)
    res = run_pipeline(settings)
    assert 0 < res["ppc"] < 1 and res["partes_validos"] > 300
    assert res["desvios_sin_causa"] > 0  # el generador deja desvíos sin observación
    html = (settings.reports_dir / "reporte_latest.html").read_text(encoding="utf-8")
    assert "PPC" in html and html.count("data:image/png;base64") == 3
    summary = json.loads((settings.reports_dir / "resumen_latest.json").read_text(encoding="utf-8"))
    assert summary["partes_validos"] == res["partes_validos"]


def test_sin_causa_never_reaches_the_classifier(settings):
    model = _train(settings)
    llm = FakeLLM()
    svc = ClassificationService(settings, ml=model, llm=llm)
    run_pipeline(settings, service=svc)
    from obrapulse import storage

    d = storage.read_table(settings.db_path, "desvios")
    sc = d[d["categoria"] == "SIN_CAUSA"]
    assert len(sc) > 0 and (sc["metodo"] == "regla").all() and (sc["observacion"] == "").all()


def test_pipeline_quarantines_bad_rows(settings, tmp_path):
    _train(settings)
    p = pd.read_csv(settings.data_dir / "partes_diarios.csv")
    p.loc[0, "cantidad_planificada"] = 0
    bad = tmp_path / "partes_malos.csv"
    p.to_csv(bad, index=False)
    assert run_pipeline(settings, partes_csv=bad)["partes_rechazados"] == 1


def test_pipeline_uses_llm_for_rca_when_available(settings):
    model = _train(settings)
    svc = ClassificationService(settings, ml=model, llm=FakeLLM())
    run_pipeline(settings, service=svc)
    html = (settings.reports_dir / "reporte_latest.html").read_text(encoding="utf-8")
    assert "fuente: llm" in html


def test_pipeline_detects_injected_anomaly_exactly(settings):
    """Verifica la obra Y la causa inyectadas (no solo 'alguna anomalía')."""
    _train(settings)
    run_pipeline(settings)
    from obrapulse import storage
    from obrapulse.anomalies import detect_ppc_drops

    p = storage.read_table(settings.db_path, "partes")
    p["cumplida"] = p["cumplida"].astype(bool)
    d = storage.read_table(settings.db_path, "desvios")
    out = detect_ppc_drops(p, d)
    assert list(out["obra"]) == ["VIV-02"]
    assert out.iloc[0]["causa_dominante"] == "MATERIALES"
    html = (settings.reports_dir / "reporte_latest.html").read_text(encoding="utf-8")
    assert "caída anómala del PPC" in html


def test_api_flow(settings):
    model = _train(settings)
    run_pipeline(settings)
    client = TestClient(create_app(settings, ClassificationService(settings, ml=model)))
    assert client.get("/health").json()["datos_cargados"] is True
    r = client.post("/classify", json={"descripcion": "se rompió la retroexcavadora"})
    assert r.status_code == 200 and r.json()["categoria"] == "EQUIPOS"
    assert client.post("/classify", json={"descripcion": "x"}).status_code == 422
    assert 0 < client.get("/kpis").json()["ppc"] < 1
    assert client.get("/kpis?obra=NOEXISTE").status_code == 404
    assert len(client.get("/obras").json()) == 4
    detalle = client.get("/datos?limite=10").json()
    assert len(detalle) == 10
    assert {"fecha", "obra", "cumplida", "valor_plan", "valor_ejec"}.issubset(detalle[0])
    filtrados = client.get("/datos?obra=VIAL-01&fecha_desde=2026-08-01&limite=10")
    assert filtrados.status_code == 200
    assert all(row["obra"] == "VIAL-01" for row in filtrados.json())
    curva = client.get("/curva-s").json()
    assert len(curva) > 0 and {"pv_acum", "ev_acum"}.issubset(curva[0])
    calidad = client.get("/calidad-datos").json()
    assert calidad["partes_validos"] > 0 and "partes_rechazados" in calidad
    assert client.get("/pareto?por=obra").status_code == 200
    assert client.get("/pareto?por=DROP").status_code == 422
    assert client.get("/anomalies").status_code == 200
    assert client.get("/report").headers["content-type"].startswith("text/html")


def test_api_requires_key_when_configured(settings):
    s = settings.__class__(**{**settings.__dict__, "api_key": "secreta"})
    client = TestClient(create_app(s, ClassificationService(s, ml=None)))
    assert client.get("/health").status_code == 200
    assert client.get("/kpis").status_code == 401
    assert client.get("/kpis", headers={"X-API-Key": "mala"}).status_code == 401
    assert client.get("/kpis", headers={"X-API-Key": "secreta"}).status_code == 409


def test_api_without_data_returns_409(settings):
    client = TestClient(create_app(settings, ClassificationService(settings, ml=None)))
    assert client.get("/kpis").status_code == 409

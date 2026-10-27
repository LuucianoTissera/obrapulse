import pandas as pd
import pytest

from obrapulse.classifier import ClassificationService
from obrapulse.classifier.llm import LLMClassifier, _extract_json
from obrapulse.classifier.ml import MLClassifier
from obrapulse.classifier.rules import classify_rules
from obrapulse.generator import generate

from .conftest import FakeLLM


@pytest.fixture(scope="module")
def trained():
    h = generate(start="2025-03-03", days=300, seed=7, anomaly=False)
    h = h[(h["causa_real"] != "") & (h["observacion"] != "")]
    h = h.rename(columns={"observacion": "descripcion", "causa_real": "categoria"})
    return MLClassifier.train(h)


def _df(*texts):
    return pd.DataFrame(
        {
            "descripcion": list(texts),
            "actividad": ["Base granular"] * len(texts),
            "obra": ["VIAL-01"] * len(texts),
        }
    )


def test_rules_basic():
    assert classify_rules("no llegó el hormigón, demora del proveedor")[0] == "MATERIALES"
    assert classify_rules("LLOVIÓ TODA LA MAÑANA, terreno saturado")[0] == "CLIMA"
    assert classify_rules("se rompió la retroexcavadora")[0] == "EQUIPOS"
    cat, conf, _ = classify_rules("asdf qwerty")
    assert cat == "OTROS" and conf < 0.5


def test_ml_accuracy_is_good_but_not_perfect(trained):
    _, metrics = trained
    assert 0.80 < metrics["accuracy"] < 0.99  # textos ambiguos impiden el 100%


def test_ml_save_and_load_roundtrip(trained, tmp_path):
    model, metrics = trained
    model.save(tmp_path / "m.joblib", metrics)
    loaded = MLClassifier.load(tmp_path / "m.joblib")
    t = ["se rompió la retroexcavadora"]
    assert loaded.predict(t) == model.predict(t)
    assert MLClassifier.load(tmp_path / "no-existe.joblib") is None


def test_hybrid_escalates_only_low_confidence_to_llm(settings, trained):
    model, _ = trained
    llm = FakeLLM(categoria="PROYECTO", confianza=0.9)
    svc = ClassificationService(settings, ml=model, llm=llm)
    out = svc.classify_dataframe(_df("lluvia, no se pudo trabajar", "problemas varios"))
    assert out.loc[0, "metodo"] == "ml"  # claro: no gasta LLM
    assert out.loc[1, "metodo"] == "llm"  # ambiguo: escala
    assert llm.calls == 1


def test_llm_failure_degrades_to_ml_and_flags_review(settings, trained):
    model, _ = trained
    svc = ClassificationService(settings, ml=model, llm=FakeLLM(fail=True))
    out = svc.classify_dataframe(_df("problemas varios"))
    assert out.loc[0, "metodo"] == "ml" and bool(out.loc[0, "requiere_revision"]) is True


def test_llm_call_budget_is_respected(settings, trained):
    model, _ = trained
    s = settings.__class__(**{**settings.__dict__, "llm_max_calls": 1})
    llm = FakeLLM()
    svc = ClassificationService(s, ml=model, llm=llm)
    svc.classify_dataframe(_df("problemas varios", "demoras en obra", "pendiente de resolver"))
    assert llm.calls == 1


def test_no_model_and_no_llm_falls_back_to_rules(settings):
    svc = ClassificationService(settings, ml=None, llm=None)
    svc.ml = None
    assert svc.classify_one("viento fuerte, se suspendió").metodo == "reglas"


def test_llm_output_is_validated_against_taxonomy():
    class Bad:
        class messages:  # noqa: N801
            @staticmethod
            def create(**kw):
                class R:
                    content = [
                        type("B", (), {"type": "text", "text": '{"categoria": "INVENTADA"}'})()
                    ]

                return R()

    assert LLMClassifier(client=Bad()).classify("algo") is None


def test_llm_cannot_predict_sin_causa():
    class Sneaky:
        class messages:  # noqa: N801
            @staticmethod
            def create(**kw):
                class R:
                    content = [
                        type(
                            "B",
                            (),
                            {"type": "text", "text": '{"categoria": "SIN_CAUSA", "confianza": 1}'},
                        )()
                    ]

                return R()

    assert LLMClassifier(client=Sneaky()).classify("algo") is None


def test_extract_json_tolerates_surrounding_text():
    assert _extract_json('ok: {"a": 1} fin') == {"a": 1}
    assert _extract_json("sin json") is None

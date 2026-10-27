from pathlib import Path

import pytest

from obrapulse.config import Settings
from obrapulse.generator import write_sample_data


@pytest.fixture(scope="session")
def sample_dir(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("sample")
    write_sample_data(str(d), days=56)
    return d


@pytest.fixture()
def settings(tmp_path, sample_dir) -> Settings:
    return Settings(
        data_dir=sample_dir,
        db_path=tmp_path / "db" / "op.db",
        model_path=tmp_path / "model.joblib",
        reports_dir=tmp_path / "reports",
        anthropic_api_key=None,
        anthropic_model="test-model",
        classifier_mode="hybrid",
        confidence_threshold=0.70,
        llm_max_calls=50,
        api_key=None,
        log_level="WARNING",
    )


class FakeLLM:
    """Doble de LLMClassifier: sin red, determinista, cuenta llamadas."""

    def __init__(self, categoria="MATERIALES", confianza=0.95, fail=False):
        self.categoria, self.confianza, self.fail, self.calls = categoria, confianza, fail, 0

    def classify(self, descripcion, actividad="", obra=""):
        self.calls += 1
        if self.fail:
            return None
        return {"categoria": self.categoria, "confianza": self.confianza, "justificacion": "fake"}

    def suggest_rca(self, categoria, obra, ejemplos):
        if self.fail:
            return None
        return {"porques": ["p1", "p2", "p3", "p4", "p5"], "acciones": ["a1", "a2", "a3"]}

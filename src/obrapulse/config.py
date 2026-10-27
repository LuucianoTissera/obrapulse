"""Configuración centralizada, 100% por variables de entorno (12-factor)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

VALID_MODES = ("hybrid", "ml", "llm", "rules")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    model_path: Path
    reports_dir: Path
    anthropic_api_key: str | None
    anthropic_model: str
    classifier_mode: str
    confidence_threshold: float
    llm_max_calls: int
    api_key: str | None
    log_level: str

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @classmethod
    def from_env(cls) -> Settings:
        mode = os.getenv("CLASSIFIER_MODE", "hybrid").strip().lower()
        if mode not in VALID_MODES:
            raise ValueError(f"CLASSIFIER_MODE inválido: {mode!r}. Opciones: {VALID_MODES}")
        threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))
        if not 0.0 < threshold <= 1.0:
            raise ValueError("CONFIDENCE_THRESHOLD debe estar en (0, 1]")
        return cls(
            data_dir=Path(os.getenv("OP_DATA_DIR", "data/sample")),
            db_path=Path(os.getenv("OP_DB_PATH", "data/runtime/obrapulse.db")),
            model_path=Path(os.getenv("OP_MODEL_PATH", "models/classifier.joblib")),
            reports_dir=Path(os.getenv("OP_REPORTS_DIR", "reports")),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
            classifier_mode=mode,
            confidence_threshold=threshold,
            llm_max_calls=int(os.getenv("LLM_MAX_CALLS", "200")),
            api_key=os.getenv("API_KEY") or None,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
    )

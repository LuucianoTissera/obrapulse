"""Orquestador de clasificación con degradación elegante.

Modo `hybrid` (recomendado):
  1) El modelo ML clasifica TODO (barato, instantáneo, local).
  2) Solo los casos de baja confianza se escalan al LLM (control de costo).
  3) Si aún así la confianza es baja -> `requiere_revision=True` (humano en el circuito).
Si falta el LLM o el modelo, el sistema sigue funcionando con lo que haya.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from ..config import Settings
from .llm import LLMClassifier
from .ml import MLClassifier
from .rules import classify_rules

log = logging.getLogger(__name__)


@dataclass
class Prediction:
    categoria: str
    confianza: float
    metodo: str  # ml | llm | reglas
    justificacion: str = ""
    requiere_revision: bool = False


class ClassificationService:
    def __init__(
        self,
        settings: Settings,
        ml: MLClassifier | None = None,
        llm: LLMClassifier | None = None,
    ):
        self.s = settings
        self.ml = ml if ml is not None else MLClassifier.load(settings.model_path)
        if llm is not None:
            self.llm = llm
        elif settings.llm_enabled and settings.classifier_mode in ("hybrid", "llm"):
            self.llm = LLMClassifier(settings.anthropic_api_key, settings.anthropic_model)
        else:
            self.llm = None
        self._llm_calls = 0
        self._cache: dict[str, Prediction | None] = {}

    # --- piezas -----------------------------------------------------------------
    def _rules(self, text: str) -> Prediction:
        cat, conf, why = classify_rules(text)
        return Prediction(cat, conf, "reglas", why)

    def _try_llm(self, text: str, actividad: str, obra: str) -> Prediction | None:
        if self.llm is None or self._llm_calls >= self.s.llm_max_calls:
            return None
        key = f"{text}|{actividad}"
        if key in self._cache:
            return self._cache[key]
        self._llm_calls += 1
        res = self.llm.classify(text, actividad, obra)
        pred = (
            Prediction(res["categoria"], res["confianza"], "llm", res["justificacion"])
            if res
            else None
        )
        self._cache[key] = pred
        return pred

    def _finalize(self, p: Prediction) -> Prediction:
        p.requiere_revision = p.confianza < self.s.confidence_threshold
        return p

    # --- API pública --------------------------------------------------------------
    def classify_one(self, text: str, actividad: str = "", obra: str = "") -> Prediction:
        mode = self.s.classifier_mode
        if mode == "rules":
            return self._finalize(self._rules(text))
        if mode == "llm":
            return self._finalize(self._try_llm(text, actividad, obra) or self._fallback(text))
        # ml / hybrid
        if self.ml is None:
            return self._finalize(self._try_llm(text, actividad, obra) or self._rules(text))
        cat, conf = self.ml.predict([text])[0]
        pred = Prediction(cat, conf, "ml")
        if mode == "hybrid" and conf < self.s.confidence_threshold:
            llm_pred = self._try_llm(text, actividad, obra)
            if llm_pred is not None:
                pred = llm_pred
        return self._finalize(pred)

    def _fallback(self, text: str) -> Prediction:
        if self.ml is not None:
            cat, conf = self.ml.predict([text])[0]
            return Prediction(cat, conf, "ml")
        return self._rules(text)

    def classify_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clasifica en lote. Vectoriza el ML y escala solo lo necesario al LLM."""
        out = df.copy()
        mode = self.s.classifier_mode
        preds: list[Prediction]
        if mode in ("ml", "hybrid") and self.ml is not None:
            base = self.ml.predict(out["descripcion"].tolist())
            preds = [Prediction(c, p, "ml") for c, p in base]
            if mode == "hybrid":
                for i, p in enumerate(preds):
                    if p.confianza < self.s.confidence_threshold:
                        row = out.iloc[i]
                        alt = self._try_llm(row["descripcion"], row["actividad"], row["obra"])
                        if alt is not None:
                            preds[i] = alt
            preds = [self._finalize(p) for p in preds]
        else:
            preds = [
                self.classify_one(r["descripcion"], r["actividad"], r["obra"])
                for _, r in out.iterrows()
            ]
        out["categoria"] = [p.categoria for p in preds]
        out["confianza"] = [round(p.confianza, 4) for p in preds]
        out["metodo"] = [p.metodo for p in preds]
        out["justificacion"] = [p.justificacion for p in preds]
        out["requiere_revision"] = [p.requiere_revision for p in preds]
        log.info(
            "clasificados=%d | llm_calls=%d | a revisión=%d",
            len(out),
            self._llm_calls,
            int(out["requiere_revision"].sum()),
        )
        return out

    @property
    def llm_calls(self) -> int:
        return self._llm_calls

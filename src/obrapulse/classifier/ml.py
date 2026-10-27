"""Clasificador ML clásico: TF-IDF + Regresión Logística.

Elegido a propósito sobre un modelo más complejo: es rápido, barato, explicable,
corre sin GPU ni internet y entrega probabilidades calibradas razonablemente."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .text import normalize

log = logging.getLogger(__name__)


def _build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    preprocessor=normalize,
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                    min_df=1,
                ),
            ),
            ("clf", LogisticRegression(max_iter=2000, C=8.0, class_weight="balanced")),
        ]
    )


class MLClassifier:
    def __init__(self, pipeline: Pipeline | None = None):
        self.pipeline = pipeline

    @classmethod
    def train(
        cls, df: pd.DataFrame, text_col: str = "descripcion", label_col: str = "categoria"
    ) -> tuple[MLClassifier, dict]:
        """Entrena con split estratificado y devuelve (modelo, métricas de test)."""
        X_tr, X_te, y_tr, y_te = train_test_split(
            df[text_col], df[label_col], test_size=0.2, random_state=42, stratify=df[label_col]
        )
        pipe = _build_pipeline().fit(X_tr, y_tr)
        report = classification_report(y_te, pipe.predict(X_te), output_dict=True, zero_division=0)
        metrics = {
            "accuracy": round(report["accuracy"], 4),
            "macro_f1": round(report["macro avg"]["f1-score"], 4),
            "n_train": len(X_tr),
            "n_test": len(X_te),
            "por_clase": {
                k: {m: round(v, 3) for m, v in vals.items()}
                for k, vals in report.items()
                if isinstance(vals, dict) and k not in ("macro avg", "weighted avg")
            },
        }
        # Re-entrena con TODO el histórico para el modelo final
        final = _build_pipeline().fit(df[text_col], df[label_col])
        log.info(
            "modelo entrenado: accuracy=%.3f macro_f1=%.3f",
            metrics["accuracy"],
            metrics["macro_f1"],
        )
        return cls(final), metrics

    def predict(self, texts: list[str]) -> list[tuple[str, float]]:
        if self.pipeline is None:
            raise RuntimeError("Modelo no cargado")
        proba = self.pipeline.predict_proba(texts)
        classes = self.pipeline.classes_
        out = []
        for row in proba:
            i = int(row.argmax())
            out.append((str(classes[i]), float(row[i])))
        return out

    def save(self, model_path: str | Path, metrics: dict | None = None) -> None:
        path = Path(model_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.pipeline, path)
        if metrics is not None:
            path.with_suffix(".metrics.json").write_text(
                json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    @classmethod
    def load(cls, model_path: str | Path) -> MLClassifier | None:
        path = Path(model_path)
        if not path.exists():
            return None
        return cls(joblib.load(path))

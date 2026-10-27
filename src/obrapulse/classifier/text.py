"""Normalización de texto compartida por todos los clasificadores."""

from __future__ import annotations

import re
import unicodedata


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text).lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9ñ\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

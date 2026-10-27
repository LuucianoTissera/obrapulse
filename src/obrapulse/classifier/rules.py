"""Clasificador por reglas (palabras clave). Es el último fallback: siempre disponible,
100% explicable y sin dependencias externas."""

from __future__ import annotations

from .text import normalize

KEYWORDS: dict[str, tuple[str, ...]] = {
    "CLIMA": (
        "lluvia",
        "llovi",
        "lloviz",
        "viento",
        "tormenta",
        "granizo",
        "calor extremo",
        "helada",
        "barro",
        "anegad",
        "saturad",
        "clima",
        "temporal",
        "pronostico",
    ),
    "MATERIALES": (
        "proveedor",
        "no llego el",
        "no llegaron",
        "sin asfalto",
        "sin cemento",
        "se termino el",
        "falta de material",
        "faltan ladrillos",
        "falta hierro",
        "demora en la entrega",
        "acopio",
        "reposicion",
        "no despacho",
    ),
    "EQUIPOS": (
        "retroexcavadora",
        "motoniveladora",
        "terminadora",
        "compactador",
        "mixer",
        "volcador",
        "grua",
        "averia",
        "falla hidraulica",
        "taller",
        "sin repuestos",
        "se rompio la",
        "equipo de",
    ),
    "MANO_OBRA": (
        "cuadrilla",
        "ausentismo",
        "poco personal",
        "sin gente",
        "falta de personal",
        "oficiales",
        "operarios",
        "ayudantes",
        "sin cobertura",
    ),
    "SUBCONTRATISTA": ("subcontrat", "contratista"),
    "PROYECTO": (
        "plano",
        "proyecto",
        "diseno",
        "definicion",
        "consulta a la inspeccion",
        "ingenieria",
        "detalle constructivo",
        "replantear",
        "orden de cambio",
        "incompatibilidad",
    ),
    "INTERFERENCIAS": (
        "interferencia",
        "servicios enterrados",
        "permiso",
        "municipal",
        "vecinos",
        "corte de calle",
        "cortar la calle",
        "poste",
        "transito",
        "caneria",
        "ocupacion",
        "terceros",
        "ente",
    ),
    "SEGURIDAD": (
        "seguridad",
        "epp",
        "andamio",
        "accidente",
        "trabajo en altura",
        "charla",
        "art observo",
        "condicion insegura",
        "apuntalamiento",
    ),
    "CALIDAD": (
        "ensayo",
        "retrabajo",
        "rehace",
        "rechazado",
        "no aprobado",
        "no conforme",
        "fuera de plomo",
        "asentamiento",
        "deficiencia",
        "defecto",
        "observo el armado",
    ),
}


def classify_rules(text: str) -> tuple[str, float, str]:
    """Devuelve (categoria, confianza, justificacion)."""
    t = normalize(text)
    scores = {cat: [k for k in kws if k in t] for cat, kws in KEYWORDS.items()}
    scores = {c: hits for c, hits in scores.items() if hits}
    if not scores:
        return "OTROS", 0.30, "Sin palabras clave reconocidas"
    best = max(scores, key=lambda c: len(scores[c]))
    conf = min(0.55 + 0.12 * len(scores[best]), 0.85)
    return best, conf, f"Palabras clave: {', '.join(scores[best])}"

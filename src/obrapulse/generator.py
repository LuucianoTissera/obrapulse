"""Generador de datos SINTÉTICOS de partes diarios de obra.

Simula lo que en una empresa constructora serían los partes diarios que cargan los capataces:
por cada actividad planificada del día, cuánto se planificó, cuánto se ejecutó y una
observación en texto libre (con ruido: sin tildes, mayúsculas, textos vagos). Incluye
lluvias que afectan a todas las obras el mismo día y una anomalía inyectada (crisis de
abastecimiento de materiales en una obra durante la última semana).
"""

from __future__ import annotations

import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# obra -> (nombre, [(actividad, unidad, cantidad_diaria, precio_unitario, tamaño_cuadrilla)])
OBRAS: dict[str, tuple[str, list[tuple[str, str, float, float, int]]]] = {
    "VIAL-01": (
        "Repavimentación y rotonda",
        [
            ("Fresado de carpeta", "m2", 900, 1800, 6),
            ("Base granular", "m3", 120, 9500, 8),
            ("Riego de liga", "m2", 1500, 450, 4),
            ("Carpeta asfáltica", "tn", 180, 52000, 10),
            ("Demarcación horizontal", "m", 800, 1300, 4),
        ],
    ),
    "VIV-02": (
        "Viviendas sociales (etapa 1)",
        [
            ("Excavación de fundaciones", "m3", 60, 6200, 6),
            ("Hormigón de fundaciones", "m3", 35, 98000, 8),
            ("Mampostería", "m2", 90, 14500, 10),
            ("Losa de cubierta", "m2", 70, 38000, 12),
            ("Instalación eléctrica", "boca", 45, 21000, 5),
            ("Revoque grueso", "m2", 110, 9800, 8),
        ],
    ),
    "ILU-03": (
        "Iluminación vial en intercambiador",
        [
            ("Excavación de zanjas", "m", 150, 4200, 5),
            ("Tendido de cable", "m", 400, 3100, 4),
            ("Montaje de columnas", "un", 6, 420000, 6),
            ("Montaje de luminarias", "un", 12, 185000, 4),
            ("Conexionado y tableros", "un", 3, 640000, 3),
        ],
    ),
    "HOR-04": (
        "Accesos en hormigón a parque industrial",
        [
            ("Movimiento de suelos", "m3", 400, 3800, 7),
            ("Compactación de subrasante", "m2", 1200, 900, 5),
            ("Colocación de hormigón", "m3", 150, 105000, 14),
            ("Aserrado de juntas", "m", 300, 2400, 3),
            ("Curado y sellado", "m2", 900, 700, 4),
        ],
    ),
}

# Plantillas de texto libre por causa ({a} = actividad en minúsculas)
TEMPLATES: dict[str, list[str]] = {
    "CLIMA": [
        "lluvia, no se pudo trabajar en {a}",
        "llovió toda la mañana, terreno saturado",
        "viento fuerte, se suspendió {a}",
        "tormenta eléctrica, se retiró al personal",
        "barro en el frente de obra, no se puede ingresar con equipos",
        "calor extremo, se cortó la jornada antes",
        "terreno anegado por la lluvia de ayer",
        "pronóstico adverso, se suspendió {a}",
    ],
    "MATERIALES": [
        "no llegó el hormigón, demora del proveedor",
        "falta de material para {a}, el proveedor no entregó",
        "sin asfalto, la planta no despachó",
        "faltan ladrillos en obra, entrega demorada",
        "demora en la entrega de cable, no se pudo avanzar con {a}",
        "se terminó el cemento, esperando reposición",
        "no llegaron las columnas, el proveedor reprogramó",
        "falta hierro para armaduras",
        "acopio insuficiente de material para {a}",
    ],
    "EQUIPOS": [
        "se rompió la retroexcavadora",
        "la terminadora quedó parada por falla hidráulica",
        "mixer en el taller, sin hormigón colocado",
        "motoniveladora sin disponibilidad, la usan en otra obra",
        "falla en el compactador, se frenó {a}",
        "avería de la grúa, no se pudo montar",
        "equipo de {a} sin repuestos, parado",
        "se pinchó el camión volcador, demora en el acarreo",
    ],
    "MANO_OBRA": [
        "faltó la cuadrilla de {a}, ausentismo",
        "poco personal para {a}",
        "sin gente suficiente, faltaron oficiales",
        "ausentismo alto por el fin de semana largo",
        "los operarios no vinieron, sin cobertura",
        "falta de personal especializado para {a}",
        "se retiró parte de la cuadrilla a otra obra",
        "faltaron ayudantes en el frente",
    ],
    "SUBCONTRATISTA": [
        "el subcontratista no se presentó",
        "demora del subcontratista de {a}",
        "subcontrato sin personal, se reprograma",
        "el contratista de electricidad no llegó a obra",
        "subcontratista sin equipos para {a}",
        "esperando al subcontratista, no terminó su tarea previa",
        "el subcontratista se atrasó con la tarea previa",
    ],
    "PROYECTO": [
        "falta definición en planos de {a}",
        "consulta a la inspección sin respuesta",
        "cambio de diseño, se frena {a}",
        "plano desactualizado, hay que replantear",
        "falta detalle constructivo, esperando ingeniería",
        "orden de cambio pendiente de aprobación",
        "incompatibilidad entre planos y obra real",
        "esperando aprobación del proyecto ejecutivo",
    ],
    "INTERFERENCIAS": [
        "cañería de agua no relevada, esperando al ente",
        "poste a trasladar, esperando a la empresa de energía",
        "falta permiso municipal para cortar la calle",
        "interferencia con servicios enterrados",
        "vecinos bloquean el acceso al frente",
        "tránsito sin desvío habilitado, no se puede trabajar",
        "esperando permiso de corte de energía",
        "ocupación del terreno por terceros",
    ],
    "SEGURIDAD": [
        "inspección de seguridad, se frenó el trabajo en altura",
        "falta andamio certificado",
        "accidente leve, parada para investigación",
        "charla de seguridad extendida y capacitación",
        "falta de EPP para el personal nuevo",
        "se detuvo {a} por condición insegura en el frente",
        "la ART observó el apuntalamiento, se corrige",
    ],
    "CALIDAD": [
        "ensayo de compactación no aprobado, se rehace",
        "hormigón rechazado por asentamiento",
        "retrabajo de {a}, fuera de plomo",
        "la inspección observó el armado, se corrige",
        "se rehace {a} por defecto de ejecución",
        "ensayo de laboratorio no conforme, se detiene {a}",
        "carpeta con deficiencias, se repasa",
    ],
    "OTROS": [
        "sin motivo declarado",
        "no se pudo avanzar",
        "demora general en el frente",
        "se reprogramó por indicación de la jefatura",
        "corte de energía general",
        "feriado local, jornada reducida",
    ],
}

# Textos genuinamente ambiguos: los capataces a veces no explican la causa.
VAGUE = [
    "se atrasó {a}",
    "no se pudo avanzar con {a}",
    "demoras en obra",
    "problemas varios",
    "pendiente de resolver",
    "{a} incompleto",
]
VAGUE_RATE = 0.12
EMPTY_RATE = 0.07  # desvío sin ninguna causa registrada
NEUTRAL = ["sin novedades", "se cumplió lo previsto", "ok", "tarea terminada"]

# causa -> peso relativo base
CAUSE_WEIGHTS = {
    "CLIMA": 0.14,
    "MATERIALES": 0.19,
    "EQUIPOS": 0.13,
    "MANO_OBRA": 0.11,
    "SUBCONTRATISTA": 0.09,
    "PROYECTO": 0.11,
    "INTERFERENCIAS": 0.08,
    "SEGURIDAD": 0.05,
    "CALIDAD": 0.07,
    "OTROS": 0.03,
}


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _noisy(text: str, rng: np.random.Generator) -> str:
    """Simula cómo escriben los capataces: sin tildes, mayúsculas, adornos."""
    if rng.random() < 0.35:
        text = _strip_accents(text)
    if rng.random() < 0.15:
        text = text.upper()
    if rng.random() < 0.10:
        text = text + " " + str(rng.choice(["!!", "urgente", "...", "(ver foto)"]))
    return text


def generate(
    start: str = "2026-08-03",
    days: int = 84,
    seed: int = 42,
    anomaly: bool = True,
) -> pd.DataFrame:
    """Devuelve los partes diarios. Incluye la columna `causa_real` (verdad) solo para entrenar."""
    rng = np.random.default_rng(seed)
    t0 = datetime.fromisoformat(start)
    causes = list(CAUSE_WEIGHTS)
    base_w = np.array(list(CAUSE_WEIGHTS.values()))
    base_w = base_w / base_w.sum()

    rows: list[dict] = []
    rid = 0
    for d in range(days):
        day = t0 + timedelta(days=d)
        if day.weekday() == 6:  # domingo: no se trabaja
            continue
        last_week = anomaly and d >= days - 7
        rainy = rng.random() < 0.06
        for obra, (_, acts) in OBRAS.items():
            n_acts = min(3, len(acts))
            chosen = rng.choice(len(acts), size=n_acts, replace=False)
            crisis = last_week and obra == "VIV-02"
            for idx in chosen:
                nombre, unidad, qty, precio, crew = acts[int(idx)]
                plan = round(qty * float(rng.uniform(0.9, 1.1)), 1)
                p_ok = 0.20 if crisis else 0.70
                weights = base_w.copy()
                if crisis:
                    weights[causes.index("MATERIALES")] *= 6
                    weights = weights / weights.sum()
                causa = None
                if rainy and rng.random() < 0.85:
                    causa = "CLIMA"
                elif rng.random() > p_ok:
                    causa = str(rng.choice(causes, p=weights))

                if causa is None:
                    ejec = round(plan * float(rng.uniform(0.97, 1.08)), 1)
                    obs = str(rng.choice(NEUTRAL)) if rng.random() < 0.2 else ""
                else:
                    frac = rng.uniform(0.0, 0.3) if causa == "CLIMA" else rng.uniform(0.0, 0.85)
                    ejec = round(plan * float(frac), 1)
                    r = rng.random()
                    if r < EMPTY_RATE:
                        obs = ""
                    else:
                        pool = VAGUE if r < EMPTY_RATE + VAGUE_RATE else TEMPLATES[causa]
                        obs = _noisy(str(rng.choice(pool)).format(a=nombre.lower()), rng)
                rid += 1
                rows.append(
                    {
                        "registro_id": f"PD{rid:06d}",
                        "fecha": day.strftime("%Y-%m-%d"),
                        "obra": obra,
                        "actividad": nombre,
                        "unidad": unidad,
                        "cantidad_planificada": plan,
                        "cantidad_ejecutada": ejec,
                        "horas_hombre": round(crew * 8 * float(rng.uniform(0.9, 1.0)), 1),
                        "precio_unitario": precio,
                        "observacion": obs,
                        "causa_real": causa or "",
                    }
                )
    return pd.DataFrame(rows)


def write_sample_data(out_dir: str, days: int = 84) -> dict[str, int]:
    """Escribe: histórico etiquetado (para entrenar) y partes diarios (a procesar)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    hist = generate(start="2025-03-03", days=days * 5, seed=7, anomaly=False)
    hist = hist[(hist["causa_real"] != "") & (hist["observacion"] != "")]
    hist = hist.rename(columns={"observacion": "descripcion", "causa_real": "categoria"})
    hist[["descripcion", "categoria"]].to_csv(out / "historico_etiquetado.csv", index=False)

    partes = generate(start="2026-08-03", days=days, seed=42, anomaly=True)
    partes.drop(columns=["causa_real"]).to_csv(out / "partes_diarios.csv", index=False)
    return {"historico": len(hist), "partes": len(partes)}

from __future__ import annotations

PJ_KEYWORDS = [
    "justicialista",
    "frente de todos",
    "frente para la victoria",
    "unión por la patria",
    "union por la patria",
    "frente renovador",
    "peronismo",
    "peronista",
    "frente cívico por santiago",
    "frente civico por santiago",
    "movimiento popular neuquino",
    "bloque justicialista",
    "pj ",
]

PRO_KEYWORDS = [
    "pro ",
    "propuesta republicana",
    "cambiemos",
    "juntos por el cambio",
    "juntos por el cambio federal",
    "ucr",
    "unión cívica radical",
    "union civica radical",
    "coalición cívica",
    "coalicion civica",
    "evolución radical",
    "evolucion radical",
]

LLA_KEYWORDS = ["la libertad avanza"]


def classify_bloc(bloc_name: str) -> str:
    """Classify a bloc name into PJ, PRO, LLA or OTHER."""
    name = bloc_name.lower().strip()
    for kw in PJ_KEYWORDS:
        if kw in name:
            return "PJ"
    for kw in PRO_KEYWORDS:
        if kw in name:
            return "PRO"
    for kw in LLA_KEYWORDS:
        if kw in name:
            return "LLA"
    return "OTROS"

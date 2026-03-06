from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

# ---------------------------------------------------------------------------
# Common law names mapping
# ---------------------------------------------------------------------------
COMMON_LAW_NAMES = [
    # --- Major 2023-2024+ laws ---
    (["bases y puntos de partida", "ley de bases", "ley bases"], "Ley Bases"),
    (["medidas fiscales paliativas", "paquete fiscal"], "Paquete Fiscal"),
    (
        [
            "régimen de incentivo para grandes inversiones",
            "regimen de incentivo para grandes inversiones",
            "rigi",
        ],
        "RIGI",
    ),
    (["decreto de necesidad y urgencia 70", "dnu 70"], "DNU 70/2023"),

    # --- Economy & taxes ---
    (["impuesto a las ganancias"], "Impuesto a las Ganancias"),
    (["bienes personales"], "Bienes Personales"),
    (
        [
            "presupuesto general",
            "presupuesto de la administración",
            "presupuesto de la administracion",
            "ley de presupuesto",
        ],
        "Presupuesto",
    ),
    (["movilidad jubilatoria", "movilidad previsional"], "Movilidad Jubilatoria"),
    (["régimen previsional", "regimen previsional"], "Regimen Previsional"),
    (["privatización", "privatizacion"], "Privatizaciones"),
    (["deuda externa", "reestructuración de deuda", "reestructuracion de deuda"], "Deuda Externa"),
    (
        ["monotributo", "régimen simplificado para pequeños contribuyentes", "regimen simplificado para pequeños contribuyentes"],
        "Monotributo",
    ),
    (["consenso fiscal"], "Consenso Fiscal"),
    (["fondo monetario internacional", "fondo monetario"], "FMI"),
    (["derechos de exportación", "derechos de exportacion", "retenciones agropecuarias"], "Retenciones / Derechos de Exportacion"),

    # --- Electoral & institutional ---
    (["boleta única", "boleta unica"], "Boleta Unica de Papel"),
    (["ficha limpia"], "Ficha Limpia"),
    (["régimen electoral", "regimen electoral", "código electoral", "codigo electoral"], "Regimen Electoral"),
    (["paridad de género", "paridad de genero"], "Paridad de Genero"),
    (["consejo de la magistratura"], "Consejo de la Magistratura"),

    # --- Codes ---
    (["código procesal penal", "codigo procesal penal"], "Codigo Procesal Penal"),
    (["código penal", "codigo penal"], "Codigo Penal"),
    (["código civil", "codigo civil"], "Codigo Civil"),
    (["código aduanero", "codigo aduanero"], "Codigo Aduanero"),

    # --- Justice & security ---
    (["juicio en ausencia"], "Juicio en Ausencia"),
    (["régimen penal juvenil", "penal juvenil"], "Regimen Penal Juvenil"),
    (["lavado de activos"], "Lavado de Activos"),
    (["extinción de dominio", "extincion de dominio"], "Extincion de Dominio"),
    (["inteligencia nacional", "agencia federal de inteligencia"], "Inteligencia Nacional"),
    (["narcotráfico", "narcotrafico"], "Narcotráfico"),

    # --- Labor ---
    (["reforma laboral", "modernización laboral", "modernizacion laboral"], "Reforma Laboral"),
    (["teletrabajo"], "Teletrabajo"),
    (["trabajo agrario"], "Trabajo Agrario"),

    # --- Housing & property ---
    (["ley de alquileres", "locaciones urbanas"], "Ley de Alquileres"),
    (["tierras rurales", "dominio nacional sobre la propiedad"], "Tierras Rurales"),

    # --- Social & rights ---
    (
        ["interrupción voluntaria del embarazo", "interrupcion voluntaria del embarazo", "aborto"],
        "IVE / Aborto",
    ),
    (["violencia de género", "violencia de genero"], "Violencia de Género"),
    (["emergencia alimentaria"], "Emergencia Alimentaria"),
    (
        [
            "matrimonio igualitario",
            "matrimonio entre personas del mismo sexo",
            "matrimonio civil",
            "código civil, sobre matrimonio",
            "codigo civil, sobre matrimonio",
        ],
        "Matrimonio Igualitario",
    ),
    (
        [
            "identidad de género",
            "identidad de genero",
            "ley de identidad",
            "cd-76/11",
        ],
        "Ley de Identidad de Género",
    ),
    (
        [
            "cupo laboral trans",
            "cupo laboral travesti",
            "acceso al empleo formal para personas travestis",
            "acceso al empleo formal para pers travestis",
            "travesti, transexual",
            "travestis, transexuales",
        ],
        "Cupo Laboral Trans",
    ),
    (["salud mental"], "Salud Mental"),
    (["barrios populares"], "Barrios Populares"),

    # --- Education & science ---
    (["financiamiento universitario"], "Financiamiento Universitario"),
    (["educación sexual", "educacion sexual"], "Educacion Sexual"),
    (
        [
            "financiamiento de la ciencia",
            "financiamiento científico",
            "financiamiento cientifico",
            "ciencia, tecnología e innovación",
            "ciencia, tecnologia e innovacion",
            "ciencia y tecnología",
            "ciencia y tecnologia",
        ],
        "Financiamiento Cientifico",
    ),

    # --- Health ---
    (["cannabis medicinal", "uso medicinal de la planta de cannabis"], "Cannabis Medicinal"),
    (
        [
            "cadena de frío de los medicamentos",
            "cadena de frio de los medicamentos",
            "producción pública de medicamentos",
            "produccion publica de medicamentos",
        ],
        "Ley de Medicamentos",
    ),

    # --- Environment ---
    (["etiquetado frontal"], "Etiquetado Frontal"),
    (["humedales"], "Ley de Humedales"),
    (["manejo del fuego"], "Manejo del Fuego"),
    (["glaciares"], "Ley de Glaciares"),
    (
        [
            "energías renovables",
            "energias renovables",
            "fuentes renovables de energía",
            "fuentes renovables de energia",
            "energía renovable",
            "energia renovable",
        ],
        "Energias Renovables",
    ),

    # --- Consumer & commerce ---
    (["góndolas", "gondolas"], "Ley de Gondolas"),
    (["economía del conocimiento", "economia del conocimiento"], "Economia del Conocimiento"),
    (["compre argentino", "compre nacional"], "Compre Argentino"),

    # --- Media & communication ---
    (["servicios de comunicación audiovisual", "servicios de comunicacion audiovisual", "ley de medios"], "Ley de Medios"),

    # --- Transparency ---
    (["acceso a la información pública", "acceso a la informacion publica"], "Acceso a Info. Publica"),

    # --- Transport & safety ---
    (["seguridad vial", "tránsito y seguridad vial", "transito y seguridad vial"], "Seguridad Vial"),
    (["ludopatía", "ludopatia", "apuestas en línea", "apuestas en linea", "juegos de azar y apuestas"], "Ludopatia / Apuestas Online"),

    # --- Other ---
    (["defensa nacional"], "Defensa Nacional"),
    (["inocencia fiscal"], "Inocencia Fiscal"),
]


def COMMON_NORM(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


# Precompute normalized keywords per rule so we don't re-normalize on every call.
_COMMON_LAW_RULES: list[tuple[list[str], str]] = []
for _keywords, _common_name in COMMON_LAW_NAMES:
    _COMMON_LAW_RULES.append(([COMMON_NORM(keyword) for keyword in _keywords], _common_name))


def _kw_matches(kw_norm: str, t_norm: str) -> bool:
    """Devuelve True si *kw_norm* se encuentra dentro de *t_norm*."""
    if len(kw_norm) <= 4:
        return bool(re.search(r"\b" + re.escape(kw_norm) + r"\b", t_norm))
    return kw_norm in t_norm


def get_common_name(title: str) -> str | None:
    """Devuelve el nombre común de ley que mejor coincide con *title* o None."""
    if not title:
        return None
    normalized_title = COMMON_NORM(title)

    best_name: str | None = None
    best_score: tuple[int, int] = (0, 0)

    for norm_keywords, common_name in _COMMON_LAW_RULES:
        matched_length = 0
        matched_count = 0
        for keyword in norm_keywords:
            if _kw_matches(keyword, normalized_title):
                matched_length += len(keyword)
                matched_count += 1

        if matched_count > 0:
            score = (matched_length, matched_count)
            if score > best_score:
                best_score = score
                best_name = common_name

    return best_name


# ---------------------------------------------------------------------------
# Law grouping
# ---------------------------------------------------------------------------

def extract_law_group_key(votacion: dict) -> str:
    title = votacion.get("title", "")
    date = votacion.get("date", "")
    chamber = votacion.get("chamber", "")

    date_part = ""
    date_match = re.search(r"(\d{2}/\d{2}/\d{4})", date)
    if date_match:
        date_part = date_match.group(1)

    od_match = re.search(r"(O\.?\s*D\.?\s*N?[°ºo]?\s*\d+(?:/\d+)?)", title, re.IGNORECASE)
    if od_match:
        od_num = re.sub(r"\s+", "", od_match.group(1).upper())
        return f"{chamber}|{od_num}|{date_part}"

    exp_match = re.search(r"(Exp(?:ediente)?\.?\s*N?[°ºo]?\s*[\d\-]+(?:/\d+)?)", title, re.IGNORECASE)
    if exp_match:
        exp_num = re.sub(r"\s+", "", exp_match.group(1).upper())
        return f"{chamber}|{exp_num}|{date_part}"

    cleaned = title.upper()
    cleaned = re.sub(r"\s*-?\s*EN\s+(GENERAL|PARTICULAR)\s*", " ", cleaned)
    cleaned = re.sub(r"\s*-?\s*ART[IÍ]?CULO?\s+\d+.*", "", cleaned)
    cleaned = re.sub(r"\s*-?\s*ART\.?\s+\d+.*", "", cleaned)
    cleaned = re.sub(r"\s*-?\s*MODIFICACIONES?\s+(AL|DEL)\s+SENADO.*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) > 15:
        return f"{chamber}|{cleaned[:100]}|{date_part}"

    return f"{chamber}|SINGLE|{votacion.get('id', '')}"


def build_law_groups(all_votaciones: list[dict]) -> dict:
    groups = defaultdict(
        lambda: {
            "votaciones": [],
            "title": "",
            "date": "",
            "common_name": None,
            "chamber": "",
        }
    )

    for votacion in all_votaciones:
        key = extract_law_group_key(votacion)
        group = groups[key]
        group["votaciones"].append(votacion)
        if len(votacion.get("title", "")) > len(group["title"]):
            group["title"] = votacion.get("title", "")
        if not group["date"]:
            group["date"] = votacion.get("date", "")
        group["chamber"] = votacion.get("chamber", "")

    for group in groups.values():
        common_name = get_common_name(group["title"])
        if common_name:
            group["common_name"] = common_name

    return dict(groups)

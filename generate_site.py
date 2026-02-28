#!/usr/bin/env python3
"""
Como Voto - Data Processor / Site Generator
============================================
Reads scraped voting data from consolidated JSON files in data/
and generates aggregated JSON files for the interactive frontend
(docs/data/ directory for GitHub Pages).

Features:
  - Reads compact consolidated DB (one file per chamber)
  - Cross-chamber name matching (legislators in both Diputados & Senadores)
  - Law grouping (EN GENERAL + EN PARTICULAR articles -> single law)
  - Common law name mapping
  - Waffle visualization data output
  - Contested-only alignment calculation
"""

import json
import os
import re
import sys
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Import ConsolidatedDB and helpers from scraper
from scraper import ConsolidatedDB, classify_bloc, VOTE_DECODE

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
DOCS_DATA_DIR = DOCS_DIR / "data"
FOTOS_DIR = DOCS_DIR / "fotos"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("processor")


# ---------------------------------------------------------------------------
# Common law names mapping
# ---------------------------------------------------------------------------
COMMON_LAW_NAMES = [
    (['bases y puntos de partida', "ley de bases", "ley bases"], "Ley Bases"),
    (["medidas fiscales paliativas", "paquete fiscal"], "Paquete Fiscal"),
    (["régimen de incentivo para grandes inversiones",
      "regimen de incentivo para grandes inversiones", "rigi"], "RIGI"),
    (["decreto de necesidad y urgencia 70", "dnu 70"], "DNU 70/2023"),
    (["movilidad jubilatoria", "movilidad previsional"],
     "Movilidad Jubilatoria"),
    (["financiamiento universitario"], "Financiamiento Universitario"),
    (["privatización", "privatizacion"], "Privatizaciones"),
    (["boleta única", "boleta unica"], "Boleta Unica de Papel"),
    (["ficha limpia"], "Ficha Limpia"),
    (["juicio en ausencia"], "Juicio en Ausencia"),
    (["presupuesto general", "presupuesto de la administración",
      "presupuesto de la administracion", "ley de presupuesto"],
     "Presupuesto"),
    (["código penal", "codigo penal"], "Codigo Penal"),
    (["código procesal penal", "codigo procesal penal"],
     "Codigo Procesal Penal"),
    (["reforma laboral", "modernización laboral",
      "modernizacion laboral"], "Reforma Laboral"),
    (["ley de alquileres", "locaciones urbanas"], "Ley de Alquileres"),
    (["impuesto a las ganancias"], "Impuesto a las Ganancias"),
    (["bienes personales"], "Bienes Personales"),
    (["deuda externa", "reestructuración de deuda",
      "reestructuracion de deuda"], "Deuda Externa"),
    (["interrupción voluntaria del embarazo",
      "interrupcion voluntaria", "aborto"], "IVE / Aborto"),
    (["violencia de género", "violencia de genero"],
     "Violencia de Genero"),
    (["emergencia alimentaria"], "Emergencia Alimentaria"),
    (["consenso fiscal"], "Consenso Fiscal"),
    (["paridad de género", "paridad de genero"], "Paridad de Genero"),
    (["acceso a la información pública",
      "acceso a la informacion publica"], "Acceso a Info. Publica"),
    (["cannabis", "uso medicinal"], "Cannabis Medicinal"),
    (["régimen previsional", "regimen previsional"],
     "Regimen Previsional"),
    (["defensa nacional"], "Defensa Nacional"),
    (["educación sexual", "educacion sexual"], "Educacion Sexual"),
    (["economía del conocimiento", "economia del conocimiento"],
     "Economia del Conocimiento"),
    (["góndolas", "gondolas"], "Ley de Gondolas"),
    (["teletrabajo"], "Teletrabajo"),
    (["etiquetado frontal"], "Etiquetado Frontal"),
    (["humedales"], "Ley de Humedales"),
    (["manejo del fuego"], "Manejo del Fuego"),
    (["régimen electoral", "regimen electoral"], "Regimen Electoral"),
    (["emergencia pública", "emergencia publica",
      "declaración de emergencia", "declaracion de emergencia"],
     "Emergencia Publica"),    # additional notable laws requested by user
    (['régimen penal juvenil', 'penal juvenil'], "Régimen Penal Juvenil"),
    (['glaciares'], "Glaciares"),
    (['inocencia fiscal'], "Inocencia Fiscal"),
    (['ciencia y tecnología', 'ciencia'], "Emergencia y Financiamiento Científico")
]


def get_common_name(title: str) -> str | None:
    t = title.lower()
    for keywords, common_name in COMMON_LAW_NAMES:
        for kw in keywords:
            if kw in t:
                return common_name
    return None


# ---------------------------------------------------------------------------
# Law grouping
# ---------------------------------------------------------------------------

def extract_law_group_key(votacion: dict) -> str:
    title = votacion.get("title", "")
    date = votacion.get("date", "")
    chamber = votacion.get("chamber", "")

    date_part = ""
    dm = re.search(r"(\d{2}/\d{2}/\d{4})", date)
    if dm:
        date_part = dm.group(1)

    # Extract O.D. / C.D. numbers
    od_match = re.search(
        r"(O\.?\s*D\.?\s*N?[°ºo]?\s*\d+(?:/\d+)?)", title, re.IGNORECASE
    )
    if od_match:
        od_num = re.sub(r"\s+", "", od_match.group(1).upper())
        return f"{chamber}|{od_num}|{date_part}"

    exp_match = re.search(
        r"(Exp(?:ediente)?\.?\s*N?[°ºo]?\s*[\d\-]+(?:/\d+)?)",
        title, re.IGNORECASE
    )
    if exp_match:
        exp_num = re.sub(r"\s+", "", exp_match.group(1).upper())
        return f"{chamber}|{exp_num}|{date_part}"

    # Strip vote-type markers to group related votes
    clean = title.upper()
    clean = re.sub(r"\s*-?\s*EN\s+(GENERAL|PARTICULAR)\s*", " ", clean)
    clean = re.sub(r"\s*-?\s*ART[IÍ]?CULO?\s+\d+.*", "", clean)
    clean = re.sub(r"\s*-?\s*ART\.?\s+\d+.*", "", clean)
    clean = re.sub(
        r"\s*-?\s*MODIFICACIONES?\s+(AL|DEL)\s+SENADO.*", "", clean
    )
    clean = re.sub(r"\s+", " ", clean).strip()

    if len(clean) > 15:
        return f"{chamber}|{clean[:100]}|{date_part}"

    return f"{chamber}|SINGLE|{votacion.get('id', '')}"


def build_law_groups(all_votaciones: list[dict]) -> dict:
    groups = defaultdict(lambda: {
        "votaciones": [], "title": "", "date": "",
        "common_name": None, "chamber": "",
    })

    for v in all_votaciones:
        key = extract_law_group_key(v)
        g = groups[key]
        g["votaciones"].append(v)
        if len(v.get("title", "")) > len(g["title"]):
            g["title"] = v.get("title", "")
        if not g["date"]:
            g["date"] = v.get("date", "")
        g["chamber"] = v.get("chamber", "")

    for key, g in groups.items():
        cn = get_common_name(g["title"])
        if cn:
            g["common_name"] = cn

    return dict(groups)


# ---------------------------------------------------------------------------
# Data loading (from consolidated JSON)
# ---------------------------------------------------------------------------

def load_all_votaciones_from_db(chamber: str) -> list[dict]:
    """Load all votaciones from a consolidated DB file, expanding them
    to the full format used by the rest of the pipeline."""
    db_path = DATA_DIR / f"{chamber}.json"
    if not db_path.exists():
        log.warning(f"Consolidated DB not found: {db_path}")
        return []

    db = ConsolidatedDB(db_path)
    db.load()
    log.info(f"Loaded {len(db.votaciones)} {chamber} votaciones from DB")
    return db.expand_all(chamber)


def clean_date(date_str: str) -> str:
    """Clean date string: extract DD/MM/YYYY and optional HH:MM."""
    m = re.search(r"(\d{2}/\d{2}/\d{4})", date_str)
    if not m:
        return date_str.strip()
    result = m.group(1)
    time_m = re.search(r"(\d{2}:\d{2})", date_str)
    if time_m:
        result += " - " + time_m.group(1)
    return result


def extract_year(date_str: str) -> int | None:
    match = re.search(r"(\d{4})", date_str)
    if match:
        return int(match.group(1))
    return None


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def compute_majority_vote(votes: list[dict], coalition: str) -> str:
    coalition_votes = [v for v in votes if v.get("coalition") == coalition]
    if not coalition_votes:
        return "N/A"

    counts = defaultdict(int)
    for v in coalition_votes:
        vote = v["vote"].upper()
        if "AFIRMATIV" in vote:
            counts["AFIRMATIVO"] += 1
        elif "NEGATIV" in vote:
            counts["NEGATIVO"] += 1
        elif "ABSTENCI" in vote or "ABSTENCION" in vote:
            counts["ABSTENCION"] += 1
        elif "AUSENT" in vote:
            counts["AUSENTE"] += 1

    active_counts = {k: v for k, v in counts.items() if k != "AUSENTE"}
    if not active_counts:
        return "AUSENTE"

    return max(active_counts, key=active_counts.get)


def compute_combined_majority(
    votes: list[dict], coalitions: list[str]
) -> str:
    """Compute majority vote across multiple coalitions combined.
    Used for 2023+ opposition bloc (LLA + PRO grouped together).
    """
    coalition_votes = [
        v for v in votes if v.get("coalition") in coalitions
    ]
    if not coalition_votes:
        return "N/A"

    counts = defaultdict(int)
    for v in coalition_votes:
        vote = v["vote"].upper()
        if "AFIRMATIV" in vote:
            counts["AFIRMATIVO"] += 1
        elif "NEGATIV" in vote:
            counts["NEGATIVO"] += 1
        elif "ABSTENCI" in vote or "ABSTENCION" in vote:
            counts["ABSTENCION"] += 1
        elif "AUSENT" in vote:
            counts["AUSENTE"] += 1

    active_counts = {k: v for k, v in counts.items() if k != "AUSENTE"}
    if not active_counts:
        return "AUSENTE"

    return max(active_counts, key=active_counts.get)


def is_contested(year: int | None, pj_majority: str, pro_majority: str,
                 lla_majority: str, opp_majority_2023: str) -> bool:
    """Determine if a votación had disagreement between the two major sides.

    For 2015-2022: PJ vs PRO — contested if they voted differently.
    For 2023-2026: PJ vs combined opposition (LLA+PRO) — contested if they
                   voted differently.
    """
    if year is None:
        return False

    if year <= 2022:
        if pj_majority in ("N/A", "AUSENTE") or \
           pro_majority in ("N/A", "AUSENTE"):
            return False
        return pj_majority != pro_majority
    else:
        if pj_majority in ("N/A", "AUSENTE") or \
           opp_majority_2023 in ("N/A", "AUSENTE"):
            return False
        return pj_majority != opp_majority_2023


def normalize_vote(vote_str: str) -> str:
    v = vote_str.upper().strip()
    if "AFIRMATIV" in v:
        return "AFIRMATIVO"
    elif "NEGATIV" in v:
        return "NEGATIVO"
    elif "ABSTENCI" in v:
        return "ABSTENCION"
    elif "AUSENT" in v:
        return "AUSENTE"
    elif "PRESIDEN" in v:
        return "PRESIDENTE"
    return v


def normalize_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name.strip().upper())
    replacements = {
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
        "Ü": "U", "Ñ": "N",
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name


def load_photo_maps() -> dict[str, str]:
    """Load photo name->filename mappings from scraper output.
    Returns a dict: normalized_name -> relative path (fotos/filename).
    """
    photo_map: dict[str, str] = {}

    # Diputados photos
    dip_photos_path = DATA_DIR / "diputados_photos.json"
    if dip_photos_path.exists():
        try:
            with open(dip_photos_path, "r", encoding="utf-8") as f:
                dip_photos = json.load(f)
            for name, filename in dip_photos.items():
                nk = normalize_name(name)
                photo_map[nk] = f"fotos/{filename}"
        except (json.JSONDecodeError, OSError):
            pass

    # Senadores photos
    sen_photos_path = DATA_DIR / "senadores_photos.json"
    if sen_photos_path.exists():
        try:
            with open(sen_photos_path, "r", encoding="utf-8") as f:
                sen_photos = json.load(f)
            for name, filename in sen_photos.items():
                nk = normalize_name(name)
                if nk not in photo_map:
                    photo_map[nk] = f"fotos/{filename}"
        except (json.JSONDecodeError, OSError):
            pass

    # Also scan the consolidated DB for photo_ids
    dip_db_path = DATA_DIR / "diputados.json"
    if dip_db_path.exists():
        db = ConsolidatedDB(dip_db_path)
        db.load()
        for ni_str, photo_id in db.photo_ids.items():
            ni = int(ni_str)
            if ni < len(db.names):
                name = db.names[ni]
                nk = normalize_name(name)
                filename = f"fotos/dip_{photo_id}.jpg"
                if nk not in photo_map:
                    photo_map[nk] = filename


    return photo_map


def attach_photos(legislators: dict, photo_map: dict[str, str]):
    """Attach photo paths to legislator records."""
    matched = 0
    for name_key, leg in legislators.items():
        photo = photo_map.get(name_key, "")
        if photo:
            full_path = DOCS_DIR / photo.replace("/", os.sep)
            if full_path.exists():
                leg["photo"] = photo
                matched += 1
            else:
                leg["photo"] = ""
        else:
            leg["photo"] = ""
    log.info(f"Attached photos to {matched}/{len(legislators)} legislators")


def build_legislator_data(
    all_votaciones: list[dict], law_groups: dict
) -> dict:
    legislators = {}

    votacion_to_group = {}
    for group_key, group_data in law_groups.items():
        for v in group_data["votaciones"]:
            vid = f"{v.get('chamber', '')}_{v.get('id', '')}"
            votacion_to_group[vid] = group_key

    for votacion in all_votaciones:
        year = extract_year(votacion.get("date", ""))
        votacion_id = votacion.get("id", "")
        chamber = votacion.get("chamber", "")
        title = votacion.get("title", "")
        date = clean_date(votacion.get("date", ""))
        vtype = votacion.get("type", "")

        vid_key = f"{chamber}_{votacion_id}"
        group_key = votacion_to_group.get(vid_key, "")
        group_data = law_groups.get(group_key, {})
        law_display_name = (
            group_data.get("common_name")
            or group_data.get("title", title)
        )

        pj_majority = compute_majority_vote(
            votacion.get("votes", []), "PJ"
        )
        pro_majority = compute_majority_vote(
            votacion.get("votes", []), "PRO"
        )
        lla_majority = compute_majority_vote(
            votacion.get("votes", []), "LLA"
        )
        opp_majority_2023 = compute_combined_majority(
            votacion.get("votes", []), ["LLA", "PRO"]
        )

        contested = is_contested(
            year, pj_majority, pro_majority,
            lla_majority, opp_majority_2023
        )

        for vote_record in votacion.get("votes", []):
            name = vote_record.get("name", "").strip()
            if not name:
                continue

            name_key = normalize_name(name)

            if name_key not in legislators:
                legislators[name_key] = {
                    "name": name,
                    "name_key": name_key,
                    "chambers": [chamber],
                    "chamber": chamber,
                    "bloc": vote_record.get("bloc", ""),
                    "province": vote_record.get("province", ""),
                    "coalition": vote_record.get("coalition",
                        classify_bloc(vote_record.get("bloc", ""))),
                    "votes": [],
                    "yearly_stats": {},
                    "alignment": {
                        "PJ": {"total": 0, "aligned": 0},
                        "PRO": {"total": 0, "aligned": 0},
                        "LLA": {"total": 0, "aligned": 0},
                    },
                    "yearly_alignment": {},
                }

            leg = legislators[name_key]

            if chamber not in leg["chambers"]:
                leg["chambers"].append(chamber)

            leg["bloc"] = vote_record.get("bloc", leg["bloc"])
            leg["province"] = vote_record.get("province", leg["province"])
            leg["coalition"] = vote_record.get(
                "coalition", leg["coalition"]
            )
            leg["chamber"] = chamber

            norm_vote = normalize_vote(vote_record.get("vote", ""))

            article_label = ""
            title_upper = title.upper()

            titulo_match = re.search(
                r"T[IÍ]TULO\s+([\dIVXLCDM]+)", title_upper
            )
            if titulo_match:
                article_label = f"Título {titulo_match.group(1)}"
            elif "EN GENERAL" in title_upper or \
                 vtype.upper() == "EN GENERAL":
                article_label = "En General"
            elif "EN PARTICULAR" in title_upper or \
                 vtype.upper() == "EN PARTICULAR":
                art_match = re.search(
                    r"ART[IÍ]?CULO?\s*\.?\s*(\d+)", title, re.IGNORECASE
                )
                if art_match:
                    article_label = f"Art. {art_match.group(1)}"
                else:
                    article_label = "En Particular"

            vote_entry = {
                "vid": votacion_id,
                "ch": chamber,
                "t": title[:200],
                "d": date,
                "yr": year,
                "v": norm_vote,
                "pj": pj_majority,
                "pro": pro_majority,
                "lla": lla_majority,
                "tp": vtype,
                "gk": group_key,
                "ln": law_display_name[:120] if law_display_name else "",
                "al": article_label,
            }
            # include link to original source when available
            vot_url = votacion.get("url")
            if vot_url:
                vote_entry["url"] = vot_url
            leg["votes"].append(vote_entry)

            if year:
                yr_key = str(year)
                if yr_key not in leg["yearly_stats"]:
                    leg["yearly_stats"][yr_key] = {
                        "AFIRMATIVO": 0, "NEGATIVO": 0,
                        "ABSTENCION": 0, "AUSENTE": 0,
                        "PRESIDENTE": 0, "total": 0,
                    }
                leg["yearly_stats"][yr_key][norm_vote] = \
                    leg["yearly_stats"][yr_key].get(norm_vote, 0) + 1
                leg["yearly_stats"][yr_key]["total"] += 1

                if yr_key not in leg["yearly_alignment"]:
                    leg["yearly_alignment"][yr_key] = {
                        "PJ": {"total": 0, "aligned": 0},
                        "PRO": {"total": 0, "aligned": 0},
                        "LLA": {"total": 0, "aligned": 0},
                    }

                if contested and norm_vote not in \
                        ("AUSENTE", "PRESIDENTE"):
                    for coalition, majority in [
                        ("PJ", pj_majority),
                        ("PRO", pro_majority),
                        ("LLA", lla_majority),
                    ]:
                        if majority not in ("N/A", "AUSENTE"):
                            leg["alignment"][coalition]["total"] += 1
                            leg["yearly_alignment"][yr_key][
                                coalition]["total"] += 1
                            if norm_vote == majority:
                                leg["alignment"][coalition]["aligned"] += 1
                                leg["yearly_alignment"][yr_key][
                                    coalition]["aligned"] += 1

    return legislators


def generate_site_data(legislators: dict, law_groups: dict):
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Legislators index
    leg_index = []
    for key, leg in sorted(legislators.items(), key=lambda x: x[0]):
        alignment_pj = (
            round(leg["alignment"]["PJ"]["aligned"]
                  / leg["alignment"]["PJ"]["total"] * 100, 1)
            if leg["alignment"]["PJ"]["total"] > 0 else None
        )
        alignment_pro = (
            round(leg["alignment"]["PRO"]["aligned"]
                  / leg["alignment"]["PRO"]["total"] * 100, 1)
            if leg["alignment"]["PRO"]["total"] > 0 else None
        )
        alignment_lla = (
            round(leg["alignment"]["LLA"]["aligned"]
                  / leg["alignment"]["LLA"]["total"] * 100, 1)
            if leg["alignment"]["LLA"]["total"] > 0 else None
        )

        total_votes = sum(
            s.get("total", 0) for s in leg["yearly_stats"].values()
        )

        chambers = sorted(set(leg["chambers"]))
        chamber_display = (
            "+".join(chambers) if len(chambers) > 1
            else chambers[0] if chambers
            else leg["chamber"]
        )

        leg_index.append({
            "k": key,
            "n": leg["name"],
            "c": chamber_display,
            "b": leg["bloc"],
            "p": leg["province"],
            "co": leg["coalition"],
            "apj": alignment_pj,
            "apro": alignment_pro,
            "alla": alignment_lla,
            "tv": total_votes,
            "ph": leg.get("photo", ""),
        })

    save_json(DOCS_DATA_DIR / "legislators.json", leg_index)
    log.info(f"Generated legislators index with {len(leg_index)} entries")

    # 2. Individual legislator detail files
    leg_details_dir = DOCS_DATA_DIR / "legislators"
    leg_details_dir.mkdir(parents=True, exist_ok=True)

    for key, leg in legislators.items():
        yearly_alignment_pct = {}
        for yr, data in sorted(leg["yearly_alignment"].items()):
            yearly_alignment_pct[yr] = {}
            for coalition in ["PJ", "PRO", "LLA"]:
                total = data[coalition]["total"]
                aligned = data[coalition]["aligned"]
                yearly_alignment_pct[yr][coalition] = (
                    round(aligned / total * 100, 1) if total > 0 else None
                )

        # Build waffle groups — merge by common_name so that e.g. all
        # "Ley Bases" O.D. numbers/dates become a single law entry
        waffle_groups = defaultdict(
            lambda: {"name": "", "votes": [], "year": None,
                     "common_name": None}
        )
        for vote in leg["votes"]:
            ln = vote.get("ln", "")
            # Determine merge key: use common_name if available, else gk
            common_name = get_common_name(ln) if ln else None
            if common_name:
                merge_key = f"COMMON|{common_name}"
            else:
                gk = vote.get("gk", "")
                merge_key = gk if gk else f"SINGLE_{vote['vid']}"

            wg = waffle_groups[merge_key]
            if not wg["name"]:
                wg["name"] = ln or vote.get("t", "")
            if common_name:
                wg["common_name"] = common_name
                wg["name"] = common_name

            # Mark whether this is an "En General" vote
            al = vote.get("al", "")
            is_general = (al == "En General"
                          or "EN GENERAL" in vote.get("t", "").upper()
                          or "VOT. EN GRAL" in vote.get("t", "").upper())

            entry = {
                "v": vote["v"],
                "al": al,
                "t": vote.get("t", ""),
                "g": is_general,
            }
            if vote.get("url"):
                entry["url"] = vote["url"]
            wg["votes"].append(entry)
            if vote.get("yr") and not wg["year"]:
                wg["year"] = vote["yr"]

        waffle_list = []
        for gk, wg in waffle_groups.items():
            # pick first available vote URL to act as law link
            law_url = ""
            for vote in wg["votes"]:
                if vote.get("url"):
                    law_url = vote["url"]
                    break

            waffle_list.append({
                "gk": gk,
                "name": wg["name"][:120],
                "year": wg["year"],
                "url": law_url,
                "votes": wg["votes"],
                "notable": wg.get("common_name") is not None,
            })
        waffle_list.sort(key=lambda x: (-(x["year"] or 0), x["name"]))

        detail = {
            "name": leg["name"],
            "name_key": key,
            "photo": leg.get("photo", ""),
            "chambers": sorted(set(leg["chambers"])),
            "chamber": leg["chamber"],
            "bloc": leg["bloc"],
            "province": leg["province"],
            "coalition": leg["coalition"],
            "yearly_stats": leg["yearly_stats"],
            "yearly_alignment": yearly_alignment_pct,
            "alignment": {
                c: round(d["aligned"] / d["total"] * 100, 1)
                   if d["total"] > 0 else None
                for c, d in leg["alignment"].items()
            },
            "votes": leg["votes"],
            "laws": waffle_list,
        }

        safe_name = re.sub(r"[^A-Z0-9_]", "_", key)[:80]
        save_json(leg_details_dir / f"{safe_name}.json", detail)

    log.info(f"Generated {len(legislators)} legislator detail files")

    # 3. Votaciones summary
    votaciones_summary = {"diputados": [], "senadores": []}

    for chamber in ["diputados", "senadores"]:
        votaciones = load_all_votaciones_from_db(chamber)
        for v in votaciones:
            votaciones_summary[chamber].append({
                "id": v.get("id"),
                "title": v.get("title", "")[:200],
                "date": clean_date(v.get("date", "")),
                "result": v.get("result", ""),
                "type": v.get("type", ""),
                "afirmativo": v.get("afirmativo", 0),
                "negativo": v.get("negativo", 0),
                "abstencion": v.get("abstencion", 0),
                "ausente": v.get("ausente", 0),
            })

    save_json(DOCS_DATA_DIR / "votaciones.json", votaciones_summary)
    log.info("Generated votaciones summary")

    # 4. Law names list
    law_names_set = set()
    for g in law_groups.values():
        cn = g.get("common_name")
        if cn:
            law_names_set.add(cn)
        else:
            t = g.get("title", "").strip()
            if t and len(t) > 5:
                law_names_set.add(t[:120])
    save_json(DOCS_DATA_DIR / "law_names.json", sorted(law_names_set))
    log.info(f"Generated {len(law_names_set)} unique law names")

    # 5. Global stats
    stats = {
        "last_updated": datetime.now().isoformat(),
        "total_legislators": len(legislators),
        "total_diputados": sum(
            1 for l in legislators.values()
            if "diputados" in l.get("chambers", [l["chamber"]])
        ),
        "total_senadores": sum(
            1 for l in legislators.values()
            if "senadores" in l.get("chambers", [l["chamber"]])
        ),
        "total_votaciones_diputados": len(votaciones_summary["diputados"]),
        "total_votaciones_senadores": len(votaciones_summary["senadores"]),
        "years_covered": sorted(set(
            yr for leg in legislators.values()
            for yr in leg["yearly_stats"].keys()
        )),
        "total_laws": len(law_groups),
    }
    save_json(DOCS_DATA_DIR / "stats.json", stats)
    log.info("Generated global stats")


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=None,
                  separators=(",", ":"))


def main():
    log.info("Como Voto - Data Processor")
    log.info(f"Loading votaciones from {DATA_DIR}")

    # Load from consolidated DBs
    all_votaciones = []
    all_votaciones.extend(load_all_votaciones_from_db("diputados"))
    all_votaciones.extend(load_all_votaciones_from_db("senadores"))

    if not all_votaciones:
        log.warning("No votaciones found. Run scraper.py first.")
        generate_site_data({}, {})
        return

    log.info(f"Loaded {len(all_votaciones)} votaciones total")

    law_groups = build_law_groups(all_votaciones)
    log.info(f"Identified {len(law_groups)} law groups")

    photo_map = load_photo_maps()
    log.info(f"Loaded photo map: {len(photo_map)} entries")

    legislators = build_legislator_data(all_votaciones, law_groups)
    log.info(f"Found {len(legislators)} unique legislators")

    attach_photos(legislators, photo_map)

    generate_site_data(legislators, law_groups)

    log.info("Processing complete!")


if __name__ == "__main__":
    main()

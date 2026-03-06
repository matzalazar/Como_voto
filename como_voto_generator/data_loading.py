from __future__ import annotations

import json
import os
import re

from scraper import ConsolidatedDB

from .common import DATA_DIR, DOCS_DIR, log
from .normalization import NAME_ALIASES, normalize_name


def load_all_votaciones_from_db(chamber: str) -> list[dict]:
    """Carga todas las votaciones desde un archivo de base consolidada."""
    db_path = DATA_DIR / f"{chamber}.json"
    if not db_path.exists():
        log.warning(f"Consolidated DB not found: {db_path}")
        return []

    db = ConsolidatedDB(db_path)
    db.load()
    log.info(f"Loaded {len(db.votaciones)} {chamber} votaciones from DB")
    return db.expand_all(chamber)


def clean_date(date_str: str) -> str:
    """Limpia una fecha: extrae DD/MM/YYYY y opcionalmente HH:MM."""
    date_match = re.search(r"(\d{2}/\d{2}/\d{4})", date_str)
    if not date_match:
        return date_str.strip()

    result = date_match.group(1)
    time_match = re.search(r"(\d{2}:\d{2})", date_str)
    if time_match:
        result += " - " + time_match.group(1)
    return result


def extract_year(date_str: str) -> int | None:
    match = re.search(r"(\d{4})", date_str)
    if match:
        return int(match.group(1))
    return None


def practical_year_range(years_list: list[str]) -> tuple[str | None, str | None]:
    """Devuelve (año_mínimo, año_máximo) ignorando outliers tempranos aislados."""
    if not years_list:
        return None, None

    ints = sorted(int(year) for year in years_list)
    start = ints[0]
    if len(ints) > 1 and (ints[1] - ints[0]) > 10:
        start = ints[1]
    return str(start), str(ints[-1])


def load_photo_maps() -> dict[str, str]:
    """Carga mapeos nombre->archivo de foto generados por el scraper."""
    photo_map: dict[str, str] = {}

    dip_photos_path = DATA_DIR / "diputados_photos.json"
    if dip_photos_path.exists():
        try:
            with open(dip_photos_path, "r", encoding="utf-8") as handle:
                dip_photos = json.load(handle)
            for name, filename in dip_photos.items():
                name_key = normalize_name(name)
                photo_map[name_key] = f"fotos/{filename}"
        except (json.JSONDecodeError, OSError):
            pass

    sen_photos_path = DATA_DIR / "senadores_photos.json"
    if sen_photos_path.exists():
        try:
            with open(sen_photos_path, "r", encoding="utf-8") as handle:
                sen_photos = json.load(handle)
            for name, filename in sen_photos.items():
                name_key = normalize_name(name)
                if name_key not in photo_map:
                    photo_map[name_key] = f"fotos/{filename}"
        except (json.JSONDecodeError, OSError):
            pass

    dip_db_path = DATA_DIR / "diputados.json"
    if dip_db_path.exists():
        db = ConsolidatedDB(dip_db_path)
        db.load()
        for name_idx_str, photo_id in db.photo_ids.items():
            name_idx = int(name_idx_str)
            if name_idx < len(db.names):
                name = db.names[name_idx]
                name_key = normalize_name(name)
                filename = f"fotos/dip_{photo_id}.jpg"
                if name_key not in photo_map:
                    photo_map[name_key] = filename

    # Propagate photos across aliases: if the canonical key has no photo but
    # its alias does (or vice-versa), copy it over so merged records get a photo.
    for alias_key, canon_key in NAME_ALIASES.items():
        if canon_key not in photo_map and alias_key in photo_map:
            photo_map[canon_key] = photo_map[alias_key]

    return photo_map


def attach_photos(legislators: dict, photo_map: dict[str, str]) -> None:
    """Adjunta rutas de foto a los registros de legisladores."""
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

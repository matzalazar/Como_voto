from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import unicodedata
from urllib.parse import quote

import requests

from .config import (
    DATA_DIR,
    FOTOS_DIR,
    HCDN_BASE,
    SENADO_BASE,
    SESSION,
    WIKI_EN_API,
    WIKI_ES_API,
    WIKIDATA_API,
    WIKI_THUMB_SIZE,
)
from .db import ConsolidatedDB
from .http import download_photo, fetch
from .io import save_json

log = logging.getLogger("scraper")


def scrape_diputados_photos():
    """Download diputado photos using photo_ids from the consolidated DB."""
    log.info("=" * 60)
    log.info("DOWNLOADING DIPUTADOS PHOTOS")
    log.info("=" * 60)

    db = ConsolidatedDB(DATA_DIR / "diputados.json")
    db.load()

    if not db.photo_ids:
        log.warning("No photo_ids found in diputados database")
        return

    name_to_file: dict[str, str] = {}
    downloaded = 0
    skipped = 0

    for ni_str, photo_id in db.photo_ids.items():
        ni = int(ni_str)
        if ni >= len(db.names):
            continue
        name = db.names[ni]

        url = f"{HCDN_BASE}/assets/diputados/{photo_id}"
        filename = f"dip_{photo_id}.jpg"
        dest = FOTOS_DIR / filename

        if dest.exists() and dest.stat().st_size > 500:
            skipped += 1
            name_to_file[name] = filename
        elif download_photo(url, filename):
            downloaded += 1
            name_to_file[name] = filename

    log.info("Diputado photos: %s new, %s already existed", downloaded, skipped)

    save_json(DATA_DIR / "diputados_photos.json", name_to_file)
    log.info("Saved diputados photo mapping (%s entries)", len(name_to_file))


def scrape_senadores_photos():
    """Download senator photos from the Senado open data JSON API."""
    log.info("=" * 60)
    log.info("DOWNLOADING SENADORES PHOTOS")
    log.info("=" * 60)

    url = f"{SENADO_BASE}/micrositios/DatosAbiertos/ExportarListadoSenadores/json"
    resp = fetch(url, delay=0.5)
    if resp is None:
        log.warning("Could not fetch Senado open data JSON")
        return

    try:
        data = resp.json()
    except (json.JSONDecodeError, ValueError):
        log.warning("Invalid JSON from Senado open data")
        return

    rows = data.get("table", {}).get("rows", [])
    log.info("Found %s senators in open data", len(rows))

    name_to_file: dict[str, str] = {}
    downloaded = 0
    skipped = 0

    for row in rows:
        sen_id = row.get("ID", "")
        apellido = row.get("APELLIDO", "").strip()
        nombre = row.get("NOMBRE", "").strip()

        if not sen_id:
            continue

        foto_url = f"{SENADO_BASE}/bundles/senadosenadores/images/fsenaG/{sen_id}.gif"
        full_name = f"{apellido}, {nombre}".strip()
        filename = f"sen_{sen_id}.gif"
        dest = FOTOS_DIR / filename

        if dest.exists() and dest.stat().st_size > 500:
            skipped += 1
            name_to_file[full_name] = filename
        elif download_photo(foto_url, filename):
            downloaded += 1
            name_to_file[full_name] = filename

    log.info("Senator photos: %s new, %s already existed", downloaded, skipped)
    save_json(DATA_DIR / "senadores_photos.json", name_to_file)
    log.info("Saved senadores photo mapping (%s entries)", len(name_to_file))


def _name_to_search_query(name: str, chamber: str = "diputado") -> str:
    """Convert 'LASTNAME, Firstname' to a Wikipedia search query."""
    name = name.strip()
    if "NO INCORPORADO" in name.upper() or "LEGISLADOR" in name.upper():
        return ""

    if "," in name:
        parts = name.split(",", 1)
        lastname = parts[0].strip().title()
        firstname = parts[1].strip().title() if len(parts) > 1 else ""
        search_name = f"{firstname} {lastname}".strip()
    else:
        search_name = name.strip().title()

    chamber_term = "diputado" if chamber == "diputados" else "senador"
    return f"{search_name} {chamber_term} Argentina"


def _safe_filename(name: str) -> str:
    """Generate a safe filename from a legislator name."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_name).strip("_").lower()
    if len(safe) > 40:
        safe = safe[:40]
    name_hash = hashlib.md5(name.encode("utf-8")).hexdigest()[:6]
    return f"wiki_{safe}_{name_hash}"


def search_wikipedia_photo(name: str, chamber: str = "diputados") -> str | None:
    """Search Wikipedia for a legislator photo URL."""
    query = _name_to_search_query(name, chamber)
    if not query:
        return None

    url = search_wikipedia_photo_from_wiki(query, WIKI_ES_API)
    if url:
        return url

    url = search_wikipedia_photo_from_wiki(query, WIKI_EN_API)
    if url:
        return url

    return search_wikidata_photo(query)


def search_wikipedia_photo_from_wiki(query: str, api_base: str) -> str | None:
    """Search a Wikipedia instance and return a thumbnail URL if found."""
    search_params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": 3,
        "srprop": "snippet",
    }
    try:
        time.sleep(0.2)
        resp = SESSION.get(api_base, params=search_params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError, ValueError):
        return None

    results = data.get("query", {}).get("search", [])
    if not results:
        return None

    for result in results:
        title = result.get("title", "")
        if not title:
            continue

        snippet = result.get("snippet", "").lower()
        if result != results[0]:
            political_kw = [
                "diputad",
                "senad",
                "legislad",
                "polític",
                "politic",
                "congres",
                "cámara",
                "camara",
                "bloque",
                "partido",
                "radical",
                "peronist",
                "justiciali",
                "ucr",
                "libertad avanza",
                "pro ",
                "kirchner",
            ]
            if not any(kw in snippet for kw in political_kw):
                continue

        img_params = {
            "action": "query",
            "titles": title,
            "prop": "pageimages",
            "format": "json",
            "pithumbsize": WIKI_THUMB_SIZE,
        }
        try:
            time.sleep(0.15)
            resp = SESSION.get(api_base, params=img_params, timeout=15)
            resp.raise_for_status()
            img_data = resp.json()
        except (requests.RequestException, json.JSONDecodeError, ValueError):
            continue

        pages = img_data.get("query", {}).get("pages", {})
        for page_info in pages.values():
            thumb = page_info.get("thumbnail", {})
            source = thumb.get("source", "")
            if source:
                return source

    return None


def search_wikidata_photo(query: str) -> str | None:
    """Search Wikidata for a person and return their P18 image URL."""
    search_params = {
        "action": "wbsearchentities",
        "search": query.replace(" diputado Argentina", "").replace(
            " senador Argentina", ""
        ),
        "language": "es",
        "format": "json",
        "limit": 3,
        "type": "item",
    }
    try:
        time.sleep(0.2)
        resp = SESSION.get(WIKIDATA_API, params=search_params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError, ValueError):
        return None

    entities = data.get("search", [])
    for entity in entities:
        entity_id = entity.get("id", "")
        if not entity_id:
            continue

        claims_params = {
            "action": "wbgetclaims",
            "entity": entity_id,
            "property": "P18",
            "format": "json",
        }
        try:
            time.sleep(0.15)
            resp = SESSION.get(WIKIDATA_API, params=claims_params, timeout=15)
            resp.raise_for_status()
            claims_data = resp.json()
        except (requests.RequestException, json.JSONDecodeError, ValueError):
            continue

        claims = claims_data.get("claims", {}).get("P18", [])
        if not claims:
            continue

        try:
            image_name = claims[0]["mainsnak"]["datavalue"]["value"]
        except (KeyError, IndexError):
            continue

        if image_name:
            safe_name = image_name.replace(" ", "_")
            md5 = hashlib.md5(safe_name.encode("utf-8")).hexdigest()
            encoded_name = quote(safe_name)
            thumb_url = (
                "https://upload.wikimedia.org/wikipedia/commons/thumb/"
                f"{md5[0]}/{md5[:2]}/{encoded_name}/{WIKI_THUMB_SIZE}px-{encoded_name}"
            )
            if safe_name.lower().endswith(".svg"):
                thumb_url += ".jpg"
            return thumb_url

    return None


def _collect_names_missing_photos(chamber: str) -> list[str]:
    """Get list of legislator names that don't have photos yet."""
    if chamber == "diputados":
        db_path = DATA_DIR / "diputados.json"
        photos_path = DATA_DIR / "diputados_photos.json"
    else:
        db_path = DATA_DIR / "senadores.json"
        photos_path = DATA_DIR / "senadores_photos.json"

    if not db_path.exists():
        return []

    db = ConsolidatedDB(db_path)
    db.load()
    all_names = set(db.names)

    existing_photos: set[str] = set()
    if photos_path.exists():
        try:
            with open(photos_path, "r", encoding="utf-8") as f:
                existing_photos = set(json.load(f).keys())
        except (json.JSONDecodeError, OSError):
            pass

    missing = []
    for name in sorted(all_names):
        if name in existing_photos:
            continue
        upper = name.upper()
        if "NO INCORPORADO" in upper or "LEGISLADOR" in upper:
            continue
        if len(name) < 4:
            continue
        missing.append(name)

    return missing

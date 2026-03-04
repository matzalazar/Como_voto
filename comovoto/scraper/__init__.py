from __future__ import annotations

from .classification import LLA_KEYWORDS, PJ_KEYWORDS, PRO_KEYWORDS, classify_bloc
from .cli import main, parse_args
from .config import (
    BASE_DIR,
    DATA_DIR,
    FOTOS_DIR,
    HCDN_BASE,
    HCDN_MAX_ID,
    REQUEST_DELAY,
    SENADO_BASE,
    SENADO_YEARS,
    SESSION,
    VOTE_DECODE,
    VOTE_ENCODE,
    WIKIDATA_API,
    WIKI_EN_API,
    WIKI_ES_API,
    WIKI_THUMB_SIZE,
)
from .db import ConsolidatedDB
from .http import download_photo, fetch, fetch_soup
from .io import ensure_dirs, save_json
from .photos import (
    _collect_names_missing_photos,
    _name_to_search_query,
    _safe_filename,
    scrape_diputados_photos,
    scrape_senadores_photos,
    search_wikidata_photo,
    search_wikipedia_photo,
    search_wikipedia_photo_from_wiki,
)
from .sources import (
    scrape_diputados,
    scrape_hcdn_votacion,
    scrape_senado_actas_list,
    scrape_senado_votacion,
    scrape_senadores,
)

__all__ = [
    "BASE_DIR",
    "DATA_DIR",
    "FOTOS_DIR",
    "HCDN_BASE",
    "HCDN_MAX_ID",
    "LLA_KEYWORDS",
    "PJ_KEYWORDS",
    "PRO_KEYWORDS",
    "REQUEST_DELAY",
    "SENADO_BASE",
    "SENADO_YEARS",
    "SESSION",
    "VOTE_DECODE",
    "VOTE_ENCODE",
    "WIKIDATA_API",
    "WIKI_EN_API",
    "WIKI_ES_API",
    "WIKI_THUMB_SIZE",
    "ConsolidatedDB",
    "_collect_names_missing_photos",
    "_name_to_search_query",
    "_safe_filename",
    "classify_bloc",
    "download_photo",
    "ensure_dirs",
    "fetch",
    "fetch_soup",
    "main",
    "parse_args",
    "save_json",
    "scrape_diputados",
    "scrape_diputados_photos",
    "scrape_hcdn_votacion",
    "scrape_senado_actas_list",
    "scrape_senado_votacion",
    "scrape_senadores",
    "scrape_senadores_photos",
    "search_wikidata_photo",
    "search_wikipedia_photo",
    "search_wikipedia_photo_from_wiki",
]

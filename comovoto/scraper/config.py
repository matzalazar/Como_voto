from __future__ import annotations

from datetime import datetime
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
FOTOS_DIR = BASE_DIR / "docs" / "fotos"

HCDN_BASE = "https://votaciones.hcdn.gob.ar"
SENADO_BASE = "https://www.senado.gob.ar"

# Rate-limiting: seconds between requests
REQUEST_DELAY = 0.3

# HCDN votacion IDs: check every single ID from 1 to this value (inclusive).
# Known range covers up to 5881 as of Feb 2026. We add margin.
HCDN_MAX_ID = 6500

# Senado periods to scrape
# Available on website: 2005 onwards (earlier years have no digital records)
SENADO_YEARS = list(range(2005, datetime.now().year + 1))

# Vote code mapping (compact integer codes for storage)
VOTE_ENCODE = {
    "AFIRMATIVO": 1,
    "NEGATIVO": 2,
    "ABSTENCION": 3,
    "AUSENTE": 4,
    "PRESIDENTE": 5,
}
VOTE_DECODE = {v: k for k, v in VOTE_ENCODE.items()}

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "ComoVoto-Scraper/2.0 "
            "(https://github.com/rquiroga7/Como_voto; educational project)"
        ),
        "Accept-Language": "es-AR,es;q=0.9",
    }
)

WIKI_ES_API = "https://es.wikipedia.org/w/api.php"
WIKI_EN_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

# Thumb size for Wikipedia photos (pixels on longest side)
WIKI_THUMB_SIZE = 300

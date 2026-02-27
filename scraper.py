#!/usr/bin/env python3
"""
Como Voto - Data Scraper
========================
Scrapes voting data from:
  - Diputados: https://votaciones.hcdn.gob.ar/
  - Senadores: https://www.senado.gob.ar/votaciones/actas

Stores results in data/ directory as JSON files.
Skips votaciones already present in the local database.
"""

import json
import os
import re
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DIPUTADOS_DIR = DATA_DIR / "diputados"
SENADORES_DIR = DATA_DIR / "senadores"

HCDN_BASE = "https://votaciones.hcdn.gob.ar"
SENADO_BASE = "https://www.senado.gob.ar"

# Rate-limiting: seconds between requests
REQUEST_DELAY = 1.0

# How many years back to scrape (HCDN goes back to ~2015, period 133)
HCDN_FIRST_PERIOD = 133  # 2015
HCDN_CURRENT_YEAR = datetime.now().year

# Senado periods to scrape (format used by the website)
SENADO_YEARS = list(range(2015, datetime.now().year + 1))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("scraper")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "ComoVoto-Scraper/1.0 (https://github.com/como-voto; educational project)",
    "Accept-Language": "es-AR,es;q=0.9",
})

# ---------------------------------------------------------------------------
# Party classification helpers
# ---------------------------------------------------------------------------
# Maps bloque names → canonical coalition.
# "PJ" = Peronist coalition (PJ / FdT / FpV / UxP)
# "PRO" = PRO coalition (PRO / Cambiemos / JxC / UCR)
# "OTHER" = everything else

PJ_KEYWORDS = [
    "justicialista", "frente de todos", "frente para la victoria",
    "unión por la patria", "union por la patria",
    "frente renovador", "peronismo", "peronista",
    "frente cívico por santiago", "frente civico por santiago",
    "movimiento popular neuquino",
    # Common PJ-allied blocs
    "bloque justicialista", "pj ",
]

PRO_KEYWORDS = [
    "pro ", "propuesta republicana",
    "cambiemos", "juntos por el cambio", "juntos por el cambio federal",
    "ucr", "unión cívica radical", "union civica radical",
    "coalición cívica", "coalicion civica",
    "evolución radical", "evolucion radical",
]

LLA_KEYWORDS = [
    "la libertad avanza",
]


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
    return "OTHER"


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def ensure_dirs():
    """Create data directories if they don't exist."""
    for d in [DATA_DIR, DIPUTADOS_DIR, SENADORES_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict | list:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_index(chamber: str) -> dict:
    """Load the votaciones index for a chamber. Returns {id: metadata}."""
    path = DATA_DIR / f"{chamber}_index.json"
    return load_json(path) if path.exists() else {}


def save_index(chamber: str, index: dict):
    save_json(DATA_DIR / f"{chamber}_index.json", index)


def votacion_exists(chamber: str, votacion_id: str) -> bool:
    """Check if a votación detail file already exists."""
    chamber_dir = DIPUTADOS_DIR if chamber == "diputados" else SENADORES_DIR
    return (chamber_dir / f"{votacion_id}.json").exists()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch(url: str, delay: float = REQUEST_DELAY) -> requests.Response | None:
    """Fetch a URL with rate limiting and error handling."""
    time.sleep(delay)
    try:
        resp = SESSION.get(url, timeout=30)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        log.warning(f"Failed to fetch {url}: {e}")
        return None


def fetch_soup(url: str, delay: float = REQUEST_DELAY) -> BeautifulSoup | None:
    resp = fetch(url, delay)
    if resp is None:
        return None
    return BeautifulSoup(resp.text, "lxml")


# ===========================================================================
#  DIPUTADOS SCRAPER
# ===========================================================================

def scrape_hcdn_actas_list() -> list[dict]:
    """
    Scrape the list of all actas (votaciones) from the HCDN site.
    The site is a single-page app; the actual data comes from an API
    or is rendered via JS. We'll scrape the statistics page that
    lists all votaciones, and also try to iterate through known
    votacion IDs.
    """
    log.info("=== Scraping HCDN Diputados actas list ===")
    existing_index = load_index("diputados")
    actas = []

    # Strategy: The HCDN site renders content via JavaScript.
    # We'll try to discover votacion IDs by iterating and checking
    # which ones return valid pages.
    # First, find the latest votacion ID by trying recent ones.
    
    # Try fetching the main page to find actas links
    soup = fetch_soup(f"{HCDN_BASE}/")
    if soup is None:
        log.error("Could not fetch HCDN main page")
        return actas

    # The site uses JS heavily, so let's try to discover votacion IDs
    # by checking the statistics page which has diputado links
    # and through those, discover actas.
    # 
    # Alternative approach: iterate votacion IDs from 1 upward
    # The site has votaciones numbered sequentially from 1 
    # (seen votacion/1 dating from 2015).
    
    # Find the highest known ID
    known_ids = set(existing_index.keys())
    
    # Determine search range
    if known_ids:
        max_known = max(int(k) for k in known_ids)
        start_id = max_known + 1
    else:
        start_id = 1  # Start from the very beginning
    
    # Probe for the current max ID with binary search
    max_id = find_hcdn_max_votacion_id(start_id)
    
    if max_id < start_id:
        log.info(f"No new HCDN votaciones found (latest known: {start_id - 1})")
        return actas
    
    log.info(f"Will scrape HCDN votaciones from ID {start_id} to {max_id}")
    
    for vid in range(start_id, max_id + 1):
        vid_str = str(vid)
        if vid_str in known_ids:
            continue
        actas.append({"id": vid_str})
    
    return actas


def find_hcdn_max_votacion_id(start_from: int) -> int:
    """Find the highest votacion ID on HCDN using a probe approach."""
    # Start probing from start_from, jump ahead in steps
    current = start_from
    step = 50
    last_valid = start_from - 1

    # First, find an upper bound
    while True:
        resp = fetch(f"{HCDN_BASE}/votacion/{current}", delay=0.3)
        if resp and resp.status_code == 200 and "¿CÓMO VOTÓ?" in resp.text:
            last_valid = current
            current += step
        else:
            break
        if current > 10000:  # Safety limit
            break

    # Binary search between last_valid and current
    lo, hi = last_valid, current
    while lo < hi:
        mid = (lo + hi + 1) // 2
        resp = fetch(f"{HCDN_BASE}/votacion/{mid}", delay=0.3)
        if resp and resp.status_code == 200 and "¿CÓMO VOTÓ?" in resp.text:
            lo = mid
        else:
            hi = mid - 1

    log.info(f"HCDN max votacion ID found: {lo}")
    return lo


def scrape_hcdn_votacion(votacion_id: str) -> dict | None:
    """Scrape a single HCDN votación detail page."""
    url = f"{HCDN_BASE}/votacion/{votacion_id}"
    soup = fetch_soup(url)
    if soup is None:
        return None

    # Check if page has actual content
    if not soup.find(string=re.compile("¿CÓMO VOTÓ?")):
        return None

    result = {
        "id": votacion_id,
        "chamber": "diputados",
        "url": url,
        "title": "",
        "date": "",
        "result": "",
        "period": "",
        "type": "",
        "afirmativo": 0,
        "negativo": 0,
        "abstencion": 0,
        "ausente": 0,
        "votes": [],
    }

    # Title - in h4 element, may include date appended
    title_el = soup.find("h4")
    if title_el:
        raw_title = title_el.get_text(strip=True)
        # Split title from date (date pattern: DD/MM/YYYY)
        date_match = re.search(r"(\d{2}/\d{2}/\d{4}\s*-?\s*\d{2}:\d{2})", raw_title)
        if date_match:
            result["date"] = date_match.group(1).strip()
            result["title"] = raw_title[:date_match.start()].strip()
        else:
            result["title"] = raw_title

    # Period info - in the page header h5
    period_el = soup.find("h5", string=re.compile(r"Período"))
    if period_el:
        result["period"] = period_el.get_text(strip=True)

    # Date fallback - look for date pattern in h5 elements
    if not result["date"]:
        for h5 in soup.find_all("h5"):
            text = h5.get_text(strip=True)
            dm = re.search(r"\d{2}/\d{2}/\d{4}", text)
            if dm:
                result["date"] = text
                break

    # Result (AFIRMATIVO/NEGATIVO)
    result_h3 = soup.find("h3")
    if result_h3:
        result["result"] = result_h3.get_text(strip=True)

    # Vote counts
    count_sections = soup.find_all("h3")
    labels = soup.find_all("h4")
    for h3, h4 in zip(count_sections, labels):
        try:
            count = int(h3.get_text(strip=True))
            label = h4.get_text(strip=True).upper()
            if "AFIRMATIVO" in label:
                result["afirmativo"] = count
            elif "NEGATIVO" in label:
                result["negativo"] = count
            elif "ABSTENCI" in label:
                result["abstencion"] = count
            elif "AUSENTE" in label:
                result["ausente"] = count
        except (ValueError, AttributeError):
            continue

    # Individual votes - from the table
    # Columns: [photo/empty, NAME, BLOQUE, PROVINCIA, VOTE, optional]
    table = soup.find("table")
    if table:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 5:
                # Cell 0 = photo (skip), Cell 1 = name, Cell 2 = bloc,
                # Cell 3 = province, Cell 4 = vote
                name = cells[1].get_text(strip=True)
                bloc = cells[2].get_text(strip=True)
                province = cells[3].get_text(strip=True)
                vote = cells[4].get_text(strip=True)

                if name and vote:
                    result["votes"].append({
                        "name": name,
                        "bloc": bloc,
                        "province": province,
                        "vote": vote.upper(),
                        "coalition": classify_bloc(bloc),
                    })

    return result


# ===========================================================================
#  SENADO SCRAPER
# ===========================================================================

def scrape_senado_actas_list(year: int) -> list[dict]:
    """
    Scrape the list of actas from the Senado for a given year/period.
    Returns list of acta metadata dicts with 'id' and basic info.
    """
    log.info(f"=== Scraping Senado actas list for {year} ===")
    existing_index = load_index("senadores")
    
    url = f"{SENADO_BASE}/votaciones/actas"
    # The Senado site uses a form POST to filter by period
    # Try fetching with period parameter
    actas = []
    
    # The site paginates - we need to fetch all pages
    page = 1
    while True:
        params = {
            "periodo": str(year),
            "page": str(page),
        }
        resp = fetch(f"{url}?periodo={year}&page={page}")
        if resp is None:
            break
        
        soup = BeautifulSoup(resp.text, "lxml")
        
        # Find acta links - they follow pattern /votaciones/detalleActa/XXXX
        detail_links = soup.find_all("a", href=re.compile(r"/votaciones/detalleActa/(\d+)"))
        
        if not detail_links:
            break
        
        for link in detail_links:
            match = re.search(r"/votaciones/detalleActa/(\d+)", link["href"])
            if match:
                acta_id = match.group(1)
                if acta_id not in existing_index:
                    actas.append({
                        "id": acta_id,
                        "text": link.get_text(strip=True),
                    })
        
        # Check for next page
        next_link = soup.find("a", string=re.compile("Siguiente"))
        if next_link and "href" in next_link.attrs:
            page += 1
        else:
            break
    
    log.info(f"Found {len(actas)} new Senado actas for {year}")
    return actas


def scrape_senado_votacion(acta_id: str) -> dict | None:
    """Scrape a single Senado votación detail page."""
    url = f"{SENADO_BASE}/votaciones/detalleActa/{acta_id}"
    soup = fetch_soup(url)
    if soup is None:
        return None

    result = {
        "id": acta_id,
        "chamber": "senadores",
        "url": url,
        "title": "",
        "date": "",
        "result": "",
        "type": "",
        "afirmativo": 0,
        "negativo": 0,
        "abstencion": 0,
        "ausente": 0,
        "votes": [],
    }

    # Title
    # The title is usually in the main content area
    content = soup.find("div", class_=re.compile("content|main|votacion", re.I))
    if not content:
        content = soup  # fallback to whole page

    # Primary strategy: find the <p> immediately after "Acta Nro:" <p>
    acta_nro_p = content.find("p", string=re.compile(r"Acta Nro", re.I))
    if acta_nro_p:
        for sib in acta_nro_p.find_next_siblings():
            if sib.name == "p":
                t = sib.get_text(strip=True)
                if t and "Secretaría" not in t and "Honorable" not in t:
                    result["title"] = t[:300]
                    break

    # Fallback: keyword search in text nodes
    if not result["title"]:
        for text_node in content.find_all(string=True):
            text = text_node.strip()
            if len(text) > 20 and ("ley" in text.lower() or "proyecto" in text.lower() 
                                    or "pliego" in text.lower() or "acuerdo" in text.lower()
                                    or "modificación" in text.lower() or "régimen" in text.lower()
                                    or "designación" in text.lower() or "modernización" in text.lower()):
                result["title"] = text[:300]
                break

    # If still no title found, try h1/h2/h3 elements
    if not result["title"]:
        for tag in ["h2", "h3", "h1"]:
            el = content.find(tag)
            if el and len(el.get_text(strip=True)) > 10:
                result["title"] = el.get_text(strip=True)
                break

    # Date - look for date patterns
    date_match = re.search(
        r"(\d{2}/\d{2}/\d{4})\s*-?\s*(\d{2}:\d{2})?",
        content.get_text()
    )
    if date_match:
        result["date"] = date_match.group(0).strip()

    # Result
    for text in content.find_all(string=re.compile(r"AFIRMATIVO|NEGATIVO", re.I)):
        result["result"] = text.strip()
        break

    # Type (EN GENERAL / EN PARTICULAR)
    for text in content.find_all(string=re.compile(r"EN GENERAL|EN PARTICULAR", re.I)):
        result["type"] = text.strip()
        break

    # Vote counts
    count_headers = content.find_all("h3")
    count_labels = content.find_all("h4")
    for h3, h4 in zip(count_headers, count_labels):
        try:
            count = int(h3.get_text(strip=True))
            label = h4.get_text(strip=True).upper()
            if "AFIRMATIVO" in label:
                result["afirmativo"] = count
            elif "NEGATIVO" in label:
                result["negativo"] = count
            elif "ABSTENCI" in label:
                result["abstencion"] = count
            elif "AUSENTE" in label:
                result["ausente"] = count
        except (ValueError, AttributeError):
            continue

    # Individual votes from the table
    # Columns: [photo/empty, NAME, BLOQUE, PROVINCIA, VOTE]
    # The detail page shows all votes at once (no pagination needed)
    table = content.find("table")
    if table:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 5:
                # Cell 0 = photo (skip), Cell 1 = name, Cell 2 = bloc,
                # Cell 3 = province, Cell 4 = vote
                name = cells[1].get_text(strip=True)
                bloc = cells[2].get_text(strip=True)
                province = cells[3].get_text(strip=True)
                vote = cells[4].get_text(strip=True)

                # Clean up name (remove "Foto de..." prefix if present)
                name = re.sub(r"^Foto de.*?Nacional\s*", "", name).strip()

                if name and vote:
                    result["votes"].append({
                        "name": name,
                        "bloc": bloc,
                        "province": province,
                        "vote": vote.upper(),
                        "coalition": classify_bloc(bloc),
                    })

    return result


# ===========================================================================
#  MAIN ORCHESTRATION
# ===========================================================================

def scrape_diputados():
    """Scrape all new Diputados votaciones."""
    log.info("=" * 60)
    log.info("SCRAPING DIPUTADOS")
    log.info("=" * 60)
    
    existing_index = load_index("diputados")
    actas = scrape_hcdn_actas_list()
    
    new_count = 0
    for acta in actas:
        vid = acta["id"]
        if votacion_exists("diputados", vid):
            log.info(f"  Skipping diputados votacion {vid} (already exists)")
            continue
        
        log.info(f"  Scraping diputados votacion {vid}...")
        data = scrape_hcdn_votacion(vid)
        if data and data.get("votes"):
            save_json(DIPUTADOS_DIR / f"{vid}.json", data)
            existing_index[vid] = {
                "title": data.get("title", ""),
                "date": data.get("date", ""),
                "result": data.get("result", ""),
            }
            new_count += 1
            log.info(f"    Saved: {data.get('title', 'Unknown')[:80]}")
        else:
            log.warning(f"    No vote data found for votacion {vid}")
    
    save_index("diputados", existing_index)
    log.info(f"Diputados: scraped {new_count} new votaciones")


def scrape_senadores():
    """Scrape all new Senado votaciones."""
    log.info("=" * 60)
    log.info("SCRAPING SENADORES")
    log.info("=" * 60)
    
    existing_index = load_index("senadores")
    
    new_count = 0
    for year in SENADO_YEARS:
        actas = scrape_senado_actas_list(year)
        
        for acta in actas:
            aid = acta["id"]
            if votacion_exists("senadores", aid):
                log.info(f"  Skipping senado votacion {aid} (already exists)")
                continue
            
            log.info(f"  Scraping senado votacion {aid}...")
            data = scrape_senado_votacion(aid)
            if data and data.get("votes"):
                save_json(SENADORES_DIR / f"{aid}.json", data)
                existing_index[aid] = {
                    "title": data.get("title", ""),
                    "date": data.get("date", ""),
                    "result": data.get("result", ""),
                }
                new_count += 1
                log.info(f"    Saved: {data.get('title', 'Unknown')[:80]}")
            else:
                log.warning(f"    No vote data found for senado votacion {aid}")
    
    save_index("senadores", existing_index)
    log.info(f"Senadores: scraped {new_count} new votaciones")


def main():
    ensure_dirs()
    
    log.info("Como Voto - Data Scraper")
    log.info(f"Data directory: {DATA_DIR}")
    
    # Parse CLI args
    chambers = sys.argv[1:] if len(sys.argv) > 1 else ["diputados", "senadores"]
    
    if "diputados" in chambers:
        scrape_diputados()
    
    if "senadores" in chambers:
        scrape_senadores()
    
    log.info("Scraping complete!")


if __name__ == "__main__":
    main()

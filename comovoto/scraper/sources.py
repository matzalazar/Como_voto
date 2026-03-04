from __future__ import annotations

import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from .classification import classify_bloc
from .config import (
    DATA_DIR,
    HCDN_BASE,
    HCDN_MAX_ID,
    REQUEST_DELAY,
    SENADO_BASE,
    SENADO_YEARS,
    SESSION,
)
from .db import ConsolidatedDB
from .http import fetch, fetch_soup

log = logging.getLogger("scraper")


def _extract_vote_counts(scope: BeautifulSoup, result: dict):
    """Fill vote counters by pairing each label with its nearest previous h3."""
    for h4 in scope.find_all("h4"):
        label = h4.get_text(" ", strip=True).upper()
        h3 = h4.find_previous("h3")
        if h3 is None:
            continue
        try:
            count = int(h3.get_text(strip=True))
        except (TypeError, ValueError):
            continue

        if "AFIRMATIVO" in label:
            result["afirmativo"] = count
        elif "NEGATIVO" in label:
            result["negativo"] = count
        elif "ABSTENCI" in label:
            result["abstencion"] = count
        elif "AUSENTE" in label:
            result["ausente"] = count


def scrape_hcdn_votacion(votacion_id: str) -> dict | None:
    """Scrape a single HCDN votacion detail page."""
    url = f"{HCDN_BASE}/votacion/{votacion_id}"
    resp = fetch(url, delay=REQUEST_DELAY, raise_for_status=False)
    if resp is None or resp.status_code != 200:
        return None
    soup = BeautifulSoup(resp.text, "lxml")

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

    title_el = soup.find("h4")
    if title_el:
        raw_title = title_el.get_text(strip=True)
        date_match = re.search(
            r"(\d{2}/\d{2}/\d{4}\s*-?\s*\d{2}:\d{2})", raw_title
        )
        if date_match:
            result["date"] = date_match.group(1).strip()
            result["title"] = raw_title[: date_match.start()].strip()
        else:
            result["title"] = raw_title

    period_el = soup.find("h5", string=re.compile(r"Período"))
    if period_el:
        result["period"] = period_el.get_text(strip=True)

    if not result["date"]:
        for h5 in soup.find_all("h5"):
            text = h5.get_text(strip=True)
            dm = re.search(r"\d{2}/\d{2}/\d{4}", text)
            if dm:
                result["date"] = text
                break

    result_h3 = soup.find("h3")
    if result_h3:
        result["result"] = result_h3.get_text(strip=True)

    _extract_vote_counts(soup, result)

    table = soup.find("table")
    if table:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 5:
                photo_id = ""
                photo_link = cells[0].find("a", href=True)
                if photo_link:
                    photo_id = photo_link["href"].rstrip("/").split("/")[-1]

                name = cells[1].get_text(strip=True)
                bloc = cells[2].get_text(strip=True)
                province = cells[3].get_text(strip=True)
                vote = cells[4].get_text(strip=True)

                if name and vote:
                    vote_entry = {
                        "name": name,
                        "bloc": bloc,
                        "province": province,
                        "vote": vote.upper(),
                        "coalition": classify_bloc(bloc),
                    }
                    if photo_id:
                        vote_entry["photo_id"] = photo_id
                    result["votes"].append(vote_entry)

    return result


def scrape_diputados():
    """Scrape all Diputados votaciones."""
    log.info("=" * 60)
    log.info("SCRAPING DIPUTADOS (IDs 1 to %d)", HCDN_MAX_ID)
    log.info("=" * 60)

    db = ConsolidatedDB(DATA_DIR / "diputados.json")
    db.load()
    log.info("Existing DB: %s votaciones, %s names", len(db.votaciones), len(db.names))

    new_count = 0
    checked = 0

    for vid_int in range(1, HCDN_MAX_ID + 1):
        vid = str(vid_int)
        if db.has_votacion(vid):
            continue

        checked += 1
        data = scrape_hcdn_votacion(vid)

        if data and data.get("votes"):
            db.add_votacion(data)
            new_count += 1

            if new_count % 50 == 0:
                db.save()
                log.info(
                    "  Checkpoint: saved %s new (ID %s, checked %s)",
                    new_count,
                    vid,
                    checked,
                )

            log.info("  [%s] Saved: %s", vid, data.get("title", "")[:80])

        if checked % 500 == 0:
            log.info(
                "  Progress: checked %s, saved %s new, at ID %s",
                checked,
                new_count,
                vid_int,
            )

    db.save()
    log.info(
        "Diputados: scraped %s new votaciones (checked %s IDs, total in DB: %s)",
        new_count,
        checked,
        len(db.votaciones),
    )


def scrape_senado_actas_list(year: int, existing_ids: set[str]) -> list[dict]:
    """Scrape Senado acta list for a given year."""
    log.info("=== Scraping Senado actas list for %s ===", year)

    url = f"{SENADO_BASE}/votaciones/actas"
    actas = []
    form_data = {"busqueda_actas[anio]": str(year)}

    time.sleep(REQUEST_DELAY)
    try:
        resp = SESSION.post(url, data=form_data, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("Failed to fetch Senado actas for %s: %s", year, exc)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    detail_links = soup.find_all("a", href=re.compile(r"/votaciones/detalleActa/(\d+)"))

    for link in detail_links:
        match = re.search(r"/votaciones/detalleActa/(\d+)", link["href"])
        if match:
            acta_id = match.group(1)
            if acta_id not in existing_ids:
                actas.append({"id": acta_id, "text": link.get_text(strip=True)})

    log.info("Found %s new Senado actas for %s", len(actas), year)
    return actas


def scrape_senado_votacion(acta_id: str) -> dict | None:
    """Scrape a single Senado votacion detail page."""
    url = f"{SENADO_BASE}/votaciones/detalleActa/{acta_id}"
    soup = fetch_soup(url, delay=0.5)
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

    content = soup.find("div", class_=re.compile("content|main|votacion", re.I))
    if not content:
        content = soup

    acta_nro_p = content.find("p", string=re.compile(r"Acta Nro", re.I))
    if acta_nro_p:
        for sib in acta_nro_p.find_next_siblings():
            if sib.name == "p":
                text = sib.get_text(strip=True)
                if text and "Secretaría" not in text and "Honorable" not in text:
                    result["title"] = text[:300]
                    break

    if not result["title"]:
        for text_node in content.find_all(string=True):
            text = text_node.strip()
            if len(text) > 20 and any(
                kw in text.lower()
                for kw in [
                    "ley",
                    "proyecto",
                    "pliego",
                    "acuerdo",
                    "modificación",
                    "régimen",
                    "designación",
                    "modernización",
                ]
            ):
                result["title"] = text[:300]
                break

    if not result["title"]:
        for tag in ["h2", "h3", "h1"]:
            el = content.find(tag)
            if el and len(el.get_text(strip=True)) > 10:
                result["title"] = el.get_text(strip=True)
                break

    date_match = re.search(r"(\d{2}/\d{2}/\d{4})\s*-?\s*(\d{2}:\d{2})?", content.get_text())
    if date_match:
        result["date"] = date_match.group(0).strip()

    for text in content.find_all(string=re.compile(r"AFIRMATIVO|NEGATIVO", re.I)):
        result["result"] = text.strip()
        break

    for text in content.find_all(string=re.compile(r"EN GENERAL|EN PARTICULAR", re.I)):
        result["type"] = text.strip()
        break

    _extract_vote_counts(content, result)

    table = content.find("table")
    if table:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 5:
                name = cells[1].get_text(strip=True)
                bloc = cells[2].get_text(strip=True)
                province = cells[3].get_text(strip=True)
                vote = cells[4].get_text(strip=True)

                name = re.sub(r"^Foto de.*?Nacional\s*", "", name).strip()

                if name and vote:
                    result["votes"].append(
                        {
                            "name": name,
                            "bloc": bloc,
                            "province": province,
                            "vote": vote.upper(),
                            "coalition": classify_bloc(bloc),
                        }
                    )

    return result


def scrape_senadores():
    """Scrape all new Senado votaciones."""
    log.info("=" * 60)
    log.info("SCRAPING SENADORES")
    log.info("=" * 60)

    db = ConsolidatedDB(DATA_DIR / "senadores.json")
    db.load()
    existing_ids = db._votacion_ids.copy()
    log.info("Existing DB: %s votaciones", len(db.votaciones))

    new_count = 0
    for year in SENADO_YEARS:
        actas = scrape_senado_actas_list(year, existing_ids)

        for acta in actas:
            aid = acta["id"]
            if db.has_votacion(aid):
                log.info("  Skipping senado votacion %s (already exists)", aid)
                continue

            log.info("  Scraping senado votacion %s...", aid)
            data = scrape_senado_votacion(aid)
            if data and data.get("votes"):
                db.add_votacion(data)
                new_count += 1
                log.info("    Saved: %s", data.get("title", "Unknown")[:80])
            else:
                log.warning("    No vote data for senado votacion %s", aid)

    db.save()
    log.info(
        "Senadores: scraped %s new votaciones (total in DB: %s)",
        new_count,
        len(db.votaciones),
    )

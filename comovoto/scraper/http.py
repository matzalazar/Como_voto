from __future__ import annotations

import logging
import time

import requests
from bs4 import BeautifulSoup

from .config import FOTOS_DIR, REQUEST_DELAY, SESSION

log = logging.getLogger("scraper")


def fetch(
    url: str,
    delay: float = REQUEST_DELAY,
    raise_for_status: bool = True,
) -> requests.Response | None:
    """Fetch a URL with rate limiting and error handling."""
    time.sleep(delay)
    try:
        resp = SESSION.get(url, timeout=30)
        if raise_for_status:
            resp.raise_for_status()
        return resp
    except requests.RequestException as exc:
        if not isinstance(exc, requests.HTTPError):
            log.warning("Failed to fetch %s: %s", url, exc)
        return None


def fetch_soup(url: str, delay: float = REQUEST_DELAY) -> BeautifulSoup | None:
    resp = fetch(url, delay)
    if resp is None:
        return None
    return BeautifulSoup(resp.text, "lxml")


def download_photo(url: str, filename: str) -> bool:
    """Download a photo to docs/fotos/. Returns True on success."""
    dest = FOTOS_DIR / filename
    if dest.exists() and dest.stat().st_size > 500:
        return True
    try:
        time.sleep(0.15)
        resp = SESSION.get(url, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 500:
            with open(dest, "wb") as f:
                f.write(resp.content)
            return True
    except requests.RequestException:
        pass
    return False

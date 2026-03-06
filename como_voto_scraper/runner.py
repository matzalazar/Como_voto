from __future__ import annotations

import sys

from .core import DATA_DIR, DEFAULT_RUN_TARGETS, ensure_dirs, log
from .hcdn import scrape_diputados
from .photos import scrape_diputados_photos, scrape_senadores_photos
from .senado import scrape_senadores


def parse_run_targets(argv: list[str]) -> set[str]:
    """Normalize CLI args into task names, defaulting to the full pipeline."""
    if not argv:
        return set(DEFAULT_RUN_TARGETS)
    return {arg.lower() for arg in argv}


def run_photo_scrapers() -> None:
    scrape_diputados_photos()
    scrape_senadores_photos()


def main() -> None:
    ensure_dirs()

    log.info("Como Voto - Data Scraper v2 (consolidated JSON)")
    log.info(f"Data directory: {DATA_DIR}")

    targets = parse_run_targets(sys.argv[1:])

    if "diputados" in targets:
        scrape_diputados()

    if "senadores" in targets:
        scrape_senadores()

    if "fotos" in targets:
        run_photo_scrapers()

    log.info("Scraping complete!")

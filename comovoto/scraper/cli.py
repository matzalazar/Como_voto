from __future__ import annotations

import logging
import sys

from .config import DATA_DIR
from .io import ensure_dirs
from .photos import scrape_diputados_photos, scrape_senadores_photos
from .sources import scrape_diputados, scrape_senadores


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("scraper")


def parse_args(args: list[str]) -> list[str]:
    """Parse CLI args and return enabled tasks."""
    if not args:
        return ["diputados", "senadores", "fotos"]

    normalized = [a.lower().strip() for a in args if a.strip()]
    valid = {"diputados", "senadores", "fotos"}
    unknown = [a for a in normalized if a not in valid]
    if unknown:
        raise SystemExit(
            "Argumentos inválidos: "
            f"{', '.join(unknown)}. Usá: diputados senadores fotos"
        )
    return normalized


def main(argv: list[str] | None = None):
    ensure_dirs()

    log.info("Como Voto - Data Scraper v2 (consolidated JSON)")
    log.info("Data directory: %s", DATA_DIR)

    args = parse_args(argv if argv is not None else sys.argv[1:])

    if "diputados" in args:
        scrape_diputados()

    if "senadores" in args:
        scrape_senadores()

    if "fotos" in args:
        scrape_diputados_photos()
        scrape_senadores_photos()

    log.info("Scraping complete!")

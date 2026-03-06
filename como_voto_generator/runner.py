from __future__ import annotations

from .common import DATA_DIR, log
from .data_loading import attach_photos, load_all_votaciones_from_db, load_photo_maps
from .export import generate_site_data
from .laws import build_law_groups
from .processing import build_legislator_data


def main() -> None:
    log.info("Como Voto - Data Processor")
    log.info(f"Loading votaciones from {DATA_DIR}")

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

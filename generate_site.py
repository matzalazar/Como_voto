#!/usr/bin/env python3
"""Punto de entrada y fachada del generador de sitio compatible hacia atrás.

Este módulo mantiene funcionando `python generate_site.py` y
`from generate_site import ...`, mientras la implementación vive en
`como_voto_generator/`.
"""

from como_voto_generator import (
    COMMON_NORM,
    NAME_ALIASES,
    _article_from_slug,
    _classify_bloc_for_term,
    _clean_votacion_title,
    _era_coalition,
    _kw_matches,
    _normalize_bloc_display,
    attach_photos,
    build_law_detail_data,
    build_law_groups,
    build_legislator_data,
    classify_bloc_mapped,
    classify_bloc_party,
    clean_date,
    compute_combined_majority,
    compute_era_alignment,
    compute_majority_vote,
    compute_per_coalition_alignment,
    compute_terms,
    compute_weighted_alignment,
    extract_law_group_key,
    extract_section_label,
    extract_year,
    generate_site_data,
    get_common_name,
    is_contested,
    load_all_votaciones_from_db,
    load_photo_maps,
    main,
    normalize_name,
    normalize_province,
    normalize_vote,
    practical_year_range,
    save_json,
)

__all__ = [
    "COMMON_NORM",
    "NAME_ALIASES",
    "_article_from_slug",
    "_classify_bloc_for_term",
    "_clean_votacion_title",
    "_era_coalition",
    "_kw_matches",
    "_normalize_bloc_display",
    "attach_photos",
    "build_law_detail_data",
    "build_law_groups",
    "build_legislator_data",
    "classify_bloc_mapped",
    "classify_bloc_party",
    "clean_date",
    "compute_combined_majority",
    "compute_era_alignment",
    "compute_majority_vote",
    "compute_per_coalition_alignment",
    "compute_terms",
    "compute_weighted_alignment",
    "extract_law_group_key",
    "extract_section_label",
    "extract_year",
    "generate_site_data",
    "get_common_name",
    "is_contested",
    "load_all_votaciones_from_db",
    "load_photo_maps",
    "main",
    "normalize_name",
    "normalize_province",
    "normalize_vote",
    "practical_year_range",
    "save_json",
]


if __name__ == "__main__":
    main()

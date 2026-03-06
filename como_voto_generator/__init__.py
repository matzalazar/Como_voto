from .common import save_json
from .data_loading import (
    attach_photos,
    clean_date,
    extract_year,
    load_all_votaciones_from_db,
    load_photo_maps,
    practical_year_range,
)
from .export import (
    build_law_detail_data,
    compute_era_alignment,
    compute_terms,
    compute_weighted_alignment,
    generate_site_data,
)
from .laws import COMMON_NORM, _kw_matches, build_law_groups, extract_law_group_key, get_common_name
from .normalization import (
    NAME_ALIASES,
    _clean_votacion_title,
    classify_bloc_party,
    extract_section_label,
    normalize_name,
    normalize_province,
    normalize_vote,
)
from .processing import (
    _article_from_slug,
    build_legislator_data,
    compute_combined_majority,
    compute_majority_vote,
    is_contested,
)
from .runner import main

__all__ = [
    "COMMON_NORM",
    "NAME_ALIASES",
    "_article_from_slug",
    "_clean_votacion_title",
    "_kw_matches",
    "attach_photos",
    "build_law_detail_data",
    "build_law_groups",
    "build_legislator_data",
    "classify_bloc_party",
    "clean_date",
    "compute_combined_majority",
    "compute_era_alignment",
    "compute_majority_vote",
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

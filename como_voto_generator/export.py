from __future__ import annotations

import re
import time
from collections import defaultdict
from datetime import datetime

from .common import DOCS_DATA_DIR, log, save_json
from .data_loading import clean_date, extract_year, load_all_votaciones_from_db, practical_year_range
from .laws import get_common_name
from .normalization import NAME_ALIASES, classify_bloc_party, extract_section_label, normalize_name, normalize_vote

_PARTY_KEYS = ("pj", "ucr", "pro", "lla", "cc", "oth")


def build_law_detail_data(law_groups: dict) -> tuple[list[dict], dict[int, dict]]:
    """Construye el desglose de votos por ley y por partido para búsqueda de leyes."""
    laws: list[dict] = []
    all_vote_names: dict[int, dict[str, list[list[str]]]] = {}
    name_set: set[str] = set()
    votacion_counter = 0

    for group in law_groups.values():
        votaciones_raw = group.get("votaciones", [])
        if not votaciones_raw:
            continue

        display_name = group.get("common_name") or group.get("title", "")
        if not display_name or len(display_name.strip()) < 3:
            continue

        year: int | None = None
        chamber = group.get("chamber", "")
        for votacion in votaciones_raw:
            y = extract_year(votacion.get("date", ""))
            if y:
                year = y
                break
            if not chamber:
                chamber = votacion.get("chamber", "")

        vs_out: list[dict] = []
        for votacion in votaciones_raw:
            votes_list = votacion.get("votes", [])
            if not votes_list:
                continue

            # Tally votes per real party (not coalition)
            tallies: dict[str, list[int]] = {
                "pj": [0, 0, 0, 0],
                "ucr": [0, 0, 0, 0],
                "pro": [0, 0, 0, 0],
                "lla": [0, 0, 0, 0],
                "cc": [0, 0, 0, 0],
                "oth": [0, 0, 0, 0],
            }
            total = [0, 0, 0, 0]

            vote_idx = {
                "AFIRMATIVO": 0,
                "NEGATIVO": 1,
                "ABSTENCION": 2,
                "AUSENTE": 3,
            }

            names: dict[str, list[list[str]]] = {party_key: [[], [], [], []] for party_key in _PARTY_KEYS}

            for vote_row in votes_list:
                vote_str = normalize_vote(vote_row.get("vote", ""))
                idx = vote_idx.get(vote_str)
                if idx is None:
                    continue

                party = classify_bloc_party(vote_row.get("bloc", ""))
                party_key = party.lower() if party != "OTROS" else "oth"

                tallies[party_key][idx] += 1
                total[idx] += 1

                leg_name = vote_row.get("name", "").strip()
                if leg_name:
                    norm = normalize_name(leg_name)
                    norm = NAME_ALIASES.get(norm, norm)
                    names[party_key][idx].append(norm)
                    name_set.add(norm)

            if sum(total) == 0:
                continue

            vi = votacion_counter
            votacion_counter += 1
            all_vote_names[vi] = names

            title_str = votacion.get("title", "")
            vtype = votacion.get("type", "")
            tp_label = extract_section_label(title_str, vtype)

            entry: dict = {
                "t": title_str[:200],
                "tp": tp_label,
                "d": clean_date(votacion.get("date", "")),
                "r": votacion.get("result", ""),
                "vi": vi,
                "tot": total,
                "pj": tallies["pj"],
                "ucr": tallies["ucr"],
                "pro": tallies["pro"],
                "lla": tallies["lla"],
                "cc": tallies["cc"],
                "oth": tallies["oth"],
            }

            vid = votacion.get("id")
            if vid:
                entry["id"] = vid
            url = votacion.get("url", "")
            if url:
                entry["url"] = url

            vs_out.append(entry)

        if not vs_out:
            continue

        law_entry: dict = {
            "n": (display_name[:120]).strip(),
            "y": year,
            "ch": chamber,
            "vs": vs_out,
        }
        if group.get("common_name"):
            law_entry["cn"] = group["common_name"]

        laws.append(law_entry)

    # Sort: notable (common_name) first, then by year desc, then by name
    laws.sort(key=lambda x: (0 if x.get("cn") else 1, -(x.get("y") or 0), x.get("n", "")))

    # Build per-year votes indices. Each year file gets its own compact name table.
    vi_to_year: dict[int, int] = {}
    for law in laws:
        year = law.get("y") or 0
        for vote_data in law.get("vs", []):
            vi = vote_data.get("vi")
            if vi is not None:
                vi_to_year[vi] = year

    year_vis: dict[int, list[int]] = defaultdict(list)
    for vi, year in vi_to_year.items():
        year_vis[year].append(vi)

    votes_by_year: dict[int, dict] = {}
    for year, vis in year_vis.items():
        year_name_set: set[str] = set()
        for vi in vis:
            party_names = all_vote_names.get(vi, {})
            for party_key in _PARTY_KEYS:
                for vote_i in range(4):
                    for name in party_names.get(party_key, [[], [], [], []])[vote_i]:
                        year_name_set.add(name)

        year_name_list = sorted(year_name_set)
        local_idx = {name: idx for idx, name in enumerate(year_name_list)}

        compact_votes: dict[str, dict] = {}
        for vi in vis:
            party_names = all_vote_names.get(vi, {})
            compact: dict[str, list[list[int]]] = {}
            for party_key in _PARTY_KEYS:
                arrays: list[list[int]] = [[], [], [], []]
                for vote_i in range(4):
                    for name in party_names.get(party_key, [[], [], [], []])[vote_i]:
                        arrays[vote_i].append(local_idx[name])
                if any(arrays[i] for i in range(4)):
                    compact[party_key] = arrays
            if compact:
                compact_votes[str(vi)] = compact

        votes_by_year[year] = {"n": year_name_list, "v": compact_votes}

    return laws, votes_by_year


def compute_terms(leg: dict, min_votes: int = 5) -> list[dict]:
    """Deriva períodos de mandato a partir de _yr_blocs + yearly_stats."""
    mandate_len = {"diputados": 4, "senadores": 6}

    yr_blocs = leg.get("_yr_blocs", {})
    yr_provinces = leg.get("_yr_provinces", {})
    yearly_stats = leg.get("yearly_stats", {})
    terms: list[dict] = []

    for chamber, year_dict in yr_blocs.items():
        max_len = mandate_len.get(chamber, 6)

        # Active years: >= min_votes total votes that year
        active = sorted(
            int(year)
            for year in year_dict
            if yearly_stats.get(year, {}).get("total", 0) >= min_votes
        )
        if not active:
            continue

        # Split into contiguous runs (gap > 2 = new service period)
        runs: list[list[int]] = []
        current = [active[0]]
        for year in active[1:]:
            if year - current[-1] <= 2:
                current.append(year)
            else:
                runs.append(current)
                current = [year]
        runs.append(current)

        for run in runs:
            i = 0
            while i < len(run):
                boundary = run[i] + max_len - 1
                sub = [year for year in run[i:] if year <= boundary]
                i += len(sub)

                bloc_totals: dict[str, int] = {}
                for year in sub:
                    for bloc, count in year_dict.get(str(year), {}).items():
                        bloc_totals[bloc] = bloc_totals.get(bloc, 0) + count
                dominant_bloc = max(bloc_totals, key=bloc_totals.get) if bloc_totals else ""

                prov_totals: dict[str, int] = {}
                for year in sub:
                    for prov, count in yr_provinces.get(chamber, {}).get(str(year), {}).items():
                        prov_totals[prov] = prov_totals.get(prov, 0) + count
                dominant_prov = max(prov_totals, key=prov_totals.get) if prov_totals else leg.get("province", "")

                terms.append(
                    {
                        "ch": chamber,
                        "yf": min(sub),
                        "yt": max(sub),
                        "b": dominant_bloc,
                        "p": dominant_prov,
                    }
                )

    terms.sort(key=lambda term: (term["yf"], term["ch"]))
    return terms


def compute_weighted_alignment(yearly_alignment: dict, coalition: str, min_total: int = 5) -> float | None:
    """Devuelve el % de alineamiento total como media ponderada anual."""
    total_weight = 0
    total_aligned = 0
    for year_str, data in yearly_alignment.items():
        try:
            year = int(year_str)
        except (ValueError, TypeError):
            continue

        coalition_data = data.get(coalition, {})
        total = coalition_data.get("total", 0)
        if total < min_total:
            continue

        # Apply the same year masks used for per-year display
        if coalition == "UCR" and year > 2014:
            continue
        if coalition in ("JxC", "PRO") and not (2015 <= year <= 2023):
            continue
        if coalition == "LLA" and year < 2024:
            continue

        total_weight += total
        total_aligned += coalition_data.get("aligned", 0)

    if total_weight == 0:
        return None
    return round(total_aligned / total_weight * 100, 1)


def compute_era_alignment(
    yearly_alignment: dict,
    coalition: str,
    year_min: int,
    year_max: int,
    min_total: int = 5,
) -> float | None:
    """% de alineamiento ponderado para ``coalition`` en [year_min, year_max]."""
    total_weight = 0
    total_aligned = 0
    for year_str, data in yearly_alignment.items():
        try:
            year = int(year_str)
        except (ValueError, TypeError):
            continue

        if not (year_min <= year <= year_max):
            continue

        coalition_data = data.get(coalition, {})
        total = coalition_data.get("total", 0)
        if total < 1:
            continue

        total_weight += total
        total_aligned += coalition_data.get("aligned", 0)

    if total_weight < min_total:
        return None
    return round(total_aligned / total_weight * 100, 1)


def generate_site_data(legislators: dict, law_groups: dict) -> None:
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Legislators index
    skip_patterns = ("NO INCORPORADO", "PENDIENTE DE INCORPORACION", "A DESIGNAR")
    leg_index = []
    for key, leg in sorted(legislators.items(), key=lambda item: item[0]):
        name_upper = key.upper()
        if any(pattern in name_upper for pattern in skip_patterns) or key.strip(". ") == "":
            continue

        alignment_pj = compute_weighted_alignment(leg["yearly_alignment"], "PJ")
        alignment_pro = compute_weighted_alignment(leg["yearly_alignment"], "PRO")
        alignment_lla = compute_weighted_alignment(leg["yearly_alignment"], "LLA")

        # Sum aligned vote counts per coalition (applying same year masks)
        def _sum_aligned(coalition: str, min_total: int = 5):
            total_weight = 0
            total_aligned = 0
            for year_str, data in leg["yearly_alignment"].items():
                try:
                    year = int(year_str)
                except (ValueError, TypeError):
                    continue

                coalition_data = data.get(coalition, {})
                total = coalition_data.get("total", 0)
                if total < min_total:
                    continue
                if coalition == "UCR" and year > 2014:
                    continue
                if coalition in ("JxC", "PRO") and not (2015 <= year <= 2023):
                    continue
                if coalition == "LLA" and year < 2024:
                    continue

                total_weight += total
                total_aligned += coalition_data.get("aligned", 0)
            return total_aligned if total_weight > 0 else None

        votes_pj = _sum_aligned("PJ")
        votes_ucr = _sum_aligned("UCR")
        votes_pro = _sum_aligned("PRO")
        votes_lla = _sum_aligned("LLA")

        total_votes = sum(stats.get("total", 0) for stats in leg["yearly_stats"].values())

        # PRESIDENTE counts as present (not absent), so: present = total - ausente
        total_ausente = sum(stats.get("AUSENTE", 0) for stats in leg["yearly_stats"].values())
        total_abstencion = sum(stats.get("ABSTENCION", 0) for stats in leg["yearly_stats"].values())
        total_present = total_votes - total_ausente
        presentismo_pct = round(total_present / total_votes * 100, 1) if total_votes > 0 else None

        chambers = sorted(set(leg["chambers"]))
        chamber_display = (
            "+".join(chambers)
            if len(chambers) > 1
            else chambers[0]
            if chambers
            else leg["chamber"]
        )

        leg_index.append(
            {
                "k": key,
                "n": leg["name"],
                "c": chamber_display,
                "b": leg["bloc"],
                "p": leg["province"],
                "co": leg["coalition"],
                "apj": alignment_pj,
                "apro": alignment_pro,
                "alla": alignment_lla,
                "vpj": votes_pj,
                "vucr": votes_ucr,
                "vpro": votes_pro,
                "vlla": votes_lla,
                "tv": total_votes,
                "ph": leg.get("photo", ""),
                "pres": presentismo_pct,
                "aus": total_ausente,
                "abst": total_abstencion,
            }
        )

    save_json(DOCS_DATA_DIR / "legislators.json", leg_index)
    log.info(f"Generated legislators index with {len(leg_index)} entries")

    # 2. Individual legislator detail files
    leg_details_dir = DOCS_DATA_DIR / "legislators"
    leg_details_dir.mkdir(parents=True, exist_ok=True)

    total_legs = len(legislators)
    count = 0
    start_time = time.time()

    for key, leg in legislators.items():
        yearly_alignment_pct = {}
        for year_str, data in sorted(leg["yearly_alignment"].items()):
            yearly_alignment_pct[year_str] = {}
            try:
                year = int(year_str)
            except Exception:
                year = None

            for coalition in ["PJ", "UCR", "JxC", "PRO", "LLA"]:
                total = data.get(coalition, {}).get("total", 0)
                aligned = data.get(coalition, {}).get("aligned", 0)
                pct = None

                # Apply year masks for opposition coalitions
                if coalition == "UCR":
                    if year is not None and year <= 2014:
                        pct = round(aligned / total * 100, 1) if total > 5 else None
                    else:
                        pct = None
                elif coalition in ("JxC", "PRO"):
                    if year is not None and 2015 <= year <= 2023:
                        pct = round(aligned / total * 100, 1) if total > 5 else None
                    else:
                        pct = None
                elif coalition == "LLA":
                    if year is not None and year >= 2024:
                        pct = round(aligned / total * 100, 1) if total > 5 else None
                    else:
                        pct = None
                else:
                    # PJ: always compute when enough votes
                    pct = round(aligned / total * 100, 1) if total > 5 else None

                yearly_alignment_pct[year_str][coalition] = pct

        # Build waffle groups — merge by common_name
        waffle_groups = defaultdict(lambda: {"name": "", "votes": [], "year": None, "common_name": None})
        for vote in leg["votes"]:
            law_name = vote.get("ln", "")
            # Determine merge key: use common_name if available, else gk.
            common_name = vote.get("cn") or (get_common_name(law_name) if law_name else None)
            if common_name:
                year = vote.get("yr", "")
                merge_key = f"COMMON|{common_name}|{year}" if year else f"COMMON|{common_name}"
            else:
                group_key = vote.get("gk", "")
                merge_key = group_key if group_key else f"SINGLE_{vote['vid']}"

            group = waffle_groups[merge_key]
            if not group["name"]:
                group["name"] = law_name or vote.get("t", "")
            if common_name:
                group["common_name"] = common_name
                group["name"] = common_name

            # Mark whether this is an "En General" vote
            article_label = vote.get("al", "")
            is_general = (
                article_label == "En General"
                or "EN GENERAL" in vote.get("t", "").upper()
                or "VOT. EN GRAL" in vote.get("t", "").upper()
            )

            entry = {
                "v": vote["v"],
                "al": article_label,
                "t": vote.get("t", ""),
                "vid": vote.get("vid"),
                "ch": vote.get("ch"),
                "g": is_general,
            }
            if vote.get("url"):
                entry["url"] = vote["url"]
            group["votes"].append(entry)
            if vote.get("yr") and not group["year"]:
                group["year"] = vote["yr"]

        waffle_list = []
        for group_key, group in waffle_groups.items():
            # Ensure at least one vote is marked g:True so the waffle always has a summary tile.
            if not any(v["g"] for v in group["votes"]):
                if len(group["votes"]) == 1:
                    group["votes"][0]["g"] = True

            # pick first available vote URL to act as law link
            law_url = ""
            for vote in group["votes"]:
                if vote.get("url"):
                    law_url = vote["url"]
                    break

            waffle_list.append(
                {
                    "gk": group_key,
                    "name": group["name"][:120],
                    "year": group["year"],
                    "url": law_url,
                    "votes": group["votes"],
                    "notable": group.get("common_name") is not None,
                }
            )
        waffle_list.sort(key=lambda item: (-(item["year"] or 0), item["name"]))

        detail = {
            "name": leg["name"],
            "name_key": key,
            "photo": leg.get("photo", ""),
            "chambers": sorted(set(leg["chambers"])),
            "chamber": leg["chamber"],
            "bloc": leg["bloc"],
            "province": leg["province"],
            "coalition": leg["coalition"],
            "yearly_stats": leg["yearly_stats"],
            "yearly_alignment": yearly_alignment_pct,
            "alignment": {coal: compute_weighted_alignment(leg["yearly_alignment"], coal) for coal in ["PJ", "UCR", "PRO", "JxC", "LLA"]},
            "era_alignment": {
                "1993-2014": {
                    "PJ": compute_era_alignment(leg["yearly_alignment"], "PJ", 1993, 2014),
                    "UCR": compute_era_alignment(leg["yearly_alignment"], "UCR", 1993, 2014),
                },
                "2015-2023": {
                    "PJ": compute_era_alignment(leg["yearly_alignment"], "PJ", 2015, 2023),
                    "PRO": compute_era_alignment(leg["yearly_alignment"], "PRO", 2015, 2023),
                },
                "2024-2026": {
                    "PJ": compute_era_alignment(leg["yearly_alignment"], "PJ", 2024, 2026),
                    "LLA": compute_era_alignment(leg["yearly_alignment"], "LLA", 2024, 2026),
                },
            },
            "terms": compute_terms(leg),
            "votes": leg["votes"],
            "laws": waffle_list,
        }

        safe_name = re.sub(r"[^A-Z0-9_]", "_", key)[:80]
        write_start = time.time()
        save_json(leg_details_dir / f"{safe_name}.json", detail)
        write_elapsed = time.time() - write_start
        count += 1

        if count % 100 == 0 or count == total_legs:
            total_elapsed = time.time() - start_time
            log.info(
                f"Wrote {count}/{total_legs} legislator files; "
                f"last_write={write_elapsed:.2f}s; total_elapsed={total_elapsed:.2f}s"
            )

    log.info(f"Generated {len(legislators)} legislator detail files")

    # 3. Votaciones summary
    votaciones_summary = {"diputados": [], "senadores": []}
    for chamber in ["diputados", "senadores"]:
        votaciones = load_all_votaciones_from_db(chamber)
        for votacion in votaciones:
            votaciones_summary[chamber].append(
                {
                    "id": votacion.get("id"),
                    "title": votacion.get("title", "")[:200],
                    "date": clean_date(votacion.get("date", "")),
                    "result": votacion.get("result", ""),
                    "type": votacion.get("type", ""),
                    "afirmativo": votacion.get("afirmativo", 0),
                    "negativo": votacion.get("negativo", 0),
                    "abstencion": votacion.get("abstencion", 0),
                    "ausente": votacion.get("ausente", 0),
                }
            )

    save_json(DOCS_DATA_DIR / "votaciones.json", votaciones_summary)
    log.info("Generated votaciones summary")

    # 3b. Law detail data (per-coalition vote breakdowns for law search)
    laws_detail, votes_by_year = build_law_detail_data(law_groups)
    save_json(DOCS_DATA_DIR / "laws_detail.json", laws_detail)
    log.info(f"Generated laws_detail.json with {len(laws_detail)} law entries")

    # 3c. Per-year voter-names indices (loaded on-demand on first bar-click)
    votes_dir = DOCS_DATA_DIR / "votes"
    votes_dir.mkdir(parents=True, exist_ok=True)
    total_votaciones = 0
    for year, year_data in sorted(votes_by_year.items()):
        save_json(votes_dir / f"votes_{year}.json", year_data)
        total_votaciones += len(year_data["v"])
    log.info(f"Generated {len(votes_by_year)} per-year vote files ({total_votaciones} votaciones total)")

    # 4. Law names list
    law_names_set = set()
    for group in law_groups.values():
        common_name = group.get("common_name")
        if common_name:
            law_names_set.add(common_name)
        else:
            title = group.get("title", "").strip()
            if title and len(title) > 5:
                law_names_set.add(title[:120])
    save_json(DOCS_DATA_DIR / "law_names.json", sorted(law_names_set))
    log.info(f"Generated {len(law_names_set)} unique law names")

    # 5. Global stats (use leg_index count to exclude placeholder entries)
    stats = {
        "last_updated": datetime.now().isoformat(),
        "total_legislators": len(leg_index),
        "total_diputados": sum(1 for entry in leg_index if "diputados" in (entry.get("c") or "")),
        "total_senadores": sum(1 for entry in leg_index if "senadores" in (entry.get("c") or "")),
        "total_votaciones_diputados": len(votaciones_summary["diputados"]),
        "total_votaciones_senadores": len(votaciones_summary["senadores"]),
        "years_covered": sorted(set(year for leg in legislators.values() for year in leg["yearly_stats"].keys())),
        "years_diputados": list(
            practical_year_range(
                sorted(
                    set(
                        str(extract_year(votacion["date"]))
                        for votacion in votaciones_summary["diputados"]
                        if votacion.get("date") and extract_year(votacion["date"])
                    )
                )
            )
        ),
        "years_senadores": list(
            practical_year_range(
                sorted(
                    set(
                        str(extract_year(votacion["date"]))
                        for votacion in votaciones_summary["senadores"]
                        if votacion.get("date") and extract_year(votacion["date"])
                    )
                )
            )
        ),
        "total_laws": len(law_groups),
    }
    save_json(DOCS_DATA_DIR / "stats.json", stats)
    log.info("Generated global stats")

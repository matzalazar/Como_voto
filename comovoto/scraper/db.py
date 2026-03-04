from __future__ import annotations

import json
import logging
from pathlib import Path

from .classification import classify_bloc
from .config import HCDN_BASE, SENADO_BASE, VOTE_DECODE, VOTE_ENCODE

log = logging.getLogger("scraper")


class ConsolidatedDB:
    """Manages a consolidated JSON database for a chamber."""

    def __init__(self, path: Path):
        self.path = path
        self.names: list[str] = []
        self.blocs: list[str] = []
        self.provinces: list[str] = []
        self.photo_ids: dict[str, str] = {}
        self.votaciones: list[dict] = []
        self._name_idx: dict[str, int] = {}
        self._bloc_idx: dict[str, int] = {}
        self._prov_idx: dict[str, int] = {}
        self._votacion_ids: set[str] = set()

    def load(self):
        """Load existing data from disk."""
        if not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Error loading %s: %s", self.path, exc)
            return

        self.names = data.get("names", [])
        self.blocs = data.get("blocs", [])
        self.provinces = data.get("provinces", [])
        self.photo_ids = data.get("photo_ids", {})
        self.votaciones = data.get("votaciones", [])

        self._name_idx = {n: i for i, n in enumerate(self.names)}
        self._bloc_idx = {b: i for i, b in enumerate(self.blocs)}
        self._prov_idx = {p: i for i, p in enumerate(self.provinces)}
        self._votacion_ids = {str(v["id"]) for v in self.votaciones}

    def save(self):
        """Save to disk (compact JSON, no indent)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "names": self.names,
            "blocs": self.blocs,
            "provinces": self.provinces,
            "photo_ids": self.photo_ids,
            "votaciones": self.votaciones,
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    def has_votacion(self, vid: str) -> bool:
        return str(vid) in self._votacion_ids

    def _get_name_idx(self, name: str) -> int:
        if name not in self._name_idx:
            idx = len(self.names)
            self.names.append(name)
            self._name_idx[name] = idx
        return self._name_idx[name]

    def _get_bloc_idx(self, bloc: str) -> int:
        if bloc not in self._bloc_idx:
            idx = len(self.blocs)
            self.blocs.append(bloc)
            self._bloc_idx[bloc] = idx
        return self._bloc_idx[bloc]

    def _get_prov_idx(self, province: str) -> int:
        if province not in self._prov_idx:
            idx = len(self.provinces)
            self.provinces.append(province)
            self._prov_idx[province] = idx
        return self._prov_idx[province]

    def add_votacion(self, raw: dict):
        """Add a votacion in raw format, converting it to compact format."""
        vid = str(raw.get("id", ""))
        if vid in self._votacion_ids:
            return

        compact_votes = []
        for vote in raw.get("votes", []):
            name = vote.get("name", "").strip()
            if not name:
                continue
            ni = self._get_name_idx(name)
            bi = self._get_bloc_idx(vote.get("bloc", ""))
            pi = self._get_prov_idx(vote.get("province", ""))
            vc = VOTE_ENCODE.get(vote.get("vote", "").upper(), 0)
            compact_votes.append([ni, bi, pi, vc])

            photo_id = vote.get("photo_id", "")
            if photo_id:
                self.photo_ids[str(ni)] = photo_id

        entry = {
            "id": vid,
            "t": raw.get("title", ""),
            "d": raw.get("date", ""),
            "r": raw.get("result", ""),
            "tp": raw.get("type", ""),
            "p": raw.get("period", ""),
            "a": raw.get("afirmativo", 0),
            "n": raw.get("negativo", 0),
            "b": raw.get("abstencion", 0),
            "u": raw.get("ausente", 0),
            "v": compact_votes,
        }
        self.votaciones.append(entry)
        self._votacion_ids.add(vid)

    def expand_votacion(self, compact: dict, chamber: str) -> dict:
        """Convert compact format back to the expanded format."""
        votes = []
        for item in compact.get("v", []):
            ni, bi, pi, vc = item
            name = self.names[ni] if ni < len(self.names) else ""
            bloc = self.blocs[bi] if bi < len(self.blocs) else ""
            province = self.provinces[pi] if pi < len(self.provinces) else ""
            vote_str = VOTE_DECODE.get(vc, "")
            entry = {
                "name": name,
                "bloc": bloc,
                "province": province,
                "vote": vote_str,
                "coalition": classify_bloc(bloc),
            }
            photo_id = self.photo_ids.get(str(ni), "")
            if photo_id:
                entry["photo_id"] = photo_id
            votes.append(entry)

        url = ""
        if chamber == "diputados" and compact.get("id"):
            url = f"{HCDN_BASE}/votacion/{compact.get('id')}"
        elif chamber == "senadores" and compact.get("id"):
            url = f"{SENADO_BASE}/votaciones/detalleActa/{compact.get('id')}"

        return {
            "id": compact.get("id", ""),
            "chamber": chamber,
            "url": url,
            "title": compact.get("t", ""),
            "date": compact.get("d", ""),
            "result": compact.get("r", ""),
            "type": compact.get("tp", ""),
            "period": compact.get("p", ""),
            "afirmativo": compact.get("a", 0),
            "negativo": compact.get("n", 0),
            "abstencion": compact.get("b", 0),
            "ausente": compact.get("u", 0),
            "votes": votes,
        }

    def expand_all(self, chamber: str) -> list[dict]:
        return [self.expand_votacion(v, chamber) for v in self.votaciones]

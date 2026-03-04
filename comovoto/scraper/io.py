from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import DATA_DIR, FOTOS_DIR


def ensure_dirs():
    """Create data directories if they don't exist."""
    for directory in [DATA_DIR, FOTOS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

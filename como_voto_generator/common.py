from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
DOCS_DATA_DIR = DOCS_DIR / "data"
FOTOS_DIR = DOCS_DIR / "fotos"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("processor")


def save_json(path: Path, data) -> None:
    """Escribe JSON de forma atómica para reducir riesgo de archivos parciales."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=None, separators=(",", ":"))
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except Exception:
                # fsync may not be available on all platforms; ignore failures.
                pass
        os.replace(tmp_path, path)
    except Exception as exc:
        log.exception(f"Failed to write JSON to {path}: {exc}")
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=None, separators=(",", ":"))
        except Exception:
            log.exception(f"Fallback write also failed for {path}")

"""Atomic JSON artifact writing shared by ingestion and source caches."""
import json
import os
import tempfile
from pathlib import Path


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    # A failed write must not leave a partially readable manifest.
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False, encoding='utf-8') as handle:
        temp_path = Path(handle.name)
        try:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write('\n')
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)

"""Atomic publication for generated artifacts."""
import json
import os
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def atomic_output(path: Path) -> Generator[Path, None, None]:
    """Publish after a successful write and clean up on failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # A sibling file inherits the destination folder's Windows permissions.
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.artifact-', delete=False) as handle:
        candidate = Path(handle.name)
    try:
        yield candidate
        os.replace(candidate, path)
    finally:
        candidate.unlink(missing_ok=True)


def write_json(path: Path, payload: dict):
    with atomic_output(path) as candidate:
        with candidate.open('w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write('\n')

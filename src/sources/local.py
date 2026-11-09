"""Snapshot user-downloaded bytes before parsing; never fetch a local source's URL."""
import hashlib
import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from src.artifacts import write_json
from src.config import Source
from src.sources.http import HttpCache, Snapshot


def acquire_snapshot(source: Source, cache: HttpCache, *, refresh=False) -> Snapshot:
    if source.local_path is None:
        if not source.url:
            raise ValueError('A source download URL or local_path is required')
        return cache.get(str(source.url), refresh=refresh)
    path = source.local_path.resolve()
    if not path.is_file():
        raise ValueError('Local input must be an existing regular file; ZIP multi-file GIS datasets first')
    # Copy on every explicit run: metadata/mtime alone cannot establish unchanged bytes.
    cache.root.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with path.open('rb') as incoming:
            before = os.fstat(incoming.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError('Local input must be a regular file; ZIP multi-file GIS datasets first')
            if before.st_size > cache.max_bytes:
                raise ValueError('Local input exceeds configured byte limit')
            digest = hashlib.sha256(); count = 0
            with tempfile.NamedTemporaryFile(dir=cache.root, delete=False) as target:
                temporary = Path(target.name)
                while chunk := incoming.read(1024 * 1024):
                    count += len(chunk); cache.transferred_bytes += len(chunk)
                    if count > cache.max_bytes:
                        raise ValueError('Local input exceeds configured byte limit')
                    if cache.transferred_bytes > cache.max_total_bytes:
                        raise ValueError('Acquisition exceeds the total transfer budget')
                    digest.update(chunk); target.write(chunk)
            after = os.fstat(incoming.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns) or count != before.st_size:
                raise ValueError('Local input changed during acquisition; retry with a stable download')
        checksum = digest.hexdigest()
        destination = cache.root / 'blobs' / checksum / 'payload'
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            with destination.open('rb') as existing:
                if hashlib.file_digest(existing, 'sha256').hexdigest() != checksum:
                    raise ValueError('Existing immutable source blob is corrupt')
        else:
            os.replace(temporary, destination)
        provenance = {'acquisition_mode': 'local_file', 'local_path': str(path),
                      'url': str(source.url or source.metadata_url or ''),
                      'downloaded_at': source.downloaded_at.isoformat() if source.downloaded_at else None}
        key = hashlib.sha256(json.dumps({**provenance, 'checksum': checksum}, sort_keys=True).encode()).hexdigest()
        index = cache.root / 'local' / f'{key}.json'
        if index.exists():
            metadata = json.loads(index.read_text())
            if metadata['checksum_sha256'] != checksum or metadata['size_bytes'] != count:
                raise ValueError('Local snapshot metadata is corrupt')
        else:
            metadata = {**provenance, 'checksum_sha256': checksum, 'size_bytes': count,
                        'retrieved_at': datetime.now(timezone.utc).isoformat()}
            write_json(index, metadata)
        return Snapshot(destination, metadata)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

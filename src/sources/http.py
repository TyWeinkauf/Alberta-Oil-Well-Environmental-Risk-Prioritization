"""Verified-TLS HTTP acquisition with retries, size caps and immutable byte caching."""
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import ROOT
from src.artifacts import write_json as _write_report


@dataclass(frozen=True)
class Snapshot:
    path: Path
    metadata: dict

    def json(self):
        return json.loads(self.path.read_bytes())


class HttpCache:
    def __init__(self, root: Path | None = None, *, max_bytes: int = 512*1024*1024, max_total_bytes: int | None=None,
                 session: requests.Session | None = None):
        self.root = root or ROOT/'data/cache/http'
        self.max_bytes = max_bytes
        self.max_total_bytes = max_total_bytes if max_total_bytes is not None else max_bytes*4
        self.transferred_bytes = 0
        self.session = session or requests.Session()
        # Session defaults preserve the platform proxy and CA trust; never use verify=False.
        retry = Retry(total=3,connect=2,read=2,status=2,backoff_factor=0.5,
                      status_forcelist=(429,500,502,503,504),allowed_methods=('GET',),respect_retry_after_header=True)
        self.session.mount('https://',HTTPAdapter(max_retries=retry))
        self.session.mount('http://',HTTPAdapter(max_retries=retry))
        self.session.headers['User-Agent'] = 'Alberta-Environmental-Screening-Educational/0.4'

    def get(self, url: str, params: dict | None = None, *, refresh: bool = False) -> Snapshot:
        parsed = urlsplit(url)
        if parsed.scheme not in ('http','https') or parsed.username or parsed.password:
            raise ValueError('Source URL must be public HTTP(S) without embedded credentials')
        # Plain HTTP is supported only for local adapter tests.
        if parsed.scheme != 'https' and parsed.hostname not in ('127.0.0.1','localhost'):
            raise ValueError('Remote sources require HTTPS with TLS verification')
        request = {'url':url,'params':params or {}}
        key = hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        index = self.root/'requests'/f'{key}.json'
        previous = json.loads(index.read_text()) if index.exists() else None
        if previous:
            payload = self.root/'blobs'/previous['checksum_sha256']/'payload'
            if not payload.is_file() or hashlib.sha256(payload.read_bytes()).hexdigest()!=previous['checksum_sha256']:
                raise ValueError('Cached source checksum mismatch; refusing to reuse corrupted input')
            if payload.stat().st_size > self.max_bytes:
                raise ValueError('Cached source exceeds configured byte limit')
            if not refresh:
                return Snapshot(payload,previous)
        headers = {}
        if previous:
            if previous.get('etag'): headers['If-None-Match']=previous['etag']
            if previous.get('last_modified'): headers['If-Modified-Since']=previous['last_modified']
        self.root.mkdir(parents=True,exist_ok=True)
        with self.session.get(url,params=params,headers=headers,stream=True,timeout=(10,60)) as response:
            if response.status_code==304:
                if not previous:
                    raise ValueError('Unexpected HTTP 304 without a verified cached input')
                return Snapshot(payload,previous)
            response.raise_for_status()
            for hop in [*response.history,response]:
                destination_url=urlsplit(hop.url)
                if destination_url.scheme!='https' and destination_url.hostname not in ('127.0.0.1','localhost'):
                    raise ValueError('Source redirect downgraded to an unverified non-HTTPS route')
            size = response.headers.get('Content-Length')
            if size and int(size)>self.max_bytes:
                raise ValueError('Source download exceeds configured byte limit')
            if size and self.transferred_bytes+int(size)>self.max_total_bytes:
                raise ValueError('Acquisition exceeds the total transfer budget')
            digest = hashlib.sha256();count=0
            with tempfile.NamedTemporaryFile(dir=self.root,delete=False) as handle:
                temporary = Path(handle.name)
                try:
                    for chunk in response.iter_content(chunk_size=1024*1024):
                        count += len(chunk)
                        self.transferred_bytes += len(chunk)
                        if count>self.max_bytes:
                            raise ValueError('Source download exceeds configured byte limit')
                        if self.transferred_bytes>self.max_total_bytes:
                            raise ValueError('Acquisition exceeds the total transfer budget')
                        digest.update(chunk);handle.write(chunk)
                except Exception:
                    temporary.unlink(missing_ok=True)
                    raise
            checksum = digest.hexdigest()
            destination = self.root/'blobs'/checksum/'payload'
            destination.parent.mkdir(parents=True,exist_ok=True)
            try:
                if destination.exists():
                    if hashlib.sha256(destination.read_bytes()).hexdigest()!=checksum:
                        raise ValueError('Existing immutable source blob is corrupt')
                else:
                    os.replace(temporary,destination)
            finally:
                temporary.unlink(missing_ok=True)
            metadata = {**request,'final_url':response.url,'checksum_sha256':checksum,'size_bytes':count,
                        'retrieved_at':datetime.now(timezone.utc).isoformat(),
                        'etag':response.headers.get('ETag'),'last_modified':response.headers.get('Last-Modified'),
                        'content_type':response.headers.get('Content-Type')}
            if previous and previous['checksum_sha256']==checksum:
                return Snapshot(destination,previous)  # Preserve unchanged input identity on refresh.
            _write_report(index,metadata)
            return Snapshot(destination,metadata)

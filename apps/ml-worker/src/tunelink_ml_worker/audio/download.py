from __future__ import annotations

import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests

DOWNLOAD_LIMIT_BYTES = 500 * 1024 * 1024


def download_audio(url: str, filename: str) -> Path:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Audio URL must use HTTP or HTTPS.")

    suffix = Path(filename).suffix or ".audio"
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    downloaded = 0
    try:
        with requests.get(url, stream=True, timeout=(10, 300)) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                downloaded += len(chunk)
                if downloaded > DOWNLOAD_LIMIT_BYTES:
                    raise ValueError("Audio object exceeds the 500 MB worker limit.")
                handle.write(chunk)
        return Path(handle.name)
    except Exception:
        Path(handle.name).unlink(missing_ok=True)
        raise
    finally:
        handle.close()

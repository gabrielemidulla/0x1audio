from __future__ import annotations

import http.client
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from io import BytesIO

from ox1audio_backend import storage

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (compatible; 0x1audio/0.1)"
_OG_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    re.IGNORECASE,
)
_SIZE_RE = re.compile(r"/\d+x\d+[a-z]*([./]|$)")
_HTTP_ERRORS = (
    urllib.error.URLError,
    TimeoutError,
    http.client.IncompleteRead,
    http.client.HTTPException,
    ConnectionError,
    OSError,
)


def _http_get(url: str, *, timeout: float = 20, retries: int = 3) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": _UA, "Accept": "*/*"},
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except _HTTP_ERRORS as exc:
            last_error = exc
            if attempt + 1 >= retries:
                break
            time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def resolve_apple_music_artist_image(name: str, *, size: int = 300) -> tuple[bytes, str] | None:
    cleaned = " ".join(name.split()).strip()
    if not cleaned:
        return None
    params = urllib.parse.urlencode(
        {
            "term": cleaned,
            "entity": "musicArtist",
            "limit": 5,
            "country": "us",
        }
    )
    try:
        payload = json.loads(_http_get(f"https://itunes.apple.com/search?{params}").decode())
    except (*_HTTP_ERRORS, json.JSONDecodeError, UnicodeDecodeError):
        logger.exception("itunes search failed for %r", cleaned)
        return None

    results = payload.get("results") or []
    chosen = next(
        (
            row
            for row in results
            if (row.get("artistName") or "").casefold() == cleaned.casefold()
        ),
        None,
    )
    if chosen is None:
        return None
    artist_id = chosen.get("artistId")
    if artist_id is None:
        return None

    try:
        html = _http_get(f"https://music.apple.com/us/artist/{artist_id}").decode(
            "utf-8", errors="replace"
        )
    except (*_HTTP_ERRORS, UnicodeDecodeError):
        logger.exception("apple music page failed for %r id=%s", cleaned, artist_id)
        return None

    match = _OG_RE.search(html)
    if match is None:
        return None
    og_url = match.group(1) or match.group(2)
    if not og_url:
        return None

    image_url = _SIZE_RE.sub(rf"/{size}x{size}cc\1", og_url, count=1)
    try:
        data = _http_get(image_url)
    except _HTTP_ERRORS:
        logger.exception("apple music image download failed for %r", cleaned)
        return None
    if not data:
        return None

    content_type = "image/png" if data[:8].startswith(b"\x89PNG") else "image/jpeg"
    return data, content_type


def store_artist_image(artist_id: uuid.UUID, data: bytes, content_type: str) -> str:
    ext = "png" if content_type == "image/png" else "jpg"
    object_key = f"artists/{artist_id}/image.{ext}"
    storage.put_object(object_key, BytesIO(data), len(data), content_type)
    return object_key


def fetch_and_store_artist_image(artist_id: uuid.UUID, name: str) -> str | None:
    resolved = resolve_apple_music_artist_image(name)
    if resolved is None:
        return None
    data, content_type = resolved
    return store_artist_image(artist_id, data, content_type)

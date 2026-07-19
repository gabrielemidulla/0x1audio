from __future__ import annotations

import uuid
from io import BytesIO

from PIL import Image

from ox1audio_backend.ingest.audio_tags import EmbeddedCover
from ox1audio_backend import storage
from ox1audio_backend.shared_constants import FALLBACK_COVER_COLOR

DEFAULT_COVER_COLOR = FALLBACK_COVER_COLOR


def cover_color_from_bytes(data: bytes) -> str:
    try:
        with Image.open(BytesIO(data)) as image:
            rgb = image.convert("RGB").resize((1, 1), Image.Resampling.BOX)
            r, g, b = rgb.getpixel((0, 0))
            return f"#{r:02x}{g:02x}{b:02x}"
    except OSError:
        return DEFAULT_COVER_COLOR


def store_track_cover(track_id: uuid.UUID, cover: EmbeddedCover) -> tuple[str, str]:
    ext = "png" if cover.content_type == "image/png" else "jpg"
    object_key = f"covers/{track_id}/cover.{ext}"
    storage.put_object(
        object_key,
        BytesIO(cover.data),
        len(cover.data),
        cover.content_type,
    )
    return object_key, cover_color_from_bytes(cover.data)

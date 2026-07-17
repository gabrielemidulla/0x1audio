from __future__ import annotations

from typing import Any

from tunelink_backend.models import Track


def track_payload(track: Track) -> dict[str, Any]:
    """Compact track dict for tools/LLM — no filenames."""
    return {
        "id": str(track.id),
        "title": track.title,
        "artist": track.artist,
    }

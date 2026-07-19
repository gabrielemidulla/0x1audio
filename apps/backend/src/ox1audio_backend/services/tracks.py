from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ox1audio_backend import storage
from ox1audio_backend.config import get_settings
from ox1audio_backend.models import Track
from ox1audio_backend.schemas.tracks import ArtistRefOut, TrackOut
from ox1audio_backend.services import artists as artist_svc

logger = logging.getLogger(__name__)


async def tracks_out(db: AsyncSession, tracks: list[Track]) -> list[TrackOut]:
    by_track = await artist_svc.artists_by_track_ids(db, [track.id for track in tracks])
    items: list[TrackOut] = []
    for track in tracks:
        item = TrackOut.model_validate(track)
        artists = by_track.get(track.id, [])
        items.append(
            item.model_copy(
                update={
                    "artists": [ArtistRefOut.model_validate(artist) for artist in artists],
                }
            )
        )
    return items


async def track_out(db: AsyncSession, track: Track) -> TrackOut:
    items = await tracks_out(db, [track])
    return items[0]



def _qdrant_request(method: str, path: str, body: dict | None = None) -> dict | None:
    settings = get_settings()
    base = settings.qdrant_url.rstrip("/")
    if not base:
        return None
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{base}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    if settings.qdrant_api_key:
        request.add_header("api-key", settings.qdrant_api_key)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        logger.exception("Qdrant request failed: %s %s", method, path)
        return None


def _delete_qdrant_points(track_ids: list[str]) -> None:
    """Remove track, profile, and segment points for the given track ids."""
    if not track_ids:
        return
    listed = _qdrant_request("GET", "/collections")
    if not listed:
        return
    collections = (listed.get("result") or {}).get("collections") or []
    names = [
        str(item.get("name"))
        for item in collections
        if item.get("name") and str(item.get("name")).startswith("ox1audio_")
    ]
    # Point ids for track + profile vectors are the track UUID.
    by_id = {"points": track_ids, "wait": True}
    # Segment points use their own ids but carry track_id in payload.
    by_filter = {
        "filter": {
            "should": [
                {"key": "track_id", "match": {"value": track_id}}
                for track_id in track_ids
            ]
        },
        "wait": True,
    }
    for name in names:
        _qdrant_request("POST", f"/collections/{name}/points/delete", by_id)
        _qdrant_request("POST", f"/collections/{name}/points/delete", by_filter)


async def delete_tracks(db: AsyncSession, track_ids: list[uuid.UUID]) -> int:
    if not track_ids:
        return 0
    tracks = list(await db.scalars(select(Track).where(Track.id.in_(track_ids))))
    if not tracks:
        return 0

    for track in tracks:
        storage.remove_object(track.object_key)
        if track.cover_object_key:
            storage.remove_object(track.cover_object_key)

    _delete_qdrant_points([str(track.id) for track in tracks])

    await db.execute(delete(Track).where(Track.id.in_([track.id for track in tracks])))
    await db.flush()
    return len(tracks)

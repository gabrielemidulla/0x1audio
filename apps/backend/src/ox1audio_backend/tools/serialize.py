from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ox1audio_backend.models import Artist, Track
from ox1audio_backend.services import artists as artist_svc


def track_payload(track: Track, artists: list[Artist] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(track.id),
        "title": track.title,
        "artist": track.artist,
        "artists": [
            {"id": str(artist.id), "name": artist.name}
            for artist in (artists or [])
        ],
    }
    if track.is_instrumental is not None:
        payload["is_instrumental"] = track.is_instrumental
    return payload


async def track_payloads(db: AsyncSession, tracks: list[Track]) -> list[dict[str, Any]]:
    by_track = await artist_svc.artists_by_track_ids(db, [track.id for track in tracks])
    return [
        track_payload(track, by_track.get(track.id, []))
        for track in tracks
    ]


async def track_payload_one(db: AsyncSession, track: Track) -> dict[str, Any]:
    payloads = await track_payloads(db, [track])
    return payloads[0]

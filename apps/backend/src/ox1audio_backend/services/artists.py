from __future__ import annotations

import re
import uuid
from typing import Literal

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ox1audio_backend.exceptions import AppError
from ox1audio_backend.models import Artist, Track, TrackArtist


class ArtistError(AppError):
    pass



# Separators that actually appear in our TPE1 / artist tags.
_SPLIT_RE = re.compile(
    r"\s*(?:,|&|/|;)\s*|\s*\b(?:feat(?:uring)?|ft)\.?\s+",
    re.IGNORECASE,
)


def split_artist_names(raw: str | None) -> list[str]:
    if not raw:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for part in _SPLIT_RE.split(raw):
        name = " ".join(part.split()).strip(" -")
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def resolve_artist_names(tag_artists: list[str] | None) -> list[str]:
    """Resolve artists from tag values only.

    Multi-value tags are kept as-is. A single combined string is split only on
    explicit separators present in the source (comma, &, /, ;, feat/ft).
    """
    values = [name for name in (tag_artists or []) if name and name.strip()]
    if not values:
        return []
    if len(values) > 1:
        names: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = " ".join(value.split()).strip()
            if not cleaned:
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            names.append(cleaned)
        return names
    return split_artist_names(values[0])


def format_artist_label(artists: list[Artist]) -> str:
    return ", ".join(artist.name for artist in artists)


async def get_or_create_artist(db: AsyncSession, name: str) -> Artist:
    cleaned = " ".join(name.split()).strip()
    if not cleaned:
        raise ValueError("Artist name required")
    existing = await db.scalar(
        select(Artist).where(func.lower(Artist.name) == cleaned.casefold())
    )
    if existing is not None:
        return existing
    artist = Artist(name=cleaned)
    try:
        async with db.begin_nested():
            db.add(artist)
            await db.flush()
    except IntegrityError:
        existing = await db.scalar(
            select(Artist).where(func.lower(Artist.name) == cleaned.casefold())
        )
        if existing is None:
            raise
        return existing
    return artist


async def set_track_artists(
    db: AsyncSession,
    track: Track,
    artist_ids: list[uuid.UUID],
) -> list[Artist]:
    # Preserve order, drop duplicates.
    ordered_ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for artist_id in artist_ids:
        if artist_id in seen:
            continue
        seen.add(artist_id)
        ordered_ids.append(artist_id)

    artists: list[Artist] = []
    if ordered_ids:
        rows = list(await db.scalars(select(Artist).where(Artist.id.in_(ordered_ids))))
        by_id = {artist.id: artist for artist in rows}
        missing = [artist_id for artist_id in ordered_ids if artist_id not in by_id]
        if missing:
            raise ArtistError("Artist not found", status_code=404)
        artists = [by_id[artist_id] for artist_id in ordered_ids]

    await db.execute(delete(TrackArtist).where(TrackArtist.track_id == track.id))
    for position, artist in enumerate(artists):
        db.add(
            TrackArtist(
                track_id=track.id,
                artist_id=artist.id,
                position=position,
            )
        )
    track.artist = format_artist_label(artists)
    await db.flush()
    return artists


async def link_artists_from_names(
    db: AsyncSession,
    track: Track,
    names: list[str],
) -> list[Artist]:
    artists = [await get_or_create_artist(db, name) for name in names]
    return await set_track_artists(db, track, [artist.id for artist in artists])


async def link_artists_from_string(
    db: AsyncSession,
    track: Track,
    raw: str | None,
) -> list[Artist]:
    return await link_artists_from_names(db, track, split_artist_names(raw))


async def link_artists_from_tags(
    db: AsyncSession,
    track: Track,
    tag_artists: list[str] | None,
) -> list[Artist]:
    return await link_artists_from_names(db, track, resolve_artist_names(tag_artists))


async def artists_by_track_ids(
    db: AsyncSession,
    track_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[Artist]]:
    if not track_ids:
        return {}
    rows = await db.execute(
        select(TrackArtist, Artist)
        .join(Artist, Artist.id == TrackArtist.artist_id)
        .where(TrackArtist.track_id.in_(track_ids))
        .order_by(TrackArtist.track_id, TrackArtist.position)
    )
    result: dict[uuid.UUID, list[Artist]] = {track_id: [] for track_id in track_ids}
    for link, artist in rows.all():
        result.setdefault(link.track_id, []).append(artist)
    return result


async def search_artists(
    db: AsyncSession,
    *,
    q: str | None,
    limit: int = 20,
    offset: int = 0,
    sort: Literal["name", "track_count", "created_at"] = "name",
    order: Literal["asc", "desc"] = "asc",
) -> list[Artist]:
    stmt = select(Artist)
    query = (q or "").strip()
    if query:
        stmt = stmt.where(Artist.name.ilike(f"%{query}%"))

    ascending = order == "asc"
    if sort == "track_count":
        track_count = (
            select(func.count())
            .select_from(TrackArtist)
            .where(TrackArtist.artist_id == Artist.id)
            .correlate(Artist)
            .scalar_subquery()
        )
        primary = track_count.asc() if ascending else track_count.desc()
        stmt = stmt.order_by(primary, Artist.name.asc())
    elif sort == "created_at":
        primary = Artist.created_at.asc() if ascending else Artist.created_at.desc()
        stmt = stmt.order_by(primary, Artist.name.asc())
    else:
        primary = Artist.name.asc() if ascending else Artist.name.desc()
        stmt = stmt.order_by(primary)

    return list(await db.scalars(stmt.offset(offset).limit(limit)))


async def count_artists(db: AsyncSession, *, q: str | None) -> int:
    stmt = select(func.count()).select_from(Artist)
    query = (q or "").strip()
    if query:
        stmt = stmt.where(Artist.name.ilike(f"%{query}%"))
    return int(await db.scalar(stmt) or 0)


async def track_counts_by_artist_ids(
    db: AsyncSession,
    artist_ids: list[uuid.UUID],
) -> dict[uuid.UUID, int]:
    if not artist_ids:
        return {}
    rows = await db.execute(
        select(TrackArtist.artist_id, func.count())
        .where(TrackArtist.artist_id.in_(artist_ids))
        .group_by(TrackArtist.artist_id)
    )
    return {artist_id: int(count) for artist_id, count in rows.all()}


async def get_artist(db: AsyncSession, artist_id: uuid.UUID) -> Artist | None:
    return await db.scalar(select(Artist).where(Artist.id == artist_id))


async def tracks_for_artist(
    db: AsyncSession,
    artist_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[Track]:
    return list(
        await db.scalars(
            select(Track)
            .join(TrackArtist, TrackArtist.track_id == Track.id)
            .where(TrackArtist.artist_id == artist_id)
            .order_by(TrackArtist.position.asc(), Track.imported_at.desc())
            .limit(limit)
        )
    )


async def delete_artist_if_unused(db: AsyncSession, artist_id: uuid.UUID) -> bool:
    artist = await db.scalar(select(Artist).where(Artist.id == artist_id))
    if artist is None:
        return False
    in_use = await db.scalar(
        select(TrackArtist.id).where(TrackArtist.artist_id == artist_id).limit(1)
    )
    if in_use is not None:
        raise ArtistError("Artist is linked to tracks", status_code=409)
    await db.delete(artist)
    await db.flush()
    return True

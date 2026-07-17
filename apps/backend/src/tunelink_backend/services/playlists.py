from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tunelink_backend.models import Playlist, PlaylistItem, Track


class PlaylistError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class PlaylistSummary:
    playlist: Playlist
    track_count: int


async def get_owned_playlist(
    db: AsyncSession,
    playlist_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Playlist:
    playlist = await db.scalar(
        select(Playlist).where(Playlist.id == playlist_id, Playlist.user_id == user_id)
    )
    if playlist is None:
        raise PlaylistError("Playlist not found", status_code=404)
    return playlist


async def list_playlist_summaries(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[PlaylistSummary]:
    count_sq = (
        select(PlaylistItem.playlist_id, func.count().label("track_count"))
        .group_by(PlaylistItem.playlist_id)
        .subquery()
    )
    rows = await db.execute(
        select(Playlist, func.coalesce(count_sq.c.track_count, 0))
        .outerjoin(count_sq, count_sq.c.playlist_id == Playlist.id)
        .where(Playlist.user_id == user_id)
        .order_by(Playlist.updated_at.desc())
    )
    return [
        PlaylistSummary(playlist=playlist, track_count=int(track_count))
        for playlist, track_count in rows.all()
    ]


async def ordered_track_ids(db: AsyncSession, playlist_id: uuid.UUID) -> list[uuid.UUID]:
    rows = await db.scalars(
        select(PlaylistItem.track_id)
        .where(PlaylistItem.playlist_id == playlist_id)
        .order_by(PlaylistItem.position.asc())
    )
    return list(rows)


async def parse_track_ids(raw_ids: list[str]) -> list[uuid.UUID]:
    parsed: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for value in raw_ids:
        try:
            track_id = uuid.UUID(value)
        except ValueError as exc:
            raise PlaylistError(f"Invalid track_id: {value}", status_code=422) from exc
        if track_id in seen:
            raise PlaylistError(f"Duplicate track_id: {value}", status_code=422)
        seen.add(track_id)
        parsed.append(track_id)
    return parsed


async def require_tracks_exist(db: AsyncSession, track_ids: list[uuid.UUID]) -> None:
    if not track_ids:
        return
    found = set(
        await db.scalars(select(Track.id).where(Track.id.in_(track_ids)))
    )
    missing = [str(track_id) for track_id in track_ids if track_id not in found]
    if missing:
        raise PlaylistError(
            f"Unknown track_id(s): {', '.join(missing)}",
            status_code=422,
        )


async def create_playlist(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    title: str,
    description: str | None = None,
    track_ids: list[str] | None = None,
) -> Playlist:
    clean_title = " ".join(title.strip().split())
    if not clean_title:
        raise PlaylistError("title is required", status_code=422)

    playlist = Playlist(
        user_id=user_id,
        title=clean_title,
        description=description.strip() if description and description.strip() else None,
    )
    db.add(playlist)
    await db.flush()

    if track_ids:
        uuids = await parse_track_ids(track_ids)
        await require_tracks_exist(db, uuids)
        for index, track_id in enumerate(uuids):
            db.add(
                PlaylistItem(
                    playlist_id=playlist.id,
                    track_id=track_id,
                    position=index,
                )
            )
        playlist.updated_at = datetime.now(timezone.utc)

    await db.flush()
    return playlist


async def update_playlist(
    db: AsyncSession,
    playlist: Playlist,
    *,
    title: str | None = None,
    description: str | None = None,
    clear_description: bool = False,
) -> Playlist:
    if title is not None:
        clean_title = " ".join(title.strip().split())
        if not clean_title:
            raise PlaylistError("title is required", status_code=422)
        playlist.title = clean_title
    if clear_description:
        playlist.description = None
    elif description is not None:
        playlist.description = description.strip() or None
    playlist.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return playlist


async def delete_playlist(db: AsyncSession, playlist: Playlist) -> None:
    await db.delete(playlist)
    await db.flush()


async def add_tracks(
    db: AsyncSession,
    playlist: Playlist,
    track_ids: list[str],
    *,
    position: int | None = None,
) -> list[uuid.UUID]:
    uuids = await parse_track_ids(track_ids)
    await require_tracks_exist(db, uuids)

    existing = set(
        await db.scalars(
            select(PlaylistItem.track_id).where(PlaylistItem.playlist_id == playlist.id)
        )
    )
    overlap = [str(track_id) for track_id in uuids if track_id in existing]
    if overlap:
        raise PlaylistError(
            f"Track(s) already in playlist: {', '.join(overlap)}",
            status_code=422,
        )

    current = await ordered_track_ids(db, playlist.id)
    insert_at = len(current) if position is None else position
    if insert_at < 0 or insert_at > len(current):
        raise PlaylistError("position out of range", status_code=422)

    new_order = current[:insert_at] + uuids + current[insert_at:]
    await _rewrite_positions(db, playlist.id, new_order)
    playlist.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return new_order


async def remove_tracks(
    db: AsyncSession,
    playlist: Playlist,
    track_ids: list[str],
) -> list[uuid.UUID]:
    uuids = await parse_track_ids(track_ids)
    existing = set(
        await db.scalars(
            select(PlaylistItem.track_id).where(PlaylistItem.playlist_id == playlist.id)
        )
    )
    missing = [str(track_id) for track_id in uuids if track_id not in existing]
    if missing:
        raise PlaylistError(
            f"Track(s) not in playlist: {', '.join(missing)}",
            status_code=422,
        )

    await db.execute(
        delete(PlaylistItem).where(
            PlaylistItem.playlist_id == playlist.id,
            PlaylistItem.track_id.in_(uuids),
        )
    )
    remaining = [track_id for track_id in await ordered_track_ids(db, playlist.id)]
    await _rewrite_positions(db, playlist.id, remaining)
    playlist.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return remaining


async def reorder_tracks(
    db: AsyncSession,
    playlist: Playlist,
    track_ids: list[str],
) -> list[uuid.UUID]:
    uuids = await parse_track_ids(track_ids)
    current = set(await ordered_track_ids(db, playlist.id))
    if set(uuids) != current:
        raise PlaylistError(
            "track_ids must be a permutation of the current playlist",
            status_code=422,
        )
    await _rewrite_positions(db, playlist.id, uuids)
    playlist.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return uuids


async def _rewrite_positions(
    db: AsyncSession,
    playlist_id: uuid.UUID,
    track_ids: list[uuid.UUID],
) -> None:
    await db.execute(delete(PlaylistItem).where(PlaylistItem.playlist_id == playlist_id))
    for index, track_id in enumerate(track_ids):
        db.add(
            PlaylistItem(
                playlist_id=playlist_id,
                track_id=track_id,
                position=index,
            )
        )
    await db.flush()

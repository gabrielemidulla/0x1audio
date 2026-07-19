from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from ox1audio_backend.models import Track, TrackStatus
from ox1audio_backend.tools import registry
from ox1audio_backend.tools.serialize import track_payload_one, track_payloads
from ox1audio_backend.tools.types import ToolContext, ToolResult, ToolSpec


class GetTrackArgs(BaseModel):
    track_id: str


class ListTracksArgs(BaseModel):
    q: str | None = Field(default=None, max_length=200)
    status: TrackStatus | None = None
    limit: int = Field(default=20, ge=1, le=200)


class LibraryStatsArgs(BaseModel):
    pass


async def get_track(ctx: ToolContext, args: GetTrackArgs) -> ToolResult:
    try:
        track_uuid = uuid.UUID(args.track_id)
    except ValueError:
        return ToolResult.error("Invalid track_id")
    track = await ctx.db.scalar(select(Track).where(Track.id == track_uuid))
    if track is None:
        return ToolResult.error("Track not found")
    return ToolResult(
        payload={"track": await track_payload_one(ctx.db, track)},
        track_ids=[str(track.id)],
    )


async def list_tracks(ctx: ToolContext, args: ListTracksArgs) -> ToolResult:
    stmt = select(Track)
    if args.status is not None:
        stmt = stmt.where(Track.status == args.status)
    query = (args.q or "").strip()
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                Track.title.ilike(pattern),
                Track.artist.ilike(pattern),
            )
        )
    stmt = stmt.order_by(Track.imported_at.desc()).limit(args.limit)
    rows = list(await ctx.db.scalars(stmt))
    tracks = await track_payloads(ctx.db, rows)
    return ToolResult(
        payload={"tracks": tracks},
        track_ids=[track["id"] for track in tracks],
    )


async def library_stats(ctx: ToolContext, _args: LibraryStatsArgs) -> ToolResult:
    status_rows = await ctx.db.execute(
        select(Track.status, func.count()).group_by(Track.status)
    )
    by_status: dict[str, int] = {str(status): count for status, count in status_rows}

    ready_tracks = await ctx.db.scalars(
        select(Track).where(Track.status == TrackStatus.READY)
    )
    total_duration_s = 0.0
    ready_count = 0
    for track in ready_tracks:
        ready_count += 1
        if track.duration_s is not None:
            total_duration_s += float(track.duration_s)

    payload: dict[str, Any] = {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "ready": ready_count,
        "total_duration_s": round(total_duration_s, 2),
    }
    return ToolResult(payload=payload)


def register_tools() -> None:
    registry.register(
        ToolSpec(
            name="get_track",
            description="Fetch one catalog track by id (title, artist, status, duration).",
            args_model=GetTrackArgs,
            handler=get_track,
        )
    )
    registry.register(
        ToolSpec(
            name="list_tracks",
            description=(
                "Browse/list catalog tracks with optional status filter. "
                "For finding a song/artist by name use search_metadata; "
                "for mood/vibe use search_vibe. Optional q is a weak metadata filter only."
            ),
            args_model=ListTracksArgs,
            handler=list_tracks,
        )
    )
    registry.register(
        ToolSpec(
            name="library_stats",
            description="Return catalog counts by status and total duration of ready tracks.",
            args_model=LibraryStatsArgs,
            handler=library_stats,
        )
    )

from __future__ import annotations

import logging
import uuid
from typing import Literal

import grpc
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from tunelink_backend.ml_client import SearchHit, get_ml_client
from tunelink_backend.models import Track, TrackStatus
from tunelink_backend.tools import registry
from tunelink_backend.tools.serialize import track_payload
from tunelink_backend.tools.types import ToolContext, ToolResult, ToolSpec

logger = logging.getLogger(__name__)


class SearchVibeArgs(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=500,
        description="Natural-language vibe, mood, or sonic description (not a title/artist lookup).",
    )
    negative_query: str | None = Field(
        default=None,
        max_length=500,
        description="Optional qualities to push away from the results.",
    )
    top_k: int = Field(default=12, ge=1, le=20)
    mode: Literal["tracks", "segments"] = "tracks"


class SearchMetadataArgs(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=200,
        description="Literal text to match against title or artist metadata.",
    )
    status: TrackStatus | None = Field(
        default=TrackStatus.READY,
        description="Optional status filter. Defaults to ready tracks.",
    )
    limit: int = Field(default=12, ge=1, le=50)


class SimilarTracksArgs(BaseModel):
    track_id: str = Field(description="Catalog track id to find AI-similar tracks for.")
    top_k: int = Field(default=6, ge=1, le=20)


def _hit_payload(track: Track, hit: SearchHit) -> dict:
    return {
        **track_payload(track),
        "score": round(float(hit.score), 4),
    }


async def _hydrate_hits(ctx: ToolContext, hits: list[SearchHit]) -> ToolResult:
    uuids: list[uuid.UUID] = []
    for hit in hits:
        try:
            uuids.append(uuid.UUID(hit.track_id))
        except ValueError:
            continue
    tracks_by_id: dict[str, Track] = {}
    if uuids:
        rows = await ctx.db.scalars(select(Track).where(Track.id.in_(uuids)))
        tracks_by_id = {str(track.id): track for track in rows}

    results: list[dict] = []
    track_ids: list[str] = []
    for hit in hits:
        track = tracks_by_id.get(hit.track_id)
        if track is None:
            continue
        results.append(_hit_payload(track, hit))
        track_ids.append(str(track.id))
    return ToolResult(payload={"results": results}, track_ids=track_ids)


async def search_vibe(ctx: ToolContext, args: SearchVibeArgs) -> ToolResult:
    """AI/ML embedding search by mood, vibe, or sonic description."""
    client = get_ml_client()
    try:
        hits = client.search_text(
            query=args.query.strip(),
            top_k=args.top_k,
            mode=args.mode,
            negative_query=args.negative_query.strip() if args.negative_query else None,
        )
    except grpc.RpcError as exc:
        logger.exception("search_vibe tool gRPC failed")
        return ToolResult.error(f"AI search failed: {exc.details() or exc.code().name}")
    finally:
        client.close()
    return await _hydrate_hits(ctx, hits)


async def search_metadata(ctx: ToolContext, args: SearchMetadataArgs) -> ToolResult:
    """Exact-ish metadata lookup over title/artist (no ML)."""
    pattern = f"%{args.query.strip()}%"
    stmt = select(Track).where(
        or_(
            Track.title.ilike(pattern),
            Track.artist.ilike(pattern),
        )
    )
    if args.status is not None:
        stmt = stmt.where(Track.status == args.status)
    stmt = stmt.order_by(Track.imported_at.desc()).limit(args.limit)
    rows = list(await ctx.db.scalars(stmt))
    tracks = [track_payload(track) for track in rows]
    return ToolResult(
        payload={"tracks": tracks, "match": "metadata"},
        track_ids=[track["id"] for track in tracks],
    )


async def similar_tracks(ctx: ToolContext, args: SimilarTracksArgs) -> ToolResult:
    """AI/ML audio similarity to a known track."""
    try:
        track_uuid = uuid.UUID(args.track_id)
    except ValueError:
        return ToolResult.error("Invalid track_id")

    track = await ctx.db.scalar(select(Track).where(Track.id == track_uuid))
    if track is None:
        return ToolResult.error("Track not found")

    client = get_ml_client()
    try:
        hits = client.similar_tracks(track_id=str(track_uuid), top_k=args.top_k)
    except grpc.RpcError as exc:
        logger.exception("similar_tracks tool gRPC failed")
        return ToolResult.error(f"AI search failed: {exc.details() or exc.code().name}")
    finally:
        client.close()
    return await _hydrate_hits(ctx, hits)


def register_tools() -> None:
    registry.register(
        ToolSpec(
            name="search_vibe",
            description=(
                "AI search: find tracks by mood, vibe, genre feel, or sonic description "
                "using ML embeddings. Use this for 'chill', 'dark techno', 'like a sunset', "
                "etc. Do NOT use this to look up a known title or artist name."
            ),
            args_model=SearchVibeArgs,
            handler=search_vibe,
        )
    )
    registry.register(
        ToolSpec(
            name="search_metadata",
            description=(
                "Metadata search: find tracks by matching title or artist text "
                "(case-insensitive substring). Use this when the user names a song, "
                "artist, or exact phrase. Do NOT use this for vibe/mood queries."
            ),
            args_model=SearchMetadataArgs,
            handler=search_metadata,
        )
    )
    registry.register(
        ToolSpec(
            name="similar_tracks",
            description=(
                "AI search: find tracks that sound similar to a known catalog track_id "
                "using ML audio embeddings. Requires a track_id from a previous tool result."
            ),
            args_model=SimilarTracksArgs,
            handler=similar_tracks,
        )
    )

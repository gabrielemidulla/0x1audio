from __future__ import annotations

import logging
import uuid
from typing import Literal

import grpc
from pydantic import BaseModel, Field
from sqlalchemy import select

from ox1audio_backend.ml_client import SearchHit, get_ml_client
from ox1audio_backend.models import Track, TrackStatus
from ox1audio_backend.services.track_search import search_tracks_by_metadata
from ox1audio_backend.tools import registry
from ox1audio_backend.tools.serialize import track_payloads
from ox1audio_backend.tools.types import ToolContext, ToolResult, ToolSpec

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

    ordered = [tracks_by_id[hit.track_id] for hit in hits if hit.track_id in tracks_by_id]
    payloads = await track_payloads(ctx.db, ordered)
    by_id = {payload["id"]: payload for payload in payloads}

    results: list[dict] = []
    track_ids: list[str] = []
    for hit in hits:
        base = by_id.get(hit.track_id)
        if base is None:
            continue
        results.append({**base, "score": round(float(hit.score), 4)})
        track_ids.append(hit.track_id)
    return ToolResult(payload={"results": results}, track_ids=track_ids)


async def search_vibe(ctx: ToolContext, args: SearchVibeArgs) -> ToolResult:
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
    rows = await search_tracks_by_metadata(
        ctx.db,
        args.query,
        status=args.status,
        limit=args.limit,
    )
    tracks = await track_payloads(ctx.db, rows)
    return ToolResult(
        payload={"tracks": tracks, "match": "metadata"},
        track_ids=[track["id"] for track in tracks],
    )


async def similar_tracks(ctx: ToolContext, args: SimilarTracksArgs) -> ToolResult:
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
                "using ML embeddings. Use for 'chill', 'dark techno', 'like a sunset', etc. "
                "Do NOT use for a named song title — that is search_metadata, then "
                "similar_tracks if the user wants songs that sound like it."
            ),
            args_model=SearchVibeArgs,
            handler=search_vibe,
        )
    )
    registry.register(
        ToolSpec(
            name="search_metadata",
            description=(
                "Metadata search: find tracks by title or artist text. Tolerates typos "
                "and matches words across title/artist "
                "(e.g. 'ghost town arcado' finds Ghost Town by Arcando). "
                "Use when the user names a song or artist — including to resolve a "
                "title into a track_id before calling similar_tracks. "
                "Do NOT use for vibe/mood queries."
            ),
            args_model=SearchMetadataArgs,
            handler=search_metadata,
        )
    )
    registry.register(
        ToolSpec(
            name="similar_tracks",
            description=(
                "AI audio similarity: find tracks that sound like a catalog track "
                "(embedding/graph neighbors). Requires track_id (UUID) from "
                "search_metadata. For 'songs like [title]', resolve the title first, "
                "then call this — and STOP. Do NOT follow up with search_metadata or "
                "artist lookups; these results are the similarity answer."
            ),
            args_model=SimilarTracksArgs,
            handler=similar_tracks,
        )
    )

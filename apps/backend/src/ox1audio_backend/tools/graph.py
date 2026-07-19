from __future__ import annotations

import logging
import uuid

import grpc
from pydantic import BaseModel, Field
from sqlalchemy import select

from ox1audio_backend.ml_client import get_ml_client
from ox1audio_backend.models import Track
from ox1audio_backend.tools import registry
from ox1audio_backend.tools.serialize import track_payloads
from ox1audio_backend.tools.types import ToolContext, ToolResult, ToolSpec

logger = logging.getLogger(__name__)


class GraphNeighborhoodArgs(BaseModel):
    focus_track_id: str | None = None
    limit: int = Field(default=12, ge=2, le=24)


async def graph_neighborhood(ctx: ToolContext, args: GraphNeighborhoodArgs) -> ToolResult:
    focus_uuid: uuid.UUID | None = None
    if args.focus_track_id:
        try:
            focus_uuid = uuid.UUID(args.focus_track_id)
        except ValueError:
            return ToolResult.error("Invalid focus_track_id")
        focus = await ctx.db.scalar(select(Track).where(Track.id == focus_uuid))
        if focus is None:
            return ToolResult.error("Focus track not found")

    client = get_ml_client()
    try:
        result = client.graph(
            focus_track_id=str(focus_uuid) if focus_uuid else None,
            limit=args.limit,
        )
    except grpc.RpcError as exc:
        logger.exception("graph_neighborhood tool gRPC failed")
        return ToolResult.error(f"ML graph failed: {exc.details() or exc.code().name}")
    finally:
        client.close()

    uuids: list[uuid.UUID] = []
    for value in result.node_ids:
        try:
            uuids.append(uuid.UUID(value))
        except ValueError:
            continue
    tracks_by_id: dict[str, Track] = {}
    if uuids:
        rows = await ctx.db.scalars(select(Track).where(Track.id.in_(uuids)))
        tracks_by_id = {str(track.id): track for track in rows}

    ordered = [
        tracks_by_id[track_id]
        for track_id in result.node_ids
        if track_id in tracks_by_id
    ]
    nodes = await track_payloads(ctx.db, ordered)
    known = set(tracks_by_id)
    links = [
        {
            "source": link.source,
            "target": link.target,
            "weight": link.weight,
            "audio_weight": link.audio_weight,
            "profile_weight": link.profile_weight,
            "reasons": link.reasons,
        }
        for link in result.links
        if link.source in known and link.target in known
    ]
    track_ids = [node["id"] for node in nodes]
    return ToolResult(
        payload={"nodes": nodes, "links": links},
        track_ids=track_ids,
    )


def register_tools() -> None:
    registry.register(
        ToolSpec(
            name="graph_neighborhood",
            description=(
                "Return a similarity neighborhood around an optional focus track, "
                "or a small sample of the catalog graph when no focus is given."
            ),
            args_model=GraphNeighborhoodArgs,
            handler=graph_neighborhood,
        )
    )

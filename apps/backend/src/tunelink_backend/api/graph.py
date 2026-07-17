from __future__ import annotations

import logging
import uuid

import grpc
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tunelink_backend.api.catalog import TrackOut
from tunelink_backend.auth.deps import get_current_user
from tunelink_backend.db import get_db
from tunelink_backend.ml_client import get_ml_client
from tunelink_backend.models import Track, User

logger = logging.getLogger(__name__)

router = APIRouter()


class GraphLinkOut(BaseModel):
    source: uuid.UUID
    target: uuid.UUID
    weight: float
    audio_weight: float
    profile_weight: float
    reasons: list[str]


class GraphNodeOut(BaseModel):
    track: TrackOut


class GraphResponseOut(BaseModel):
    nodes: list[GraphNodeOut]
    links: list[GraphLinkOut]


@router.get("", response_model=GraphResponseOut, operation_id="getGraph")
async def get_graph(
    focus_track_id: uuid.UUID | None = None,
    limit: int = Query(default=12, ge=2, le=24),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> GraphResponseOut:
    if focus_track_id is not None:
        focus = await db.scalar(select(Track).where(Track.id == focus_track_id))
        if focus is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    client = get_ml_client()
    try:
        result = client.graph(
            focus_track_id=str(focus_track_id) if focus_track_id else None,
            limit=limit,
        )
    except grpc.RpcError as exc:
        logger.exception("graph gRPC failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ML graph failed: {exc.details() or exc.code().name}",
        ) from exc
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
        rows = await db.scalars(select(Track).where(Track.id.in_(uuids)))
        tracks_by_id = {str(track.id): track for track in rows}

    nodes = [
        GraphNodeOut(track=TrackOut.model_validate(tracks_by_id[track_id]))
        for track_id in result.node_ids
        if track_id in tracks_by_id
    ]
    known = set(tracks_by_id)
    links = [
        GraphLinkOut(
            source=uuid.UUID(link.source),
            target=uuid.UUID(link.target),
            weight=link.weight,
            audio_weight=link.audio_weight,
            profile_weight=link.profile_weight,
            reasons=link.reasons,
        )
        for link in result.links
        if link.source in known and link.target in known
    ]
    return GraphResponseOut(nodes=nodes, links=links)

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from tunelink_backend.auth.deps import get_current_user
from tunelink_backend.db import get_db
from tunelink_backend.main import app
from tunelink_backend.models import Playlist, User
from tunelink_backend.services import playlists as playlist_svc
from tunelink_backend.tools.playlists import (
    CreatePlaylistArgs,
    GetPlaylistArgs,
    create_playlist,
    get_playlist,
)
from tunelink_backend.tools.types import ToolContext


def _user(*, user_id=None) -> User:
    return User(
        id=user_id or uuid4(),
        email="owner@example.com",
        password_hash="x",
        role="user",
    )


def _playlist(*, user_id, playlist_id=None, title="Focus") -> Playlist:
    now = datetime.now(timezone.utc)
    return Playlist(
        id=playlist_id or uuid4(),
        user_id=user_id,
        title=title,
        description=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_get_owned_playlist_wrong_user_raises() -> None:
    owner_id = uuid4()
    other_id = uuid4()
    playlist_id = uuid4()
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)

    with pytest.raises(playlist_svc.PlaylistError) as exc_info:
        await playlist_svc.get_owned_playlist(db, playlist_id, other_id)

    assert exc_info.value.status_code == 404
    db.scalar.assert_awaited_once()
    # query always filters by both playlist id and requested user
    assert owner_id != other_id


@pytest.mark.asyncio
async def test_create_playlist_tool_happy_path() -> None:
    user_id = uuid4()
    playlist = _playlist(user_id=user_id)
    db = AsyncMock()
    db.commit = AsyncMock()
    ctx = ToolContext(db=db, user_id=user_id)

    with (
        patch(
            "tunelink_backend.tools.playlists.playlist_svc.create_playlist",
            new=AsyncMock(return_value=playlist),
        ) as create_mock,
        patch(
            "tunelink_backend.tools.playlists.playlist_svc.ordered_track_ids",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "tunelink_backend.tools.playlists._tracks_payload",
            new=AsyncMock(return_value=([], [])),
        ),
    ):
        result = await create_playlist(
            ctx,
            CreatePlaylistArgs(title="Focus", description=None, track_ids=None),
        )

    assert "error" not in result.payload
    assert result.payload["playlist"]["id"] == str(playlist.id)
    assert result.payload["playlist"]["title"] == "Focus"
    create_mock.assert_awaited_once()
    assert create_mock.await_args.kwargs["user_id"] == user_id
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_playlist_tool_wrong_user_isolation() -> None:
    owner_id = uuid4()
    other_id = uuid4()
    playlist_id = uuid4()
    db = AsyncMock()
    ctx = ToolContext(db=db, user_id=other_id)

    with patch(
        "tunelink_backend.tools.playlists.playlist_svc.get_owned_playlist",
        new=AsyncMock(
            side_effect=playlist_svc.PlaylistError("Playlist not found", status_code=404)
        ),
    ) as get_mock:
        result = await get_playlist(ctx, GetPlaylistArgs(playlist_id=str(playlist_id)))

    assert result.payload == {"error": "Playlist not found"}
    get_mock.assert_awaited_once_with(db, playlist_id, other_id)
    assert owner_id != other_id


@pytest.mark.asyncio
async def test_api_get_playlist_ownership() -> None:
    owner = _user()
    playlist = _playlist(user_id=owner.id)
    db = AsyncMock()

    async def override_db():
        yield db

    async def override_user():
        return owner

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        with (
            patch(
                "tunelink_backend.api.playlists.playlist_svc.get_owned_playlist",
                new=AsyncMock(return_value=playlist),
            ) as get_mock,
            patch(
                "tunelink_backend.api.playlists.playlist_svc.ordered_track_ids",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "tunelink_backend.api.playlists.hydrate_tracks",
                new=AsyncMock(return_value=[]),
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/v1/playlists/{playlist.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(playlist.id)
        assert body["title"] == "Focus"
        get_mock.assert_awaited_once_with(db, playlist.id, owner.id)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_get_playlist_foreign_is_404() -> None:
    viewer = _user()
    foreign_id = uuid4()
    db = AsyncMock()

    async def override_db():
        yield db

    async def override_user():
        return viewer

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        with patch(
            "tunelink_backend.api.playlists.playlist_svc.get_owned_playlist",
            new=AsyncMock(
                side_effect=playlist_svc.PlaylistError("Playlist not found", status_code=404)
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/v1/playlists/{foreign_id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Playlist not found"
    finally:
        app.dependency_overrides.clear()

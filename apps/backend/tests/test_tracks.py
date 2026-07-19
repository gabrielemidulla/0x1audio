from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from ox1audio_backend.models import Track, TrackStatus
from ox1audio_backend.services import tracks as track_svc


def _track(*, track_id=None) -> Track:
    now = datetime.now(timezone.utc)
    return Track(
        id=track_id or uuid4(),
        title="Song",
        artist="Artist",
        original_filename="song.mp3",
        object_key="audio/song.mp3",
        cover_object_key="covers/song.jpg",
        content_type="audio/mpeg",
        size_bytes=1000,
        status=TrackStatus.READY,
        imported_at=now,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_delete_tracks_removes_storage_and_rows() -> None:
    track = _track()
    db = AsyncMock()
    db.scalars = AsyncMock(return_value=[track])
    db.execute = AsyncMock()
    db.flush = AsyncMock()

    with (
        patch("ox1audio_backend.services.tracks.storage.remove_object") as remove_mock,
        patch("ox1audio_backend.services.tracks._delete_qdrant_points") as qdrant_mock,
    ):
        deleted = await track_svc.delete_tracks(db, [track.id])

    assert deleted == 1
    assert remove_mock.call_count == 2
    qdrant_mock.assert_called_once_with([str(track.id)])
    db.execute.assert_awaited_once()
    db.flush.assert_awaited_once()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_delete_tracks_empty_ids() -> None:
    db = AsyncMock()
    deleted = await track_svc.delete_tracks(db, [])
    assert deleted == 0
    db.scalars.assert_not_called()

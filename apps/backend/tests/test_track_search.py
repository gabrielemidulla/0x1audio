from __future__ import annotations

import pytest

from ox1audio_backend.models import TrackStatus
from ox1audio_backend.services.track_search import (
    metadata_match_score,
    metadata_query_tokens,
    search_tracks_by_metadata,
    track_metadata_match_clause,
)


def test_metadata_tokens_drop_stopwords() -> None:
    assert metadata_query_tokens("Ghost town of arcando") == [
        "ghost",
        "town",
        "arcando",
    ]
    assert metadata_query_tokens("Ghost Town Arcado") == [
        "ghost",
        "town",
        "arcado",
    ]


def test_metadata_match_score_prefers_ghost_town_with_typo() -> None:
    query = "Ghost Town Arcado"
    ghost = metadata_match_score(
        "Ghost Town (feat. Vanessa Campagna)",
        "Arcando, ThatBehavior",
        query,
    )
    other_arcando = metadata_match_score("Elevate", "Arcando, Fabian Mazur", query)
    noise = metadata_match_score("Downtown Lights", "Someone", query)
    assert ghost > other_arcando
    assert ghost > noise


def test_track_metadata_match_clause_builds() -> None:
    assert track_metadata_match_clause("") is None
    assert track_metadata_match_clause("ghost town of arcando") is not None
    assert track_metadata_match_clause("Ghost Town Arcado") is not None


@pytest.mark.asyncio
async def test_search_tracks_by_metadata_fuzzy_and_exact() -> None:
    """Single DB session / event loop to avoid asyncpg pool loop conflicts."""
    from ox1audio_backend.db import SessionLocal

    async with SessionLocal() as db:
        typo = await search_tracks_by_metadata(
            db,
            "Ghost Town Arcado",
            status=TrackStatus.READY,
            limit=5,
        )
        exact = await search_tracks_by_metadata(
            db,
            "ghost town of arcando",
            status=TrackStatus.READY,
            limit=5,
        )
        nonsense = await search_tracks_by_metadata(
            db,
            "zzxqvnmplkjhgfdsa987",
            status=TrackStatus.READY,
            limit=5,
        )

    assert typo, "expected fuzzy match for Ghost Town / Arcando"
    assert "ghost town" in typo[0].title.lower()
    assert "arcando" in (typo[0].artist or "").lower()

    assert exact
    assert "ghost town" in exact[0].title.lower()

    assert nonsense == []

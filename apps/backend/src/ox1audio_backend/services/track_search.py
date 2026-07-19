from __future__ import annotations

import re
from difflib import SequenceMatcher

from sqlalchemy import Float, and_, case, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from ox1audio_backend.models import Artist, Track, TrackArtist, TrackStatus

# pg_trgm word_similarity threshold (Arcado↔Arcando ≈ 0.57).
WORD_SIM_THRESHOLD = 0.45

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "by",
        "feat",
        "ft",
        "with",
        "from",
        "for",
        "in",
        "on",
        "at",
    }
)


def metadata_query_tokens(query: str) -> list[str]:
    """Significant tokens for multi-word catalog metadata search."""
    tokens: list[str] = []
    seen: set[str] = set()
    for raw in re.split(r"[^a-z0-9]+", query.lower()):
        if len(raw) < 3 or raw in _STOPWORDS or raw in seen:
            continue
        seen.add(raw)
        tokens.append(raw)
    return tokens


def _ilike_contains(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _haystack_expr():
    return func.concat(
        Track.title,
        literal(" "),
        func.coalesce(Track.artist, literal("")),
    )


def _field_matches_token_exact(token: str):
    pattern = _ilike_contains(token)
    artist_track_ids = (
        select(TrackArtist.track_id)
        .join(Artist, Artist.id == TrackArtist.artist_id)
        .where(Artist.name.ilike(pattern, escape="\\"))
    )
    return or_(
        Track.title.ilike(pattern, escape="\\"),
        Track.artist.ilike(pattern, escape="\\"),
        Track.id.in_(artist_track_ids),
    )


def _field_matches_token_fuzzy(token: str):
    """Token fuzzy-matches a word in title/artist or a linked artist name."""
    hay = _haystack_expr()
    linked = (
        select(TrackArtist.track_id)
        .join(Artist, Artist.id == TrackArtist.artist_id)
        .where(func.word_similarity(literal(token), Artist.name) > WORD_SIM_THRESHOLD)
    )
    return or_(
        func.word_similarity(literal(token), hay) > WORD_SIM_THRESHOLD,
        func.word_similarity(literal(token), Track.title) > WORD_SIM_THRESHOLD,
        func.word_similarity(literal(token), func.coalesce(Track.artist, literal("")))
        > WORD_SIM_THRESHOLD,
        Track.id.in_(linked),
    )


def _exact_match_clause(cleaned: str, tokens: list[str]):
    phrase = _ilike_contains(cleaned)
    artist_track_ids = (
        select(TrackArtist.track_id)
        .join(Artist, Artist.id == TrackArtist.artist_id)
        .where(Artist.name.ilike(phrase, escape="\\"))
    )
    phrase_clause = or_(
        Track.title.ilike(phrase, escape="\\"),
        Track.artist.ilike(phrase, escape="\\"),
        Track.id.in_(artist_track_ids),
    )
    if not tokens:
        return phrase_clause
    if len(tokens) == 1:
        return or_(phrase_clause, _field_matches_token_exact(tokens[0]))
    return or_(phrase_clause, and_(*[_field_matches_token_exact(tok) for tok in tokens]))


def _fuzzy_match_clause(tokens: list[str]):
    if not tokens:
        return None
    if len(tokens) == 1:
        return _field_matches_token_fuzzy(tokens[0])
    return and_(*[_field_matches_token_fuzzy(tok) for tok in tokens])


def track_metadata_match_clause(query: str):
    """
    Match tracks by title / denormalized artist / linked artist names.

    Combines:
    - exact phrase / all-tokens substring match
    - fuzzy all-tokens match via pg_trgm word_similarity (typo tolerant)
    """
    cleaned = query.strip()
    if not cleaned:
        return None

    tokens = metadata_query_tokens(cleaned)
    exact = _exact_match_clause(cleaned, tokens)
    fuzzy = _fuzzy_match_clause(tokens)
    if fuzzy is None:
        return exact
    return or_(exact, fuzzy)


def metadata_relevance_expr(query: str) -> ColumnElement:
    """SQL relevance score for ORDER BY when searching with q=."""
    cleaned = query.strip()
    tokens = metadata_query_tokens(cleaned)
    hay = _haystack_expr()
    lowered_q = literal(cleaned.lower())
    lowered_hay = func.lower(hay)

    score = cast(func.similarity(lowered_q, lowered_hay), Float) * 20.0
    score = score + case(
        (func.lower(Track.title) == cleaned.lower(), 100.0),
        (Track.title.ilike(_ilike_contains(cleaned), escape="\\"), 50.0),
        else_=0.0,
    )
    for tok in tokens:
        score = score + cast(func.word_similarity(literal(tok), hay), Float) * 8.0
        score = score + case(
            (Track.title.ilike(_ilike_contains(tok), escape="\\"), 6.0),
            else_=0.0,
        )
        score = score + case(
            (Track.artist.ilike(_ilike_contains(tok), escape="\\"), 4.0),
            else_=0.0,
        )
    return score


def _best_word_ratio(token: str, text: str) -> float:
    best = 0.0
    for word in re.split(r"[^a-z0-9]+", (text or "").lower()):
        if len(word) < 2:
            continue
        best = max(best, SequenceMatcher(None, token, word).ratio())
    return best


def metadata_match_score(title: str, artist: str, query: str) -> float:
    """
    Python-side ranking mirror (unit tests / fallback).
    Uses SequenceMatcher as a stand-in for pg_trgm word_similarity.
    """
    q = query.strip().lower()
    title_l = (title or "").lower()
    artist_l = (artist or "").lower()
    hay = f"{title_l} {artist_l}".strip()
    tokens = metadata_query_tokens(q)

    score = SequenceMatcher(None, q, hay).ratio() * 20.0
    if title_l == q:
        score += 100.0
    elif q and q in title_l:
        score += 50.0
    elif q and q in hay:
        score += 30.0

    for tok in tokens:
        score += _best_word_ratio(tok, hay) * 8.0
        if tok in title_l:
            score += 6.0
        elif tok in artist_l:
            score += 4.0
    return score


async def search_tracks_by_metadata(
    db: AsyncSession,
    query: str,
    *,
    status: TrackStatus | None = TrackStatus.READY,
    limit: int = 12,
    offset: int = 0,
) -> list[Track]:
    """Ranked metadata search used by chat tools and catalog listing."""
    cleaned = query.strip()
    clause = track_metadata_match_clause(cleaned)
    if clause is None:
        return []

    stmt = select(Track).where(clause)
    if status is not None:
        stmt = stmt.where(Track.status == status)
    stmt = (
        stmt.order_by(
            metadata_relevance_expr(cleaned).desc(),
            Track.imported_at.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return list(await db.scalars(stmt))

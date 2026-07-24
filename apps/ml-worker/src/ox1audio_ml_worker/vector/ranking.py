from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any

from ox1audio_ml_worker.config import get_settings


@dataclass
class BaselineStats:
    mean: float
    std: float

    def z(self, score: float) -> float:
        return (score - self.mean) / self.std


@dataclass
class ScoredTrack:
    track_id: str
    score: float
    track_score: float
    best_segment_score: float
    segment_coverage: float
    match_scope: str
    matched_segment_ids: list[str]
    reasons: list[str]
    standout: float | None


def baseline_from_scores(scores: list[float]) -> BaselineStats | None:
    settings = get_settings()
    if len(scores) < settings.min_sample:
        return None
    mean = statistics.fmean(scores)
    std = statistics.pstdev(scores)
    return BaselineStats(mean, max(std, 0.01))


def cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def clamp01(value: float) -> float:
    return max(0.0, min(value, 1.0))


def query_terms(query: str | None) -> list[str]:
    if not query:
        return []
    return [term.strip().lower() for term in query.split() if term.strip()]


def term_matches_tag(term: str, tag: str) -> bool:
    return term == tag or term in tag or tag in term


def soft_tag_boost(query: str | None, search_tags: list[str]) -> float:
    terms = query_terms(query)
    if not terms or not search_tags:
        return 0.0
    tags = {tag.strip().lower() for tag in search_tags if tag.strip()}
    if any(term_matches_tag(term, tag) for term in terms for tag in tags):
        return get_settings().tag_boost_sigma
    return 0.0


def build_scored_track(
    track_id: str,
    row: dict[str, Any],
    mode: str,
    audio_baseline: BaselineStats | None,
    profile_baseline: BaselineStats | None,
    *,
    query_text: str | None = None,
) -> ScoredTrack:
    settings = get_settings()
    segment_rows = sorted(row["segments"], key=lambda item: item[1], reverse=True)
    track_score = float(row["track_score"])
    best_segment_score = float(segment_rows[0][1]) if segment_rows else track_score
    segment_count = max(int(row["segment_count"]), 1)
    matched_segments = [
        segment_id for segment_id, score in segment_rows[:2] if score > 0
    ]
    coverage = min(
        len([score for _, score in segment_rows if score > 0.25]) / segment_count,
        1.0,
    )
    audio_evidence = (
        (best_segment_score * 0.7) + (track_score * 0.3)
        if mode == "segments"
        else (track_score * 0.75) + (best_segment_score * 0.25)
    )
    profile_score = row.get("profile_score")
    has_audio_evidence = bool(segment_rows) or track_score != 0.0
    tag_boost = soft_tag_boost(query_text, list(row.get("search_tags") or []))

    standout: float | None = None
    if audio_baseline is not None:
        z_audio = audio_baseline.z(audio_evidence) if has_audio_evidence else None
        z_profile = (
            profile_baseline.z(float(profile_score))
            if profile_score is not None and profile_baseline is not None
            else None
        )
        if z_audio is not None and z_profile is not None:
            standout = (z_audio * settings.audio_search_weight) + (
                z_profile * settings.profile_search_weight
            )
        elif z_profile is not None:
            standout = z_profile
        else:
            standout = z_audio if z_audio is not None else 0.0
        standout += coverage * 0.25
        standout += tag_boost
        score = clamp01(standout / settings.sigma_full_scale)
    else:
        audio_score = (
            (best_segment_score * 0.58) + (track_score * 0.22) + (coverage * 0.2)
            if mode == "segments"
            else (track_score * 0.7) + (best_segment_score * 0.2) + (coverage * 0.1)
        )
        score = audio_score
        if profile_score is not None:
            score = (audio_score * settings.audio_search_weight) + (
                max(0.0, float(profile_score)) * settings.profile_search_weight
            )
        if tag_boost:
            score = clamp01(score + (tag_boost / settings.sigma_full_scale))

    scope = (
        "segment"
        if best_segment_score > track_score + 0.08
        else "mixed"
        if coverage >= 0.4
        else "track"
    )
    reasons = list(row.get("reasons") or [])[:3]
    if tag_boost > 0:
        reasons = ["tag overlap", *reasons][:3]

    return ScoredTrack(
        track_id=track_id,
        score=round(score, 4),
        track_score=round(track_score, 4),
        best_segment_score=round(best_segment_score, 4),
        segment_coverage=round(coverage, 4),
        match_scope=scope,
        matched_segment_ids=matched_segments,
        reasons=reasons,
        standout=standout,
    )


def filter_tiny_catalog(results: list[ScoredTrack]) -> list[ScoredTrack]:
    settings = get_settings()
    min_score = 0.08
    standout_margin = 0.04
    mad_multiplier = 1.6
    results = [result for result in results if result.score >= min_score]
    if len(results) < settings.min_sample:
        return results
    scores = [result.score for result in results]
    median = statistics.median(scores)
    mad = statistics.median(abs(score - median) for score in scores)
    floor = median + max(standout_margin, mad_multiplier * mad)
    return [result for result in results if result.score >= floor]


def combined_graph_score(
    audio_score: float,
    profile_score: float,
    *,
    sonic_weight: float | None = None,
    vibe_weight: float | None = None,
) -> float:
    """Blend audio + profile cosines. Weights are raw multipliers (need not sum to 1)."""
    settings = get_settings()
    audio_w = settings.audio_search_weight if sonic_weight is None else float(sonic_weight)
    profile_w = (
        settings.profile_search_weight if vibe_weight is None else float(vibe_weight)
    )
    audio_w = max(0.0, audio_w)
    profile_w = max(0.0, profile_w)
    if audio_w <= 0 and profile_w <= 0:
        return max(0.0, audio_score)
    if profile_w <= 0:
        return max(0.0, audio_score) * audio_w
    if audio_w <= 0:
        return max(0.0, profile_score) * profile_w
    return (max(0.0, audio_score) * audio_w) + (max(0.0, profile_score) * profile_w)

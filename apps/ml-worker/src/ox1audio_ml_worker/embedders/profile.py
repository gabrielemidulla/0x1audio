from __future__ import annotations

from typing import Any

from ox1audio_ml_worker.config import get_settings

PROFILE_TAG_PREFIX = "Music tags: "


def track_audio_profile_text(analysis: dict[str, Any]) -> str:
    genres = qualifying_labels(analysis.get("genre_scores"), max_count=10)
    moods = qualifying_labels(analysis.get("mood_scores"), max_count=12)
    instruments = qualifying_labels(analysis.get("instrument_scores"), max_count=12)
    fallback_tags = qualifying_labels(analysis.get("model_tags"), max_count=10)

    head_genres = genres[:3]
    head_moods = moods[:5]
    head_instruments = instruments[:5]

    parts: list[str] = []
    if analysis.get("is_instrumental") is True:
        parts.append("An instrumental track without vocals")
    elif analysis.get("is_instrumental") is False:
        parts.append("A vocal track")
    elif head_genres:
        parts.append(f"A {join_labels(head_genres)} track")
    else:
        parts.append("A music track")
    if head_genres and analysis.get("is_instrumental") is not None:
        parts.append(f"in a {join_labels(head_genres)} style")
    if head_moods:
        parts.append(f"with a {join_labels(head_moods)} mood")
    if head_instruments:
        parts.append(f"featuring {join_labels(head_instruments)}")
    sentence = " ".join(parts) + "."

    if not head_genres and not head_moods and not head_instruments:
        if not fallback_tags:
            return ""
        return f"A music track described as {join_labels(fallback_tags)}."

    extra = [
        label
        for label in genres[3:] + moods[5:] + instruments[5:]
        if label not in head_genres + head_moods + head_instruments
    ]
    if extra:
        sentence += f" Also tagged: {join_labels(extra[:12])}."
    return sentence


def track_profile_tag_text(analysis: dict[str, Any]) -> str:
    tags: list[str] = []
    seen: set[str] = set()
    for key in ("genre_scores", "mood_scores", "instrument_scores"):
        for label in qualifying_labels(analysis.get(key), max_count=15):
            normalized_label = label.strip().lower()
            if normalized_label and normalized_label not in seen:
                seen.add(normalized_label)
                tags.append(label.strip())
    if not tags:
        for label in qualifying_labels(analysis.get("model_tags"), max_count=12):
            normalized_label = label.strip().lower()
            if normalized_label and normalized_label not in seen:
                seen.add(normalized_label)
                tags.append(label.strip())
    if not tags:
        return ""
    return f"{PROFILE_TAG_PREFIX}{', '.join(tags)}."


def profile_search_tags(analysis: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    if analysis.get("is_instrumental") is True:
        tags.extend(["instrumental", "no vocals"])
        seen.update({"instrumental", "no vocals"})
    elif analysis.get("is_instrumental") is False:
        tags.extend(["vocals", "vocal"])
        seen.update({"vocals", "vocal"})
    for key in ("genre_scores", "mood_scores", "instrument_scores", "model_tags"):
        for label in qualifying_labels(analysis.get(key), max_count=20):
            normalized_label = label.strip().lower()
            if normalized_label and normalized_label not in seen:
                seen.add(normalized_label)
                tags.append(normalized_label)
    return tags


def qualifying_labels(
    scores: object,
    *,
    max_count: int = 12,
    min_relative: float | None = None,
) -> list[str]:
    if not isinstance(scores, dict) or not scores:
        return []

    relative = (
        get_settings().profile_label_relative if min_relative is None else min_relative
    )
    items: list[tuple[str, float]] = []
    for label, score in scores.items():
        text = str(label).strip()
        if not text:
            continue
        try:
            value = float(score)
        except (TypeError, ValueError):
            value = 0.0
        items.append((text, value))
    if not items:
        return []

    peak = max(value for _, value in items)
    floor = peak * relative
    return [label for label, value in items if value >= floor][:max_count]


def join_labels(labels: list[str]) -> str:
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + " and " + labels[-1]

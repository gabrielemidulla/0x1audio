from __future__ import annotations

import math
import uuid
from pathlib import Path
from typing import Any

import librosa
import numpy as np

from tunelink_ml_worker.audio.essentia import analyze_rich_audio

SAMPLE_RATE = 24_000
SEGMENT_SECONDS = 30
MAX_SEGMENTS = 12
CLIP_SECONDS = 10
MAX_CLIPS_PER_SEGMENT = 6
WAVEFORM_SAMPLES = 240


def load_audio(path: Path) -> tuple[np.ndarray, float]:
    samples, _ = librosa.load(path, sr=SAMPLE_RATE, mono=True)
    if samples.size == 0:
        raise ValueError("Audio file did not contain decodable samples.")
    return samples.astype(np.float32), float(samples.size / SAMPLE_RATE)


def analyze_track(
    samples: np.ndarray,
    duration_s: float,
    audio_path: Path | None = None,
) -> dict[str, Any]:
    tempo, _beats = librosa.beat.beat_track(y=samples, sr=SAMPLE_RATE)
    bpm_value = float(np.asarray(tempo).reshape(-1)[0]) if np.size(tempo) else 0.0
    clips, clip_segment_indices, segments = clips_for_embedding(samples, duration_s)
    energy = _average(segment["energy"] for segment in segments)
    valence = _average(segment["valence"] for segment in segments)
    tension = _average(segment["tension"] for segment in segments)
    tags = feature_tags(energy, valence, tension)
    mood = [label for label in ("energetic", "uplifting", "dark", "calm") if label in tags][
        :3
    ]
    genre = "Electronic" if "bright" in tags or "driving" in tags else "Music"

    analysis: dict[str, Any] = {
        "duration_s": round(duration_s, 3),
        "bpm": round(bpm_value) if bpm_value > 0 else None,
        "genre": genre,
        "mood": mood,
        "tags": tags,
        "model_tags": score_map(tags),
        "mood_scores": score_map(mood),
        "instrument_scores": {},
        "genre_scores": {genre.casefold(): 0.5},
        "segments": segments,
        "waveform": waveform_analysis(samples, duration_s),
        "clips": clips,
        "clip_segment_indices": clip_segment_indices,
    }

    rich = analyze_rich_audio(audio_path, segments)
    analysis["genre"] = ranked_genre_label(rich.get("genre_scores", {})) or genre
    analysis["mood"] = ranked_mood_labels(rich.get("mood_scores", {})) or mood
    analysis["tags"] = rich.get("tags", tags)
    analysis["model_tags"] = rich.get("model_tags", {})
    analysis["mood_scores"] = rich.get("mood_scores", {})
    analysis["instrument_scores"] = rich.get("instrument_scores", {})
    analysis["genre_scores"] = rich.get("genre_scores", {})

    for segment, rich_segment in zip(segments, rich.get("segments", [])):
        if not isinstance(rich_segment, dict):
            continue
        segment["tags"] = list(rich_segment.get("tags", segment["tags"]))
        segment["model_tags"] = dict(rich_segment.get("model_tags", segment["model_tags"]))
        segment["mood_scores"] = dict(
            rich_segment.get("mood_scores", segment["mood_scores"])
        )
        segment["instrument_scores"] = dict(
            rich_segment.get("instrument_scores", segment["instrument_scores"])
        )
        segment["genre_scores"] = dict(
            rich_segment.get("genre_scores", segment["genre_scores"])
        )
    return analysis


def clips_for_embedding(
    samples: np.ndarray,
    duration_s: float,
) -> tuple[list[np.ndarray], list[int], list[dict[str, Any]]]:
    segment_seconds = max(SEGMENT_SECONDS, duration_s / MAX_SEGMENTS)
    segment_count = max(1, min(MAX_SEGMENTS, math.ceil(duration_s / segment_seconds)))
    clips: list[np.ndarray] = []
    clip_segment_indices: list[int] = []
    segments: list[dict[str, Any]] = []

    for index in range(segment_count):
        start_s = index * segment_seconds
        end_s = min(duration_s, start_s + segment_seconds)
        start = int(start_s * SAMPLE_RATE)
        end = max(start + 1, int(end_s * SAMPLE_RATE))
        window = samples[start:end]
        for clip in segment_clips(window):
            clips.append(clip)
            clip_segment_indices.append(index)
        segments.append(segment_analysis(index, start_s, end_s, window))

    return clips, clip_segment_indices, segments


def segment_clips(window: np.ndarray) -> list[np.ndarray]:
    target = SAMPLE_RATE * CLIP_SECONDS
    if window.size <= target:
        return [model_clip(window)]

    count = min(MAX_CLIPS_PER_SEGMENT, math.ceil(window.size / target))
    if count == 1:
        return [model_clip(window)]

    step = (window.size - target) / (count - 1)
    return [window[int(i * step) : int(i * step) + target] for i in range(count)]


def model_clip(samples: np.ndarray) -> np.ndarray:
    target = SAMPLE_RATE * CLIP_SECONDS
    if samples.size >= target:
        offset = max(0, (samples.size - target) // 2)
        return samples[offset : offset + target]
    repeats = math.ceil(target / max(samples.size, 1))
    return np.tile(samples, repeats)[:target]


def segment_analysis(
    index: int,
    start_s: float,
    end_s: float,
    samples: np.ndarray,
) -> dict[str, Any]:
    rms = float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0
    energy = clamp(rms * 8)
    crossings = (
        float(np.mean(np.abs(np.diff(np.signbit(samples))))) if samples.size > 1 else 0.0
    )
    tension = clamp(crossings * 10)
    centroid = (
        float(np.mean(librosa.feature.spectral_centroid(y=samples, sr=SAMPLE_RATE)))
        if samples.size > 512
        else 0.0
    )
    brightness = clamp(centroid / 6000)
    valence = clamp((brightness * 0.65) + ((1 - tension) * 0.35))
    tags = feature_tags(energy, valence, tension)
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"segment:{index}:{start_s}:{end_s}")),
        "start_s": round(start_s, 3),
        "end_s": round(end_s, 3),
        "description": segment_description(energy, valence, tension),
        "tags": tags,
        "model_tags": score_map(tags),
        "mood_scores": score_map(tags[:3]),
        "instrument_scores": {},
        "genre_scores": {},
        "energy": round(energy, 4),
        "valence": round(valence, 4),
        "tension": round(tension, 4),
    }


def waveform_analysis(
    samples: np.ndarray,
    duration_s: float,
    points: int = WAVEFORM_SAMPLES,
) -> dict[str, Any]:
    if samples.size == 0:
        return {
            "version": 1,
            "duration_s": round(duration_s, 3),
            "sample_count": 0,
            "samples": [],
        }

    bucket_count = max(1, min(points, samples.size))
    buckets = np.array_split(np.abs(samples), bucket_count)
    peaks = np.array(
        [float(bucket.max()) if bucket.size else 0.0 for bucket in buckets],
        dtype=np.float32,
    )
    peak = float(peaks.max()) if peaks.size else 0.0
    if peak > 0:
        peaks = peaks / peak

    return {
        "version": 1,
        "duration_s": round(duration_s, 3),
        "sample_count": int(samples.size),
        "samples": [round(float(value), 4) for value in peaks],
    }


def feature_tags(energy: float, valence: float, tension: float) -> list[str]:
    return [
        "energetic" if energy >= 0.55 else "calm",
        "uplifting" if valence >= 0.55 else "dark",
        "driving" if tension >= 0.45 else "smooth",
        "bright" if valence >= 0.65 else "moody",
    ]


def segment_description(energy: float, valence: float, tension: float) -> str:
    return (
        f"{'High' if energy >= 0.55 else 'Low'}-energy, "
        f"{'bright' if valence >= 0.55 else 'moody'} passage with "
        f"{'driving' if tension >= 0.45 else 'smooth'} texture."
    )


def score_map(labels: list[str]) -> dict[str, float]:
    return {
        label: round(max(0.2, 1 - (index * 0.12)), 4)
        for index, label in enumerate(labels)
    }


def ranked_mood_labels(scores: object) -> list[str]:
    if not isinstance(scores, dict):
        return []
    excluded = {
        "background",
        "commercial",
        "advertising",
        "corporate",
        "movie",
        "film",
        "documentary",
    }
    moods = [
        str(label)
        for label, score in scores.items()
        if str(label) not in excluded and float(score) >= 0.08
    ]
    return moods[:4]


def ranked_genre_label(scores: object) -> str | None:
    if not isinstance(scores, dict):
        return None
    labels = [str(label) for label in list(scores.keys())[:3] if label]
    if not labels:
        return None
    return " / ".join(label.title() for label in labels)


def clamp(value: float) -> float:
    return max(0.0, min(value, 1.0))


def _average(values: Any) -> float:
    collected = list(values)
    return sum(collected) / len(collected) if collected else 0.0

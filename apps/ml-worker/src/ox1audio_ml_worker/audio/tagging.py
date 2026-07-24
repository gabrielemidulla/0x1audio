"""MIT Short-chunk CNN tagging — replaces Essentia Discogs/Jamendo heads.

Preserves the downstream contract: dict[str, float] label → score maps for
genre / instrument / mood, plus merged tags and per-segment scores.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import torch

from ox1audio_ml_worker.audio.short_chunk import TAGS, ShortChunkCNN_Res
from ox1audio_ml_worker.config import get_settings

PROVIDER_NAME = "short-chunk-cnn-jamendo-top50"

# Confirmed from upstream eval.py / paper: 16 kHz, 59049 samples (~3.69 s).
TAGGER_SAMPLE_RATE = 16_000
CHUNK_SAMPLES = 59_049
MAX_CHUNKS = 16
VOCAL_TAG = "instrument---voice"


def analyze_rich_audio(
    audio_path: Path | None,
    segments: list[dict[str, Any]],
    samples_48k: np.ndarray | None = None,
    sample_rate: int | None = None,
) -> dict[str, Any]:
    if audio_path is None and samples_48k is None:
        raise RuntimeError("Rich audio analysis requires audio samples or a file path.")
    return short_chunk_analyze(
        audio_path=audio_path,
        segments=segments,
        samples_48k=samples_48k,
        sample_rate=sample_rate,
    )


def short_chunk_analyze(
    *,
    audio_path: Path | None,
    segments: list[dict[str, Any]],
    samples_48k: np.ndarray | None = None,
    sample_rate: int | None = None,
) -> dict[str, Any]:
    audio_16k = load_tagger_audio(audio_path, samples_48k, sample_rate)
    duration = max(float(len(audio_16k)) / TAGGER_SAMPLE_RATE, 0.1)
    predictions = predict_chunks(audio_16k)  # (n_chunks, n_tags)

    mood_scores = top_scores_for_prefix(predictions, "mood/theme---", limit=10, minimum=0.08)
    instrument_scores = top_scores_for_prefix(
        predictions, "instrument---", limit=8, minimum=0.08
    )
    genre_scores = top_scores_for_prefix(predictions, "genre---", limit=8, minimum=0.05)
    vocalness = round(class_score(predictions, VOCAL_TAG), 4)
    model_tags = merge_scores(mood_scores, instrument_scores, genre_scores)

    segment_results: list[dict[str, Any]] = []
    for segment in segments:
        start_s = max(float(segment["start_s"]), 0.0)
        end_s = min(float(segment["end_s"]), duration)
        start = int(start_s * TAGGER_SAMPLE_RATE)
        end = max(start + 1, int(end_s * TAGGER_SAMPLE_RATE))
        window = audio_16k[start:end]
        segment_pred = predict_chunks(window)
        segment_mood = top_scores_for_prefix(
            segment_pred, "mood/theme---", limit=8, minimum=0.08
        )
        segment_instruments = top_scores_for_prefix(
            segment_pred, "instrument---", limit=6, minimum=0.08
        )
        segment_genres = top_scores_for_prefix(
            segment_pred, "genre---", limit=6, minimum=0.05
        )
        segment_results.append(
            {
                "tags": merged_tags(segment_mood, segment_instruments, segment_genres),
                "model_tags": merge_scores(
                    segment_mood, segment_instruments, segment_genres
                ),
                "mood_scores": segment_mood,
                "instrument_scores": segment_instruments,
                "genre_scores": segment_genres,
            }
        )

    return {
        "provider": PROVIDER_NAME,
        "tags": merged_tags(mood_scores, instrument_scores, genre_scores),
        "model_tags": model_tags,
        "mood_scores": mood_scores,
        "instrument_scores": instrument_scores,
        "genre_scores": genre_scores,
        "vocalness": vocalness,
        "segments": segment_results,
    }


def load_tagger_audio(
    audio_path: Path | None,
    samples_48k: np.ndarray | None,
    sample_rate: int | None,
) -> np.ndarray:
    if samples_48k is not None and sample_rate is not None:
        if int(sample_rate) == TAGGER_SAMPLE_RATE:
            return samples_48k.astype(np.float32)
        return librosa.resample(
            samples_48k.astype(np.float32),
            orig_sr=int(sample_rate),
            target_sr=TAGGER_SAMPLE_RATE,
        ).astype(np.float32)
    if audio_path is None:
        raise RuntimeError("Tagger requires samples or an audio path.")
    samples, _ = librosa.load(audio_path, sr=TAGGER_SAMPLE_RATE, mono=True)
    if samples.size == 0:
        raise ValueError("Audio file did not contain decodable samples.")
    return samples.astype(np.float32)


@lru_cache(maxsize=1)
def tagger_device() -> torch.device:
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is required for the ML worker (torch.cuda.is_available() is False)"
        )
    return torch.device("cuda")


@lru_cache(maxsize=1)
def tagger_model() -> ShortChunkCNN_Res:
    settings = get_settings()
    weights = settings.tagger_weights_path
    if not weights.is_file():
        raise RuntimeError(
            "Missing Short-chunk CNN weights. Run "
            "`uv run python scripts/download_short_chunk_model.py`. "
            f"Expected: {weights}"
        )
    model = ShortChunkCNN_Res(n_class=len(TAGS))
    state = torch.load(weights, map_location="cpu", weights_only=False)
    if "spec.mel_scale.fb" in state:
        model.spec.mel_scale.fb = state["spec.mel_scale.fb"]
    model.load_state_dict(state)
    return model.to(tagger_device()).eval()


def predict_chunks(audio: np.ndarray) -> np.ndarray:
    """Return (n_chunks, n_tags) sigmoid scores; pads short audio by tiling."""
    if audio.size == 0:
        return np.zeros((1, len(TAGS)), dtype=np.float32)

    if audio.size < CHUNK_SAMPLES:
        repeats = math.ceil(CHUNK_SAMPLES / max(audio.size, 1))
        audio = np.tile(audio, repeats)[:CHUNK_SAMPLES]

    length = int(audio.size)
    n_chunks = min(MAX_CHUNKS, max(1, length // CHUNK_SAMPLES))
    if length == CHUNK_SAMPLES or n_chunks == 1:
        batch = audio[:CHUNK_SAMPLES][None, :]
    else:
        hop = max(1, (length - CHUNK_SAMPLES) // n_chunks)
        rows = [
            audio[i * hop : i * hop + CHUNK_SAMPLES]
            for i in range(n_chunks)
            if i * hop + CHUNK_SAMPLES <= length
        ]
        if not rows:
            rows = [audio[:CHUNK_SAMPLES]]
        batch = np.stack(rows, axis=0)

    tensor = torch.from_numpy(batch.astype(np.float32)).to(tagger_device())
    with torch.inference_mode():
        scores = tagger_model()(tensor)
    return scores.detach().float().cpu().numpy()


def top_scores_for_prefix(
    predictions: np.ndarray,
    prefix: str,
    *,
    limit: int,
    minimum: float,
) -> dict[str, float]:
    if predictions.size == 0:
        return {}
    vector = np.max(predictions, axis=0)
    ranked: list[tuple[str, float]] = []
    for label, score in zip(TAGS, vector):
        if not str(label).startswith(prefix):
            continue
        value = float(score)
        if value < minimum:
            continue
        ranked.append((normalize_label(str(label)), value))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return {label: round(score, 4) for label, score in ranked[:limit]}


def class_score(predictions: np.ndarray, label: str) -> float:
    if predictions.size == 0:
        return 0.0
    vector = np.max(predictions, axis=0)
    target = label.casefold()
    for class_name, score in zip(TAGS, vector):
        if str(class_name).casefold() == target:
            return float(score)
    return 0.0


def top_scores(
    predictions: np.ndarray,
    classes: list[str],
    *,
    limit: int,
    minimum: float,
) -> dict[str, float]:
    if predictions.size == 0:
        return {}
    vector = np.max(predictions, axis=0)
    return ranked_scores(vector, classes, limit=limit, minimum=minimum)


def top_scores_for_rows(
    predictions: np.ndarray,
    classes: list[str],
    row_start: int,
    row_end: int,
    *,
    limit: int,
    minimum: float,
) -> dict[str, float]:
    if predictions.size == 0:
        return {}
    row_start = max(0, min(row_start, len(predictions) - 1))
    row_end = max(row_start + 1, min(row_end, len(predictions)))
    window = predictions[row_start:row_end]
    mixed = (np.mean(window, axis=0) * 0.65) + (np.max(window, axis=0) * 0.35)
    return ranked_scores(mixed, classes, limit=limit, minimum=minimum)


def ranked_scores(
    vector: np.ndarray,
    classes: list[str],
    *,
    limit: int,
    minimum: float,
) -> dict[str, float]:
    ranked = sorted(
        (
            (normalize_label(label), float(score))
            for label, score in zip(classes, vector)
            if float(score) >= minimum
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    return {label: round(score, 4) for label, score in ranked[:limit]}


def normalize_label(label: str) -> str:
    """Strip Jamendo `genre---` / `instrument---` / `mood/theme---` prefixes."""
    text = label.strip()
    for prefix in ("genre---", "instrument---", "mood/theme---", "mood---", "theme---"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.replace("_", " ").replace("---", " / ").strip()
    return text.casefold()


def merged_tags(*score_groups: dict[str, float]) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for scores in score_groups:
        for label in scores:
            if label not in seen:
                tags.append(label)
                seen.add(label)
    return tags


def merge_scores(*groups: dict[str, float]) -> dict[str, float]:
    merged: dict[str, float] = {}
    for group in groups:
        for label, score in group.items():
            merged[label] = max(score, merged.get(label, 0.0))
    return dict(sorted(merged.items(), key=lambda item: item[1], reverse=True))

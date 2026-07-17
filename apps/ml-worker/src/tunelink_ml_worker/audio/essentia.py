from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from tunelink_ml_worker.config import get_settings

PROVIDER_NAME = "essentia-discogs-effnet-mtg-jamendo"

MODEL_FILES = {
    "embedding": "discogs-effnet-bs64-1",
    "moodtheme": "mtg_jamendo_moodtheme-discogs-effnet-1",
    "instrument": "mtg_jamendo_instrument-discogs-effnet-1",
    "genre": "genre_discogs400-discogs-effnet-1",
}


def analyze_rich_audio(
    audio_path: Path | None,
    segments: list[dict[str, Any]],
) -> dict[str, Any]:
    if audio_path is None:
        raise RuntimeError("Rich audio analysis requires an audio file path.")
    return essentia_analyze(audio_path, segments)


def model_path(name: str, suffix: str) -> Path:
    return get_settings().essentia_models_dir / f"{MODEL_FILES[name]}.{suffix}"


def require_model_files() -> None:
    missing = [
        str(path)
        for key in MODEL_FILES
        for path in (model_path(key, "pb"), model_path(key, "json"))
        if not path.exists()
    ]
    if missing:
        raise RuntimeError(
            "Missing Essentia model files. Run "
            "`uv run python scripts/download_essentia_models.py`. Missing: "
            + ", ".join(missing)
        )


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return value


def model_io(metadata: dict[str, Any]) -> tuple[str, str]:
    schema = metadata.get("schema") or {}
    if not isinstance(schema, dict):
        return "model/Placeholder", "PartitionedCall:0"
    inputs = schema.get("inputs") or []
    outputs = schema.get("outputs") or []
    input_name = (
        inputs[0].get("name", "model/Placeholder")
        if inputs and isinstance(inputs[0], dict)
        else "model/Placeholder"
    )
    prediction_outputs = [
        output
        for output in outputs
        if isinstance(output, dict) and output.get("output_purpose") == "predictions"
    ]
    selected = (
        prediction_outputs[0]
        if prediction_outputs
        else outputs[0]
        if outputs and isinstance(outputs[0], dict)
        else {"name": "PartitionedCall:0"}
    )
    return str(input_name), str(selected["name"])


@lru_cache(maxsize=1)
def model_bundle():
    require_model_files()
    from essentia.standard import (  # type: ignore[import-untyped]
        MonoLoader,
        TensorflowPredict2D,
        TensorflowPredictEffnetDiscogs,
    )

    metadata = {key: load_json(model_path(key, "json")) for key in MODEL_FILES}
    embedding_model = TensorflowPredictEffnetDiscogs(
        graphFilename=str(model_path("embedding", "pb")),
        output="PartitionedCall:1",
    )
    heads = {}
    for key in ("moodtheme", "instrument", "genre"):
        input_name, output_name = model_io(metadata[key])
        heads[key] = TensorflowPredict2D(
            graphFilename=str(model_path(key, "pb")),
            input=input_name,
            output=output_name,
        )
    return MonoLoader, embedding_model, heads, metadata


def essentia_analyze(audio_path: Path, segments: list[dict[str, Any]]) -> dict[str, Any]:
    MonoLoader, embedding_model, heads, metadata = model_bundle()
    audio = MonoLoader(filename=str(audio_path), sampleRate=16000, resampleQuality=4)()
    duration = max(float(len(audio)) / 16000, 0.1)
    embeddings = ensure_2d(embedding_model(audio))
    predictions = {key: ensure_2d(head(embeddings)) for key, head in heads.items()}

    mood_scores = top_scores(
        predictions["moodtheme"],
        metadata["moodtheme"]["classes"],
        limit=10,
        minimum=0.08,
    )
    instrument_scores = top_scores(
        predictions["instrument"],
        metadata["instrument"]["classes"],
        limit=8,
        minimum=0.08,
    )
    genre_scores = top_scores(
        predictions["genre"],
        metadata["genre"]["classes"],
        limit=8,
        minimum=0.05,
    )
    model_tags = merge_scores(mood_scores, instrument_scores, genre_scores)

    row_count = max(1, len(predictions["moodtheme"]))
    segment_results: list[dict[str, Any]] = []
    for segment in segments:
        row_start = int(np.floor((max(float(segment["start_s"]), 0) / duration) * row_count))
        row_end = int(
            np.ceil((min(float(segment["end_s"]), duration) / duration) * row_count)
        )
        segment_mood = top_scores_for_rows(
            predictions["moodtheme"],
            metadata["moodtheme"]["classes"],
            row_start,
            row_end,
            limit=8,
            minimum=0.08,
        )
        segment_instruments = top_scores_for_rows(
            predictions["instrument"],
            metadata["instrument"]["classes"],
            row_start,
            row_end,
            limit=6,
            minimum=0.08,
        )
        segment_genres = top_scores_for_rows(
            predictions["genre"],
            metadata["genre"]["classes"],
            row_start,
            row_end,
            limit=6,
            minimum=0.05,
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
        "segments": segment_results,
    }


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


def ensure_2d(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    if values.ndim == 0:
        return values.reshape(1, 1)
    if values.ndim == 1:
        return values.reshape(1, -1)
    if values.ndim > 2:
        return values.reshape(-1, values.shape[-1])
    return values


def normalize_label(label: str) -> str:
    label = label.replace("---", " / ").replace("_", " ").strip()
    if " / " in label:
        label = label.split(" / ", 1)[1]
    return label.casefold()


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

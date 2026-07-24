"""CLAP zero-shot affective axes (affect-v1).

Scores bipolar vibe dimensions from audio using the same LAION-CLAP model
as embeddings — Apache 2.0, no extra packages. Results feed the MiniLM
profile sentence so "intimate" vs "dark" can separate sonically similar tracks.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

AFFECT_VERSION = "affect-v1"

# Temperature for sigmoid(temp * (pos - neg)). Cosine deltas after mean-pool
# text features are typically ~0.005–0.02; temp≈80 maps that into a usable [0,1].
AFFECT_TEMPERATURE = 80.0

# Each axis: (positive prompts, negative prompts, high-pole label, low-pole label).
# Prefer short tag-style phrases — closer to CLAP music training captions.
AFFECT_AXES: dict[str, tuple[list[str], list[str], str, str]] = {
    "intimacy": (
        ["intimate", "romantic", "soft close vocals", "tender ballad"],
        ["distant", "cold impersonal", "detached", "public anthem"],
        "intimate",
        "distant",
    ),
    "darkness": (
        ["dark", "scary", "eerie", "ominous", "horror"],
        ["bright", "cheerful", "sunny", "light airy"],
        "dark",
        "bright",
    ),
    "tension": (
        ["tense", "anxious", "restless", "uneasy"],
        ["calm", "relaxed", "smooth", "settled"],
        "tense",
        "smooth",
    ),
    "warmth": (
        ["warm", "cozy", "gentle", "lush"],
        ["cold", "sterile", "harsh", "icy"],
        "warm",
        "cold",
    ),
    "energy_feel": (
        ["energetic", "driving", "urgent", "pulsing"],
        ["calm", "still", "peaceful", "spacious"],
        "restless",
        "calm",
    ),
    "nostalgia": (
        ["nostalgic", "wistful", "dreamy night", "bittersweet"],
        ["modern blunt", "present day", "matter of fact"],
        "nostalgic",
        "present",
    ),
}


def score_affect(clips: list[np.ndarray]) -> dict[str, float]:
    """Return axis → [0, 1] scores (1 = high pole) from CLAP clip embeddings."""
    if not clips:
        return {axis: 0.5 for axis in AFFECT_AXES}

    import torch
    import torch.nn.functional as F

    from ox1audio_ml_worker.embedders.provider import (
        MODEL_LOCK,
        clap_bundle,
        clap_text_features,
        worker_device,
    )

    processor, model = clap_bundle()
    device = worker_device()
    sampling_rate = int(processor.feature_extractor.sampling_rate)

    with MODEL_LOCK, torch.inference_mode():
        audio_inputs = processor(
            audio=[clip.astype(np.float32) for clip in clips],
            sampling_rate=sampling_rate,
            return_tensors="pt",
            padding=True,
        )
        audio_inputs = {key: value.to(device) for key, value in audio_inputs.items()}
        audio_vectors = model.get_audio_features(**audio_inputs)
        audio_vectors = F.normalize(audio_vectors, dim=-1)
        track_audio = F.normalize(audio_vectors.mean(dim=0, keepdim=True), dim=-1)

        scores: dict[str, float] = {}
        for axis, (pos_prompts, neg_prompts, _high, _low) in AFFECT_AXES.items():
            prompts = [*pos_prompts, *neg_prompts]
            text_vectors = clap_text_features(processor, model, prompts, device)
            sims = (track_audio @ text_vectors.T).squeeze(0)
            n_pos = len(pos_prompts)
            pos = float(sims[:n_pos].mean().item())
            neg = float(sims[n_pos:].mean().item())
            scores[axis] = round(_sigmoid(AFFECT_TEMPERATURE * (pos - neg)), 4)

    logger.debug("affect scores=%s", scores)
    return scores


def affect_labels(scores: dict[str, float], *, minimum: float = 0.6) -> list[str]:
    """High-pole labels for axes at/above minimum; else low-pole if clearly low."""
    labels: list[str] = []
    for axis, (_pos, _neg, high, low) in AFFECT_AXES.items():
        value = float(scores.get(axis, 0.5))
        if value >= minimum:
            labels.append(high)
        elif value <= (1.0 - minimum):
            labels.append(low)
    return labels


def affect_phrase(scores: dict[str, float]) -> str:
    """Prose + compact fingerprint for the MiniLM profile sentence.

    Always include every axis so near-ties (e.g. two dark/tense tracks) still
    differ slightly in embedding space when raw scores diverge.
    """
    highs = affect_labels(scores, minimum=0.62)
    if not highs:
        ranked = sorted(
            (
                (abs(float(scores.get(axis, 0.5)) - 0.5), axis)
                for axis in AFFECT_AXES
            ),
            reverse=True,
        )
        if ranked and ranked[0][0] >= 0.08:
            _delta, axis = ranked[0]
            value = float(scores.get(axis, 0.5))
            _pos, _neg, high, low = AFFECT_AXES[axis]
            highs = [high if value >= 0.5 else low]

    fingerprint = ", ".join(
        f"{axis.replace('_', ' ')} {float(scores.get(axis, 0.5)):.2f}"
        for axis in AFFECT_AXES
    )
    if not highs:
        return f"Affect: {fingerprint}"
    if len(highs) == 1:
        feeling = f"The feeling is {highs[0]}"
    elif len(highs) == 2:
        feeling = f"The feeling is {highs[0]} and {highs[1]}"
    else:
        feeling = f"The feeling is {', '.join(highs[:-1])}, and {highs[-1]}"
    return f"{feeling}. Affect: {fingerprint}"


def _sigmoid(value: float) -> float:
    return float(1.0 / (1.0 + np.exp(-value)))


def merge_affect_into_analysis(analysis: dict[str, Any], clips: list[np.ndarray]) -> None:
    scores = score_affect(clips)
    analysis["affect_scores"] = scores
    analysis["affect_labels"] = affect_labels(scores)
    analysis["affect_version"] = AFFECT_VERSION

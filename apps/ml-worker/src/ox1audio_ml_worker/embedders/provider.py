from __future__ import annotations

import logging
import threading
from functools import lru_cache

import numpy as np

from ox1audio_ml_worker.audio.tagging import PROVIDER_NAME as TAGGER_BASE
from ox1audio_ml_worker.audio.affect import AFFECT_VERSION
from ox1audio_ml_worker.config import get_settings

logger = logging.getLogger(__name__)

MODEL_LOCK = threading.RLock()
LANGUAGE_MODEL_LOCK = threading.RLock()

EXPECTED_AUDIO_VECTOR_SIZE = 512


def normalized(vector: list[float] | np.ndarray) -> list[float]:
    values = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(values))
    if norm == 0:
        return [0.0 for _ in values]
    return [float(value) for value in values / norm]


def blend_profile_vectors(
    sentence_vector: list[float] | None,
    tag_vector: list[float] | None,
    *,
    sentence_weight: float | None = None,
) -> list[float] | None:
    if sentence_vector is None and tag_vector is None:
        return None
    if sentence_vector is None:
        return tag_vector
    if tag_vector is None:
        return sentence_vector
    weight = (
        get_settings().profile_sentence_weight
        if sentence_weight is None
        else sentence_weight
    )
    weight = max(0.0, min(weight, 1.0))
    return normalized(
        [
            (sentence * weight) + (tag * (1.0 - weight))
            for sentence, tag in zip(sentence_vector, tag_vector)
        ]
    )


class ModelProvider:
    def __init__(self) -> None:
        settings = get_settings()
        self.model_id = settings.clap_model_id
        self.language_model_id = settings.language_model_id
        # Profile collection versions with tagger + affect recipe together.
        self.tagger_name = f"{TAGGER_BASE}__{AFFECT_VERSION}"

    @property
    def name(self) -> str:
        return "laion-clap-music"

    @property
    def version(self) -> str:
        return self.model_id

    @property
    def vector_size(self) -> int:
        return EXPECTED_AUDIO_VECTOR_SIZE

    @property
    def profile_vector_size(self) -> int:
        return get_settings().language_vector_size

    def embed_text(self, text: str) -> list[float]:
        processor, model = clap_bundle()
        device = worker_device()
        with MODEL_LOCK:
            vectors = clap_text_features(processor, model, [text], device)
        return tensor_vector(vectors[0])

    def embed_audio_clips(self, clips: list[np.ndarray]) -> list[list[float]]:
        import torch

        if not clips:
            return []

        processor, model = clap_bundle()
        device = worker_device()
        # ClapFeatureExtractor expects 48 kHz; clips are prepared at SAMPLE_RATE.
        sampling_rate = int(processor.feature_extractor.sampling_rate)
        with MODEL_LOCK, torch.inference_mode():
            inputs = processor(
                audio=[clip.astype(np.float32) for clip in clips],
                sampling_rate=sampling_rate,
                return_tensors="pt",
                padding=True,
            )
            inputs = {key: value.to(device) for key, value in inputs.items()}
            vectors = model.get_audio_features(**inputs)
        result = [tensor_vector(vector) for vector in vectors]
        for vector in result:
            if len(vector) != EXPECTED_AUDIO_VECTOR_SIZE:
                raise RuntimeError(
                    f"CLAP audio embedding dim is {len(vector)}, expected "
                    f"{EXPECTED_AUDIO_VECTOR_SIZE}. Refusing to reshape collections."
                )
        return result

    def embed_profile_text(self, text: str) -> list[float]:
        vectors = self.embed_profile_texts([text])
        return vectors[0] if vectors else [0.0] * self.profile_vector_size

    def embed_profile_query(self, query: str) -> list[float]:
        text = query.strip()
        if not text:
            return [0.0] * self.profile_vector_size
        if len(text.split()) == 1:
            return self.embed_profile_text(f"Music tags: {text}.")
        return blend_profile_vectors(
            self.embed_profile_text(text),
            self.embed_profile_text(f"Music tags: {text}."),
        ) or [0.0] * self.profile_vector_size

    def embed_profile_texts(self, texts: list[str]) -> list[list[float]]:
        cleaned = [text.strip() for text in texts]
        if not cleaned:
            return []

        import torch

        tokenizer, model = language_model_bundle(self.language_model_id)
        device = worker_device()
        with LANGUAGE_MODEL_LOCK, torch.inference_mode():
            inputs = tokenizer(
                cleaned,
                padding=True,
                truncation=True,
                return_tensors="pt",
            )
            inputs = {key: value.to(device) for key, value in inputs.items()}
            hidden_states = model(**inputs).last_hidden_state
        mask = inputs["attention_mask"].unsqueeze(-1)
        pooled = (hidden_states * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
        return [tensor_vector(vector) for vector in pooled]


@lru_cache(maxsize=1)
def worker_device():
    import torch

    # CUDA-only: Compose always runs ml-worker with an NVIDIA GPU.
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is required for the ML worker (torch.cuda.is_available() is False)"
        )
    device = torch.device("cuda")
    logger.info("ML worker device=cuda (%s)", torch.cuda.get_device_name(0))
    return device


@lru_cache(maxsize=1)
def clap_bundle():
    from transformers import ClapModel, ClapProcessor

    model_id = get_settings().clap_model_id
    processor = ClapProcessor.from_pretrained(model_id, local_files_only=True)
    model = ClapModel.from_pretrained(model_id, local_files_only=True)
    projection_dim = int(getattr(model.config, "projection_dim", 0) or 0)
    if projection_dim != EXPECTED_AUDIO_VECTOR_SIZE:
        raise RuntimeError(
            f"CLAP projection_dim is {projection_dim}, expected "
            f"{EXPECTED_AUDIO_VECTOR_SIZE}. Stopping rather than reshaping collections."
        )
    return processor, model.to(worker_device()).eval()


def clap_text_features(processor, model, texts: list[str], device):
    """Project CLAP text embeddings with mean pooling.

    HuggingFace ``get_text_features`` uses RoBERTa ``pooler_output`` (CLS+tanh).
    For some LAION CLAP checkpoints (notably ``larger_clap_music``) the CLS
    pooler collapses prompts to ~0.999 cosine — mean-pooling
    ``last_hidden_state`` (original LAION CLAP) restores discrimination.
    Harmless for healthy checkpoints such as ``larger_clap_music_and_speech``.
    """
    import torch
    import torch.nn.functional as F

    if not texts:
        return torch.empty((0, EXPECTED_AUDIO_VECTOR_SIZE), device=device)

    with torch.inference_mode():
        inputs = processor(text=texts, return_tensors="pt", padding=True)
        inputs = {key: value.to(device) for key, value in inputs.items()}
        text_outputs = model.text_model(
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
        )
        mask = inputs["attention_mask"].unsqueeze(-1).type_as(text_outputs.last_hidden_state)
        pooled = (text_outputs.last_hidden_state * mask).sum(dim=1) / mask.sum(dim=1).clamp(
            min=1
        )
        projected = model.text_projection(pooled)
        return F.normalize(projected, dim=-1)


@lru_cache(maxsize=2)
def language_model_bundle(model_id: str):
    from transformers import AutoModel, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=True)
    model = AutoModel.from_pretrained(model_id, local_files_only=True).to(worker_device()).eval()
    return tokenizer, model


def tensor_vector(tensor) -> list[float]:
    return normalized(tensor.detach().float().cpu().numpy())

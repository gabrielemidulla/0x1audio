from __future__ import annotations

import logging
import threading
from functools import lru_cache

import numpy as np

from ox1audio_ml_worker.config import get_settings

logger = logging.getLogger(__name__)

MODEL_LOCK = threading.RLock()
LANGUAGE_MODEL_LOCK = threading.RLock()


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
        self.model_id = settings.muq_model_id
        self.language_model_id = settings.language_model_id

    @property
    def name(self) -> str:
        return "muq-mulan-large"

    @property
    def version(self) -> str:
        return self.model_id

    @property
    def vector_size(self) -> int:
        return 512

    @property
    def profile_vector_size(self) -> int:
        return get_settings().language_vector_size

    def embed_text(self, text: str) -> list[float]:
        import torch

        with MODEL_LOCK, torch.inference_mode():
            vectors = muq_model()(texts=[text])
        return tensor_vector(vectors[0])

    def embed_audio_clips(self, clips: list[np.ndarray]) -> list[list[float]]:
        import torch

        batch = torch.stack([torch.from_numpy(clip).float() for clip in clips]).to(
            muq_device()
        )
        with MODEL_LOCK, torch.inference_mode():
            vectors = muq_model()(wavs=batch, parallel_processing=False)
        return [tensor_vector(vector) for vector in vectors]

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
        device = muq_device()
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
def muq_device():
    import torch

    # CUDA-only: Compose always runs ml-worker with an NVIDIA GPU.
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is required for the ML worker (torch.cuda.is_available() is False)"
        )
    device = torch.device("cuda")
    logger.info("MuQ device=cuda (%s)", torch.cuda.get_device_name(0))
    return device


@lru_cache(maxsize=1)
def muq_model():
    from muq import MuQMuLan

    model_id = get_settings().muq_model_id
    model = MuQMuLan.from_pretrained(model_id, local_files_only=True)
    return model.to(muq_device()).eval()


@lru_cache(maxsize=2)
def language_model_bundle(model_id: str):
    from transformers import AutoModel, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=True)
    model = AutoModel.from_pretrained(model_id, local_files_only=True).to(muq_device()).eval()
    return tokenizer, model


def tensor_vector(tensor) -> list[float]:
    return normalized(tensor.detach().float().cpu().numpy())

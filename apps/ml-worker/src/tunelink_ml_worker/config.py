from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_timeout_seconds: float
    muq_model_id: str
    language_model_id: str
    language_vector_size: int
    essentia_models_dir: Path
    audio_search_weight: float
    profile_search_weight: float
    baseline_sample: int
    min_sample: int
    min_standout_sigma: float
    sigma_full_scale: float
    tag_boost_sigma: float
    profile_sentence_weight: float
    profile_label_relative: float


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    default_essentia = (
        Path(__file__).resolve().parents[2] / "data" / "models" / "essentia"
    )
    return Settings(
        host=os.getenv("ML_WORKER_HOST", "0.0.0.0"),
        port=int(os.getenv("ML_WORKER_PORT", "50051")),
        qdrant_url=os.getenv("QDRANT_URL", "http://127.0.0.1:6333"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY") or None,
        qdrant_timeout_seconds=float(os.getenv("QDRANT_TIMEOUT_SECONDS", "30")),
        muq_model_id=os.getenv("ML_MODEL_ID", "OpenMuQ/MuQ-MuLan-large"),
        language_model_id=os.getenv(
            "LANGUAGE_MODEL_ID",
            "sentence-transformers/all-MiniLM-L6-v2",
        ),
        language_vector_size=int(os.getenv("LANGUAGE_VECTOR_SIZE", "384")),
        essentia_models_dir=Path(
            os.getenv("ESSENTIA_MODELS_DIR", str(default_essentia))
        ),
        audio_search_weight=float(os.getenv("SEARCH_AUDIO_WEIGHT", "0.45")),
        profile_search_weight=float(os.getenv("SEARCH_PROFILE_WEIGHT", "0.55")),
        baseline_sample=int(os.getenv("SEARCH_BASELINE_SAMPLE", "256")),
        min_sample=int(os.getenv("SEARCH_MIN_SAMPLE", "8")),
        min_standout_sigma=float(os.getenv("SEARCH_MIN_STANDOUT_SIGMA", "1.0")),
        sigma_full_scale=float(os.getenv("SEARCH_SIGMA_FULL_SCALE", "4.0")),
        tag_boost_sigma=float(os.getenv("SEARCH_TAG_BOOST", "0.15")),
        profile_sentence_weight=float(os.getenv("PROFILE_SENTENCE_WEIGHT", "0.5")),
        profile_label_relative=float(os.getenv("PROFILE_LABEL_RELATIVE", "0.35")),
    )

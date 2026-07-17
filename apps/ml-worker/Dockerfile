# CUDA ML worker — x86_64 + NVIDIA (matches goodtaste pytorch base).
# Torch comes from the base image; do not install a CPU wheel over it.

FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

COPY --from=ghcr.io/astral-sh/uv:0.7.12 /uv /usr/local/bin/uv

RUN apt-get update \
  && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    TOKENIZERS_PARALLELISM=false \
    HF_HOME=/models/huggingface \
    ESSENTIA_MODELS_DIR=/app/data/models/essentia \
    QDRANT_URL=http://qdrant:6333

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY data ./data

# Install into the image Python (already has CUDA torch). Skip torch from PyPI.
RUN uv pip install --system --no-cache \
    "grpcio>=1.68.0" \
    "protobuf>=5.28.0" \
    "qdrant-client>=1.15.0,<1.16" \
    "requests>=2.32,<3" \
    "numpy>=1.26,<2" \
    "librosa>=0.10.1,<0.11" \
    "soundfile>=0.13,<0.14" \
    "muq==0.1.0" \
    "huggingface-hub>=0.34,<1" \
    "transformers>=4.51,<5" \
    "essentia-tensorflow==2.1b6.dev1389"

EXPOSE 50051
CMD ["python", "-m", "tunelink_ml_worker"]

# CUDA ML worker — x86_64 + NVIDIA.
# Torch comes from the base image; do not install a CPU/PyPI wheel over it.

FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

COPY --from=ghcr.io/astral-sh/uv:0.7.12 /uv /usr/local/bin/uv

RUN apt-get update \
  && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH" \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    TOKENIZERS_PARALLELISM=false \
    HF_HOME=/models/huggingface \
    QDRANT_URL=http://qdrant:6333

COPY pyproject.toml uv.lock README.md config.yaml ./
COPY src ./src
COPY scripts ./scripts
COPY data ./data

# Lockfile install; reuse CUDA torch from the base image via system site-packages.
RUN uv venv /app/.venv --system-site-packages \
  && uv sync --frozen --no-dev --no-install-package torch \
  && python -c "import torch; import ox1audio_ml_worker"

EXPOSE 50051
CMD ["python", "-m", "ox1audio_ml_worker"]

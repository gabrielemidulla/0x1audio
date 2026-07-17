# ML worker — gRPC compute plane (analyze / search / graph)

Downloads audio via short-lived MinIO URLs. Writes dual vectors to Qdrant.
No Postgres, no auth. Recipe: [docs/ML.md](../../docs/ML.md).

## Runtime: CUDA in Docker

Indexing runs on an **x86_64 host with NVIDIA GPU**. Compose always builds the
CUDA image (`pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime`) and passes `gpus: all`.

```bash
# Essentia models (once, from this directory)
uv run python scripts/download_essentia_models.py

# Full stack (NVIDIA Container Toolkit required)
docker compose -f compose.yaml -f compose.dev.yaml up -d --build ml-worker backend-worker
```

Device policy: **CUDA required** — the worker raises if `torch.cuda.is_available()` is false.

| Variable | Default | Role |
|----------|---------|------|
| `QDRANT_URL` | `http://127.0.0.1:6333` | Vector DB |
| `QDRANT_API_KEY` | — | Optional |
| `ESSENTIA_MODELS_DIR` | `data/models/essentia` | `.pb` / `.json` heads |
| `ML_MODEL_ID` | `OpenMuQ/MuQ-MuLan-large` | Audio/text MuQ |
| `LANGUAGE_MODEL_ID` | `sentence-transformers/all-MiniLM-L6-v2` | Profile MiniLM |
| `HF_HOME` | `/models/huggingface` in Compose | Model cache |
| `CUDA_VISIBLE_DEVICES` | `0` | GPU selection |

First analyze downloads MuQ + MiniLM into `HF_HOME`. Soft tag boost only — no hard lexical gate.

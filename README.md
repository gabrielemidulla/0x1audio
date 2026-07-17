# Tunelink

Personal music catalog with ML indexing: import tracks, search by natural language, explore similarity graphs.

## Layout

```text
apps/backend      API (uvicorn) + ingest worker process — uv
apps/frontend     React Router + shadcn (static SPA) — pnpm
apps/ml-worker    gRPC ML worker (MuQ + MiniLM + Essentia → Qdrant) — CUDA
proto/            Shared protobuf (./generate.sh → both apps)
docs/SPEC.md      Product & ownership
docs/INGEST.md    Upload / ZIP / import_job
docs/ML.md        Index / search / graph
compose.yaml      Shared infra (Postgres, Qdrant, MinIO)
compose.dev.yaml  Hot-reload app services (ml-worker uses GPU)
compose.prod.yaml Production app images (ml-worker uses GPU)
```

## Spec

See [docs/SPEC.md](docs/SPEC.md). External MVP reference (not in this repo): `~/projects/goodtaste/__OLD__/`.

## Docker Compose

Requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) for `ml-worker`.

```bash
cp .env.example .env
```

| Mode | Command |
|------|---------|
| Infra only (no host ports) | `docker compose up -d` |
| Dev (LAN, `0.0.0.0`) | `docker compose -f compose.yaml -f compose.dev.yaml up --build` |
| Prod (localhost only) | `docker compose -f compose.yaml -f compose.prod.yaml up -d --build` |

Dev publishes on `0.0.0.0` (reachable at `http://<lan-ip>:5173`). The Vite dev server proxies `/api` → backend so the API base URL stays same-origin.

| Service | Dev port | Prod port |
|---------|----------|-----------|
| Frontend | `5173` | `8080` |
| Backend | `8000` | `8000` |
| ML worker | `50051` | `50051` |
| Postgres | `5432` | `5432` |
| Qdrant | `6333` / `6334` | same |
| MinIO | `9100` / `9001` | same |

## Local without app containers

```bash
docker compose up -d
cd apps/backend && uv sync && uv run uvicorn tunelink_backend.main:app --reload --port 8000
cd apps/frontend && pnpm install && pnpm dev
```

`ml-worker` is CUDA-only via Compose; run it in Docker rather than on the host.

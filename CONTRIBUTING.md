# Contributing

Thanks for helping improve **0x1audio**. This doc covers setup, local development, and how we take changes.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) (ML worker today requires CUDA)
- [uv](https://docs.astral.sh/uv/) (backend / ml-worker)
- [pnpm](https://pnpm.io/) 10+ and Node 22+ (frontend)
- Git

## Quick start

```bash
cp .env.example .env
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

Frontend: `http://localhost:5173` · API: `http://localhost:8000`

Architecture notes for the ML plane: [apps/ml-worker/README.md](apps/ml-worker/README.md).

## Repo layout

| Path | Role |
|------|------|
| `apps/frontend` | React Router UI |
| `apps/backend` | FastAPI control plane + ingest worker |
| `apps/ml-worker` | gRPC embeddings → Qdrant |
| `proto/` | Shared protobuf definitions |

## Local development

### Full stack (Compose)

Prefer Compose for Postgres, MinIO, Qdrant, and the ML worker. Override ports and secrets via `.env`.

Personal config overlays (optional):

```bash
cp apps/backend/config.local.example.yaml apps/backend/config.local.yaml
cp apps/ml-worker/config.local.example.yaml apps/ml-worker/config.local.yaml
```

Priority: **env → `config.local.yaml` → `config.yaml` → defaults**.

### Frontend

```bash
cd apps/frontend
pnpm install
pnpm dev
```

Useful scripts: `pnpm typecheck`, `pnpm format`, `pnpm build`, `pnpm generate:api` (OpenAPI client).

### Backend

```bash
cd apps/backend
uv sync
uv run pytest -q
```

Lint / types: `uv run ruff check .`, `uv run basedpyright`.

### ML worker

CUDA is required today (`torch.cuda.is_available()`). Download Essentia models once, then run via Compose or host tooling as described in the ML worker README.

Protobuf stubs under `generated/` are checked in — keep them in sync if you change `proto/`.

## Pull requests

1. Open an issue first for larger changes (new backends, API shape, hosting).
2. Keep PRs focused — one concern per PR when practical.
3. Match existing style; avoid drive-by refactors unrelated to the change.
4. Add or update tests when you touch backend behavior.
5. Ensure CI would pass locally where you can:
   - Backend: `uv sync --frozen && uv run pytest -q`
   - Frontend: `pnpm install --frozen-lockfile && pnpm build`
6. Describe **why** in the PR body, not only what changed.
7. Do not commit secrets, local configs (`config.local.yaml`), or `.env`.

## Code style

- **Python**: 3.12 (backend), 3.11–3.12 (ml-worker); Ruff line length 100.
- **Frontend**: TypeScript, Prettier, React Router 7.
- Prefer small, readable diffs over large speculative abstractions.

## Reporting bugs

Include OS, GPU/runtime (NVIDIA / planned ROCm / Metal / iGPU), Compose vs host-run, and steps to reproduce. Logs from `backend`, `backend-worker`, and `ml-worker` help a lot.

## Questions

Open a GitHub issue or discussion. See the [roadmap](README.md#roadmap) for planned work you can pick up.

# Backend

FastAPI control plane: auth, catalog (soon), MinIO, OpenAPI, gRPC to `apps/ml-worker`.

**Tooling: uv + uvicorn**

```bash
cd apps/backend
uv sync
uv run uvicorn tunelink_backend.main:app --reload --host 0.0.0.0 --port 8000
```

Or via Compose (hot reload):

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build backend
```

Auth: email/password in Postgres; session JWT via Authlib’s JOSE stack (`joserfc`). Cookie name `session`.

Requires Postgres (`docker compose up -d postgres`) and env from `.env.example` (`DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS`).

See [docs/SPEC.md](../../docs/SPEC.md).

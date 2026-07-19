<p align="center">
  <img src=".github/assets/logo.webp" alt="0x1audio" width="280" />
</p>

**0x1audio** is a personal music catalog with ML indexing. Import your tracks, search by natural language or sound, and explore a similarity graph.

```text
apps/frontend     React UI
apps/backend      API + ingest worker
apps/ml-worker    gRPC embeddings → Qdrant
proto/            shared protobuf
```

```bash
cp .env.example .env
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

Requires NVIDIA Container Toolkit for the ML worker. Architecture: [apps/ml-worker/README.md](apps/ml-worker/README.md).

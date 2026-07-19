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

## Use cases

### Home

Ask your library, jump into catalog / playlists / graph / jobs, and see what just finished indexing.

<p align="center">
  <img src=".github/assets/screenshot/home.webp" alt="Home — ask your library and open core surfaces" width="900" />
</p>

### Graph

Pick a seed track and walk the sound-alike neighborhood — linked tracks, playback, and the similarity map.

<p align="center">
  <img src=".github/assets/screenshot/graph.webp" alt="Graph — explore sound-alike track neighborhoods" width="900" />
</p>

### Chat

Describe a vibe in natural language, get matching tracks, then create a playlist from the same conversation.

<p align="center">
  <img src=".github/assets/screenshot/chat.webp" alt="Chat — vibe search and playlist creation" width="900" />
</p>

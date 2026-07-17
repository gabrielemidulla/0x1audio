# Protobuf (API ↔ ML worker)

Source of truth: `tunelink/v1/ml_worker.proto`.

Generate Python stubs into both apps:

```bash
cd proto
uv venv .venv && uv pip install --python .venv/bin/python grpcio-tools
./generate.sh
```

Outputs:

- `apps/backend/src/tunelink_backend/ml_client/generated/`
- `apps/ml-worker/src/tunelink_ml_worker/generated/`

See [docs/SPEC.md](../docs/SPEC.md).

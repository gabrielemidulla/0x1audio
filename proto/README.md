# Protobuf

Source: `ox1audio/v1/ml_worker.proto`.

```bash
cd proto
uv venv .venv && uv pip install --python .venv/bin/python grpcio-tools
./generate.sh
```

Writes stubs into `apps/backend/.../ml_client/generated/` and `apps/ml-worker/.../generated/`.

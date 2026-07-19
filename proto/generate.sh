#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
PY="${ROOT}/.venv/bin/python"

if [[ ! -x "$PY" ]]; then
  echo "Create a local venv first:"
  echo "  cd proto && uv venv .venv && uv pip install --python .venv/bin/python grpcio-tools"
  exit 1
fi

rewrite_grpc_import() {
  local grpc_file="$1"
  local prefix="$2"
  "$PY" - "$grpc_file" "$prefix" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
prefix = sys.argv[2]
text = path.read_text()
patterns = [
    r"^import ox1audio\.ml\.v1\.ml_worker_pb2 as (.*)$",
    r"^from ox1audio\.ml\.v1 import ml_worker_pb2 as (.*)$",
    r"^import ox1audio\.v1\.ml_worker_pb2 as (.*)$",
    r"^from ox1audio\.v1 import ml_worker_pb2 as (.*)$",
]
for pattern in patterns:
    text, n = re.subn(
        pattern,
        rf"from {prefix} import ml_worker_pb2 as \1",
        text,
        count=1,
        flags=re.M,
    )
    if n:
        break
path.write_text(text)
PY
}

gen_into() {
  local dest="$1"
  local prefix="$2"
  rm -rf "$dest"
  mkdir -p "$dest"
  "$PY" -m grpc_tools.protoc \
    -I"$ROOT" \
    --python_out="$dest" \
    --grpc_python_out="$dest" \
    --pyi_out="$dest" \
    "$ROOT/ox1audio/v1/ml_worker.proto"
  touch "$dest/ox1audio/__init__.py"
  touch "$dest/ox1audio/v1/__init__.py"
  rewrite_grpc_import "$dest/ox1audio/v1/ml_worker_pb2_grpc.py" "$prefix"
}

BACKEND_DEST="$REPO/apps/backend/src/ox1audio_backend/ml_client/generated"
WORKER_DEST="$REPO/apps/ml-worker/src/ox1audio_ml_worker/generated"

gen_into "$BACKEND_DEST" "ox1audio_backend.ml_client.generated.ox1audio.v1"
gen_into "$WORKER_DEST" "ox1audio_ml_worker.generated.ox1audio.v1"

echo "Generated:"
echo "  $BACKEND_DEST"
echo "  $WORKER_DEST"

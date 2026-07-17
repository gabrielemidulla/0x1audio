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

gen_into() {
  local dest="$1"
  local import_fix="$2"
  rm -rf "$dest"
  mkdir -p "$dest"
  "$PY" -m grpc_tools.protoc \
    -I"$ROOT" \
    --python_out="$dest" \
    --grpc_python_out="$dest" \
    --pyi_out="$dest" \
    "$ROOT/tunelink/v1/ml_worker.proto"
  touch "$dest/tunelink/__init__.py"
  touch "$dest/tunelink/v1/__init__.py"
  local grpc_file="$dest/tunelink/v1/ml_worker_pb2_grpc.py"
  if [[ "$(uname)" == "Darwin" ]]; then
    sed -i '' "s/^import tunelink\\.v1\\.ml_worker_pb2 as \\(.*\\)$/from ${import_fix} import ml_worker_pb2 as \\1/" "$grpc_file"
    sed -i '' "s/^from tunelink\\.v1 import ml_worker_pb2 as \\(.*\\)$/from ${import_fix} import ml_worker_pb2 as \\1/" "$grpc_file"
  else
    sed -i "s/^import tunelink\\.v1\\.ml_worker_pb2 as \\(.*\\)$/from ${import_fix} import ml_worker_pb2 as \\1/" "$grpc_file"
    sed -i "s/^from tunelink\\.v1 import ml_worker_pb2 as \\(.*\\)$/from ${import_fix} import ml_worker_pb2 as \\1/" "$grpc_file"
  fi
}

BACKEND_DEST="$REPO/apps/backend/src/tunelink_backend/ml_client/generated"
WORKER_DEST="$REPO/apps/ml-worker/src/tunelink_ml_worker/generated"

gen_into "$BACKEND_DEST" "tunelink_backend.ml_client.generated.tunelink.v1"
gen_into "$WORKER_DEST" "tunelink_ml_worker.generated.tunelink.v1"

echo "Generated:"
echo "  $BACKEND_DEST"
echo "  $WORKER_DEST"

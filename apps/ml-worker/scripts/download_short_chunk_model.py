#!/usr/bin/env python3
"""Download Short-chunk CNN Jamendo weights (MIT) for rich ML audio tagging."""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "data" / "models" / "short_chunk"
WEIGHTS_NAME = "best_model.pth"

# Upstream LFS object for models/jamendo/short_res/best_model.pth
WEIGHTS_URL = (
    "https://media.githubusercontent.com/media/minzwon/sota-music-tagging-models/"
    "master/models/jamendo/short_res/best_model.pth"
)


def download(url: str, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size > 0:
        print(f"exists {destination} ({destination.stat().st_size} bytes)")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(f"{destination.suffix}.tmp")
    print(f"download {url}")
    urllib.request.urlretrieve(url, temp_path)
    if temp_path.stat().st_size < 1_000_000:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Downloaded file looks too small ({temp_path}); "
            "Git LFS may not have resolved. Try cloning the upstream repo with git-lfs."
        )
    temp_path.replace(destination)
    print(f"wrote {destination} ({destination.stat().st_size} bytes)")


def main() -> int:
    try:
        download(WEIGHTS_URL, MODELS_DIR / WEIGHTS_NAME)
    except Exception as exc:
        print(f"failed {WEIGHTS_NAME}: {exc}", file=sys.stderr)
        return 1
    print(f"Short-chunk CNN weights ready in {MODELS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

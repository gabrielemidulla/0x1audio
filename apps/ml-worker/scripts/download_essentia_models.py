#!/usr/bin/env python3
"""Download Essentia/Discogs model files for rich ML audio analysis."""

from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = Path(
    os.getenv(
        "ESSENTIA_MODELS_DIR",
        str(ROOT / "data" / "models" / "essentia"),
    )
)

MODEL_URLS = {
    "discogs-effnet-bs64-1.pb": "https://essentia.upf.edu/models/music-style-classification/discogs-effnet/discogs-effnet-bs64-1.pb",
    "discogs-effnet-bs64-1.json": "https://essentia.upf.edu/models/music-style-classification/discogs-effnet/discogs-effnet-bs64-1.json",
    "mtg_jamendo_moodtheme-discogs-effnet-1.pb": "https://essentia.upf.edu/models/classification-heads/mtg_jamendo_moodtheme/mtg_jamendo_moodtheme-discogs-effnet-1.pb",
    "mtg_jamendo_moodtheme-discogs-effnet-1.json": "https://essentia.upf.edu/models/classification-heads/mtg_jamendo_moodtheme/mtg_jamendo_moodtheme-discogs-effnet-1.json",
    "mtg_jamendo_instrument-discogs-effnet-1.pb": "https://essentia.upf.edu/models/classification-heads/mtg_jamendo_instrument/mtg_jamendo_instrument-discogs-effnet-1.pb",
    "mtg_jamendo_instrument-discogs-effnet-1.json": "https://essentia.upf.edu/models/classification-heads/mtg_jamendo_instrument/mtg_jamendo_instrument-discogs-effnet-1.json",
    "genre_discogs400-discogs-effnet-1.pb": "https://essentia.upf.edu/models/classification-heads/genre_discogs400/genre_discogs400-discogs-effnet-1.pb",
    "genre_discogs400-discogs-effnet-1.json": "https://essentia.upf.edu/models/classification-heads/genre_discogs400/genre_discogs400-discogs-effnet-1.json",
}


def download(url: str, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size > 0:
        print(f"exists {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(f"{destination.suffix}.tmp")
    print(f"download {url}")
    urllib.request.urlretrieve(url, temp_path)
    temp_path.replace(destination)
    print(f"wrote {destination}")


def main() -> int:
    for filename, url in MODEL_URLS.items():
        try:
            download(url, MODELS_DIR / filename)
        except Exception as exc:
            print(f"failed {filename}: {exc}", file=sys.stderr)
            return 1
    print(f"Essentia models ready in {MODELS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

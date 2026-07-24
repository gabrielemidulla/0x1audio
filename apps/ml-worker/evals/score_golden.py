#!/usr/bin/env python3
"""Score golden queries against a running ML worker.

Reports Precision@k, Recall@k, and MRR. Relevance for positive queries is
derived from catalog analysis tags (see relevant_tags_any in the golden file).
expect_none queries treat any returned hit as a false positive.

Usage (Compose up, backend/ML reachable):

    uv run python evals/score_golden.py --k 6
    uv run python evals/score_golden.py --k 6 --out evals/results_after.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load_golden(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["queries"])


def relevant_from_catalog(tags_any: list[str]) -> set[str]:
    """Best-effort relevance from Postgres track.analysis tags."""
    try:
        import asyncio

        from sqlalchemy import select

        from ox1audio_backend.db import SessionLocal
        from ox1audio_backend.models import Track, TrackStatus
    except ImportError:
        print(
            "ox1audio_backend not importable; pass --relevant-map or run from backend venv",
            file=sys.stderr,
        )
        return set()

    needles = {tag.casefold() for tag in tags_any}

    async def _load() -> set[str]:
        hits: set[str] = set()
        async with SessionLocal() as session:
            tracks = (
                await session.scalars(
                    select(Track).where(Track.status == TrackStatus.READY)
                )
            ).all()
            for track in tracks:
                analysis = track.analysis if isinstance(track.analysis, dict) else {}
                bag: set[str] = set()
                for key in ("tags", "mood"):
                    for label in analysis.get(key) or []:
                        bag.add(str(label).casefold())
                for scores in (
                    analysis.get("genre_scores") or {},
                    analysis.get("mood_scores") or {},
                    analysis.get("model_tags") or {},
                ):
                    if isinstance(scores, dict):
                        bag.update(str(label).casefold() for label in scores)
                genre = analysis.get("genre")
                if genre:
                    bag.add(str(genre).casefold())
                    for part in str(genre).replace("/", " ").split():
                        bag.add(part.casefold())
                if bag & needles:
                    hits.add(str(track.id))
        return hits

    return asyncio.run(_load())


def precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    top = ranked[:k]
    if not top:
        return 1.0 if not relevant else 0.0
    return sum(1 for track_id in top if track_id in relevant) / len(top)


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 1.0
    top = ranked[:k]
    return sum(1 for track_id in top if track_id in relevant) / len(relevant)


def mrr(ranked: list[str], relevant: set[str]) -> float:
    if not relevant:
        return 1.0 if not ranked else 0.0
    for index, track_id in enumerate(ranked, start=1):
        if track_id in relevant:
            return 1.0 / index
    return 0.0


def search(query: str, top_k: int, target: str) -> list[str]:
    # Prefer backend MlClient when available; fall back to raw grpc.
    try:
        from ox1audio_backend.ml_client import MlClient

        client = MlClient(target=target)
        try:
            hits = client.search_text(query=query, top_k=top_k)
            return [hit.track_id for hit in hits]
        finally:
            client.close()
    except ImportError:
        pass

    import grpc

    sys.path.insert(0, str(ROOT / "src"))
    from ox1audio_ml_worker.generated.ox1audio.v1 import (  # type: ignore
        ml_worker_pb2,
        ml_worker_pb2_grpc,
    )

    channel = grpc.insecure_channel(target)
    stub = ml_worker_pb2_grpc.MlWorkerStub(channel)
    response = stub.SearchText(
        ml_worker_pb2.SearchTextRequest(query=query, top_k=top_k),
        timeout=60,
    )
    channel.close()
    return [item.track_id for item in response.results]


def load_relevant(item: dict[str, Any], golden_path: Path) -> set[str]:
    if item.get("expect_none"):
        return set()
    if item.get("relevant_track_ids"):
        return {str(value) for value in item["relevant_track_ids"]}
    ids_file = item.get("relevant_ids_file")
    if ids_file:
        path = Path(ids_file)
        if not path.is_absolute():
            path = golden_path.parent / path
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {str(value) for value in payload.get("ids", [])}
    tags_any = list(item.get("relevant_tags_any") or [])
    return relevant_from_catalog(tags_any) if tags_any else set()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--golden",
        type=Path,
        default=ROOT / "evals" / "golden_queries.json",
    )
    parser.add_argument("--k", type=int, default=6)
    parser.add_argument("--target", default="127.0.0.1:50051")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    queries = load_golden(args.golden)
    rows: list[dict[str, Any]] = []
    for item in queries:
        expect_none = bool(item.get("expect_none"))
        relevant = load_relevant(item, args.golden)

        ranked = search(item["query"], args.k, args.target)
        row = {
            "id": item["id"],
            "query": item["query"],
            "expect_none": expect_none,
            "relevant_count": len(relevant),
            "returned": ranked,
            "precision_at_k": round(precision_at_k(ranked, relevant, args.k), 4),
            "recall_at_k": round(recall_at_k(ranked, relevant, args.k), 4),
            "mrr": round(mrr(ranked, relevant), 4),
        }
        rows.append(row)
        print(
            f"{row['id']}: P@{args.k}={row['precision_at_k']} "
            f"R@{args.k}={row['recall_at_k']} MRR={row['mrr']} "
            f"n_rel={row['relevant_count']} n_hit={len(ranked)}"
        )

    payload = {"k": args.k, "target": args.target, "results": rows}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

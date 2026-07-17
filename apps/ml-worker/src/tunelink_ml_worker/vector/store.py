from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient, models

from tunelink_ml_worker.config import get_settings
from tunelink_ml_worker.embedders.provider import ModelProvider
from tunelink_ml_worker.vector.ranking import (
    ScoredTrack,
    baseline_from_scores,
    build_scored_track,
    combined_graph_score,
    cosine,
    filter_tiny_catalog,
)


class VectorStore:
    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider
        self.collection = collection_name(provider.name, provider.version)
        self.profile_collection = collection_name(
            "language-profile",
            provider.language_model_id,
        )
        self.client = qdrant_client()
        self.ensure_collections()

    def upsert_track(
        self,
        *,
        track_id: str,
        track_vector: list[float],
        segments: list[dict[str, Any]],
        segment_vectors: list[list[float]],
        metadata: dict[str, Any],
        profile_vector: list[float] | None = None,
        profile_text: str | None = None,
        search_tags: list[str] | None = None,
    ) -> None:
        points = [
            models.PointStruct(
                id=track_id,
                vector=track_vector,
                payload={
                    "track_id": track_id,
                    "kind": "track",
                    "segment_count": len(segments),
                    **metadata,
                },
            )
        ]
        points.extend(
            models.PointStruct(
                id=segment["id"],
                vector=vector,
                payload={
                    "track_id": track_id,
                    "kind": "segment",
                    **segment,
                },
            )
            for segment, vector in zip(segments, segment_vectors)
        )
        self.client.upsert(collection_name=self.collection, points=points, wait=True)

        if profile_vector:
            self.client.upsert(
                collection_name=self.profile_collection,
                points=[
                    models.PointStruct(
                        id=track_id,
                        vector=profile_vector,
                        payload={
                            "track_id": track_id,
                            "kind": "profile",
                            "profile_text": profile_text or "",
                            "search_tags": search_tags or [],
                            **metadata,
                        },
                    )
                ],
                wait=True,
            )

    def search(
        self,
        vector: list[float],
        top_k: int,
        operation: str,
        *,
        negative_vector: list[float] | None = None,
        profile_vector: list[float] | None = None,
        negative_profile_vector: list[float] | None = None,
        mode: str = "tracks",
        query_text: str | None = None,
        exclude_track_id: str | None = None,
    ) -> list[ScoredTrack]:
        settings = get_settings()
        audio_baseline = self.audio_baseline(vector, negative_vector)
        profile_baseline = (
            self.profile_baseline(profile_vector, negative_profile_vector)
            if profile_vector
            else None
        )

        response = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=max(80, top_k * 20),
            with_payload=True,
            with_vectors=True,
        )
        grouped: dict[str, dict[str, Any]] = {}

        for point in response.points:
            payload = point.payload or {}
            track_id = str(payload.get("track_id", ""))
            if not track_id or track_id == exclude_track_id:
                continue
            adjusted = float(point.score)
            if negative_vector and point.vector:
                adjusted -= max(0.0, cosine(negative_vector, list(point.vector))) * 0.35
            row = grouped.setdefault(
                track_id,
                {
                    "track_score": 0.0,
                    "segments": [],
                    "reasons": [],
                    "segment_count": 0,
                    "profile_score": None,
                    "search_tags": [],
                },
            )
            if payload.get("kind") == "track":
                row["track_score"] = adjusted
                row["segment_count"] = int(payload.get("segment_count", 0))
                row["reasons"] = list(payload.get("tags", []))[:3]
            else:
                row["segments"].append((str(point.id), adjusted))

        if profile_vector:
            profile_response = self.client.query_points(
                collection_name=self.profile_collection,
                query=profile_vector,
                limit=max(80, top_k * 20),
                with_payload=True,
                with_vectors=True,
            )
            for point in profile_response.points:
                payload = point.payload or {}
                track_id = str(payload.get("track_id", ""))
                if not track_id or track_id == exclude_track_id:
                    continue
                adjusted = float(point.score)
                if negative_profile_vector and point.vector:
                    adjusted -= (
                        max(0.0, cosine(negative_profile_vector, list(point.vector)))
                        * 0.45
                    )
                row = grouped.setdefault(
                    track_id,
                    {
                        "track_score": 0.0,
                        "segments": [],
                        "reasons": [],
                        "segment_count": 0,
                        "profile_score": None,
                        "search_tags": [],
                    },
                )
                row["profile_score"] = adjusted
                row["search_tags"] = list(payload.get("search_tags") or [])
                if not row["reasons"]:
                    row["reasons"] = list(payload.get("tags", []))[:3]

        scored = [
            build_scored_track(
                track_id,
                row,
                mode,
                audio_baseline,
                profile_baseline,
                query_text=query_text,
            )
            for track_id, row in grouped.items()
        ]
        scored.sort(key=lambda item: item.score, reverse=True)

        if operation in {"search_text", "search_audio"}:
            if audio_baseline is not None:
                results = [
                    item
                    for item in scored
                    if item.standout is not None
                    and item.standout >= settings.min_standout_sigma
                ]
            else:
                results = filter_tiny_catalog(scored)
        else:
            results = scored

        return results[:top_k]

    def audio_baseline(
        self,
        vector: list[float],
        negative_vector: list[float] | None = None,
    ):
        settings = get_settings()
        records, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=track_kind_filter(),
            limit=settings.baseline_sample,
            with_payload=False,
            with_vectors=True,
        )
        scores: list[float] = []
        for record in records:
            if not record.vector:
                continue
            score = cosine(vector, list(record.vector))
            if negative_vector:
                score -= max(0.0, cosine(negative_vector, list(record.vector))) * 0.35
            scores.append(score)
        return baseline_from_scores(scores)

    def profile_baseline(
        self,
        profile_vector: list[float],
        negative_profile_vector: list[float] | None = None,
    ):
        settings = get_settings()
        records, _ = self.client.scroll(
            collection_name=self.profile_collection,
            limit=settings.baseline_sample,
            with_payload=False,
            with_vectors=True,
        )
        scores: list[float] = []
        for record in records:
            if not record.vector:
                continue
            score = cosine(profile_vector, list(record.vector))
            if negative_profile_vector:
                score -= (
                    max(0.0, cosine(negative_profile_vector, list(record.vector))) * 0.45
                )
            scores.append(score)
        return baseline_from_scores(scores)

    def similar(self, track_id: str, top_k: int) -> list[ScoredTrack]:
        points = self.client.retrieve(
            collection_name=self.collection,
            ids=[track_id],
            with_vectors=True,
        )
        if not points or not points[0].vector:
            return []
        profile_points = self.client.retrieve(
            collection_name=self.profile_collection,
            ids=[track_id],
            with_vectors=True,
        )
        profile_vector = (
            list(profile_points[0].vector)
            if profile_points and profile_points[0].vector
            else None
        )
        return self.search(
            list(points[0].vector),
            top_k,
            "similar_tracks",
            profile_vector=profile_vector,
            exclude_track_id=track_id,
        )

    def graph(
        self,
        *,
        focus_track_id: str | None,
        limit: int,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        limit = max(2, min(limit, 24))
        if focus_track_id:
            focus_records = self.client.retrieve(
                collection_name=self.collection,
                ids=[focus_track_id],
                with_payload=True,
                with_vectors=True,
            )
            focus = focus_records[0] if focus_records else None
            if (
                focus
                and focus.vector
                and (focus.payload or {}).get("kind") == "track"
            ):
                records = self._neighbor_records_for_focus(focus, limit)
                return self._build_graph(records)

        records, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=track_kind_filter(),
            limit=limit,
            with_payload=True,
            with_vectors=True,
        )
        return self._build_graph(records)

    def _neighbor_records_for_focus(self, focus: Any, limit: int) -> list[Any]:
        focus_id = str(focus.id)
        candidates: dict[str, dict[str, float]] = {
            focus_id: {"audio_score": 1.0, "profile_score": 1.0}
        }

        audio_response = self.client.query_points(
            collection_name=self.collection,
            query=focus.vector,
            query_filter=track_kind_filter(),
            limit=max(limit * 3, 24),
            with_payload=True,
            with_vectors=True,
        )
        for point in audio_response.points:
            point_id = str(point.id)
            if point_id == focus_id:
                continue
            row = candidates.setdefault(
                point_id, {"audio_score": 0.0, "profile_score": 0.0}
            )
            row["audio_score"] = max(float(point.score), 0.0)

        profile_records = self.client.retrieve(
            collection_name=self.profile_collection,
            ids=[focus_id],
            with_vectors=True,
        )
        focus_profile = profile_records[0].vector if profile_records else None
        if focus_profile:
            profile_response = self.client.query_points(
                collection_name=self.profile_collection,
                query=focus_profile,
                limit=max(limit * 3, 24),
                with_payload=True,
                with_vectors=True,
            )
            for point in profile_response.points:
                point_id = str(point.id)
                if point_id == focus_id:
                    continue
                row = candidates.setdefault(
                    point_id, {"audio_score": 0.0, "profile_score": 0.0}
                )
                row["profile_score"] = max(float(point.score), 0.0)

        ranked_ids = sorted(
            (track_id for track_id in candidates if track_id != focus_id),
            key=lambda track_id: combined_graph_score(
                candidates[track_id]["audio_score"],
                candidates[track_id]["profile_score"],
            ),
            reverse=True,
        )[: max(limit - 1, 0)]

        neighbors: list[Any] = []
        if ranked_ids:
            neighbors = self.client.retrieve(
                collection_name=self.collection,
                ids=ranked_ids,
                with_payload=True,
                with_vectors=True,
            )
            neighbors = [
                record
                for record in neighbors
                if record.vector and (record.payload or {}).get("kind") == "track"
            ]
        return [focus, *neighbors]

    def _build_graph(self, records: list[Any]) -> tuple[list[str], list[dict[str, Any]]]:
        profile_vectors = self._load_profile_vectors([str(record.id) for record in records])
        pairwise: list[tuple[str, str, float, float, float]] = []

        for left_index, left in enumerate(records):
            if not left.vector:
                continue
            left_id = str(left.id)
            left_profile = profile_vectors.get(left_id)
            for right in records[left_index + 1 :]:
                if not right.vector:
                    continue
                right_id = str(right.id)
                audio_weight = max(0.0, cosine(list(left.vector), list(right.vector)))
                right_profile = profile_vectors.get(right_id)
                profile_weight = (
                    max(0.0, cosine(left_profile, right_profile))
                    if left_profile and right_profile
                    else 0.0
                )
                weight = combined_graph_score(audio_weight, profile_weight)
                pairwise.append(
                    (left_id, right_id, weight, audio_weight, profile_weight)
                )

        # Keep top-3 outgoing edges per node (undirected dedupe).
        by_node: dict[str, list[tuple[str, str, float, float, float]]] = {}
        for source, target, weight, audio_weight, profile_weight in pairwise:
            by_node.setdefault(source, []).append(
                (source, target, weight, audio_weight, profile_weight)
            )
            by_node.setdefault(target, []).append(
                (source, target, weight, audio_weight, profile_weight)
            )

        kept: dict[tuple[str, str], tuple[float, float, float]] = {}
        for edges in by_node.values():
            for source, target, weight, audio_weight, profile_weight in sorted(
                edges, key=lambda item: item[2], reverse=True
            )[:3]:
                key = (source, target) if source < target else (target, source)
                existing = kept.get(key)
                if existing is None or weight > existing[0]:
                    kept[key] = (weight, audio_weight, profile_weight)

        links = [
            {
                "source": source,
                "target": target,
                "weight": round(weight, 4),
                "audio_weight": round(audio_weight, 4),
                "profile_weight": round(profile_weight, 4),
                "reasons": ["audio + profile similarity"],
            }
            for (source, target), (weight, audio_weight, profile_weight) in kept.items()
        ]
        return [str(record.id) for record in records], links

    def _load_profile_vectors(self, track_ids: list[str]) -> dict[str, list[float]]:
        if not track_ids:
            return {}
        records = self.client.retrieve(
            collection_name=self.profile_collection,
            ids=track_ids,
            with_vectors=True,
        )
        return {
            str(record.id): list(record.vector)
            for record in records
            if record.vector
        }

    def ensure_collections(self) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(
                    size=self.provider.vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name="kind",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name="track_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

        if not self.client.collection_exists(self.profile_collection):
            self.client.create_collection(
                collection_name=self.profile_collection,
                vectors_config=models.VectorParams(
                    size=self.provider.profile_vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
            self.client.create_payload_index(
                collection_name=self.profile_collection,
                field_name="kind",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            self.client.create_payload_index(
                collection_name=self.profile_collection,
                field_name="track_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )


@lru_cache(maxsize=1)
def qdrant_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=settings.qdrant_timeout_seconds,
        check_compatibility=False,
    )


def track_kind_filter() -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="kind",
                match=models.MatchValue(value="track"),
            )
        ]
    )


def collection_name(provider: str, version: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"tunelink_{provider}_{version}")
    return value[:120]

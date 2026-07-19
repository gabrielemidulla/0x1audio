from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from ox1audio_ml_worker.audio.analysis import analyze_track, load_audio
from ox1audio_ml_worker.audio.download import download_audio
from ox1audio_ml_worker.embedders.profile import (
    profile_search_tags,
    track_audio_profile_text,
    track_profile_tag_text,
)
from ox1audio_ml_worker.embedders.provider import (
    ModelProvider,
    blend_profile_vectors,
    normalized,
)
from ox1audio_ml_worker.vector.store import VectorStore

logger = logging.getLogger(__name__)


class WorkerOperations:
    def __init__(self) -> None:
        self.provider = ModelProvider()
        self.vectors = VectorStore(self.provider)

    def analyze_track(
        self,
        *,
        track_id: str,
        audio_url: str,
        filename: str,
    ) -> dict[str, Any]:
        audio_path = download_audio(audio_url, filename)
        try:
            samples, duration_s = load_audio(audio_path)
            analysis = analyze_track(samples, duration_s, audio_path)

            for index, segment in enumerate(analysis["segments"]):
                segment["id"] = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"track:{track_id}:segment:{index}",
                    )
                )

            clip_vectors = self.provider.embed_audio_clips(analysis.pop("clips"))
            segment_vectors = segment_vectors_from_clips(
                clip_vectors,
                analysis.pop("clip_segment_indices"),
                len(analysis["segments"]),
            )
            track_vector = normalized(
                [sum(values) / len(values) for values in zip(*segment_vectors)]
            )

            profile_text = track_audio_profile_text(analysis)
            tag_text = track_profile_tag_text(analysis)
            sentence_vector = (
                self.provider.embed_profile_text(profile_text) if profile_text else None
            )
            tag_vector = self.provider.embed_profile_text(tag_text) if tag_text else None
            profile_vector = blend_profile_vectors(sentence_vector, tag_vector)

            self.vectors.upsert_track(
                track_id=track_id,
                track_vector=track_vector,
                segments=list(analysis["segments"]),
                segment_vectors=segment_vectors,
                metadata={
                    "tags": analysis["tags"],
                    "mood": analysis["mood"],
                    "genre": analysis["genre"],
                    "model_provider": self.provider.name,
                    "model_version": self.provider.version,
                },
                profile_vector=profile_vector,
                profile_text=profile_text,
                search_tags=profile_search_tags(analysis),
            )

            logger.info(
                "analyzed track_id=%s duration=%.1fs segments=%s",
                track_id,
                analysis["duration_s"],
                len(analysis["segments"]),
            )
            return {
                "track_id": track_id,
                "model_provider": self.provider.name,
                "model_version": self.provider.version,
                **analysis,
            }
        finally:
            Path(audio_path).unlink(missing_ok=True)

    def search_text(
        self,
        *,
        query: str,
        top_k: int,
        mode: str = "tracks",
        negative_query: str | None = None,
    ) -> list[dict[str, Any]]:
        top_k = max(1, min(top_k or 6, 20))
        vector = self.provider.embed_text(query)
        profile_vector = self.provider.embed_profile_query(query)
        negative = self.provider.embed_text(negative_query) if negative_query else None
        negative_profile = (
            self.provider.embed_profile_query(negative_query) if negative_query else None
        )
        results = self.vectors.search(
            vector,
            top_k,
            "search_text",
            negative_vector=negative,
            profile_vector=profile_vector,
            negative_profile_vector=negative_profile,
            mode=mode,
            query_text=query,
        )
        return [scored_to_dict(result) for result in results]

    def search_audio(self, *, audio_url: str, top_k: int) -> list[dict[str, Any]]:
        top_k = max(1, min(top_k or 6, 20))
        audio_path = download_audio(audio_url, "query.audio")
        try:
            samples, duration_s = load_audio(audio_path)
            analysis = analyze_track(samples, duration_s, audio_path)
            clip_vectors = self.provider.embed_audio_clips(analysis["clips"])
            vector = normalized(
                [sum(values) / len(values) for values in zip(*clip_vectors)]
            )
            results = self.vectors.search(vector, top_k, "search_audio")
            return [scored_to_dict(result) for result in results]
        finally:
            Path(audio_path).unlink(missing_ok=True)

    def similar_tracks(self, *, track_id: str, top_k: int) -> list[dict[str, Any]]:
        top_k = max(1, min(top_k or 6, 20))
        results = self.vectors.similar(track_id, top_k)
        return [scored_to_dict(result) for result in results]

    def graph(
        self,
        *,
        focus_track_id: str | None,
        limit: int,
    ) -> dict[str, Any]:
        limit = limit or 12
        node_ids, links = self.vectors.graph(
            focus_track_id=focus_track_id or None,
            limit=limit,
        )
        return {"node_ids": node_ids, "links": links}


def segment_vectors_from_clips(
    clip_vectors: list[list[float]],
    clip_segment_indices: list[int],
    segment_count: int,
) -> list[list[float]]:
    grouped: dict[int, list[list[float]]] = {}
    for vector, segment_index in zip(clip_vectors, clip_segment_indices):
        grouped.setdefault(segment_index, []).append(vector)

    segment_vectors: list[list[float]] = []
    for index in range(segment_count):
        vectors = grouped.get(index)
        if not vectors:
            raise ValueError(f"Segment {index} produced no embedding clips.")
        segment_vectors.append(
            normalized([sum(values) / len(values) for values in zip(*vectors)])
        )
    return segment_vectors


def scored_to_dict(result: Any) -> dict[str, Any]:
    return {
        "track_id": result.track_id,
        "score": result.score,
        "track_score": result.track_score,
        "best_segment_score": result.best_segment_score,
        "segment_coverage": result.segment_coverage,
        "match_scope": result.match_scope,
        "matched_segment_ids": result.matched_segment_ids,
        "reasons": result.reasons,
    }

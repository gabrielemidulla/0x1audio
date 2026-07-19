from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import grpc
from google.protobuf.json_format import MessageToDict

from ox1audio_backend.config import get_settings
from ox1audio_backend.ml_client.generated.ox1audio.v1 import ml_worker_pb2, ml_worker_pb2_grpc


@dataclass(frozen=True)
class AnalyzeResult:
    track_id: str
    model_provider: str
    model_version: str
    analysis: dict[str, Any]


@dataclass(frozen=True)
class SearchHit:
    track_id: str
    score: float
    track_score: float
    best_segment_score: float
    segment_coverage: float
    match_scope: str
    matched_segment_ids: list[str]
    reasons: list[str]


@dataclass(frozen=True)
class GraphLink:
    source: str
    target: str
    weight: float
    audio_weight: float
    profile_weight: float
    reasons: list[str]


@dataclass(frozen=True)
class GraphResult:
    node_ids: list[str]
    links: list[GraphLink]


class MlClient:
    def __init__(self, target: str | None = None) -> None:
        settings = get_settings()
        self._target = target or settings.ml_worker_target
        self._channel = grpc.insecure_channel(self._target)
        self._stub = ml_worker_pb2_grpc.MlWorkerStub(self._channel)

    def close(self) -> None:
        self._channel.close()

    def analyze_track(
        self,
        *,
        job_id: str,
        track_id: str,
        audio_url: str,
        filename: str,
        timeout_s: float | None = None,
    ) -> AnalyzeResult:
        settings = get_settings()
        timeout = timeout_s if timeout_s is not None else settings.ml_worker_timeout_seconds
        response = self._stub.AnalyzeTrack(
            ml_worker_pb2.AnalyzeTrackRequest(
                job_id=job_id,
                track_id=track_id,
                audio_url=audio_url,
                filename=filename,
            ),
            timeout=timeout,
        )
        analysis = MessageToDict(response, preserving_proto_field_name=True)
        analysis.pop("track_id", None)
        analysis.pop("model_provider", None)
        analysis.pop("model_version", None)
        return AnalyzeResult(
            track_id=response.track_id,
            model_provider=response.model_provider,
            model_version=response.model_version,
            analysis=analysis,
        )

    def search_text(
        self,
        *,
        query: str,
        top_k: int = 6,
        mode: str = "tracks",
        negative_query: str | None = None,
        timeout_s: float | None = None,
    ) -> list[SearchHit]:
        settings = get_settings()
        timeout = timeout_s if timeout_s is not None else settings.ml_search_timeout_seconds
        request = ml_worker_pb2.SearchTextRequest(
            query=query,
            top_k=top_k,
            mode=_search_mode(mode),
        )
        if negative_query:
            request.negative_query = negative_query
        response = self._stub.SearchText(request, timeout=timeout)
        return [_search_hit(item) for item in response.results]

    def search_audio(
        self,
        *,
        audio_url: str,
        top_k: int = 6,
        timeout_s: float | None = None,
    ) -> list[SearchHit]:
        settings = get_settings()
        timeout = timeout_s if timeout_s is not None else settings.ml_search_timeout_seconds
        response = self._stub.SearchAudio(
            ml_worker_pb2.SearchAudioRequest(audio_url=audio_url, top_k=top_k),
            timeout=timeout,
        )
        return [_search_hit(item) for item in response.results]

    def similar_tracks(
        self,
        *,
        track_id: str,
        top_k: int = 6,
        timeout_s: float | None = None,
    ) -> list[SearchHit]:
        settings = get_settings()
        timeout = timeout_s if timeout_s is not None else settings.ml_search_timeout_seconds
        response = self._stub.SimilarTracks(
            ml_worker_pb2.SimilarTracksRequest(track_id=track_id, top_k=top_k),
            timeout=timeout,
        )
        return [_search_hit(item) for item in response.results]

    def graph(
        self,
        *,
        focus_track_id: str | None = None,
        limit: int = 12,
        timeout_s: float | None = None,
    ) -> GraphResult:
        settings = get_settings()
        timeout = timeout_s if timeout_s is not None else settings.ml_search_timeout_seconds
        request = ml_worker_pb2.GraphRequest(limit=limit)
        if focus_track_id:
            request.focus_track_id = focus_track_id
        response = self._stub.Graph(request, timeout=timeout)
        return GraphResult(
            node_ids=list(response.node_ids),
            links=[
                GraphLink(
                    source=link.source,
                    target=link.target,
                    weight=float(link.weight),
                    audio_weight=float(link.audio_weight),
                    profile_weight=float(link.profile_weight),
                    reasons=list(link.reasons),
                )
                for link in response.links
            ],
        )


def get_ml_client() -> MlClient:
    return MlClient()


def _search_mode(mode: str) -> int:
    if mode == "segments":
        return ml_worker_pb2.SEARCH_MODE_SEGMENTS
    return ml_worker_pb2.SEARCH_MODE_TRACKS


def _search_hit(item: ml_worker_pb2.SearchResult) -> SearchHit:
    return SearchHit(
        track_id=item.track_id,
        score=float(item.score),
        track_score=float(item.track_score),
        best_segment_score=float(item.best_segment_score),
        segment_coverage=float(item.segment_coverage),
        match_scope=item.match_scope,
        matched_segment_ids=list(item.matched_segment_ids),
        reasons=list(item.reasons),
    )

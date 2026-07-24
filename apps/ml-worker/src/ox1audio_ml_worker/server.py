from __future__ import annotations

import logging
from concurrent import futures
from functools import lru_cache
from typing import Any

import grpc

from ox1audio_ml_worker.config import get_settings
from ox1audio_ml_worker.generated.ox1audio.v1 import ml_worker_pb2, ml_worker_pb2_grpc
from ox1audio_ml_worker.operations import WorkerOperations

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_operations() -> WorkerOperations:
    return WorkerOperations()


class MlWorkerServicer(ml_worker_pb2_grpc.MlWorkerServicer):
    def AnalyzeTrack(self, request, context):  # noqa: N802
        try:
            result = get_operations().analyze_track(
                track_id=request.track_id,
                audio_url=request.audio_url,
                filename=request.filename or "track.audio",
            )
            return _analyze_response(result)
        except Exception as exc:
            logger.exception("AnalyzeTrack failed track_id=%s", request.track_id)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return ml_worker_pb2.AnalyzeTrackResponse()

    def SearchText(self, request, context):  # noqa: N802
        try:
            mode = _search_mode(request.mode)
            negative = request.negative_query if request.HasField("negative_query") else None
            results = get_operations().search_text(
                query=request.query,
                top_k=request.top_k,
                mode=mode,
                negative_query=negative,
            )
            return ml_worker_pb2.SearchResponse(results=[_search_result(r) for r in results])
        except Exception as exc:
            logger.exception("SearchText failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return ml_worker_pb2.SearchResponse()

    def SearchAudio(self, request, context):  # noqa: N802
        try:
            results = get_operations().search_audio(
                audio_url=request.audio_url,
                top_k=request.top_k,
            )
            return ml_worker_pb2.SearchResponse(results=[_search_result(r) for r in results])
        except Exception as exc:
            logger.exception("SearchAudio failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return ml_worker_pb2.SearchResponse()

    def SimilarTracks(self, request, context):  # noqa: N802
        try:
            results = get_operations().similar_tracks(
                track_id=request.track_id,
                top_k=request.top_k,
            )
            return ml_worker_pb2.SearchResponse(results=[_search_result(r) for r in results])
        except Exception as exc:
            logger.exception("SimilarTracks failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return ml_worker_pb2.SearchResponse()

    def Graph(self, request, context):  # noqa: N802
        try:
            focus = (
                request.focus_track_id if request.HasField("focus_track_id") else None
            )
            sonic = (
                float(request.sonic_weight) if request.HasField("sonic_weight") else None
            )
            vibe = (
                float(request.vibe_weight) if request.HasField("vibe_weight") else None
            )
            result = get_operations().graph(
                focus_track_id=focus,
                limit=request.limit,
                sonic_weight=sonic,
                vibe_weight=vibe,
            )
            return ml_worker_pb2.GraphResponse(
                node_ids=result["node_ids"],
                links=[_graph_link(link) for link in result["links"]],
            )
        except Exception as exc:
            logger.exception("Graph failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return ml_worker_pb2.GraphResponse()


def _search_mode(mode: int) -> str:
    if mode == ml_worker_pb2.SEARCH_MODE_SEGMENTS:
        return "segments"
    return "tracks"


def _analyze_response(result: dict[str, Any]) -> ml_worker_pb2.AnalyzeTrackResponse:
    waveform = result.get("waveform") or {}
    response = ml_worker_pb2.AnalyzeTrackResponse(
        track_id=str(result["track_id"]),
        model_provider=str(result["model_provider"]),
        model_version=str(result["model_version"]),
        duration_s=float(result.get("duration_s") or 0.0),
        genre=str(result.get("genre") or ""),
        mood=[str(item) for item in result.get("mood") or []],
        tags=[str(item) for item in result.get("tags") or []],
        model_tags=_float_map(result.get("model_tags")),
        mood_scores=_float_map(result.get("mood_scores")),
        instrument_scores=_float_map(result.get("instrument_scores")),
        genre_scores=_float_map(result.get("genre_scores")),
        affect_scores=_float_map(result.get("affect_scores")),
        affect_labels=[str(item) for item in result.get("affect_labels") or []],
        waveform=ml_worker_pb2.WaveformAnalysis(
            version=int(waveform.get("version") or 1),
            duration_s=float(waveform.get("duration_s") or 0.0),
            sample_count=int(waveform.get("sample_count") or 0),
            samples=[float(value) for value in waveform.get("samples") or []],
        ),
    )
    if result.get("bpm") is not None:
        response.bpm = int(result["bpm"])
    if "is_instrumental" in result and result["is_instrumental"] is not None:
        response.is_instrumental = bool(result["is_instrumental"])
    if result.get("vocalness") is not None:
        response.vocalness = float(result["vocalness"])

    for segment in result.get("segments") or []:
        response.segments.append(
            ml_worker_pb2.SegmentAnalysis(
                id=str(segment.get("id") or ""),
                start_s=float(segment.get("start_s") or 0.0),
                end_s=float(segment.get("end_s") or 0.0),
                description=str(segment.get("description") or ""),
                tags=[str(item) for item in segment.get("tags") or []],
                model_tags=_float_map(segment.get("model_tags")),
                mood_scores=_float_map(segment.get("mood_scores")),
                instrument_scores=_float_map(segment.get("instrument_scores")),
                genre_scores=_float_map(segment.get("genre_scores")),
                energy=float(segment.get("energy") or 0.0),
                valence=float(segment.get("valence") or 0.0),
                tension=float(segment.get("tension") or 0.0),
            )
        )
    return response


def _search_result(result: dict[str, Any]) -> ml_worker_pb2.SearchResult:
    return ml_worker_pb2.SearchResult(
        track_id=str(result["track_id"]),
        score=float(result["score"]),
        track_score=float(result["track_score"]),
        best_segment_score=float(result["best_segment_score"]),
        segment_coverage=float(result["segment_coverage"]),
        match_scope=str(result["match_scope"]),
        matched_segment_ids=[str(item) for item in result["matched_segment_ids"]],
        reasons=[str(item) for item in result["reasons"]],
    )


def _graph_link(link: dict[str, Any]) -> ml_worker_pb2.GraphLink:
    return ml_worker_pb2.GraphLink(
        source=str(link["source"]),
        target=str(link["target"]),
        weight=float(link["weight"]),
        audio_weight=float(link["audio_weight"]),
        profile_weight=float(link["profile_weight"]),
        reasons=[str(item) for item in link.get("reasons") or []],
    )


def _float_map(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, float] = {}
    for key, score in value.items():
        try:
            result[str(key)] = float(score)
        except (TypeError, ValueError):
            continue
    return result


def serve(host: str | None = None, port: int | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    listen_host = host or settings.host
    listen_port = port or settings.port

    # Eagerly connect Qdrant / create collections; models load lazily on first RPC.
    get_operations()

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=2),
        options=[
            ("grpc.max_send_message_length", 64 * 1024 * 1024),
            ("grpc.max_receive_message_length", 64 * 1024 * 1024),
        ],
    )
    ml_worker_pb2_grpc.add_MlWorkerServicer_to_server(MlWorkerServicer(), server)
    listen = f"{listen_host}:{listen_port}"
    server.add_insecure_port(listen)
    server.start()
    logger.info("ml-worker listening on %s", listen)
    server.wait_for_termination()

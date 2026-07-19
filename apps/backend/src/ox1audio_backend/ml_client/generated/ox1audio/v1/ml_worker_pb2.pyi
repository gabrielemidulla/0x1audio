from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SearchMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SEARCH_MODE_UNSPECIFIED: _ClassVar[SearchMode]
    SEARCH_MODE_TRACKS: _ClassVar[SearchMode]
    SEARCH_MODE_SEGMENTS: _ClassVar[SearchMode]
SEARCH_MODE_UNSPECIFIED: SearchMode
SEARCH_MODE_TRACKS: SearchMode
SEARCH_MODE_SEGMENTS: SearchMode

class AnalyzeTrackRequest(_message.Message):
    __slots__ = ("job_id", "track_id", "audio_url", "filename")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    TRACK_ID_FIELD_NUMBER: _ClassVar[int]
    AUDIO_URL_FIELD_NUMBER: _ClassVar[int]
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    track_id: str
    audio_url: str
    filename: str
    def __init__(self, job_id: _Optional[str] = ..., track_id: _Optional[str] = ..., audio_url: _Optional[str] = ..., filename: _Optional[str] = ...) -> None: ...

class SegmentAnalysis(_message.Message):
    __slots__ = ("id", "start_s", "end_s", "description", "tags", "model_tags", "mood_scores", "instrument_scores", "genre_scores", "energy", "valence", "tension")
    class ModelTagsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: float
        def __init__(self, key: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    class MoodScoresEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: float
        def __init__(self, key: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    class InstrumentScoresEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: float
        def __init__(self, key: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    class GenreScoresEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: float
        def __init__(self, key: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    ID_FIELD_NUMBER: _ClassVar[int]
    START_S_FIELD_NUMBER: _ClassVar[int]
    END_S_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    MODEL_TAGS_FIELD_NUMBER: _ClassVar[int]
    MOOD_SCORES_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_SCORES_FIELD_NUMBER: _ClassVar[int]
    GENRE_SCORES_FIELD_NUMBER: _ClassVar[int]
    ENERGY_FIELD_NUMBER: _ClassVar[int]
    VALENCE_FIELD_NUMBER: _ClassVar[int]
    TENSION_FIELD_NUMBER: _ClassVar[int]
    id: str
    start_s: float
    end_s: float
    description: str
    tags: _containers.RepeatedScalarFieldContainer[str]
    model_tags: _containers.ScalarMap[str, float]
    mood_scores: _containers.ScalarMap[str, float]
    instrument_scores: _containers.ScalarMap[str, float]
    genre_scores: _containers.ScalarMap[str, float]
    energy: float
    valence: float
    tension: float
    def __init__(self, id: _Optional[str] = ..., start_s: _Optional[float] = ..., end_s: _Optional[float] = ..., description: _Optional[str] = ..., tags: _Optional[_Iterable[str]] = ..., model_tags: _Optional[_Mapping[str, float]] = ..., mood_scores: _Optional[_Mapping[str, float]] = ..., instrument_scores: _Optional[_Mapping[str, float]] = ..., genre_scores: _Optional[_Mapping[str, float]] = ..., energy: _Optional[float] = ..., valence: _Optional[float] = ..., tension: _Optional[float] = ...) -> None: ...

class WaveformAnalysis(_message.Message):
    __slots__ = ("version", "duration_s", "sample_count", "samples")
    VERSION_FIELD_NUMBER: _ClassVar[int]
    DURATION_S_FIELD_NUMBER: _ClassVar[int]
    SAMPLE_COUNT_FIELD_NUMBER: _ClassVar[int]
    SAMPLES_FIELD_NUMBER: _ClassVar[int]
    version: int
    duration_s: float
    sample_count: int
    samples: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, version: _Optional[int] = ..., duration_s: _Optional[float] = ..., sample_count: _Optional[int] = ..., samples: _Optional[_Iterable[float]] = ...) -> None: ...

class AnalyzeTrackResponse(_message.Message):
    __slots__ = ("track_id", "model_provider", "model_version", "duration_s", "bpm", "genre", "mood", "tags", "model_tags", "mood_scores", "instrument_scores", "genre_scores", "segments", "waveform", "is_instrumental", "vocalness")
    class ModelTagsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: float
        def __init__(self, key: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    class MoodScoresEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: float
        def __init__(self, key: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    class InstrumentScoresEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: float
        def __init__(self, key: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    class GenreScoresEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: float
        def __init__(self, key: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    TRACK_ID_FIELD_NUMBER: _ClassVar[int]
    MODEL_PROVIDER_FIELD_NUMBER: _ClassVar[int]
    MODEL_VERSION_FIELD_NUMBER: _ClassVar[int]
    DURATION_S_FIELD_NUMBER: _ClassVar[int]
    BPM_FIELD_NUMBER: _ClassVar[int]
    GENRE_FIELD_NUMBER: _ClassVar[int]
    MOOD_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    MODEL_TAGS_FIELD_NUMBER: _ClassVar[int]
    MOOD_SCORES_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_SCORES_FIELD_NUMBER: _ClassVar[int]
    GENRE_SCORES_FIELD_NUMBER: _ClassVar[int]
    SEGMENTS_FIELD_NUMBER: _ClassVar[int]
    WAVEFORM_FIELD_NUMBER: _ClassVar[int]
    IS_INSTRUMENTAL_FIELD_NUMBER: _ClassVar[int]
    VOCALNESS_FIELD_NUMBER: _ClassVar[int]
    track_id: str
    model_provider: str
    model_version: str
    duration_s: float
    bpm: int
    genre: str
    mood: _containers.RepeatedScalarFieldContainer[str]
    tags: _containers.RepeatedScalarFieldContainer[str]
    model_tags: _containers.ScalarMap[str, float]
    mood_scores: _containers.ScalarMap[str, float]
    instrument_scores: _containers.ScalarMap[str, float]
    genre_scores: _containers.ScalarMap[str, float]
    segments: _containers.RepeatedCompositeFieldContainer[SegmentAnalysis]
    waveform: WaveformAnalysis
    is_instrumental: bool
    vocalness: float
    def __init__(self, track_id: _Optional[str] = ..., model_provider: _Optional[str] = ..., model_version: _Optional[str] = ..., duration_s: _Optional[float] = ..., bpm: _Optional[int] = ..., genre: _Optional[str] = ..., mood: _Optional[_Iterable[str]] = ..., tags: _Optional[_Iterable[str]] = ..., model_tags: _Optional[_Mapping[str, float]] = ..., mood_scores: _Optional[_Mapping[str, float]] = ..., instrument_scores: _Optional[_Mapping[str, float]] = ..., genre_scores: _Optional[_Mapping[str, float]] = ..., segments: _Optional[_Iterable[_Union[SegmentAnalysis, _Mapping]]] = ..., waveform: _Optional[_Union[WaveformAnalysis, _Mapping]] = ..., is_instrumental: _Optional[bool] = ..., vocalness: _Optional[float] = ...) -> None: ...

class SearchTextRequest(_message.Message):
    __slots__ = ("query", "negative_query", "top_k", "mode")
    QUERY_FIELD_NUMBER: _ClassVar[int]
    NEGATIVE_QUERY_FIELD_NUMBER: _ClassVar[int]
    TOP_K_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    query: str
    negative_query: str
    top_k: int
    mode: SearchMode
    def __init__(self, query: _Optional[str] = ..., negative_query: _Optional[str] = ..., top_k: _Optional[int] = ..., mode: _Optional[_Union[SearchMode, str]] = ...) -> None: ...

class SearchAudioRequest(_message.Message):
    __slots__ = ("audio_url", "top_k")
    AUDIO_URL_FIELD_NUMBER: _ClassVar[int]
    TOP_K_FIELD_NUMBER: _ClassVar[int]
    audio_url: str
    top_k: int
    def __init__(self, audio_url: _Optional[str] = ..., top_k: _Optional[int] = ...) -> None: ...

class SimilarTracksRequest(_message.Message):
    __slots__ = ("track_id", "top_k")
    TRACK_ID_FIELD_NUMBER: _ClassVar[int]
    TOP_K_FIELD_NUMBER: _ClassVar[int]
    track_id: str
    top_k: int
    def __init__(self, track_id: _Optional[str] = ..., top_k: _Optional[int] = ...) -> None: ...

class SearchResult(_message.Message):
    __slots__ = ("track_id", "score", "track_score", "best_segment_score", "segment_coverage", "match_scope", "matched_segment_ids", "reasons")
    TRACK_ID_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    TRACK_SCORE_FIELD_NUMBER: _ClassVar[int]
    BEST_SEGMENT_SCORE_FIELD_NUMBER: _ClassVar[int]
    SEGMENT_COVERAGE_FIELD_NUMBER: _ClassVar[int]
    MATCH_SCOPE_FIELD_NUMBER: _ClassVar[int]
    MATCHED_SEGMENT_IDS_FIELD_NUMBER: _ClassVar[int]
    REASONS_FIELD_NUMBER: _ClassVar[int]
    track_id: str
    score: float
    track_score: float
    best_segment_score: float
    segment_coverage: float
    match_scope: str
    matched_segment_ids: _containers.RepeatedScalarFieldContainer[str]
    reasons: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, track_id: _Optional[str] = ..., score: _Optional[float] = ..., track_score: _Optional[float] = ..., best_segment_score: _Optional[float] = ..., segment_coverage: _Optional[float] = ..., match_scope: _Optional[str] = ..., matched_segment_ids: _Optional[_Iterable[str]] = ..., reasons: _Optional[_Iterable[str]] = ...) -> None: ...

class SearchResponse(_message.Message):
    __slots__ = ("results",)
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    results: _containers.RepeatedCompositeFieldContainer[SearchResult]
    def __init__(self, results: _Optional[_Iterable[_Union[SearchResult, _Mapping]]] = ...) -> None: ...

class GraphRequest(_message.Message):
    __slots__ = ("focus_track_id", "limit")
    FOCUS_TRACK_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    focus_track_id: str
    limit: int
    def __init__(self, focus_track_id: _Optional[str] = ..., limit: _Optional[int] = ...) -> None: ...

class GraphLink(_message.Message):
    __slots__ = ("source", "target", "weight", "audio_weight", "profile_weight", "reasons")
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    WEIGHT_FIELD_NUMBER: _ClassVar[int]
    AUDIO_WEIGHT_FIELD_NUMBER: _ClassVar[int]
    PROFILE_WEIGHT_FIELD_NUMBER: _ClassVar[int]
    REASONS_FIELD_NUMBER: _ClassVar[int]
    source: str
    target: str
    weight: float
    audio_weight: float
    profile_weight: float
    reasons: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, source: _Optional[str] = ..., target: _Optional[str] = ..., weight: _Optional[float] = ..., audio_weight: _Optional[float] = ..., profile_weight: _Optional[float] = ..., reasons: _Optional[_Iterable[str]] = ...) -> None: ...

class GraphResponse(_message.Message):
    __slots__ = ("node_ids", "links")
    NODE_IDS_FIELD_NUMBER: _ClassVar[int]
    LINKS_FIELD_NUMBER: _ClassVar[int]
    node_ids: _containers.RepeatedScalarFieldContainer[str]
    links: _containers.RepeatedCompositeFieldContainer[GraphLink]
    def __init__(self, node_ids: _Optional[_Iterable[str]] = ..., links: _Optional[_Iterable[_Union[GraphLink, _Mapping]]] = ...) -> None: ...

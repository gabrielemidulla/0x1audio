from __future__ import annotations

from uuid import uuid4

from ox1audio_backend.tools import ensure_registered, list_specs
from ox1audio_backend.tools.langchain import build_langchain_tools
from ox1audio_backend.tools.types import ToolContext


EXPECTED_TOOLS = {
    "search_vibe",
    "search_metadata",
    "similar_tracks",
    "graph_neighborhood",
    "get_track",
    "list_tracks",
    "library_stats",
    "search_artists",
    "get_artist",
    "list_playlists",
    "get_playlist",
    "create_playlist",
    "update_playlist",
    "add_tracks_to_playlist",
    "remove_tracks_from_playlist",
    "reorder_playlist",
    "delete_playlist",
}


def test_all_tools_registered() -> None:
    ensure_registered()
    names = {spec.name for spec in list_specs()}
    assert names == EXPECTED_TOOLS


def test_langchain_bridge_matches_registry() -> None:
    ensure_registered()
    # db is unused when only building schemas
    tools = build_langchain_tools(ToolContext(db=None, user_id=uuid4()))  # type: ignore[arg-type]
    assert {tool.name for tool in tools} == EXPECTED_TOOLS
    for tool in tools:
        assert tool.description
        assert tool.args_schema is not None

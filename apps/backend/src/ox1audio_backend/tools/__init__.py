from __future__ import annotations

from ox1audio_backend.tools import catalog, graph, playlists, search
from ox1audio_backend.tools import artists as artist_tools
from ox1audio_backend.tools.registry import execute, get_spec, list_specs

_registered = False


def ensure_registered() -> None:
    global _registered
    if _registered:
        return
    search.register_tools()
    graph.register_tools()
    catalog.register_tools()
    artist_tools.register_tools()
    playlists.register_tools()
    _registered = True


ensure_registered()

__all__ = [
    "ensure_registered",
    "execute",
    "get_spec",
    "list_specs",
]

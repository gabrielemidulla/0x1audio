from fastapi import APIRouter

from ox1audio_backend.api.artists import router as artists_router
from ox1audio_backend.api.auth import router as auth_router
from ox1audio_backend.api.catalog import router as catalog_router
from ox1audio_backend.api.chat import router as chat_router
from ox1audio_backend.api.graph import router as graph_router
from ox1audio_backend.api.health import router as health_router
from ox1audio_backend.api.playlists import router as playlists_router
from ox1audio_backend.api.search import router as search_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(catalog_router, prefix="/catalog", tags=["catalog"])
# Nested under /catalog so artists sit with tracks/imports/jobs.
api_router.include_router(artists_router, prefix="/catalog", tags=["artists"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(graph_router, prefix="/graph", tags=["graph"])
api_router.include_router(chat_router, prefix="/chats", tags=["chats"])
api_router.include_router(playlists_router, prefix="/playlists", tags=["playlists"])
api_router.include_router(health_router, tags=["health"])

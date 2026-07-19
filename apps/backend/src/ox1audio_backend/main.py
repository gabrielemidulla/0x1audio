from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from ox1audio_backend.api.router import api_router
from ox1audio_backend.config import get_settings
from ox1audio_backend.db import init_db
from ox1audio_backend.services.chat_title import start_title_backfill
from ox1audio_backend import storage
from ox1audio_backend.shared_constants import build_openapi_constants

OPENAPI_TAGS = [
    {"name": "auth", "description": "Registration, sessions, and profile"},
    {"name": "catalog", "description": "Tracks, imports, and indexing jobs"},
    {"name": "artists", "description": "Artist records linked to the catalog"},
    {"name": "search", "description": "Text, audio, and similar-track search"},
    {"name": "graph", "description": "Similarity neighborhood for exploration"},
    {"name": "chats", "description": "Conversational catalog assistant"},
    {"name": "playlists", "description": "Private track lists"},
    {"name": "health", "description": "Liveness"},
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    storage.ensure_bucket()
    # Catch chats that never got an LLM title (crashed stream, old rows, etc.).
    title_backfill = start_title_backfill()
    yield
    if not title_backfill.done():
        title_backfill.cancel()
        try:
            await title_backfill
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="0x1audio",
    version="0.1.0",
    summary="Private music catalog with search, chat, and playlists.",
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
)


def custom_openapi():
    if app.openapi_schema is not None:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        summary=app.summary,
        routes=app.routes,
        tags=OPENAPI_TAGS,
    )
    schema["x-ox1audio-constants"] = build_openapi_constants()
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

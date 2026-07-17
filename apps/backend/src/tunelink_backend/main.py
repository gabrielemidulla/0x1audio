from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tunelink_backend.api.router import api_router
from tunelink_backend.config import get_settings
from tunelink_backend.db import init_db
from tunelink_backend import storage


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    storage.ensure_bucket()
    yield


app = FastAPI(title="Tunelink", version="0.1.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

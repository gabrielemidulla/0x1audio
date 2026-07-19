from __future__ import annotations

from fastapi import HTTPException

from ox1audio_backend.exceptions import AppError


def http_error(exc: AppError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)

"""ML job retry helpers — permanent vs retriable failures."""

from __future__ import annotations

MAX_ML_ATTEMPTS = 3


def is_permanent_ml_error(exc: BaseException) -> bool:
    if isinstance(exc, FileNotFoundError):
        return True
    message = str(exc)
    return message in {"Track missing", "Cancelled"} or message.startswith(
        "Object missing:"
    )


def backoff_seconds(attempt_count: int) -> int:
    return min(60, 2**attempt_count)

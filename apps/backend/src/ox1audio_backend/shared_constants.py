"""Shared UI/API constants — source of truth for OpenAPI `x-ox1audio-constants`."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

PasswordRuleKind = Literal[
    "min_length",
    "has_upper",
    "has_lower",
    "has_digit",
    "has_special",
]


class PasswordRule(TypedDict):
    id: str
    label: str
    kind: PasswordRuleKind


ALLOWED_AUDIO_EXTENSIONS: list[str] = [
    ".mp3",
    ".wav",
    ".flac",
    ".m4a",
    ".ogg",
    ".aac",
]

ALLOWED_IMAGE_MIME_TYPES: list[str] = [
    "image/jpeg",
    "image/png",
    "image/webp",
]

FALLBACK_COVER_COLOR = "#64748b"

COVER_COLOR_CHROMA_BIAS = 0.35
COVER_COLOR_DEFAULT_LIMIT = 4

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

PASSWORD_RULES: list[PasswordRule] = [
    {
        "id": "length",
        "label": f"At least {PASSWORD_MIN_LENGTH} characters",
        "kind": "min_length",
    },
    {
        "id": "upper",
        "label": "One uppercase letter",
        "kind": "has_upper",
    },
    {
        "id": "lower",
        "label": "One lowercase letter",
        "kind": "has_lower",
    },
    {
        "id": "number",
        "label": "One number",
        "kind": "has_digit",
    },
    {
        "id": "special",
        "label": "One special character",
        "kind": "has_special",
    },
]


def allowed_audio_extensions_csv() -> str:
    return ",".join(ALLOWED_AUDIO_EXTENSIONS)


def build_openapi_constants() -> dict[str, Any]:
    """Payload embedded in OpenAPI as `x-ox1audio-constants` (build-time only)."""
    from ox1audio_backend.services.playlist_colors import playlist_colors_for_openapi

    return {
        "playlistColors": playlist_colors_for_openapi(),
        "password": {
            "minLength": PASSWORD_MIN_LENGTH,
            "maxLength": PASSWORD_MAX_LENGTH,
            "rules": list(PASSWORD_RULES),
        },
        "allowedAudioExtensions": list(ALLOWED_AUDIO_EXTENSIONS),
        "allowedImageMimeTypes": list(ALLOWED_IMAGE_MIME_TYPES),
        "fallbackCoverColor": FALLBACK_COVER_COLOR,
        "coverColorRanking": {
            "chromaBias": COVER_COLOR_CHROMA_BIAS,
            "defaultLimit": COVER_COLOR_DEFAULT_LIMIT,
        },
    }

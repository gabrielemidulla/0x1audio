from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from mutagen import MutagenError
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp3 import MP3


@dataclass(frozen=True)
class EmbeddedCover:
    data: bytes
    content_type: str


@dataclass(frozen=True)
class AudioTags:
    title: str | None
    artist: str | None
    cover: EmbeddedCover | None = None


def read_audio_tags(data: bytes, filename: str) -> AudioTags:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".mp3", ".flac", ".m4a", ".ogg", ".aac", ".wav"}:
        return AudioTags(title=None, artist=None, cover=None)

    try:
        if suffix == ".mp3":
            return _read_mp3(data)
        if suffix == ".flac":
            return _read_flac(data)
        if suffix == ".m4a":
            return _read_m4a(data)
        return _read_easy(data, filename)
    except (MutagenError, OSError, KeyError, TypeError, ValueError):
        return AudioTags(title=None, artist=None, cover=None)


def _read_mp3(data: bytes) -> AudioTags:
    bio = BytesIO(data)
    title: str | None = None
    artist: str | None = None
    try:
        audio = MP3(bio, ID3=EasyID3)
        title = _first(audio.get("title"))
        artist = _first(audio.get("artist"))
    except ID3NoHeaderError:
        pass

    cover = None
    bio.seek(0)
    try:
        for frame in ID3(bio).values():
            if getattr(frame, "FrameID", None) != "APIC":
                continue
            mime = _normalize_image_mime(getattr(frame, "mime", None))
            payload = bytes(getattr(frame, "data", b"") or b"")
            if mime and payload:
                cover = EmbeddedCover(data=payload, content_type=mime)
                break
    except MutagenError:
        pass

    return AudioTags(title=title, artist=artist, cover=cover)


def _read_flac(data: bytes) -> AudioTags:
    from mutagen.flac import FLAC

    audio = FLAC(BytesIO(data))
    title = _first(audio.get("title"))
    artist = _first(audio.get("artist"))
    cover = None
    if audio.pictures:
        pic = audio.pictures[0]
        mime = _normalize_image_mime(pic.mime)
        if mime and pic.data:
            cover = EmbeddedCover(data=bytes(pic.data), content_type=mime)
    return AudioTags(title=title, artist=artist, cover=cover)


def _read_m4a(data: bytes) -> AudioTags:
    from mutagen.mp4 import MP4, MP4Cover

    audio = MP4(BytesIO(data))
    tags = audio.tags or {}
    title = _first(tags.get("\xa9nam"))
    artist = _first(tags.get("\xa9ART"))
    cover = None
    for item in tags.get("covr") or []:
        if not isinstance(item, (MP4Cover, bytes)):
            continue
        raw = bytes(item)
        fmt = getattr(item, "imageformat", None)
        if fmt == MP4Cover.FORMAT_PNG:
            mime = "image/png"
        else:
            mime = "image/jpeg"
        if raw:
            cover = EmbeddedCover(data=raw, content_type=mime)
            break
    return AudioTags(title=title, artist=artist, cover=cover)


def _read_easy(data: bytes, filename: str) -> AudioTags:
    from mutagen import File

    audio = File(BytesIO(data), filename=filename, easy=True)
    if audio is None or audio.tags is None:
        return AudioTags(title=None, artist=None, cover=None)
    return AudioTags(
        title=_first(audio.tags.get("title")),
        artist=_first(audio.tags.get("artist")),
        cover=None,
    )


def _normalize_image_mime(mime: str | None) -> str | None:
    if not mime:
        return None
    value = mime.strip().lower()
    if value in {"image/jpg", "image/jpeg", "jpeg", "jpg"}:
        return "image/jpeg"
    if value in {"image/png", "png"}:
        return "image/png"
    return None


def _first(values: object) -> str | None:
    if not values:
        return None
    if isinstance(values, list):
        text = str(values[0]).strip() if values else ""
    else:
        text = str(values).strip()
    return text[:512] or None

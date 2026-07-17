from __future__ import annotations

import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import PurePosixPath
from types import TracebackType

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")

AUDIO_CONTENT_TYPES: dict[str, str] = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".aac": "audio/aac",
}


class ZipSafetyError(Exception):
    pass


@dataclass(frozen=True)
class ZipAudioEntry:
    safe_filename: str
    data: bytes
    content_type: str


def safe_filename(filename: str) -> str:
    name = PurePosixPath(filename.replace("\\", "/")).name
    if not name or name in {".", ".."}:
        raise ZipSafetyError(f"Invalid filename: {filename!r}")
    cleaned = _SAFE_FILENAME.sub("_", name).strip("._")
    if not cleaned:
        raise ZipSafetyError(f"Invalid filename: {filename!r}")
    return cleaned[:200]


def _entry_path_unsafe(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    return path.is_absolute() or ".." in path.parts or not path.name


def _collect_audio_infos(
    archive: zipfile.ZipFile,
    *,
    allowed_extensions: set[str],
    max_files: int,
    max_uncompressed_bytes: int,
    max_file_bytes: int,
) -> list[zipfile.ZipInfo]:
    audio_infos: list[zipfile.ZipInfo] = []
    uncompressed_total = 0

    for info in archive.infolist():
        if info.is_dir():
            continue
        if getattr(info, "is_symlink", lambda: False)():
            raise ZipSafetyError(f"Symlinks are not allowed: {info.filename}")
        if _entry_path_unsafe(info.filename):
            raise ZipSafetyError(f"Unsafe path in archive: {info.filename}")

        name = PurePosixPath(info.filename.replace("\\", "/")).name
        suffix = PurePosixPath(name).suffix.lower()
        if suffix not in allowed_extensions:
            continue

        if info.file_size > max_file_bytes:
            raise ZipSafetyError(
                f"File exceeds per-file limit ({max_file_bytes} bytes): {info.filename}"
            )

        uncompressed_total += info.file_size
        if uncompressed_total > max_uncompressed_bytes:
            raise ZipSafetyError(
                f"Uncompressed size exceeds limit ({max_uncompressed_bytes} bytes)"
            )

        audio_infos.append(info)
        if len(audio_infos) > max_files:
            raise ZipSafetyError(f"Too many audio files (max {max_files})")

    if not audio_infos:
        raise ZipSafetyError("ZIP contains no supported audio files")
    return audio_infos


class SafeAudioZip:
    """Open a ZIP, validate audio members, then stream one file at a time."""

    def __init__(
        self,
        zip_path: str,
        *,
        allowed_extensions: set[str],
        max_files: int,
        max_uncompressed_bytes: int,
        max_file_bytes: int,
    ) -> None:
        try:
            self._archive = zipfile.ZipFile(zip_path, "r")
        except zipfile.BadZipFile as exc:
            raise ZipSafetyError("Not a valid ZIP archive") from exc
        try:
            self._infos = _collect_audio_infos(
                self._archive,
                allowed_extensions=allowed_extensions,
                max_files=max_files,
                max_uncompressed_bytes=max_uncompressed_bytes,
                max_file_bytes=max_file_bytes,
            )
        except Exception:
            self._archive.close()
            raise
        self._max_file_bytes = max_file_bytes

    @property
    def total_files(self) -> int:
        return len(self._infos)

    def __enter__(self) -> SafeAudioZip:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._archive.close()

    def __iter__(self) -> Iterator[ZipAudioEntry]:
        for info in self._infos:
            name = PurePosixPath(info.filename.replace("\\", "/")).name
            safe_name = safe_filename(name)
            suffix = PurePosixPath(safe_name).suffix.lower()
            with self._archive.open(info, "r") as raw:
                data = raw.read(self._max_file_bytes + 1)
            if len(data) > self._max_file_bytes:
                raise ZipSafetyError(
                    f"File exceeds per-file limit ({self._max_file_bytes} bytes): {info.filename}"
                )
            yield ZipAudioEntry(
                safe_filename=safe_name,
                data=data,
                content_type=AUDIO_CONTENT_TYPES.get(suffix, "application/octet-stream"),
            )

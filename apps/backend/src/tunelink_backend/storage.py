from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error
from urllib3.response import BaseHTTPResponse

from tunelink_backend.config import get_settings

_MINIO_REGION = "us-east-1"


@dataclass(frozen=True)
class OpenedObject:
    stream: BaseHTTPResponse
    content_type: str
    content_length: int
    total_size: int
    status_code: int
    content_range: str | None = None


def parse_byte_range(range_header: str | None, total_size: int) -> tuple[int, int] | None:
    if not range_header or not range_header.startswith("bytes="):
        return None
    start_text, _, end_text = range_header.removeprefix("bytes=").partition("-")
    try:
        start = int(start_text) if start_text else 0
    except ValueError:
        return None
    if start < 0 or start >= total_size:
        return None
    try:
        end = int(end_text) if end_text else total_size - 1
    except ValueError:
        end = total_size - 1
    if end < start:
        return None
    return start, min(end, total_size - 1)


@lru_cache
def _client() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
        region=_MINIO_REGION,
    )


def ensure_bucket() -> None:
    settings = get_settings()
    client = _client()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def put_object(
    object_key: str,
    data: BinaryIO,
    length: int,
    content_type: str,
) -> None:
    settings = get_settings()
    _client().put_object(
        settings.minio_bucket,
        object_key,
        data,
        length=length,
        content_type=content_type,
    )


def fput_object(object_key: str, file_path: str, content_type: str) -> None:
    """Upload a local file path (streams from disk — use for large ZIPs)."""
    settings = get_settings()
    _client().fput_object(
        settings.minio_bucket,
        object_key,
        file_path,
        content_type=content_type,
    )


def fget_object(object_key: str, file_path: str) -> None:
    settings = get_settings()
    _client().fget_object(settings.minio_bucket, object_key, file_path)


def get_object_bytes(object_key: str) -> tuple[bytes, str]:
    settings = get_settings()
    response = _client().get_object(settings.minio_bucket, object_key)
    try:
        data = response.read()
        content_type = response.headers.get("Content-Type") or "application/octet-stream"
        return data, content_type
    finally:
        response.close()
        response.release_conn()


def open_object(object_key: str, range_header: str | None = None) -> OpenedObject:
    settings = get_settings()
    client = _client()
    stat = client.stat_object(settings.minio_bucket, object_key)
    total_size = int(stat.size)
    content_type = (
        (stat.metadata or {}).get("Content-Type")
        or (stat.metadata or {}).get("content-type")
        or "application/octet-stream"
    )
    byte_range = parse_byte_range(range_header, total_size)
    if byte_range is None:
        stream = client.get_object(settings.minio_bucket, object_key)
        return OpenedObject(
            stream=stream,
            content_type=content_type,
            content_length=total_size,
            total_size=total_size,
            status_code=200,
        )

    start, end = byte_range
    length = end - start + 1
    stream = client.get_object(
        settings.minio_bucket,
        object_key,
        offset=start,
        length=length,
    )
    return OpenedObject(
        stream=stream,
        content_type=content_type,
        content_length=length,
        total_size=total_size,
        status_code=206,
        content_range=f"bytes {start}-{end}/{total_size}",
    )


def presigned_get_url(object_key: str) -> str:
    """Short-lived GET URL for the ML worker (signed for the configured MinIO host)."""
    settings = get_settings()
    return _client().presigned_get_object(
        settings.minio_bucket,
        object_key,
        expires=timedelta(seconds=settings.presign_expires_seconds),
    )


def object_stat(object_key: str):
    settings = get_settings()
    return _client().stat_object(settings.minio_bucket, object_key)


def object_exists(object_key: str) -> bool:
    try:
        object_stat(object_key)
        return True
    except S3Error:
        return False


def remove_object(object_key: str) -> None:
    settings = get_settings()
    try:
        _client().remove_object(settings.minio_bucket, object_key)
    except S3Error:
        pass

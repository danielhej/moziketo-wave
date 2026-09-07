from __future__ import annotations

import asyncio
import mimetypes
import uuid
from typing import Literal

from fastapi import HTTPException, status

from app.core.config import get_settings

UploadKind = Literal["avatar", "cover", "audio"]

ALLOWED_MIME: dict[UploadKind, set[str]] = {
    "avatar": {"image/jpeg", "image/png", "image/webp"},
    "cover": {"image/jpeg", "image/png", "image/webp"},
    "audio": {"audio/mpeg", "audio/mp4", "audio/x-m4a", "audio/mp3"},
}

MAX_BYTES: dict[UploadKind, int] = {
    "avatar": 2 * 1024 * 1024,
    "cover": 10 * 1024 * 1024,
    "audio": 10 * 1024 * 1024,
}

EXT_BY_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
}


def storage_configured() -> bool:
    settings = get_settings()
    return bool(
        settings.s3_bucket.strip()
        and settings.s3_access_key.strip()
        and settings.s3_secret_key.strip()
    )


def _validate_upload(kind: UploadKind, content_type: str, size: int) -> None:
    settings = get_settings()
    if not storage_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage is not configured",
        )

    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized not in ALLOWED_MIME[kind]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported content type for {kind}: {content_type}",
        )

    max_bytes = min(MAX_BYTES[kind], settings.upload_max_bytes)
    if size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds max size of {max_bytes} bytes",
        )


def _object_key(kind: UploadKind, content_type: str) -> str:
    ext = EXT_BY_MIME.get(content_type.split(";", 1)[0].strip().lower())
    if not ext:
        ext = mimetypes.guess_extension(content_type) or "bin"
        ext = ext.lstrip(".")
    return f"uploads/{kind}/{uuid.uuid4()}.{ext}"


def _upload_sync(*, key: str, body: bytes, content_type: str) -> str:
    import boto3
    from botocore.config import Config

    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint or None,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=Config(signature_version="s3v4"),
    )
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
        ACL="public-read",
    )
    base = settings.s3_public_base_url.rstrip("/")
    return f"{base}/{key}"


async def upload_bytes(*, kind: UploadKind, content: bytes, content_type: str) -> str:
    _validate_upload(kind, content_type, len(content))
    key = _object_key(kind, content_type)
    return await asyncio.to_thread(
        _upload_sync,
        key=key,
        body=content,
        content_type=content_type.split(";", 1)[0].strip().lower(),
    )

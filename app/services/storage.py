from __future__ import annotations

import asyncio
import mimetypes
import uuid
from typing import Literal
from urllib.parse import unquote, urlparse

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


def _s3_client():
    import boto3
    from botocore.config import Config

    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint or None,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=Config(signature_version="s3v4"),
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


def canonical_object_url(key: str) -> str:
    settings = get_settings()
    base = settings.s3_public_base_url.rstrip("/")
    return f"{base}/{key}"


def parse_managed_object_key(url: str) -> str | None:
    """Return S3 object key if URL belongs to our configured bucket/base."""
    if not url or not storage_configured():
        return None
    settings = get_settings()
    base = settings.s3_public_base_url.rstrip("/")
    if url.startswith(base + "/"):
        return unquote(url[len(base) + 1 :])
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    bucket = settings.s3_bucket.lower()
    if host.startswith(f"{bucket}.") and "arvanstorage" in host:
        return unquote(parsed.path.lstrip("/"))
    return None


def _upload_sync(*, key: str, body: bytes, content_type: str) -> str:
    settings = get_settings()
    client = _s3_client()
    extra: dict[str, str] = {"ContentType": content_type}
    acl = settings.s3_upload_acl.strip()
    if acl and acl.lower() != "private":
        extra["ACL"] = acl
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=body,
        **extra,
    )
    return canonical_object_url(key)


def _presign_get_sync(*, key: str, ttl: int) -> str:
    settings = get_settings()
    client = _s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=ttl,
    )


def _check_s3_sync() -> bool:
    if not storage_configured():
        return False
    settings = get_settings()
    client = _s3_client()
    client.head_bucket(Bucket=settings.s3_bucket)
    return True


async def check_s3() -> str:
    """Return ok, error, or skipped for health probes."""
    if not storage_configured():
        return "skipped"
    try:
        await asyncio.to_thread(_check_s3_sync)
        return "ok"
    except Exception:
        return "error"


async def presign_get_url(url: str, *, ttl: int | None = None) -> str:
    key = parse_managed_object_key(url)
    if key is None:
        return url
    settings = get_settings()
    expires = ttl if ttl is not None else settings.s3_presign_ttl_seconds
    return await asyncio.to_thread(_presign_get_sync, key=key, ttl=expires)


async def upload_bytes(*, kind: UploadKind, content: bytes, content_type: str) -> str:
    _validate_upload(kind, content_type, len(content))
    key = _object_key(kind, content_type)
    url = await asyncio.to_thread(
        _upload_sync,
        key=key,
        body=content,
        content_type=content_type.split(";", 1)[0].strip().lower(),
    )
    if get_settings().s3_upload_acl.strip().lower() == "private":
        return await presign_get_url(url)
    return url


async def resolve_media_url(stored_url: str) -> str:
    """Return presigned URL for private bucket objects; pass through legacy public URLs."""
    key = parse_managed_object_key(stored_url)
    if key is None:
        return stored_url
    if get_settings().s3_upload_acl.strip().lower() == "private":
        return await presign_get_url(stored_url)
    return stored_url

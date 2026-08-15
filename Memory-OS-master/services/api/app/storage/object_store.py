"""S3-compatible object storage abstraction.

Supports local filesystem (dev) and S3/MinIO (prod). Used for audit log
archives, export bundles, and large attachment payloads.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()


class ObjectStore(ABC):
    @abstractmethod
    async def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        ...

    @abstractmethod
    async def get(self, key: str) -> bytes:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        ...


class LocalObjectStore(ObjectStore):
    def __init__(self, base_path: str) -> None:
        self.base = Path(base_path)
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = key.replace("..", "").lstrip("/")
        return self.base / safe

    async def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return str(p)

    async def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    async def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    async def exists(self, key: str) -> bool:
        return self._path(key).exists()


class S3ObjectStore(ObjectStore):
    def __init__(self) -> None:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore

        kwargs = {"region_name": settings.s3_region}
        if settings.s3_endpoint:
            kwargs["endpoint_url"] = settings.s3_endpoint
        if settings.aws_access_key_id:
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        self._client = boto3.client("s3", config=Config(signature_version="s3v4"), **kwargs)
        self._bucket = settings.s3_bucket or "memory-os"

    async def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)
        return f"s3://{self._bucket}/{key}"

    async def get(self, key: str) -> bytes:
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        return resp["Body"].read()

    async def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    async def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False


def build_object_store() -> ObjectStore:
    if settings.object_storage_backend == "s3" and settings.s3_bucket:
        try:
            return S3ObjectStore()
        except ImportError:
            pass
    return LocalObjectStore(settings.object_storage_local_path)

from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import Protocol
from urllib.parse import quote


class StorageError(RuntimeError):
    """Base error for an object storage operation."""


class StorageConfigurationError(StorageError):
    """Raised when an enabled storage backend has incomplete configuration."""


class StorageObjectNotFoundError(StorageError):
    """Raised when a requested object key does not exist."""


@dataclass(frozen=True)
class PresignedUpload:
    object_key: str
    url: str
    headers: dict[str, str]
    expires_in: int


class ObjectStorage(Protocol):
    def create_upload_url(
        self, object_key: str, content_type: str, public_api_url: str
    ) -> PresignedUpload: ...

    def download_bytes(self, object_key: str) -> bytes: ...

    def upload_bytes(self, object_key: str, data: bytes, content_type: str) -> None: ...

    def create_download_url(self, object_key: str, public_api_url: str) -> str: ...


def _validate_object_key(object_key: str) -> str:
    path = PurePosixPath(object_key)
    if not object_key or path.is_absolute() or ".." in path.parts:
        raise StorageError("Invalid object key.")
    return path.as_posix()


class LocalMockObjectStorage:
    """Filesystem-backed development storage with one-time upload/download tokens."""

    def __init__(self, root_dir: Path, expires_in: int) -> None:
        self.root_dir = root_dir
        self.expires_in = expires_in
        self._tokens: dict[str, tuple[str, str, str]] = {}
        self._lock = Lock()

    def _path_for(self, object_key: str) -> Path:
        safe_key = _validate_object_key(object_key)
        return self.root_dir.joinpath(*PurePosixPath(safe_key).parts)

    def _create_token(self, object_key: str, method: str, content_type: str) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._tokens[token] = (object_key, method, content_type)
        return token

    def _consume_token(self, object_key: str, method: str, token: str) -> str:
        with self._lock:
            expected = self._tokens.pop(token, None)
        if expected is None or expected[0] != object_key or expected[1] != method:
            raise StorageError("The storage link is invalid or has already been used.")
        return expected[2]

    def create_upload_url(
        self, object_key: str, content_type: str, public_api_url: str
    ) -> PresignedUpload:
        object_key = _validate_object_key(object_key)
        token = self._create_token(object_key, "PUT", content_type)
        object_url = quote(object_key, safe="/")
        return PresignedUpload(
            object_key=object_key,
            url=f"{public_api_url.rstrip('/')}/api/storage/mock/{object_url}?token={token}",
            headers={"Content-Type": content_type},
            expires_in=self.expires_in,
        )

    def receive_upload(self, object_key: str, token: str, data: bytes, content_type: str) -> None:
        expected_content_type = self._consume_token(object_key, "PUT", token)
        if content_type != expected_content_type:
            raise StorageError("The storage upload content type does not match the signed request.")
        self.upload_bytes(object_key, data, content_type)

    def download_bytes(self, object_key: str) -> bytes:
        path = self._path_for(object_key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise StorageObjectNotFoundError("The requested object does not exist.") from exc

    def upload_bytes(self, object_key: str, data: bytes, content_type: str) -> None:
        del content_type
        path = self._path_for(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def create_download_url(self, object_key: str, public_api_url: str) -> str:
        object_key = _validate_object_key(object_key)
        token = self._create_token(object_key, "GET", "image/png")
        object_url = quote(object_key, safe="/")
        return f"{public_api_url.rstrip('/')}/api/storage/mock/{object_url}?token={token}"

    def read_download(self, object_key: str, token: str) -> tuple[bytes, str]:
        content_type = self._consume_token(object_key, "GET", token)
        return self.download_bytes(object_key), content_type


class S3ObjectStorage:
    """S3-compatible adapter for Yandex Object Storage in production."""

    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        expires_in: int,
    ) -> None:
        if not all((endpoint, bucket, access_key_id, secret_access_key)):
            raise StorageConfigurationError(
                "S3 storage requires S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY_ID and "
                "S3_SECRET_ACCESS_KEY."
            )

        import boto3

        self.bucket = bucket
        self.expires_in = expires_in
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def create_upload_url(
        self, object_key: str, content_type: str, public_api_url: str
    ) -> PresignedUpload:
        del public_api_url
        object_key = _validate_object_key(object_key)
        url = self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": object_key, "ContentType": content_type},
            ExpiresIn=self.expires_in,
            HttpMethod="PUT",
        )
        return PresignedUpload(
            object_key=object_key,
            url=url,
            headers={"Content-Type": content_type},
            expires_in=self.expires_in,
        )

    def download_bytes(self, object_key: str) -> bytes:
        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=_validate_object_key(object_key),
            )
            return response["Body"].read()
        except Exception as exc:  # boto3 exposes multiple transport-specific exception types.
            raise StorageError("Could not download the source image from object storage.") from exc

    def upload_bytes(self, object_key: str, data: bytes, content_type: str) -> None:
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=_validate_object_key(object_key),
                Body=data,
                ContentType=content_type,
            )
        except Exception as exc:  # boto3 exposes multiple transport-specific exception types.
            raise StorageError("Could not save the processed image to object storage.") from exc

    def create_download_url(self, object_key: str, public_api_url: str) -> str:
        del public_api_url
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": _validate_object_key(object_key)},
            ExpiresIn=self.expires_in,
            HttpMethod="GET",
        )


def create_object_storage(
    *,
    backend: str,
    mock_dir: Path,
    endpoint: str,
    bucket: str,
    region: str,
    access_key_id: str,
    secret_access_key: str,
    expires_in: int,
) -> ObjectStorage:
    if backend == "mock":
        return LocalMockObjectStorage(mock_dir, expires_in)
    if backend == "s3":
        return S3ObjectStorage(
            endpoint=endpoint,
            bucket=bucket,
            region=region,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            expires_in=expires_in,
        )
    raise StorageConfigurationError("STORAGE_BACKEND must be either 'mock' or 's3'.")

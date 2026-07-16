from __future__ import annotations

import io
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Protocol
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.errors import ModelNotInstalledError
from app.jobs import InMemoryJobStore
from app.services.background_remover import BiRefNetBackgroundRemover
from app.storage import (
    LocalMockObjectStorage,
    ObjectStorage,
    StorageError,
    StorageObjectNotFoundError,
    create_object_storage,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
READ_CHUNK_SIZE = 1024 * 1024


class BackgroundRemover(Protocol):
    is_installed: bool
    is_loaded: bool

    def remove(self, image: Image.Image) -> Image.Image: ...


class PresignUploadRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(alias="contentType")


class BackgroundRemovalJobRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    object_key: str = Field(alias="objectKey", min_length=1, max_length=512)


@lru_cache(maxsize=1)
def get_background_remover() -> BiRefNetBackgroundRemover:
    return BiRefNetBackgroundRemover(settings.model_dir)


@lru_cache(maxsize=1)
def get_object_storage() -> ObjectStorage:
    try:
        return create_object_storage(
            backend=settings.storage_backend,
            mock_dir=settings.storage_mock_dir,
            endpoint=settings.s3_endpoint,
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            expires_in=settings.presign_expires_seconds,
        )
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Хранилище недоступно: {exc}",
        ) from exc


@lru_cache(maxsize=1)
def get_job_store() -> InMemoryJobStore:
    return InMemoryJobStore()


app = FastAPI(
    title=settings.app_name,
    version="1.1.0",
    description="Локальное и production-удаление фона с помощью BiRefNet.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)


def ensure_allowed_content_type(content_type: str) -> None:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Поддерживаются только JPG, PNG и WebP.",
        )


def ensure_allowed_size(data: bytes) -> None:
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Файл слишком большой. Максимум: {settings.max_upload_size_mb} МБ.",
        )


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name[:120] or "upload"


async def read_upload(file: UploadFile) -> bytes:
    content_length = file.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.max_upload_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"Файл слишком большой. Максимум: {settings.max_upload_size_mb} МБ.",
                )
        except ValueError:
            pass

    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(READ_CHUNK_SIZE):
        total += len(chunk)
        if total > settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Файл слишком большой. Максимум: {settings.max_upload_size_mb} МБ.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def decode_image(data: bytes) -> Image.Image:
    try:
        source = Image.open(io.BytesIO(data))
        detected_format = source.format
        source.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Не удалось прочитать изображение. Выберите корректный JPG, PNG или WebP.",
        ) from exc

    if detected_format not in ALLOWED_IMAGE_FORMATS:
        source.close()
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Поддерживаются только JPG, PNG и WebP.",
        )

    width, height = source.size
    if width <= 0 or height <= 0 or width * height > settings.max_image_pixels:
        source.close()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Слишком большое разрешение. Максимум: {settings.max_image_pixels:,} пикселей.",
        )

    transposed = ImageOps.exif_transpose(source)
    if transposed is not source:
        source.close()
    return transposed


async def remove_background_from_bytes(data: bytes, remover: BackgroundRemover) -> bytes:
    image = decode_image(data)
    try:
        try:
            result = await run_in_threadpool(remover.remove, image)
        except ModelNotInstalledError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except Exception as exc:
            logger.exception("Background removal failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось удалить фон. Попробуйте другое изображение.",
            ) from exc
    finally:
        image.close()

    output = io.BytesIO()
    try:
        result.save(output, format="PNG", optimize=True)
        return output.getvalue()
    finally:
        result.close()


@app.get("/api/health")
def health(
    remover: Annotated[BackgroundRemover, Depends(get_background_remover)],
) -> dict[str, object]:
    return {
        "status": "ok",
        "modelInstalled": remover.is_installed,
        "modelLoaded": remover.is_loaded,
    }


@app.get("/api/config")
def public_config() -> dict[str, object]:
    return {
        "maxFileSizeBytes": settings.max_upload_bytes,
        "acceptedFormats": ["image/jpeg", "image/png", "image/webp"],
        "storageBackend": settings.storage_backend,
    }


@app.post("/api/remove-background", response_class=Response)
async def remove_background(
    file: Annotated[UploadFile, File(...)],
    remover: Annotated[BackgroundRemover, Depends(get_background_remover)],
) -> Response:
    ensure_allowed_content_type(file.content_type or "")
    try:
        data = await read_upload(file)
    finally:
        await file.close()

    if not data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Файл пуст.")

    payload = await remove_background_from_bytes(data, remover)
    return Response(
        content=payload,
        media_type="image/png",
        headers={
            "Content-Disposition": 'attachment; filename="background-removed.png"',
            "Cache-Control": "no-store",
        },
    )


@app.post("/api/uploads/presign")
def presign_upload(
    body: PresignUploadRequest,
    request: Request,
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> dict[str, object]:
    ensure_allowed_content_type(body.content_type)
    upload_id = uuid4().hex
    object_key = f"uploads/{upload_id}/{safe_filename(body.filename)}"
    presigned = storage.create_upload_url(object_key, body.content_type, str(request.base_url))
    return {
        "objectKey": presigned.object_key,
        "uploadUrl": presigned.url,
        "uploadHeaders": presigned.headers,
        "expiresIn": presigned.expires_in,
    }


@app.put("/api/storage/mock/{object_key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def mock_storage_upload(
    object_key: str,
    request: Request,
    token: str,
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> Response:
    if not isinstance(storage, LocalMockObjectStorage):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mock storage is disabled.",
        )
    content_type = request.headers.get("content-type", "")
    ensure_allowed_content_type(content_type)
    data = await request.body()
    ensure_allowed_size(data)
    try:
        storage.receive_upload(object_key, token, data, content_type)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/storage/mock/{object_key:path}")
def mock_storage_download(
    object_key: str,
    token: str,
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> Response:
    if not isinstance(storage, LocalMockObjectStorage):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mock storage is disabled.",
        )
    try:
        data, content_type = storage.read_download(object_key, token)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return Response(content=data, media_type=content_type, headers={"Cache-Control": "no-store"})


@app.post("/api/remove-background/jobs")
async def create_background_removal_job(
    body: BackgroundRemovalJobRequest,
    request: Request,
    remover: Annotated[BackgroundRemover, Depends(get_background_remover)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
    job_store: Annotated[InMemoryJobStore, Depends(get_job_store)],
) -> dict[str, str | None]:
    if not body.object_key.startswith("uploads/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Можно обрабатывать только объект, созданный через /api/uploads/presign.",
        )

    job = job_store.create(body.object_key)
    try:
        data = storage.download_bytes(body.object_key)
        ensure_allowed_size(data)
        payload = await remove_background_from_bytes(data, remover)
        result_key = f"results/{job.id}/background-removed.png"
        storage.upload_bytes(result_key, payload, "image/png")
        result_url = storage.create_download_url(result_key, str(request.base_url))
        job_store.complete(job, result_key, result_url)
    except HTTPException as exc:
        job_store.fail(job, str(exc.detail))
        raise
    except StorageObjectNotFoundError as exc:
        job_store.fail(job, str(exc))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StorageError as exc:
        job_store.fail(job, str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка object storage: {exc}",
        ) from exc

    return job.to_public_dict()


@app.get("/api/remove-background/jobs/{job_id}")
def get_background_removal_job(
    job_id: str,
    job_store: Annotated[InMemoryJobStore, Depends(get_job_store)],
) -> dict[str, str | None]:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задание не найдено.")
    return job.to_public_dict()

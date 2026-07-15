from __future__ import annotations

import io
import logging
from functools import lru_cache
from typing import Annotated, Protocol

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import settings
from app.errors import ModelNotInstalledError
from app.services.background_remover import BiRefNetBackgroundRemover

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
READ_CHUNK_SIZE = 1024 * 1024


class BackgroundRemover(Protocol):
    is_installed: bool
    is_loaded: bool

    def remove(self, image: Image.Image) -> Image.Image: ...


@lru_cache(maxsize=1)
def get_background_remover() -> BiRefNetBackgroundRemover:
    return BiRefNetBackgroundRemover(settings.model_dir)


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Локальное удаление фона с помощью BiRefNet.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


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
    }


@app.post("/api/remove-background", response_class=Response)
async def remove_background(
    file: Annotated[UploadFile, File(...)],
    remover: Annotated[BackgroundRemover, Depends(get_background_remover)],
) -> Response:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Поддерживаются только JPG, PNG и WebP.",
        )

    try:
        data = await read_upload(file)
    finally:
        await file.close()

    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Файл пуст.",
        )

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
        payload = output.getvalue()
    finally:
        result.close()

    return Response(
        content=payload,
        media_type="image/png",
        headers={
            "Content-Disposition": 'attachment; filename="background-removed.png"',
            "Cache-Control": "no-store",
        },
    )

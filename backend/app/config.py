from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


def _csv_env(name: str, default: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, default).split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    app_name: str = "FON API"
    model_id: str = os.getenv("BIREFNET_MODEL_ID", "ZhengPeng7/BiRefNet")
    model_dir: Path = Path(
        os.getenv("BIREFNET_MODEL_DIR", str(PROJECT_DIR / "models" / "BiRefNet"))
    ).resolve()
    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "15"))
    max_image_pixels: int = int(os.getenv("MAX_IMAGE_PIXELS", "40000000"))
    allowed_origins: tuple[str, ...] = _csv_env(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    )
    storage_backend: str = os.getenv("STORAGE_BACKEND", "mock").lower()
    storage_mock_dir: Path = Path(
        os.getenv("STORAGE_MOCK_DIR", str(BACKEND_DIR / ".storage"))
    ).resolve()
    s3_endpoint: str = os.getenv("S3_ENDPOINT", "")
    s3_bucket: str = os.getenv("S3_BUCKET", "")
    s3_region: str = os.getenv("S3_REGION", "ru-central1")
    s3_access_key_id: str = os.getenv("S3_ACCESS_KEY_ID", "")
    s3_secret_access_key: str = os.getenv("S3_SECRET_ACCESS_KEY", "")
    presign_expires_seconds: int = int(os.getenv("PRESIGN_EXPIRES_SECONDS", "900"))

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()

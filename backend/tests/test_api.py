from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image


def test_health_reports_model_state(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "modelInstalled": True,
        "modelLoaded": True,
    }


def test_public_config(client: TestClient) -> None:
    response = client.get("/api/config")

    assert response.status_code == 200
    body = response.json()
    assert body["maxFileSizeBytes"] > 0
    assert "image/webp" in body["acceptedFormats"]


def test_remove_background_returns_transparent_png(
    client: TestClient, png_bytes: bytes
) -> None:
    response = client.post(
        "/api/remove-background",
        files={"file": ("photo.png", png_bytes, "image/png")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    result = Image.open(io.BytesIO(response.content))
    assert result.mode == "RGBA"
    assert result.size == (32, 24)
    assert result.getchannel("A").getextrema() == (128, 128)


def test_rejects_unknown_content_type(client: TestClient) -> None:
    response = client.post(
        "/api/remove-background",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 415
    assert "JPG" in response.json()["detail"]


def test_rejects_invalid_image(client: TestClient) -> None:
    response = client.post(
        "/api/remove-background",
        files={"file": ("broken.png", b"not an image", "image/png")},
    )

    assert response.status_code == 422
    assert "прочитать" in response.json()["detail"]


def test_rejects_empty_file(client: TestClient) -> None:
    response = client.post(
        "/api/remove-background",
        files={"file": ("empty.webp", b"", "image/webp")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Файл пуст."

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app, get_background_remover


class FakeBackgroundRemover:
    is_installed = True
    is_loaded = True

    def remove(self, image: Image.Image) -> Image.Image:
        result = image.convert("RGBA")
        result.putalpha(Image.new("L", result.size, 128))
        return result


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_background_remover] = lambda: FakeBackgroundRemover()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (32, 24), "#ff5d3a").save(output, format="PNG")
    return output.getvalue()

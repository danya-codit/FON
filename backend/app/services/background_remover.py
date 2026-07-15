from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

from app.errors import ModelNotInstalledError

logger = logging.getLogger(__name__)


class BiRefNetBackgroundRemover:
    """Loads BiRefNet from disk once and performs local foreground segmentation."""

    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir
        self._model: Any | None = None
        self._device: Any | None = None
        self._dtype: Any | None = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    @property
    def is_installed(self) -> bool:
        return (self.model_dir / "config.json").is_file()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _load(self) -> None:
        if self._model is not None:
            return

        with self._load_lock:
            if self._model is not None:
                return
            if not self.is_installed:
                raise ModelNotInstalledError(
                    "BiRefNet не найден. Выполните: python scripts/download_model.py"
                )

            try:
                import torch
                from transformers import AutoModelForImageSegmentation
            except ImportError as exc:  # pragma: no cover - depends on local environment
                raise ModelNotInstalledError(
                    "Не установлены зависимости модели. Выполните: pip install -r requirements.txt"
                ) from exc

            if torch.cuda.is_available():
                device = torch.device("cuda")
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                device = torch.device("mps")
            else:
                device = torch.device("cpu")

            logger.info("Loading BiRefNet from %s on %s", self.model_dir, device)
            model = AutoModelForImageSegmentation.from_pretrained(
                str(self.model_dir),
                trust_remote_code=True,
                local_files_only=True,
            )
            model.to(device)
            if device.type == "cpu":
                # BiRefNet weights are stored as FP16; CPU convolutions expect FP32 input/weights.
                model.float()
            model.eval()
            self._device = device
            self._dtype = next(model.parameters()).dtype
            self._model = model
            logger.info("BiRefNet is ready")

    def remove(self, image: Image.Image) -> Image.Image:
        self._load()

        import torch
        from torchvision import transforms
        from torchvision.transforms.functional import InterpolationMode

        original = image.convert("RGBA")
        rgb_image = original.convert("RGB")
        preprocess = transforms.Compose(
            [
                transforms.Resize((1024, 1024), interpolation=InterpolationMode.BILINEAR),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=(0.485, 0.456, 0.406),
                    std=(0.229, 0.224, 0.225),
                ),
            ]
        )
        batch = (
            preprocess(rgb_image)
            .unsqueeze(0)
            .to(device=self._device, dtype=self._dtype)
        )

        with self._inference_lock, torch.inference_mode():
            prediction = self._model(batch)
            if hasattr(prediction, "logits"):
                prediction = prediction.logits
            elif isinstance(prediction, (list, tuple)):
                prediction = prediction[-1]
            mask_tensor = prediction.sigmoid().detach().float().cpu()[0].squeeze()

        mask = Image.fromarray((mask_tensor.numpy() * 255).clip(0, 255).astype("uint8"))
        mask = mask.resize(original.size, Image.Resampling.LANCZOS)

        # Preserve transparency that may already exist in a source PNG/WebP.
        source_alpha = original.getchannel("A")
        combined_alpha = ImageChops.multiply(source_alpha, mask)
        original.putalpha(combined_alpha)
        return original

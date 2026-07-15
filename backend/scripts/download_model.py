from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download BiRefNet to the local models directory."
    )
    parser.add_argument("--force", action="store_true", help="Download files again.")
    args = parser.parse_args()

    settings.model_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {settings.model_id} to {settings.model_dir}")
    snapshot_download(
        repo_id=settings.model_id,
        local_dir=settings.model_dir,
        force_download=args.force,
    )

    if not (settings.model_dir / "config.json").is_file():
        raise RuntimeError("Download finished, but config.json was not found.")

    print("BiRefNet is ready for offline use.")
    print("The API loads only local files and does not contact Hugging Face during processing.")


if __name__ == "__main__":
    # Keep Hugging Face progress output readable in Windows terminals.
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    main()

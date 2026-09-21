"""BytePlus ModelArk SeeDream image generation client using arkruntime."""

import os
import time
import logging
import base64
import mimetypes
from typing import Optional, List, Dict, Any, Callable
import requests
from arkruntime import Ark

logger = logging.getLogger("multimedia_seedream")

DEFAULT_IMAGE_MODEL = "dola-seedream-5-0-pro-260628"
DEFAULT_BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"


class SeeDreamClient:
    """Client for generating images via BytePlus ModelArk SeeDream."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        model_id: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("ARK_API_KEY")
        if not self.api_key:
            raise ValueError(
                "BytePlus ARK_API_KEY is required for SeeDream image generation. "
                "Please configure in Settings or .env."
            )
        self.base_url = os.getenv("ARK_BASE_URL", base_url)
        self.model_id = model_id or os.getenv("ARK_IMAGE_MODEL") or DEFAULT_IMAGE_MODEL
        self.client = Ark(base_url=self.base_url, api_key=self.api_key)

    def _prepare_image_reference(self, image_source: str) -> str:
        """Converts a local file path or returns a remote URL / data URI for multimodal input."""
        if not image_source:
            return image_source
        if image_source.startswith("http://") or image_source.startswith("https://") or image_source.startswith("data:"):
            return image_source

        target_path = None
        if os.path.exists(image_source) and os.path.isfile(image_source):
            target_path = image_source
        else:
            cleaned = image_source.lstrip("/")
            if os.path.exists(cleaned) and os.path.isfile(cleaned):
                target_path = cleaned
            else:
                proj_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                candidates = [
                    os.path.join(proj_root, cleaned),
                    os.path.join(proj_root, "uploads", "reference_assets", os.path.basename(image_source)),
                    os.path.join("uploads", "reference_assets", os.path.basename(image_source))
                ]
                for c in candidates:
                    if os.path.exists(c) and os.path.isfile(c):
                        target_path = c
                        break

        if target_path and os.path.exists(target_path):
            mime_type, _ = mimetypes.guess_type(target_path)
            mime_type = mime_type or "image/jpeg"
            with open(target_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            logger.info(f"Prepared multimodal reference image from {target_path} ({len(encoded)} base64 chars).")
            return f"data:{mime_type};base64,{encoded}"

        return image_source

    def generate_image(
        self,
        prompt: str,
        output_path: str,
        reference_assets: Optional[List[Dict[str, Any]]] = None,
        ratio: str = "16:9",
        resolution: str = "2K",
        watermark: bool = False,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> str:
        """Generates an image via SeeDream and saves it to output_path."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        if status_callback:
            status_callback("preparing", {"message": "Preparing image prompt & references...", "elapsed": 0})

        clean_prompt = f"{prompt.strip()} --no watermark, text, logo, subtitles, ui, timestamps"

        # Prepare reference images if any
        images_input: List[str] = []
        if reference_assets:
            for asset in reference_assets:
                asset_path = asset.get("local_path") or asset.get("url") or asset.get("filename")
                if not asset_path:
                    continue
                prepared = self._prepare_image_reference(asset_path)
                if prepared:
                    images_input.append(prepared)

        if status_callback:
            status_callback("submitting", {"message": f"Submitting task to {self.model_id}...", "elapsed": 1})

        size_map = {
            "16:9": "1920x1080" if "4k" in str(resolution).lower() or "2k" in str(resolution).lower() else "1280x720",
            "9:16": "1080x1920",
            "1:1": "1024x1024",
            "4:3": "1024x768",
            "3:4": "768x1024",
            "21:9": "2560x1080"
        }
        target_size = size_map.get(ratio, "1920x1080")

        gen_kwargs: Dict[str, Any] = {
            "model": self.model_id,
            "prompt": clean_prompt,
            "watermark": watermark,
        }
        if images_input:
            gen_kwargs["image"] = images_input if len(images_input) > 1 else images_input[0]
        if target_size:
            gen_kwargs["size"] = target_size

        logger.info(f"Submitting SeeDream request (model={self.model_id}, images={len(images_input)})...")

        resp = self.client.images.generate(**gen_kwargs)

        if not getattr(resp, "data", None) or len(resp.data) == 0:
            error_msg = getattr(resp, "error", None) or "No image data returned from ModelArk"
            raise RuntimeError(f"SeeDream image generation failed: {error_msg}")

        item = resp.data[0]
        if status_callback:
            status_callback("downloading", {"message": "Saving rendered image...", "elapsed": 2})

        if getattr(item, "url", None):
            self._download_file(item.url, output_path)
        elif getattr(item, "b64_json", None):
            img_bytes = base64.b64decode(item.b64_json)
            with open(output_path, "wb") as f:
                f.write(img_bytes)
        else:
            raise RuntimeError(f"Unexpected image item payload: {item}")

        logger.info(f"SeeDream image saved successfully to {output_path}")
        return output_path

    def _download_file(self, url: str, destination: str):
        """Streams and saves remote image URL to disk."""
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(destination, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)


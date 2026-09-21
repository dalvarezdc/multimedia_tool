"""xAI Grok Imagine Video Generation Client.

Handles task submission to the Grok Imagine Video API (api.x.ai),
multimodal character consistency, status polling, and asset downloading.
"""

import os
import time
import base64
import logging
import mimetypes
from typing import Optional, Dict, Any, Callable, List
import requests

logger = logging.getLogger(__name__)

class GrokVideoClient:
    """Client wrapper for xAI's Grok Imagine Video generation models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.x.ai/v1",
        model_id: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("XAI_API_KEY must be provided or set in environment variables.")

        self.base_url = os.getenv("XAI_BASE_URL", base_url).rstrip("/")
        self.model_id = model_id or os.getenv("XAI_VIDEO_MODEL") or "grok-imagine-video-1.5"

    def _prepare_image_reference(self, image_source: str) -> str:
        """Converts local file path to base64 data URI or returns remote URL."""
        if image_source.startswith("http://") or image_source.startswith("https://"):
            return image_source

        if os.path.exists(image_source):
            mime_type, _ = mimetypes.guess_type(image_source)
            mime_type = mime_type or "image/png"
            with open(image_source, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            return f"data:{mime_type};base64,{encoded}"

        return image_source

    def generate_video(
        self,
        prompt: str,
        output_path: str,
        character_reference_image: Optional[str] = None,
        watermark: bool = False,
        duration: int = 5,
        ratio: str = "16:9",
        poll_interval: int = 4,
        timeout_seconds: int = 300,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> str:
        """Submits video generation job to xAI Grok Imagine, polls for completion, and downloads MP4.

        Args:
            prompt: Text description of the desired cutscene.
            output_path: Local path where the MP4 video will be written.
            character_reference_image: Optional image URL or local path for character consistency.
            watermark: Unused / False (xAI video generations via API are watermark-free).
            duration: Video duration in seconds (1 to 15).
            ratio: Aspect ratio (e.g. '16:9').
            poll_interval: Polling frequency in seconds.
            timeout_seconds: Maximum wait timeout before aborting.
            status_callback: Optional progress callback receiving stage and metadata dict.

        Returns:
            The path to the downloaded MP4 file.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        if status_callback:
            status_callback("preparing", {"message": "Preparing prompt and parameters...", "elapsed": 0})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # xAI payload structure
        payload: Dict[str, Any] = {
            "model": self.model_id,
            "prompt": prompt.strip(),
            "duration": min(max(duration, 1), 15),
            "aspect_ratio": ratio
        }

        if character_reference_image:
            image_ref = self._prepare_image_reference(character_reference_image)
            payload["image_url"] = image_ref
            logger.info("Injected character reference image into xAI Grok payload.")

        # 1. Submit Generation Job
        url = f"{self.base_url}/videos/generations"
        logger.info(f"Submitting Grok Imagine video job to {url} (model={self.model_id})...")
        if status_callback:
            status_callback("submitting", {"message": f"Submitting job to {self.model_id}...", "elapsed": 0})

        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if not resp.ok:
            raise RuntimeError(f"xAI API error ({resp.status_code}): {resp.text}")

        res_data = resp.json()
        request_id = res_data.get("request_id") or res_data.get("id")
        if not request_id:
            raise RuntimeError(f"xAI API did not return request_id: {res_data}")

        logger.info(f"xAI Grok job dispatched. Request ID: {request_id}. Polling...")
        if status_callback:
            status_callback("queued", {"request_id": request_id, "message": "Queued in xAI processing pool", "elapsed": 1})

        # 2. Status Polling Loop
        poll_url = f"{self.base_url}/videos/{request_id}"
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            poll_resp = requests.get(poll_url, headers=headers, timeout=30)
            if not poll_resp.ok:
                logger.warning(f"Polling warning ({poll_resp.status_code}): {poll_resp.text}")
                time.sleep(poll_interval)
                continue

            status_data = poll_resp.json()
            status = status_data.get("status", "").lower()
            elapsed = int(time.time() - start_time)

            if status in ("done", "succeeded", "completed"):
                logger.info("Grok video generation succeeded! Downloading MP4...")
                if status_callback:
                    status_callback("downloading", {"request_id": request_id, "elapsed": elapsed, "message": f"Downloading video stream ({elapsed}s)..."})

                video_url = status_data.get("video_url") or status_data.get("url")
                if not video_url and "result" in status_data:
                    video_url = status_data["result"].get("video_url")

                if not video_url:
                    raise RuntimeError(f"Completed job missing video_url: {status_data}")

                self._download_file(video_url, output_path)
                logger.info(f"Video saved to {output_path}")

                if status_callback:
                    status_callback("auditing", {"request_id": request_id, "elapsed": int(time.time() - start_time), "message": "Finalizing video..."})

                return output_path

            elif status in ("failed", "error", "cancelled"):
                error_msg = status_data.get("error", "Unknown error")
                raise RuntimeError(f"Grok video generation failed: {error_msg}")

            else:
                if status_callback:
                    status_callback("rendering", {
                        "request_id": request_id,
                        "upstream_status": status,
                        "elapsed": elapsed,
                        "message": f"Sampling video frames ({elapsed}s)"
                    })

            time.sleep(poll_interval)

        raise TimeoutError(f"Grok video generation {request_id} timed out after {timeout_seconds} seconds.")

    def _download_file(self, url: str, destination: str):
        """Streams remote video file to local disk."""
        with requests.get(url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(destination, "wb") as f:
                for chunk in resp.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)


class GrokImageClient:
    """Client for xAI Grok Imagine image generation and editing."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.x.ai/v1",
        model_id: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("XAI_API_KEY must be provided or set in environment variables.")
        self.base_url = os.getenv("XAI_BASE_URL", base_url).rstrip("/")
        self.model_id = model_id or os.getenv("XAI_IMAGE_MODEL") or "grok-imagine-image-2.0"

    def _prepare_image_reference(self, image_source: str) -> str:
        if not image_source:
            return image_source
        if image_source.startswith("http://") or image_source.startswith("https://") or image_source.startswith("data:"):
            return image_source
        if os.path.exists(image_source) and os.path.isfile(image_source):
            mime_type, _ = mimetypes.guess_type(image_source)
            mime_type = mime_type or "image/png"
            with open(image_source, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            return f"data:{mime_type};base64,{encoded}"
        return image_source

    def _map_resolution(self, resolution: str) -> str:
        r = (resolution or "2K").lower()
        if any(k in r for k in ("4k", "2k", "1080")):
            return "2k"
        return "1k"

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
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        if status_callback:
            status_callback("preparing", {"message": "Preparing Grok Imagine image request...", "elapsed": 0})

        images_input: List[str] = []
        if reference_assets:
            for asset in reference_assets:
                asset_path = asset.get("local_path") or asset.get("url") or asset.get("filename")
                if not asset_path:
                    continue
                prepared = self._prepare_image_reference(asset_path)
                if prepared:
                    images_input.append(prepared)
                if len(images_input) >= 5:
                    break

        payload: Dict[str, Any] = {
            "model": self.model_id,
            "prompt": prompt.strip(),
            "n": 1,
            "aspect_ratio": ratio,
            "resolution": self._map_resolution(resolution),
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if images_input:
            endpoint = f"{self.base_url}/images/edits"
            refs = [{"url": u, "type": "image_url"} for u in images_input]
            payload["image"] = refs[0] if len(refs) == 1 else refs
        else:
            endpoint = f"{self.base_url}/images/generations"

        if status_callback:
            status_callback("submitting", {"message": f"Submitting to {self.model_id}...", "elapsed": 1})

        logger.info(f"Submitting Grok image request to {endpoint} (model={self.model_id}, refs={len(images_input)})")
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=120)
        if not resp.ok:
            raise RuntimeError(f"xAI image API error ({resp.status_code}): {resp.text}")
        data = resp.json()
        items = data.get("data") or []
        if not items:
            raise RuntimeError(f"Grok image generation returned no data: {data}")
        item = items[0]
        url = item.get("url")
        b64 = item.get("b64_json")
        if status_callback:
            status_callback("downloading", {"message": "Saving rendered image...", "elapsed": 2})
        if url:
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(output_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
        elif b64:
            with open(output_path, "wb") as f:
                f.write(base64.b64decode(b64))
        else:
            raise RuntimeError(f"Unexpected Grok image payload: {item}")
        logger.info(f"Grok image saved to {output_path}")
        return output_path

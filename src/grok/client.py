"""xAI Grok Imagine Video Generation Client.

Handles task submission to the Grok Imagine Video API (api.x.ai),
multimodal character consistency, status polling, and asset downloading.
"""

import os
import time
import base64
import logging
import mimetypes
from typing import Optional, Dict, Any
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
        timeout_seconds: int = 300
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

        Returns:
            The path to the downloaded MP4 file.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

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
        
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if not resp.ok:
            raise RuntimeError(f"xAI API error ({resp.status_code}): {resp.text}")

        res_data = resp.json()
        request_id = res_data.get("request_id") or res_data.get("id")
        if not request_id:
            raise RuntimeError(f"xAI API did not return request_id: {res_data}")

        logger.info(f"xAI Grok job dispatched. Request ID: {request_id}. Polling...")

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

            if status in ("done", "succeeded", "completed"):
                logger.info("Grok video generation succeeded! Downloading MP4...")
                video_url = status_data.get("video_url") or status_data.get("url")
                if not video_url and "result" in status_data:
                    video_url = status_data["result"].get("video_url")

                if not video_url:
                    raise RuntimeError(f"Completed job missing video_url: {status_data}")

                self._download_file(video_url, output_path)
                logger.info(f"Video saved to {output_path}")
                return output_path

            elif status in ("failed", "error", "cancelled"):
                error_msg = status_data.get("error", "Unknown error")
                raise RuntimeError(f"Grok video generation failed: {error_msg}")

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

"""BytePlus ModelArk Seedance Video Generation Client.

Handles task submission, watermark-free configuration, asynchronous status polling,
and asset downloading.
"""

import os
import time
import logging
from typing import Optional, Dict, Any
import requests
from arkruntime import Ark

logger = logging.getLogger(__name__)

class SeedanceClient:
    """Client wrapper for ByteDance's Seedance video generation model on BytePlus ModelArk."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://ark.ap-southeast.bytepluses.com/api/v3",
        model_id: str = "dreamina-seedance-2-0-260128"
    ):
        self.api_key = api_key or os.getenv("ARK_API_KEY")
        if not self.api_key:
            raise ValueError("ARK_API_KEY must be provided or set in environment variables.")
        
        self.base_url = os.getenv("ARK_BASE_URL", base_url)
        self.model_id = os.getenv("ARK_SEEDANCE_MODEL", model_id)
        
        self.client = Ark(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    def generate_video(
        self,
        prompt: str,
        output_path: str,
        watermark: bool = False,
        duration: int = 5,
        ratio: str = "16:9",
        poll_interval: int = 3,
        timeout_seconds: int = 300
    ) -> str:
        """Submits a video generation task, polls for completion, and saves the resulting MP4.

        Args:
            prompt: Text prompt describing the desired video scene.
            output_path: Local file path where the completed video will be saved.
            watermark: If False, disables the default ByteDance watermark on the video.
            duration: Video length in seconds (default 5).
            ratio: Aspect ratio (e.g., '16:9').
            poll_interval: Seconds between status poll requests.
            timeout_seconds: Maximum time to wait before timing out.

        Returns:
            The path to the downloaded MP4 file.
        """
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Enforce negative prompt constraints to guarantee no watermarks or text overlays
        clean_prompt = f"{prompt.strip()} --no watermark, text, logo, subtitles, ui, timestamps"

        logger.info(f"Submitting Seedance task (model={self.model_id}, watermark={watermark})...")
        task_response = self.client.content_generation.tasks.create(
            model=self.model_id,
            content=[
                {
                    "type": "text",
                    "text": clean_prompt
                }
            ],
            watermark=watermark,  # Explicitly toggles off watermark
            duration=duration,
            ratio=ratio,
        )

        task_id = getattr(task_response, "id", None) or task_response.get("id")
        if not task_id:
            raise RuntimeError(f"Failed to obtain task_id from BytePlus response: {task_response}")

        logger.info(f"Task submitted successfully. Task ID: {task_id}")

        # Polling loop
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            task_status = self.client.content_generation.tasks.get(task_id=task_id)
            status = getattr(task_status, "status", None) or task_status.get("status")

            if status == "succeeded":
                logger.info(f"Task {task_id} succeeded! Downloading video...")
                content = getattr(task_status, "content", None) or task_status.get("content")
                video_url = getattr(content, "video_url", None) or content.get("video_url")
                
                if not video_url:
                    raise RuntimeError("Status is succeeded but no video_url found in payload.")

                self._download_file(video_url, output_path)
                logger.info(f"Video saved to {output_path}")
                return output_path

            elif status in ("failed", "cancelled"):
                error_msg = getattr(task_status, "error", None) or task_status.get("error", "Unknown error")
                raise RuntimeError(f"Seedance task {task_id} failed with status '{status}': {error_msg}")

            time.sleep(poll_interval)

        raise TimeoutError(f"Seedance task {task_id} timed out after {timeout_seconds} seconds.")

    def _download_file(self, url: str, destination: str):
        """Streams and saves remote video URL to disk."""
        with requests.get(url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(destination, "wb") as f:
                for chunk in resp.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)

"""BytePlus ModelArk Seedance Video Generation Client.

Handles task submission, multimodal character references, watermark-free configuration,
asynchronous status polling, and asset downloading.
"""

import os
import time
import base64
import logging
import mimetypes
from typing import Optional, Dict, Any, List, Callable
import requests
from arkruntime import Ark

logger = logging.getLogger(__name__)

class SeedanceClient:
    """Client wrapper for ByteDance / BytePlus Seedance Video Generation models via ModelArk."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://ark.ap-southeast.bytepluses.com/api/v3",
        model_id: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("ARK_API_KEY")
        if not self.api_key:
            raise ValueError("ARK_API_KEY must be provided or set in environment variables.")
        
        self.base_url = os.getenv("ARK_BASE_URL", base_url)
        self.model_id = model_id or os.getenv("ARK_SEEDANCE_MODEL") or "dreamina-seedance-2-5-260628"
        
        self.client = Ark(
            base_url=self.base_url,
            api_key=self.api_key,
        )

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
            mime_type = mime_type or ("video/mp4" if target_path.lower().endswith((".mp4", ".mov", ".webm")) else "image/jpeg")
            with open(target_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            logger.info(f"Prepared multimodal asset from {target_path} ({len(encoded)} base64 chars, mime={mime_type}).")
            return f"data:{mime_type};base64,{encoded}"
        
        return image_source

    def generate_video(
        self,
        prompt: str,
        output_path: str,
        character_reference_image: Optional[str] = None,
        generation_mode: str = "ref_to_video",
        first_frame_image: Optional[str] = None,
        last_frame_image: Optional[str] = None,
        ip_effect_name: Optional[str] = None,
        watermark: bool = False,
        duration: int = 5,
        ratio: str = "16:9",
        resolution: Optional[str] = None,
        generate_audio: Optional[bool] = None,
        draft_mode: bool = False,
        reference_assets: Optional[List[Dict[str, Any]]] = None,
        poll_interval: int = 3,
        timeout_seconds: int = 300,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> str:
        """Submits a video generation task, polls for completion, and saves the resulting MP4.

        Args:
            prompt: Text prompt describing the desired video scene.
            output_path: Local file path where the completed video will be saved.
            character_reference_image: Local path or URL to character reference image for identity consistency.
            generation_mode: 'ref_to_video' (default), 'first_last_frame', or 'ip_effects'.
            first_frame_image: Start keyframe image (used in 'first_last_frame' mode).
            last_frame_image: End keyframe image (optional, used in 'first_last_frame' mode).
            ip_effect_name: Stylized character effect or motion preset (used in 'ip_effects' mode).
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

        if status_callback:
            status_callback("preparing", {"message": "Preparing assets and prompt...", "elapsed": 0})

        mode = generation_mode.lower().replace("-", "_")

        # Base prompt with watermark nullification
        clean_prompt = f"{prompt.strip()} --no watermark, text, logo, subtitles, ui, timestamps"

        content_payload: List[Dict[str, Any]] = []

        # 1. Mode: First & Last Frame Keyframing
        if mode == "first_last_frame":
            if not first_frame_image and character_reference_image:
                first_frame_image = character_reference_image

            if first_frame_image:
                content_payload.append({
                    "type": "image_url",
                    "image_url": {"url": self._prepare_image_reference(first_frame_image)},
                    "role": "first_frame"
                })
            if last_frame_image:
                content_payload.append({
                    "type": "image_url",
                    "image_url": {"url": self._prepare_image_reference(last_frame_image)},
                    "role": "last_frame"
                })
            logger.info(f"Configured First/Last Frame generation mode (has_start={bool(first_frame_image)}, has_end={bool(last_frame_image)}).")

        # 2. Mode: IP Effects (Character Transformation / Preset Motion)
        elif mode == "ip_effects":
            effect = ip_effect_name or "stylized_character_transform"
            clean_prompt = f"[IP Effect: {effect}] {clean_prompt}"
            if character_reference_image:
                content_payload.append({
                    "type": "image_url",
                    "image_url": {"url": self._prepare_image_reference(character_reference_image)},
                    "role": "reference_image"
                })
            logger.info(f"Configured IP Effects mode with preset '{effect}'.")

        # 3. Mode: Ref-to-Video (Default Omni-Reference)
        else:
            if reference_assets:
                added_count = 0
                for asset in reference_assets:
                    asset_path = asset.get("local_path") or asset.get("url") or asset.get("filename")
                    if not asset_path:
                        continue
                    asset_type = asset.get("type", "image")
                    prepared_url = self._prepare_image_reference(asset_path)
                    role = "reference_video" if asset_type == "video" else "reference_image"
                    content_payload.append({
                        "type": "video_url" if asset_type == "video" else "image_url",
                        ("video_url" if asset_type == "video" else "image_url"): {"url": prepared_url},
                        "role": role
                    })
                    added_count += 1
                logger.info(f"Configured Ref-to-Video with {added_count} reference assets in multimodal content payload.")
            elif character_reference_image:
                content_payload.append({
                    "type": "image_url",
                    "image_url": {"url": self._prepare_image_reference(character_reference_image)},
                    "role": "reference_image"
                })
                logger.info("Configured Ref-to-Video mode with character reference image.")

        # Append text prompt
        content_payload.append({
            "type": "text",
            "text": clean_prompt
        })

        if status_callback:
            status_callback("submitting", {"message": f"Submitting task to {self.model_id}...", "elapsed": 0})

        logger.info(f"Submitting Seedance task (model={self.model_id}, watermark={watermark})...")
        create_kwargs: Dict[str, Any] = {
            "model": self.model_id,
            "content": content_payload,
            "watermark": watermark,
            "duration": duration,
            "ratio": ratio,
        }
        if resolution:
            create_kwargs["resolution"] = resolution
        if generate_audio is not None:
            create_kwargs["generate_audio"] = generate_audio
        if draft_mode:
            create_kwargs["draft"] = True
        task_response = self.client.content_generation.tasks.create(**create_kwargs)

        task_id = getattr(task_response, "id", None) or task_response.get("id")
        if not task_id:
            raise RuntimeError(f"Failed to obtain task_id from BytePlus response: {task_response}")

        logger.info(f"Task submitted successfully. Task ID: {task_id}")
        if status_callback:
            status_callback("queued", {"task_id": task_id, "message": "Queued in ModelArk GPU pool", "elapsed": 1})

        # Polling loop
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            task_status = self.client.content_generation.tasks.get(task_id=task_id)
            status = getattr(task_status, "status", None) or task_status.get("status")
            elapsed = int(time.time() - start_time)

            if status == "succeeded":
                logger.info(f"Task {task_id} succeeded! Downloading video...")
                if status_callback:
                    status_callback("downloading", {"task_id": task_id, "elapsed": elapsed, "message": f"Downloading video stream ({elapsed}s)..."})

                content = getattr(task_status, "content", None) or task_status.get("content")
                video_url = getattr(content, "video_url", None) or content.get("video_url")
                
                if not video_url:
                    raise RuntimeError("Status is succeeded but no video_url found in payload.")

                self._download_file(video_url, output_path)
                logger.info(f"Video saved to {output_path}")

                if status_callback:
                    status_callback("auditing", {"task_id": task_id, "elapsed": int(time.time() - start_time), "message": "Finalizing video..."})

                return output_path

            elif status in ("failed", "cancelled"):
                error_msg = getattr(task_status, "error", None) or task_status.get("error", "Unknown error")
                raise RuntimeError(f"Seedance task {task_id} failed with status '{status}': {error_msg}")

            else:
                st_label = "Rendering video frames" if status in ("running", "processing") else "Queued in GPU cluster"
                if status_callback:
                    status_callback("rendering" if status in ("running", "processing") else "queued", {
                        "task_id": task_id,
                        "upstream_status": status,
                        "elapsed": elapsed,
                        "message": f"{st_label} ({elapsed}s)"
                    })

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

"""Mureka Audio & Music Generation API Client.

Interfaces with the Mureka API (https://api.mureka.ai/v1) to generate songs,
soundtracks, instrumental music, lyrics, and song extensions.
"""

import os
import re
import time
import logging
from typing import Dict, Any, List, Optional, Callable
from urllib.parse import urlparse
import requests

logger = logging.getLogger("mureka_client")

DEFAULT_MUREKA_HOST = "api.mureka.ai"
DEFAULT_MUREKA_API_URL = f"https://{DEFAULT_MUREKA_HOST}/v1"
DEFAULT_AUDIO_MODEL = "mureka-9.5"
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class MurekaAPIError(RuntimeError):
    """Exception raised for Mureka API errors."""
    pass


def allowed_mureka_hosts() -> set:
    """Official host, plus operator-configured hosts from the process environment.

    The settings API cannot widen this set. MUREKA_ALLOWED_HOSTS is read only
    from the server environment.
    """
    hosts = {DEFAULT_MUREKA_HOST}
    extra = os.getenv("MUREKA_ALLOWED_HOSTS", "")
    for item in extra.split(","):
        host = item.strip().lower().rstrip(".")
        if host:
            hosts.add(host)
    return hosts


def resolve_mureka_base_url(base_url: Optional[str] = None) -> str:
    """Return https://<allowed-host>/v1 or raise ValueError.

    Rejects other schemes, credentials, ports, paths, and hosts so a caller
    cannot aim the bearer token at an internal address or their own server.
    """
    raw = (base_url if base_url is not None else os.getenv("MUREKA_API_URL", "")).strip()
    if not raw:
        raw = DEFAULT_MUREKA_API_URL
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.port not in (None, 443)
        or host not in allowed_mureka_hosts()
    ):
        raise ValueError(
            "Mureka API URL must be https://api.mureka.ai/v1 with no credentials or query."
        )
    path = (parsed.path or "").rstrip("/")
    if path not in ("", "/v1"):
        raise ValueError("Mureka API URL path must be /v1.")
    return f"https://{host}/v1"


def validate_mureka_task_id(task_id: str) -> str:
    if not _TASK_ID_RE.fullmatch(task_id or ""):
        raise ValueError("Invalid Mureka task id.")
    return task_id


class MurekaAudioClient:
    """Client for generating music and audio using the official Mureka API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_id: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("MUREKA_API_KEY")
        if not self.api_key:
            raise ValueError(
                "MUREKA_API_KEY must be provided via constructor or environment variable."
            )

        self.base_url = resolve_mureka_base_url(base_url)
        self.model_id = model_id or os.getenv("MUREKA_MODEL", DEFAULT_AUDIO_MODEL)
        self.default_model = self.model_id

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _post(self, endpoint: str, payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.info("Mureka POST %s", url)
        resp = requests.post(
            url,
            json=payload,
            headers=self._headers,
            timeout=timeout,
            allow_redirects=False,
        )
        if 300 <= resp.status_code < 400:
            logger.error("Mureka refused redirect %s from %s", resp.status_code, url)
            raise MurekaAPIError(f"Mureka API refused a redirect ({resp.status_code}).")
        if not resp.ok:
            logger.error("Mureka API error %s on %s", resp.status_code, url)
            raise MurekaAPIError(f"Mureka API error ({resp.status_code}).")
        return resp.json()

    def _get(self, endpoint: str, timeout: int = 30) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.info("Mureka GET %s", url)
        resp = requests.get(
            url,
            headers=self._headers,
            timeout=timeout,
            allow_redirects=False,
        )
        if 300 <= resp.status_code < 400:
            logger.error("Mureka refused redirect %s from %s", resp.status_code, url)
            raise MurekaAPIError(f"Mureka API refused a redirect ({resp.status_code}).")
        if not resp.ok:
            logger.error("Mureka API error %s on %s", resp.status_code, url)
            raise MurekaAPIError(f"Mureka API error ({resp.status_code}).")
        return resp.json()

    def easy_generate(
        self,
        prompt: str,
        styles: Optional[List[str]] = None,
        model: Optional[str] = None,
        n: int = 2,
        reference_id: Optional[str] = None,
        vocal_id: Optional[str] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Prompt to Song: generates a complete song with vocals from a text prompt and styles.

        POST /v1/song/easy-generate
        """
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "model": model or self.model_id or "auto",
            "n": max(1, min(3, int(n))),
            "stream": bool(stream)
        }
        if styles:
            payload["styles"] = styles
        if reference_id:
            payload["reference_id"] = reference_id
        if vocal_id:
            payload["vocal_id"] = vocal_id

        return self._post("/song/easy-generate", payload)

    def generate_soundtrack(
        self,
        prompt: Optional[str] = None,
        image_id: Optional[str] = None,
        video_id: Optional[str] = None,
        model: Optional[str] = None,
        n: int = 2,
        audio_start: Optional[int] = None,
        audio_end: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate Soundtrack: generates BGM tailored to a video or image.

        POST /v1/soundtrack/generate
        """
        payload: Dict[str, Any] = {
            "model": model or self.model_id or "auto",
            "n": max(1, min(3, int(n)))
        }
        if prompt:
            payload["prompt"] = prompt
        if image_id:
            payload["image_id"] = image_id
        if video_id:
            payload["video_id"] = video_id
        if audio_start is not None:
            payload["audio_start"] = audio_start
        if audio_end is not None:
            payload["audio_end"] = audio_end

        return self._post("/soundtrack/generate", payload)

    def generate_song(
        self,
        lyrics: str,
        prompt: Optional[str] = None,
        model: Optional[str] = None,
        gender: Optional[str] = None,
        n: int = 2,
        reference_id: Optional[str] = None,
        vocal_id: Optional[str] = None,
        melody_id: Optional[str] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Lyrics to Song: generates a song composed according to user-supplied lyrics.

        POST /v1/song/generate
        """
        payload: Dict[str, Any] = {
            "lyrics": lyrics,
            "model": model or self.model_id or "auto",
            "n": max(1, min(3, int(n))),
            "stream": bool(stream)
        }
        if prompt:
            payload["prompt"] = prompt
        if gender in ("female", "male"):
            payload["gender"] = gender
        if reference_id:
            payload["reference_id"] = reference_id
        if vocal_id:
            payload["vocal_id"] = vocal_id
        if melody_id:
            payload["melody_id"] = melody_id

        return self._post("/song/generate", payload)

    def extend_song(
        self,
        lyrics: str,
        extend_at: int,
        song_id: Optional[str] = None,
        upload_audio_id: Optional[str] = None,
        extend_type: str = "tail",
        model: str = "mureka-8"
    ) -> Dict[str, Any]:
        """Extend Song: extends a previously generated or uploaded song forwards (tail) or backwards (head).

        POST /v1/song/extend
        """
        payload: Dict[str, Any] = {
            "lyrics": lyrics,
            "extend_at": int(extend_at),
            "model": model,
            "extend_type": extend_type
        }
        if song_id:
            payload["song_id"] = song_id
        elif upload_audio_id:
            payload["upload_audio_id"] = upload_audio_id
        else:
            raise ValueError("Either song_id or upload_audio_id must be provided to extend a song.")

        return self._post("/song/extend", payload)

    def generate_instrumental(
        self,
        prompt: Optional[str] = None,
        instrumental_id: Optional[str] = None,
        model: Optional[str] = None,
        n: int = 2,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Generate Instrumental: generates instrumental music without vocals.

        POST /v1/instrumental/generate
        """
        payload: Dict[str, Any] = {
            "model": model or self.model_id or "auto",
            "n": max(1, min(3, int(n))),
            "stream": bool(stream)
        }
        if prompt:
            payload["prompt"] = prompt
        if instrumental_id:
            payload["instrumental_id"] = instrumental_id

        return self._post("/instrumental/generate", payload)

    def generate_lyrics(self, prompt: str) -> Dict[str, Any]:
        """Generate Lyrics: creates song lyrics from a descriptive theme or story prompt.

        POST /v1/lyrics/generate
        """
        payload = {"prompt": prompt}
        res = self._post("/lyrics/generate", payload)
        if "lyrics" not in res and "text" in res:
            res["lyrics"] = res["text"]
        return res

    def query_task(self, task_id: str) -> Dict[str, Any]:
        """Query task status for song or soundtrack generation.

        GET /v1/song/query/{task_id}
        """
        return self._get(f"/song/query/{validate_mureka_task_id(task_id)}")

    def query_instrumental_task(self, task_id: str) -> Dict[str, Any]:
        """Query instrumental generation task status.

        GET /v1/instrumental/query/{task_id}
        """
        return self._get(f"/instrumental/query/{validate_mureka_task_id(task_id)}")

    def poll_song(
        self,
        task_id: str,
        timeout_seconds: int = 300,
        poll_interval: float = 2.0,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """Polls a song task until terminal status (succeeded, failed, cancelled, timeouted)."""
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            data = self.query_task(task_id)
            status = data.get("status")

            if status_callback:
                status_callback(status, data)

            if status == "succeeded":
                return data
            if status in ("failed", "cancelled", "timeouted"):
                reason = data.get("failed_reason") or status
                raise MurekaAPIError(f"Mureka audio task {task_id} failed: {reason}")

            time.sleep(poll_interval)

        raise TimeoutError(f"Mureka audio task {task_id} timed out after {timeout_seconds}s")

    def upload_file(
        self,
        file_content: bytes,
        filename: str,
        purpose: str = "audio",
        mime_type: str = "audio/mpeg",
        timeout: int = 60
    ) -> Dict[str, Any]:
        """Uploads an audio file to Mureka for recognition, extension, or transcription.

        POST /v1/files/upload
        """
        url = f"{self.base_url}/files/upload"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        files = {"file": (filename, file_content, mime_type)}
        data = {"purpose": purpose}

        logger.info(f"Mureka POST {url} (multipart upload: {filename}, purpose={purpose})")
        resp = requests.post(url, headers=headers, data=data, files=files, timeout=timeout)
        if not resp.ok:
            err_msg = f"Mureka API upload error ({resp.status_code}): {resp.text}"
            logger.error(err_msg)
            raise MurekaAPIError(err_msg)
        return resp.json()

    def recognize_song(self, upload_audio_id: str, timeout: int = 60) -> Dict[str, Any]:
        """Recognizes lyrics and vocal sections in an uploaded audio file.

        POST /v1/song/recognize
        """
        if not upload_audio_id:
            raise ValueError("upload_audio_id is required to recognize song lyrics.")
        return self._post("/song/recognize", {"upload_audio_id": upload_audio_id}, timeout=timeout)

    def describe_song(self, url: str, timeout: int = 60) -> Dict[str, Any]:
        """Analyzes and describes music genres, instruments, tags, and summary.

        POST /v1/song/describe
        `url` can be a remote URL or a data URI (e.g. data:audio/mp3;base64,...).
        """
        if not url:
            raise ValueError("url (or data URI) is required to describe a song.")
        return self._post("/song/describe", {"url": url}, timeout=timeout)

    def transcribe_song(
        self,
        upload_audio_id: Optional[str] = None,
        song_id: Optional[str] = None,
        url: Optional[str] = None,
        title: Optional[str] = None,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """Transcribes audio into sheet music, returning a downloadable ZIP with XML and PDF scores.

        POST /v1/song/transcribe
        """
        payload: Dict[str, Any] = {}
        if upload_audio_id:
            payload["upload_audio_id"] = upload_audio_id
        elif song_id:
            payload["song_id"] = song_id
        elif url:
            payload["url"] = url
        else:
            raise ValueError("Either upload_audio_id, song_id, or url must be provided to transcribe.")

        if title:
            payload["title"] = title

        return self._post("/song/transcribe", payload, timeout=timeout)

    def get_billing(self) -> Dict[str, Any]:
        """Queries account billing and balance information.

        GET /v1/account/billing
        """
        return self._get("/account/billing")


def format_recognized_lyrics(lyrics_sections: Optional[List[Dict[str, Any]]]) -> str:
    """Formats lyrics_sections from recognize_song into clean lyrics text ready for the composer."""
    if not lyrics_sections:
        return ""
    blocks = []
    for i, sec in enumerate(lyrics_sections, 1):
        lines = sec.get("lines") or []
        sec_lines = [l.get("text", "").strip() for l in lines if l.get("text", "").strip()]
        if sec_lines:
            blocks.append(f"[Section {i}]\n" + "\n".join(sec_lines))
    return "\n\n".join(blocks)

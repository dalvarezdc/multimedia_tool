"""Tests for xAI Grok Imagine video client: submit, poll, download, errors."""

import json
import pytest
import requests
from src.grok.client import GrokVideoClient


class _Resp:
    def __init__(self, ok=True, status_code=200, payload=None, text="", body=b"mp4data"):
        self.ok = ok
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or json.dumps(self._payload)
        self._body = body

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(self.text)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, chunk_size=16384):
        yield self._body
        yield b""


def _client(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "mock_xai_key")
    monkeypatch.setattr("src.grok.client.time.sleep", lambda s: None)
    return GrokVideoClient()


def test_prepare_image_reference_url_and_local(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    assert client._prepare_image_reference("https://cdn.example/ref.png") == "https://cdn.example/ref.png"
    assert client._prepare_image_reference("http://cdn.example/ref.png") == "http://cdn.example/ref.png"
    assert client._prepare_image_reference("missing-file.png") == "missing-file.png"

    img = tmp_path / "hero.png"
    img.write_bytes(b"png-bytes")
    uri = client._prepare_image_reference(str(img))
    assert uri.startswith("data:image/png;base64,")


def test_generate_video_succeeds_with_stages_and_character_ref(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    img = tmp_path / "ref.jpg"
    img.write_bytes(b"jpg")
    out = tmp_path / "out" / "clip.mp4"
    captured_post = {}
    polls = {"n": 0}
    stages = []

    def fake_post(url, json=None, headers=None, timeout=None):
        captured_post["url"] = url
        captured_post["json"] = json
        captured_post["headers"] = headers
        return _Resp(payload={"request_id": "req_1"})

    def fake_get(url, headers=None, timeout=None, stream=False):
        if stream or "example.com" in url:
            return _Resp(body=b"video-bytes")
        polls["n"] += 1
        if polls["n"] == 1:
            return _Resp(ok=False, status_code=502, text="upstream blip")
        if polls["n"] == 2:
            return _Resp(payload={"status": "running"})
        return _Resp(payload={
            "status": "completed",
            "result": {"video_url": "https://example.com/clip.mp4"},
        })

    monkeypatch.setattr("src.grok.client.requests.post", fake_post)
    monkeypatch.setattr("src.grok.client.requests.get", fake_get)

    path = client.generate_video(
        prompt="  Hermes flies  ",
        output_path=str(out),
        character_reference_image=str(img),
        duration=99,
        ratio="9:16",
        poll_interval=0,
        status_callback=lambda stage, meta: stages.append(stage),
    )
    assert path == str(out)
    assert out.read_bytes() == b"video-bytes"
    assert captured_post["json"]["duration"] == 15
    assert captured_post["json"]["aspect_ratio"] == "9:16"
    assert captured_post["json"]["image_url"].startswith("data:")
    assert captured_post["headers"]["Authorization"] == "Bearer mock_xai_key"
    assert stages == ["preparing", "submitting", "queued", "rendering", "downloading", "auditing"]


def test_generate_video_uses_id_and_video_url_fields(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    out = tmp_path / "clip.mp4"

    def fake_post(url, json=None, headers=None, timeout=None):
        return _Resp(payload={"id": "job_9"})

    def fake_get(url, headers=None, timeout=None, stream=False):
        if stream or url.endswith(".mp4"):
            return _Resp(body=b"ok")
        return _Resp(payload={"status": "succeeded", "video_url": "https://cdn/x.mp4"})

    monkeypatch.setattr("src.grok.client.requests.post", fake_post)
    monkeypatch.setattr("src.grok.client.requests.get", fake_get)
    assert client.generate_video("scene", str(out), poll_interval=0) == str(out)


def test_generate_video_http_error(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        "src.grok.client.requests.post",
        lambda *a, **k: _Resp(ok=False, status_code=401, text="bad key"),
    )
    with pytest.raises(RuntimeError, match="xAI API error"):
        client.generate_video("p", str(tmp_path / "o.mp4"), poll_interval=0)


def test_generate_video_missing_request_id(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        "src.grok.client.requests.post",
        lambda *a, **k: _Resp(payload={"status": "queued"}),
    )
    with pytest.raises(RuntimeError, match="request_id"):
        client.generate_video("p", str(tmp_path / "o.mp4"), poll_interval=0)


def test_generate_video_missing_video_url(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        "src.grok.client.requests.post",
        lambda *a, **k: _Resp(payload={"id": "job"}),
    )
    monkeypatch.setattr(
        "src.grok.client.requests.get",
        lambda *a, **k: _Resp(payload={"status": "done"}),
    )
    with pytest.raises(RuntimeError, match="video_url"):
        client.generate_video("p", str(tmp_path / "o.mp4"), poll_interval=0)


def test_generate_video_failed_status(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        "src.grok.client.requests.post",
        lambda *a, **k: _Resp(payload={"id": "job"}),
    )
    monkeypatch.setattr(
        "src.grok.client.requests.get",
        lambda *a, **k: _Resp(payload={"status": "failed", "error": "safety"}),
    )
    with pytest.raises(RuntimeError, match="safety"):
        client.generate_video("p", str(tmp_path / "o.mp4"), poll_interval=0)


def test_generate_video_timeout(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    clock = {"n": 0}

    def fake_time():
        clock["n"] += 1
        return 0.0 if clock["n"] < 6 else 10_000.0

    monkeypatch.setattr("src.grok.client.time.time", fake_time)
    monkeypatch.setattr(
        "src.grok.client.requests.post",
        lambda *a, **k: _Resp(payload={"id": "job"}),
    )
    monkeypatch.setattr(
        "src.grok.client.requests.get",
        lambda *a, **k: _Resp(payload={"status": "running"}),
    )
    with pytest.raises(TimeoutError, match="timed out"):
        client.generate_video("p", str(tmp_path / "o.mp4"), poll_interval=0, timeout_seconds=1)

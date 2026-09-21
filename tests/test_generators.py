"""Tests for video generator clients (BytePlus Seedance & xAI Grok)."""

import os
import pytest
from src.generators import get_video_generator
from src.seedance.client import SeedanceClient
from src.grok.client import GrokVideoClient

def test_factory_seedance():
    os.environ["ARK_API_KEY"] = "mock_ark_key"
    client = get_video_generator("seedance")
    assert isinstance(client, SeedanceClient)
    assert client.api_key == "mock_ark_key"

def test_factory_grok():
    os.environ["XAI_API_KEY"] = "mock_xai_key"
    client = get_video_generator("grok")
    assert isinstance(client, GrokVideoClient)
    assert client.api_key == "mock_xai_key"

def test_factory_invalid_provider():
    with pytest.raises(ValueError, match="Unknown video provider"):
        get_video_generator("unsupported_provider")

def test_grok_missing_api_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="XAI_API_KEY must be provided"):
        GrokVideoClient()

def test_seedance_modes_configuration():
    os.environ["ARK_API_KEY"] = "mock_ark_key"
    client = SeedanceClient()
    assert client.model_id is not None
    # Verify helper parses local or remote refs correctly
    assert client._prepare_image_reference("https://example.com/ref.png") == "https://example.com/ref.png"

def test_factory_model_id_overrides_env(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "mock_ark_key")
    monkeypatch.setenv("ARK_SEEDANCE_MODEL", "dreamina-seedance-2-0-260128")
    client = get_video_generator(
        "seedance",
        api_key="mock_ark_key",
        model_id="dreamina-seedance-2-5-260628",
    )
    assert client.model_id == "dreamina-seedance-2-5-260628"

def test_grok_model_id_passthrough(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "mock_xai_key")
    monkeypatch.setenv("XAI_VIDEO_MODEL", "ignored-env-model")
    client = get_video_generator(
        "grok",
        api_key="mock_xai_key",
        model_id="grok-imagine-video-1.5",
    )
    assert isinstance(client, GrokVideoClient)
    assert client.model_id == "grok-imagine-video-1.5"


def test_seedance_content_roles(monkeypatch, tmp_path):
    monkeypatch.setenv("ARK_API_KEY", "mock_ark_key")
    client = SeedanceClient()

    captured_kwargs = {}

    class MockTasks:
        def create(self, **kwargs):
            nonlocal captured_kwargs
            captured_kwargs = kwargs
            return {"id": "mock_task_123"}

        def get(self, task_id):
            return {
                "status": "succeeded",
                "content": {"video_url": "https://example.com/mock.mp4"}
            }

    client.client.content_generation.tasks = MockTasks()
    monkeypatch.setattr(client, "_download_file", lambda url, dest: None)

    # 1. Test ref-to-video mode with image and video assets
    img_file = tmp_path / "img.png"
    img_file.write_bytes(b"dummy_png")
    vid_file = tmp_path / "vid.mp4"
    vid_file.write_bytes(b"dummy_mp4")

    client.generate_video(
        prompt="A battle in space",
        output_path=str(tmp_path / "out.mp4"),
        generation_mode="ref-to-video",
        reference_assets=[
            {"type": "image", "local_path": str(img_file)},
            {"type": "video", "local_path": str(vid_file)},
        ],
        character_reference_image=str(img_file)
    )

    content = captured_kwargs["content"]
    # Image asset should have role: reference_image
    img_entry = next(c for c in content if c.get("type") == "image_url")
    assert img_entry["role"] == "reference_image"

    # Video asset should have role: reference_video
    vid_entry = next(c for c in content if c.get("type") == "video_url")
    assert vid_entry["role"] == "reference_video"

    # 2. Test first_last_frame mode
    client.generate_video(
        prompt="Keyframed morph",
        output_path=str(tmp_path / "out2.mp4"),
        generation_mode="first_last_frame",
        first_frame_image=str(img_file),
        last_frame_image=str(img_file),
    )
    content2 = captured_kwargs["content"]
    roles2 = [c.get("role") for c in content2 if "role" in c]
    assert "first_frame" in roles2
    assert "last_frame" in roles2
    assert "reference" not in roles2


def test_seedance_status_callback_stages(monkeypatch, tmp_path):
    monkeypatch.setenv("ARK_API_KEY", "mock_ark_key")
    client = SeedanceClient()

    poll_count = 0

    class MockTasks:
        def create(self, **kwargs):
            return {"id": "task_stage_test"}

        def get(self, task_id):
            nonlocal poll_count
            poll_count += 1
            if poll_count == 1:
                return {"status": "running"}
            return {
                "status": "succeeded",
                "content": {"video_url": "https://example.com/stage_test.mp4"}
            }

    client.client.content_generation.tasks = MockTasks()
    monkeypatch.setattr(client, "_download_file", lambda url, dest: None)

    stages_recorded = []
    def on_status(stage, meta):
        stages_recorded.append((stage, meta))

    client.generate_video(
        prompt="A testing sequence",
        output_path=str(tmp_path / "stage_out.mp4"),
        status_callback=on_status,
        poll_interval=0
    )

    stage_names = [s[0] for s in stages_recorded]
    assert "preparing" in stage_names
    assert "submitting" in stage_names
    assert "queued" in stage_names
    assert "rendering" in stage_names
    assert "downloading" in stage_names
    assert "auditing" in stage_names




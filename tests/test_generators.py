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


def test_seedance_missing_api_key(monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ARK_API_KEY"):
        SeedanceClient()


def test_seedance_prepare_image_fallbacks(monkeypatch, tmp_path):
    monkeypatch.setenv("ARK_API_KEY", "mock_ark_key")
    client = SeedanceClient()
    assert client._prepare_image_reference("") == ""
    assert client._prepare_image_reference("data:image/png;base64,xx") == "data:image/png;base64,xx"
    assert client._prepare_image_reference("missing.png") == "missing.png"

    img = tmp_path / "uploads" / "hero.png"
    img.parent.mkdir()
    img.write_bytes(b"png")
    monkeypatch.chdir(tmp_path)
    uri = client._prepare_image_reference("/uploads/hero.png")
    assert uri.startswith("data:")


def _mock_tasks(client, create_return, get_return):
    class MockTasks:
        def create(self, **kwargs):
            MockTasks.kwargs = kwargs
            return create_return

        def get(self, task_id=None, **kwargs):
            if callable(get_return):
                return get_return()
            return get_return

    client.client.content_generation.tasks = MockTasks()
    return MockTasks


def test_seedance_ip_effects_and_character_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("ARK_API_KEY", "mock_ark_key")
    client = SeedanceClient()
    img = tmp_path / "c.png"
    img.write_bytes(b"png")
    monkeypatch.setattr(client, "_download_file", lambda url, dest: None)
    tasks = _mock_tasks(
        client,
        {"id": "t1"},
        {"status": "succeeded", "content": {"video_url": "https://x/v.mp4"}},
    )
    client.generate_video(
        prompt="fx",
        output_path=str(tmp_path / "out.mp4"),
        generation_mode="ip_effects",
        ip_effect_name="glow",
        character_reference_image=str(img),
        poll_interval=0,
        draft_mode=True,
        resolution="1080p",
        generate_audio=True,
    )
    assert tasks.kwargs["draft"] is True
    assert tasks.kwargs["resolution"] == "1080p"
    roles = [c.get("role") for c in tasks.kwargs["content"]]
    assert "reference_image" in roles

    client.generate_video(
        prompt="frames",
        output_path=str(tmp_path / "out2.mp4"),
        generation_mode="first_last_frame",
        character_reference_image=str(img),
        poll_interval=0,
    )
    roles = [c.get("role") for c in tasks.kwargs["content"]]
    assert "first_frame" in roles

    client.generate_video(
        prompt="char only",
        output_path=str(tmp_path / "out3.mp4"),
        character_reference_image=str(img),
        poll_interval=0,
    )
    roles = [c.get("role") for c in tasks.kwargs["content"]]
    assert "reference_image" in roles

    client.generate_video(
        prompt="empty asset skipped",
        output_path=str(tmp_path / "out4.mp4"),
        reference_assets=[{"type": "image"}],
        poll_interval=0,
    )
    types = [c.get("type") for c in tasks.kwargs["content"]]
    assert types == ["text"]

    skipped = tmp_path / "uploads" / "reference_assets"
    skipped.mkdir(parents=True)
    (skipped / "cov_hero.png").write_bytes(b"png")
    monkeypatch.chdir(tmp_path)
    uri = client._prepare_image_reference("missing-dir/cov_hero.png")
    assert uri.startswith("data:")


def test_seedance_task_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("ARK_API_KEY", "mock_ark_key")
    client = SeedanceClient()
    monkeypatch.setattr(client, "_download_file", lambda url, dest: None)
    monkeypatch.setattr("src.seedance.client.time.sleep", lambda s: None)

    _mock_tasks(client, {}, {"status": "succeeded"})
    with pytest.raises(RuntimeError, match="task_id"):
        client.generate_video("p", str(tmp_path / "a.mp4"), poll_interval=0)

    _mock_tasks(client, {"id": "t"}, {"status": "succeeded", "content": {}})
    with pytest.raises(RuntimeError, match="video_url"):
        client.generate_video("p", str(tmp_path / "b.mp4"), poll_interval=0)

    _mock_tasks(client, {"id": "t"}, {"status": "failed", "error": "boom"})
    with pytest.raises(RuntimeError, match="boom"):
        client.generate_video("p", str(tmp_path / "c.mp4"), poll_interval=0)

    clock = {"n": 0}

    def fake_time():
        clock["n"] += 1
        return 0.0 if clock["n"] < 6 else 10_000.0

    monkeypatch.setattr("src.seedance.client.time.time", fake_time)
    _mock_tasks(client, {"id": "t"}, {"status": "queued"})
    with pytest.raises(TimeoutError, match="timed out"):
        client.generate_video("p", str(tmp_path / "d.mp4"), poll_interval=0, timeout_seconds=1)


def test_factory_seedream(monkeypatch):
    from src.generators import get_image_generator
    from src.seedream.client import SeeDreamClient

    monkeypatch.setenv("ARK_API_KEY", "mock_ark_key")
    client = get_image_generator("seedream", model_id="dola-seedream-5-0-pro-260628")
    assert isinstance(client, SeeDreamClient)
    assert client.model_id == "dola-seedream-5-0-pro-260628"


def test_seedream_generate_image(monkeypatch, tmp_path):
    from src.seedream.client import SeeDreamClient

    monkeypatch.setenv("ARK_API_KEY", "mock_ark_key")
    client = SeeDreamClient()

    captured_args = {}

    class MockImages:
        def generate(self, **kwargs):
            nonlocal captured_args
            captured_args = kwargs
            class MockItem:
                url = "https://example.com/test_generated_image.png"
                b64_json = None
            class MockResp:
                data = [MockItem()]
            return MockResp()

    client.client.images = MockImages()

    # Mock download
    def mock_download(url, dest):
        with open(dest, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\nfake_png_data")

    monkeypatch.setattr(client, "_download_file", mock_download)

    test_ref = tmp_path / "ref_char.png"
    test_ref.write_bytes(b"fake_image_bytes")

    out_file = tmp_path / "generated.png"
    client.generate_image(
        prompt="A hero standing atop a neon tower",
        output_path=str(out_file),
        reference_assets=[
            {
                "id": "ref1",
                "type": "image",
                "local_path": str(test_ref)
            }
        ],
        ratio="16:9"
    )

    assert out_file.exists()
    assert "A hero standing atop a neon tower" in captured_args.get("prompt")
    assert "image" in captured_args
    assert captured_args["image"].startswith("data:image/png;base64,")





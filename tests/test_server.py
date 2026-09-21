"""Tests for FastAPI backend server routes, settings management, and studio separation."""

import os
import pytest
from starlette.testclient import TestClient
from src.server import create_app

@pytest.fixture
def client(tmp_path, monkeypatch):
    test_uploads = tmp_path / "uploads"
    test_data = tmp_path / "data"
    test_uploads.mkdir(parents=True, exist_ok=True)
    test_data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MULTIMEDIA_UPLOADS_DIR", str(test_uploads))
    monkeypatch.setenv("MULTIMEDIA_DATA_DIR", str(test_data))
    app = create_app()
    return TestClient(app)

def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "api"


def test_api_only_mode_does_not_serve_html(tmp_path, monkeypatch):
    test_uploads = tmp_path / "uploads"
    test_data = tmp_path / "data"
    test_uploads.mkdir(parents=True, exist_ok=True)
    test_data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MULTIMEDIA_UPLOADS_DIR", str(test_uploads))
    monkeypatch.setenv("MULTIMEDIA_DATA_DIR", str(test_data))
    monkeypatch.setenv("SERVE_UI", "0")
    app = create_app()
    client = TestClient(app)
    assert client.get("/").status_code == 404
    assert client.get("/app").status_code == 404
    assert client.get("/portal").status_code == 404
    health = client.get("/api/health")
    assert health.status_code == 200
    assert client.get("/api/usage").status_code == 200
    assert client.get("/api/openapi.json").status_code == 200


def test_landing_page_route(client):
    response = client.get("/portal")
    assert response.status_code == 200
    assert "RetroArk" in response.text
    assert "Launch Studio" in response.text

def test_studio_app_route(client):
    response = client.get("/app")
    assert response.status_code == 200
    assert "RetroArk" in response.text
    assert "Video Studio" in response.text
    assert "RPG Studio" in response.text
    assert "Ref-to-video" in response.text

def test_console_routes(client):
    for route in ["/", "/video", "/rpg", "/api-keys", "/docs", "/settings", "/usage"]:
        response = client.get(route)
        assert response.status_code == 200
        assert "RetroArk" in response.text

def test_api_usage_endpoint(client):
    response = client.get("/api/usage")
    assert response.status_code == 200
    data = response.json()
    assert "total_generations" in data
    assert "video_generations" in data
    assert "rpg_renders" in data
    assert "watermark_free_rate" in data
    assert "records" in data

def test_test_connection_endpoint(client, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    res = client.post("/api/settings/test-connection", json={"provider": "seedance"})
    assert res.status_code == 200
    assert res.json()["status"] == "error"

    class FakeResp:
        status_code = 200

    monkeypatch.setenv("ARK_API_KEY", "test_mock_api_key_valid")
    monkeypatch.setattr("src.server.requests.get", lambda *args, **kwargs: FakeResp())
    res = client.post("/api/settings/test-connection", json={"provider": "seedance"})
    assert res.status_code == 200
    assert res.json()["status"] == "success"

def test_get_settings(client, monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "test_secret_ark_key")
    monkeypatch.setenv("XAI_API_KEY", "test_secret_xai_key")
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["has_ark_key"] is True
    assert data["has_xai_key"] is True
    assert "..._key" in data["ark_key_masked"]

def test_post_settings(client, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    
    payload = {
        "ark_api_key": "new_ark_key_value",
        "xai_api_key": "new_xai_key_value",
        "ark_base_url": "https://ark.custom.endpoint/api/v3",
        "provider": "seedance"
    }
    response = client.post("/api/settings", json=payload)
    assert response.status_code == 200
    assert os.getenv("ARK_API_KEY") == "new_ark_key_value"
    assert os.getenv("XAI_API_KEY") == "new_xai_key_value"
    assert os.getenv("ARK_BASE_URL") == "https://ark.custom.endpoint/api/v3"

def test_plan_missing_key_returns_400(client, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    payload = {
        "topic": "Testing without key",
        "chapter_count": 3
    }
    response = client.post("/api/plan", json=payload)
    assert response.status_code == 400
    assert "ARK_API_KEY is required" in response.json()["detail"]

def test_cutscene_generate_modes(client, monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "test_mock_key")
    modes = ["ref_to_video", "first_last_frame", "ip_effects"]
    for mode in modes:
        payload = {
            "chapter_id": 1,
            "prompt": f"Hero testing {mode}",
            "generation_mode": mode,
            "provider": "seedance",
            "video_model": "dreamina-seedance-2-5-260628"
        }
        response = client.post("/api/cutscenes/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["chapter_id"] == 1
        assert data["model"] == "dreamina-seedance-2-5-260628"

def test_api_models_endpoint(client, monkeypatch):
    monkeypatch.delenv("ARK_SEEDANCE_MODEL", raising=False)
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert data["total_models"] >= 28
    assert "video" in data["catalog"]
    assert "director_llm" in data["catalog"]
    assert "dreamina-seedance" in data["active_video_model"]


def test_cutscene_generate_passes_ratio(client, monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "test_mock_key")
    payload = {
        "chapter_id": 9,
        "prompt": "Hermes soaring over temples",
        "generation_mode": "ref_to_video",
        "provider": "seedance",
        "video_model": "dreamina-seedance-2-5-260628",
        "ratio": "9:16",
        "duration_seconds": 5,
    }
    response = client.post("/api/cutscenes/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "dreamina-seedance-2-5-260628"
    assert data["provider"] == "seedance"


def test_cutscene_generate_first_last_frame_mode(client, monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "test_mock_key")
    payload = {
        "chapter_id": 12,
        "prompt": "Morph from dawn to dusk",
        "generation_mode": "first_last_frame",
        "first_frame_image": "/uploads/reference_assets/frame1.png",
        "last_frame_image": "/uploads/reference_assets/frame2.png",
        "provider": "seedance",
        "video_model": "dreamina-seedance-2-5-260628",
        "duration_seconds": 5,
    }
    response = client.post("/api/cutscenes/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "dreamina-seedance-2-5-260628"
    assert data["provider"] == "seedance"

def test_settings_update_models(client, monkeypatch):
    payload = {
        "director_model": "seed-2-0-pro-260328",
        "video_model": "dreamina-seedance-2-0-fast-260128",
        "rpg_resolution": "720p",
        "chapter_count": 5,
        "provider": "seedance",
    }
    response = client.post("/api/settings", json=payload)
    assert response.status_code == 200
    assert os.getenv("ARK_LLM_MODEL") == "seed-2-0-pro-260328"
    assert os.getenv("ARK_SEEDANCE_MODEL") == "dreamina-seedance-2-0-fast-260128"
    assert os.getenv("RPG_CANVAS_RESOLUTION") == "720p"
    assert os.getenv("RPG_CHAPTER_COUNT") == "5"

    settings = client.get("/api/settings").json()
    assert settings["rpg_resolution"] == "720p"
    assert settings["chapter_count"] == 5

def test_plan_requires_topic_or_storyboard(client, monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "test_mock_key")
    response = client.post("/api/plan", json={"topic": "", "purpose": "rpg"})
    assert response.status_code == 400

def test_docs_describe_actual_usage(client):
    html = client.get("/docs").text
    assert "How to use this app" in html
    assert "Generate world" in html
    assert "/api/plan" in html
    assert "Record walk" in html

def test_usage_starts_empty(client):
    data = client.get("/api/usage").json()
    assert data["total_generations"] == 0
    assert data["records"] == []
    assert data["watermark_free_rate"] == "n/a"

def test_reference_assets_upload_tokens_and_delete(client, tmp_path):
    # Test uploading multiple files (images and video)
    image1_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    image2_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    video_bytes = b"\x00\x00\x00 ftypisom"

    files = [
        ("files", ("character_pose.png", image1_bytes, "image/png")),
        ("files", ("scenery_bg.jpg", image2_bytes, "image/jpeg")),
        ("files", ("action_reference.mp4", video_bytes, "video/mp4")),
    ]

    response = client.post("/api/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["uploaded"]) == 3

    assets = data["assets"]
    assert assets[0]["filename"] == "character_pose.png"
    assert assets[0]["token"] == "@Pictures 1"
    assert assets[0]["type"] == "image"

    assert assets[1]["filename"] == "scenery_bg.jpg"
    assert assets[1]["token"] == "@Pictures 2"
    assert assets[1]["type"] == "image"

    assert assets[2]["filename"] == "action_reference.mp4"
    assert assets[2]["token"] == "@Video 1"
    assert assets[2]["type"] == "video"

    # Test GET /api/upload/assets
    res_get = client.get("/api/upload/assets")
    assert res_get.status_code == 200
    assert len(res_get.json()["assets"]) == 3

    # Test deleting one asset and verifying re-indexing
    first_id = assets[0]["id"]
    res_del = client.delete(f"/api/upload/assets/{first_id}")
    assert res_del.status_code == 200
    remaining = res_del.json()["assets"]
    assert len(remaining) == 2
    # The remaining image should now be re-indexed to @Pictures 1
    assert remaining[0]["filename"] == "scenery_bg.jpg"
    assert remaining[0]["token"] == "@Pictures 1"
    assert remaining[1]["token"] == "@Video 1"

    # Test clearing all assets
    res_clear = client.delete("/api/upload/assets")
    assert res_clear.status_code == 200
    assert len(res_clear.json()["assets"]) == 0

def test_cutscene_generate_with_reference_assets(client, monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "test_mock_key")
    payload = {
        "chapter_id": 42,
        "prompt": "Hermes executing combat maneuver matching @Video 1 dressed as @Pictures 1",
        "generation_mode": "ref_to_video",
        "provider": "seedance",
        "video_model": "dreamina-seedance-2-5-260628",
        "reference_assets": [
            {
                "id": "asset1",
                "filename": "hermes_suit.png",
                "token": "@Pictures 1",
                "type": "image",
                "url": "/uploads/reference_assets/asset1_hermes_suit.png"
            },
            {
                "id": "asset2",
                "filename": "sword_slash.mp4",
                "token": "@Video 1",
                "type": "video",
                "url": "/uploads/reference_assets/asset2_sword_slash.mp4"
            }
        ]
    }
    response = client.post("/api/cutscenes/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert data["chapter_id"] == 42

def test_api_models_includes_grok_video(client):
    from src.inventory import inventory_manager
    inventory_manager.refresh_inventory()
    data = client.get("/api/models").json()
    video_ids = [m["id"] for m in data["catalog"]["video"]]
    assert "grok-imagine-video-1.5" in video_ids
    grok = next(m for m in data["catalog"]["video"] if m["id"] == "grok-imagine-video-1.5")
    assert grok["provider"] == "grok"
    assert 15 in grok["durations"]
    image_ids = [m["id"] for m in data["catalog"]["image"]]
    assert "grok-imagine-image-2.0" in image_ids
    assert "grok-imagine-image" in image_ids
    img = next(m for m in data["catalog"]["image"] if m["id"] == "grok-imagine-image-2.0")
    assert img["provider"] == "grok"
    assert img["category"] == "image"


def test_ui_recent_creations_includes_elapsed_tag(client):
    html = client.get("/app").text
    assert "recent-elapsed-tag" in html
    assert "function formatElapsed" in html
    assert "prependRecentGeneration" in html
    assert "Time to generate" in html


def test_ui_image_result_uses_png_download_chrome(client):
    html = client.get("/app").text
    assert "Download MP4" in html
    assert "Download PNG" in html
    assert "isImageResultShowing" in html
    assert "syncPlayerResultChrome" in html
    assert "seedream-output.png" in html


def test_ui_contains_reference_import_elements(client):
    response = client.get("/app")
    assert response.status_code == 200
    html = response.text
    assert "ref-upload-menu" in html
    assert "btn-menu-upload-files" in html
    assert "btn-menu-upload-folder" in html
    assert "imported-assets-tray" in html
    assert "mention-autocomplete-popup" in html
    assert "ref-file-input" in html
    assert "ref-folder-input" in html

def test_multimedia_route_and_ui_renaming(client):
    res = client.get("/multimedia")
    assert res.status_code == 200
    html = res.text
    assert "Multimedia Studio" in html
    assert "Model Inventory &amp; API Sync" in html or "Model Inventory & API Sync" in html
    assert "btn-refresh-inventory" in html
    assert "inventory-table-body" in html

def test_models_refresh_endpoint(client, monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "test_mock_key")
    res = client.post("/api/models/refresh")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "snapshot" in data
    assert data["snapshot"]["total_models"] >= 20

def test_custom_models_endpoint_lifecycle(client):
    # Register custom endpoint
    payload = {
        "id": "ep-custom-seedance-lora-v1",
        "display_name": "Studio Fine-tuned Seedance",
        "category": "video"
    }
    res_add = client.post("/api/models/custom", json=payload)
    assert res_add.status_code == 200
    assert res_add.json()["status"] == "success"

    # Verify present in /api/models
    res_list = client.get("/api/models")
    assert res_list.status_code == 200
    models_data = res_list.json()
    all_ids = [m["id"] for m in models_data["all_models"]]
    assert "ep-custom-seedance-lora-v1" in all_ids

    # Delete custom endpoint
    res_del = client.delete("/api/models/custom/ep-custom-seedance-lora-v1")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "success"


def test_cutscene_status_includes_stage_tracking(client, monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "test_mock_key")
    from src.seedance.client import SeedanceClient
    def mock_generate(self, **kwargs):
        cb = kwargs.get("status_callback")
        if cb:
            cb("rendering", {"message": "Rendering video frames (5s)", "elapsed": 5})
        return "./renders/cutscenes/chapter_99.mp4"

    monkeypatch.setattr(SeedanceClient, "generate_video", mock_generate)

    payload = {
        "chapter_id": 99,
        "prompt": "Epic action scene",
        "provider": "seedance",
        "video_model": "dreamina-seedance-2-5-260628"
    }
    gen_res = client.post("/api/cutscenes/generate", json=payload)
    assert gen_res.status_code == 200

    status_res = client.get("/api/cutscenes/status/99")
    assert status_res.status_code == 200
    st_data = status_res.json()
    assert "stage" in st_data
    assert "stage_label" in st_data
    assert "elapsed_seconds" in st_data
    assert st_data["model"] == "dreamina-seedance-2-5-260628"


def test_ui_contains_generation_status_capsule(client):
    res = client.get("/multimedia")
    assert res.status_code == 200
    html = res.text
    assert "generation-status-capsule" in html
    assert "generation-stage-label" in html
    assert "generation-elapsed-badge" in html


def test_reference_asset_persistence_across_reloads(tmp_path, monkeypatch):
    test_uploads = tmp_path / "uploads"
    test_data = tmp_path / "data"
    test_uploads.mkdir(parents=True, exist_ok=True)
    test_data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MULTIMEDIA_UPLOADS_DIR", str(test_uploads))
    monkeypatch.setenv("MULTIMEDIA_DATA_DIR", str(test_data))

    # 1. First server session uploads an asset
    app1 = create_app()
    client1 = TestClient(app1)
    img_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    res_upload = client1.post("/api/upload", files=[("files", ("hero.png", img_bytes, "image/png"))])
    assert res_upload.status_code == 200
    uploaded_id = res_upload.json()["uploaded"][0]["id"]

    # 2. Simulate server restart with fresh create_app()
    app2 = create_app()
    client2 = TestClient(app2)
    res_assets = client2.get("/api/upload/assets")
    assert res_assets.status_code == 200
    assets = res_assets.json()["assets"]
    assert len(assets) == 1
    assert assets[0]["id"] == uploaded_id
    assert assets[0]["filename"] == "hero.png"
    assert assets[0]["token"] == "@Pictures 1"


def test_reference_assets_disk_auto_discovery(tmp_path, monkeypatch):
    test_uploads = tmp_path / "uploads"
    test_data = tmp_path / "data"
    test_uploads.mkdir(parents=True, exist_ok=True)
    test_data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MULTIMEDIA_UPLOADS_DIR", str(test_uploads))
    monkeypatch.setenv("MULTIMEDIA_DATA_DIR", str(test_data))

    # Place an unindexed file directly on disk
    manual_file = test_uploads / "aabbccdd_character.jpg"
    manual_file.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01")

    app = create_app()
    client = TestClient(app)
    res = client.get("/api/upload/assets")
    assert res.status_code == 200
    assets = res.json()["assets"]
    assert len(assets) == 1
    assert assets[0]["id"] == "aabbccdd"
    assert assets[0]["filename"] == "character.jpg"
    assert assets[0]["token"] == "@Pictures 1"


def test_cutscene_resolves_reference_assets_and_passes_to_seedance(tmp_path, monkeypatch):
    test_uploads = tmp_path / "uploads"
    test_data = tmp_path / "data"
    test_uploads.mkdir(parents=True, exist_ok=True)
    test_data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MULTIMEDIA_UPLOADS_DIR", str(test_uploads))
    monkeypatch.setenv("MULTIMEDIA_DATA_DIR", str(test_data))
    monkeypatch.setenv("ARK_API_KEY", "test_mock_key")

    app = create_app()
    client = TestClient(app)

    img_file = test_uploads / "99887766_soldier.jpg"
    img_file.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01")

    received_kwargs = {}
    from src.seedance.client import SeedanceClient
    def mock_generate(self, **kwargs):
        received_kwargs.update(kwargs)
        return "./renders/cutscenes/chapter_101.mp4"

    monkeypatch.setattr(SeedanceClient, "generate_video", mock_generate)

    payload = {
        "chapter_id": 101,
        "prompt": "Soldiers in white uniform battling",
        "provider": "seedance",
        "video_model": "dreamina-seedance-2-0-mini-260615",
        "reference_assets": [
            {
                "id": "99887766",
                "filename": "soldier.jpg",
                "url": "/uploads/reference_assets/99887766_soldier.jpg"
            }
        ]
    }
    gen_res = client.post("/api/cutscenes/generate", json=payload)
    assert gen_res.status_code == 200
    assert "reference_assets" in received_kwargs
    ref_assets = received_kwargs["reference_assets"]
    assert len(ref_assets) == 1
    assert ref_assets[0]["id"] == "99887766"
    assert os.path.exists(ref_assets[0]["local_path"])


def test_seedance_client_embeds_multimodal_content_payload(tmp_path, monkeypatch):
    test_img = tmp_path / "reference.jpg"
    test_img.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01")

    from src.seedance.client import SeedanceClient
    import requests

    client = SeedanceClient(api_key="mock_key")

    captured_create_args = {}
    class FakeTaskResponse:
        id = "mock_task_123"

    class FakeTaskStatus:
        status = "succeeded"
        content = {"video_url": "https://example.com/mock.mp4"}

    class FakeTasksAPI:
        def create(self, **kwargs):
            captured_create_args.update(kwargs)
            return FakeTaskResponse()

        def get(self, task_id):
            return FakeTaskStatus()

    class FakeContentGen:
        tasks = FakeTasksAPI()

    client.client.content_generation = FakeContentGen()

    class FakeReqResp:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def raise_for_status(self):
            pass
        def iter_content(self, chunk_size=8192):
            yield b"dummy_mp4_content"

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeReqResp())

    out_file = tmp_path / "out.mp4"

    client.generate_video(
        prompt="Soldiers confront each other",
        output_path=str(out_file),
        reference_assets=[
            {
                "id": "ref1",
                "type": "image",
                "token": "@Pictures 1",
                "local_path": str(test_img)
            }
        ]
    )

    assert "content" in captured_create_args
    content = captured_create_args["content"]
    assert len(content) == 2  # 1 image + 1 text prompt
    assert content[0]["type"] == "image_url"
    assert content[0]["role"] == "reference_image"
    assert content[0]["image_url"]["url"].startswith("data:image/")
    assert content[1]["type"] == "text"
    assert "Soldiers confront each other" in content[1]["text"]


class _FakePlanner:
    def __init__(self, *args, **kwargs):
        pass

    def plan_storyboard(self, **kwargs):
        return {"theme": "greek_night_sky", "chapters": [{"id": 1, "title": "Start"}]}

    def improve_storyboard(self, storyboard, instruction=None):
        updated = dict(storyboard)
        updated["improved"] = True
        updated["instruction"] = instruction
        return updated


def test_plan_storyboard_success_and_improve(client, monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "mock_key")
    monkeypatch.setattr("src.server.DirectorPlanner", _FakePlanner)

    missing = client.get("/api/storyboard")
    assert missing.status_code == 404

    res = client.post("/api/plan", json={"topic": "Local LLMs", "chapter_count": 3, "purpose": "rpg"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["storyboard"]["theme"] == "greek_night_sky"

    got = client.get("/api/storyboard")
    assert got.status_code == 200
    assert got.json()["theme"] == "greek_night_sky"

    improved = client.post("/api/plan", json={
        "topic": "",
        "storyboard": {"theme": "old", "chapters": [{"id": 1}]},
        "instruction": "Tighten titles",
    })
    assert improved.status_code == 200
    assert improved.json()["storyboard"]["improved"] is True

    upd = client.post("/api/storyboard/update", json={"theme": "patched", "chapters": []})
    assert upd.status_code == 200
    assert client.get("/api/storyboard").json()["theme"] == "patched"


def test_plan_storyboard_planner_failure(client, monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "mock_key")

    class Boom:
        def __init__(self, *a, **k):
            pass

        def plan_storyboard(self, **k):
            raise RuntimeError("llm down")

    monkeypatch.setattr("src.server.DirectorPlanner", Boom)
    res = client.post("/api/plan", json={"topic": "x"})
    assert res.status_code == 500
    assert "llm down" in res.json()["detail"]


def test_test_connection_grok_401_and_network_error(client, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-key")

    class Unauthorized:
        status_code = 401

    monkeypatch.setattr("src.server.requests.get", lambda *a, **k: Unauthorized())
    res = client.post("/api/settings/test-connection", json={"provider": "grok"})
    assert res.status_code == 200
    assert res.json()["status"] == "error"
    assert "401" in res.json()["message"]

    def boom(*a, **k):
        raise __import__("requests").RequestException("dns")

    monkeypatch.setattr("src.server.requests.get", boom)
    res = client.post("/api/settings/test-connection", json={"provider": "grok"})
    assert res.json()["status"] == "error"
    assert "Could not reach" in res.json()["message"]

    monkeypatch.delenv("XAI_API_KEY", raising=False)
    res = client.post("/api/settings/test-connection", json={"provider": "grok"})
    assert res.json()["status"] == "error"


def test_cutscene_grok_missing_key(client, monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    res = client.post("/api/cutscenes/generate", json={
        "chapter_id": 1,
        "prompt": "Hermes",
        "provider": "grok",
    })
    assert res.status_code == 400
    assert "XAI_API_KEY" in res.json()["detail"]


def test_cutscene_seedance_missing_key(client, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    res = client.post("/api/cutscenes/generate", json={
        "chapter_id": 1,
        "prompt": "Hermes",
        "provider": "seedance",
    })
    assert res.status_code == 400
    assert "ARK_API_KEY" in res.json()["detail"]


def test_custom_model_empty_id_and_delete_missing(client):
    res = client.post("/api/models/custom", json={"id": "   ", "display_name": "blank"})
    assert res.status_code == 400
    missing = client.delete("/api/models/custom/does-not-exist")
    assert missing.status_code == 404


def test_images_generate_worker_failure_and_refs(client, monkeypatch, tmp_path):
    monkeypatch.setenv("ARK_API_KEY", "k")

    class Boom:
        def generate_image(self, **kwargs):
            raise RuntimeError("render failed")

    monkeypatch.setattr("src.server.get_image_generator", lambda **k: Boom())
    res = client.post("/api/images/generate", json={"prompt": "fail me", "chapter_id": 21})
    assert res.status_code == 200
    st = client.get("/api/generation/status/21").json()
    assert st["status"] == "failed"

    img_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    uploaded = client.post("/api/upload", files=[("files", ("hero.png", img_bytes, "image/png"))]).json()
    asset_id = uploaded["uploaded"][0]["id"]
    local_copy = tmp_path / "extra.png"
    local_copy.write_bytes(img_bytes)

    class Ok:
        def generate_image(self, **kwargs):
            assert kwargs["reference_assets"]
            return kwargs["output_path"]

    monkeypatch.setattr("src.server.get_image_generator", lambda **k: Ok())
    res = client.post("/api/images/generate", json={
        "prompt": "with refs",
        "chapter_id": 22,
        "reference_assets": [
            {"id": asset_id},
            {"id": "ghost", "local_path": str(local_copy), "filename": "extra.png", "type": "image"},
        ],
    })
    assert res.status_code == 200
    assert client.get("/api/generation/status/22").json()["status"] == "succeeded"


def test_cutscene_skips_unknown_reference(client, monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "k")
    received = {}

    def mock_generate(self, **kwargs):
        received.update(kwargs)
        return "./renders/cutscenes/chapter_33.mp4"

    from src.seedance.client import SeedanceClient
    monkeypatch.setattr(SeedanceClient, "generate_video", mock_generate)
    res = client.post("/api/cutscenes/generate", json={
        "chapter_id": 33,
        "prompt": "skip junk refs",
        "provider": "seedance",
        "reference_assets": [{"id": "missing"}],
    })
    assert res.status_code == 200
    assert received.get("reference_assets") in (None, [])


def test_images_generate_grok_missing_key_and_success(client, monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    res = client.post("/api/images/generate", json={
        "prompt": "a still of hermes",
        "provider": "grok",
        "image_model": "grok-imagine-image-2.0",
    })
    assert res.status_code == 400
    assert "XAI_API_KEY" in res.json()["detail"]

    monkeypatch.setenv("XAI_API_KEY", "xai-k")

    class FakeGrokImg:
        def generate_image(self, **kwargs):
            return kwargs["output_path"]

    monkeypatch.setattr("src.server.get_image_generator", lambda **k: FakeGrokImg())
    res = client.post("/api/images/generate", json={
        "prompt": "a still of hermes",
        "provider": "grok",
        "image_model": "grok-imagine-image-2.0",
        "chapter_id": 44,
        "api_key": "xai-k",
    })
    assert res.status_code == 200
    assert res.json()["type"] == "image"
    assert res.json()["model"] == "grok-imagine-image-2.0"


def test_images_generate_missing_key_and_success(client, monkeypatch, tmp_path):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    res = client.post("/api/images/generate", json={"prompt": "temple"})
    assert res.status_code == 400

    monkeypatch.setenv("ARK_API_KEY", "k")

    class FakeImg:
        def generate_image(self, **kwargs):
            cb = kwargs.get("status_callback")
            if cb:
                cb("downloading", {"message": "Saving"})
            return kwargs["output_path"]

    monkeypatch.setattr("src.server.get_image_generator", lambda **k: FakeImg())
    res = client.post("/api/images/generate", json={"prompt": "a temple at dusk", "chapter_id": 7})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "started"
    assert data["type"] == "image"
    st = client.get("/api/generation/status/7").json()
    assert st["status"] in ("succeeded", "processing", "generating")


def test_cutscene_routes_seedream_model_to_image(client, monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "k")

    class FakeImg:
        def generate_image(self, **kwargs):
            return kwargs["output_path"]

    monkeypatch.setattr("src.server.get_image_generator", lambda **k: FakeImg())
    res = client.post("/api/cutscenes/generate", json={
        "chapter_id": 8,
        "prompt": "portrait",
        "provider": "seedream",
        "video_model": "dola-seedream-5-0-pro-260628",
    })
    assert res.status_code == 200
    assert res.json()["type"] == "image"


def test_cutscene_status_not_started(client):
    res = client.get("/api/cutscenes/status/40404")
    assert res.status_code == 200
    assert res.json()["status"] == "not_started"


def test_reference_assets_corrupt_json(tmp_path, monkeypatch):
    test_uploads = tmp_path / "uploads"
    test_data = tmp_path / "data"
    test_uploads.mkdir()
    test_data.mkdir()
    monkeypatch.setenv("MULTIMEDIA_UPLOADS_DIR", str(test_uploads))
    monkeypatch.setenv("MULTIMEDIA_DATA_DIR", str(test_data))
    (test_data / "reference_assets.json").write_text("{bad")
    app = create_app()
    client = TestClient(app)
    assert client.get("/api/upload/assets").json()["assets"] == []


def test_reference_assets_fallback_path_and_unprefixed_file(tmp_path, monkeypatch):
    test_uploads = tmp_path / "uploads"
    test_data = tmp_path / "data"
    test_uploads.mkdir()
    test_data.mkdir()
    monkeypatch.setenv("MULTIMEDIA_UPLOADS_DIR", str(test_uploads))
    monkeypatch.setenv("MULTIMEDIA_DATA_DIR", str(test_data))
    (test_uploads / "notes.txt").write_text("skip me")
    (test_uploads / "hero.png").write_bytes(b"\x89PNG")
    (test_uploads / "missing_path_record.jpg").write_bytes(b"\xff\xd8")
    (test_data / "reference_assets.json").write_text(
        '[{"id": "deadbeef", "filename": "missing_path_record.jpg", "url": "/uploads/reference_assets/missing_path_record.jpg", "local_path": "/no/such/file.jpg", "type": "image", "token": "@Pictures 1"}]'
    )
    app = create_app()
    client = TestClient(app)
    assets = client.get("/api/upload/assets").json()["assets"]
    names = {a["filename"] for a in assets}
    assert "hero.png" in names
    assert "missing_path_record.jpg" in names
    assert "notes.txt" not in names


def test_image_generate_endpoint(client, monkeypatch, tmp_path):
    monkeypatch.setenv("ARK_API_KEY", "mock_ark_key")

    class MockSeeDreamClient:
        def __init__(self, **kwargs):
            pass

        def generate_image(self, prompt, output_path, **kwargs):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\nfake_generated_image")
            if "status_callback" in kwargs and kwargs["status_callback"]:
                kwargs["status_callback"]("rendering", {"message": "Rendering 2k image..."})

    import src.server as server_mod
    monkeypatch.setattr(server_mod, "get_image_generator", lambda **kwargs: MockSeeDreamClient())

    payload = {
        "chapter_id": 88,
        "task_id": "88",
        "prompt": "Cyberpunk cityscape under neon rain",
        "image_model": "dola-seedream-5-0-pro-260628",
        "ratio": "16:9",
        "resolution": "2k",
        "provider": "seedream"
    }

    res = client.post("/api/images/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "started"
    assert data["type"] == "image"
    assert data["chapter_id"] == 88

    # Check status endpoint
    res_status = client.get("/api/cutscenes/status/88")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["status"] == "succeeded"
    assert status_data["type"] == "image"
    assert status_data["path"] == "/renders/images/img_88.png"

    # Also test /api/generation/status alias
    res_alias = client.get("/api/generation/status/88")
    assert res_alias.status_code == 200
    assert res_alias.json()["status"] == "succeeded"


def test_cutscene_generate_delegates_to_image(client, monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "mock_ark_key")

    class MockSeeDreamClient:
        def __init__(self, **kwargs):
            pass

        def generate_image(self, prompt, output_path, **kwargs):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\nfake_delegated_image")

    import src.server as server_mod
    monkeypatch.setattr(server_mod, "get_image_generator", lambda **kwargs: MockSeeDreamClient())

    payload = {
        "chapter_id": 99,
        "prompt": "An oil painting of mountains",
        "generation_mode": "image_generation",
        "video_model": "dola-seedream-5-0-pro-260628",
        "provider": "seedance"
    }

    res = client.post("/api/cutscenes/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "started"
    assert data["type"] == "image"
    assert data["model"] == "dola-seedream-5-0-pro-260628"


def test_estimate_cost_endpoint(client):
    # Test video model cost estimation
    res = client.get("/api/cost/estimate", params={
        "model": "dreamina-seedance-2-0-fast-260128",
        "duration": 5,
        "resolution": "720p",
        "clips": 1
    })
    assert res.status_code == 200
    data = res.json()
    assert data["cost"] == "USD 0.6048"

    # Test 10s duration doubling
    res10 = client.get("/api/cost/estimate", params={
        "model": "dreamina-seedance-2-0-fast-260128",
        "duration": 10,
        "resolution": "720p",
        "clips": 1
    })
    assert res10.status_code == 200
    assert res10.json()["cost"] == "USD 1.2096"

    # Test image model cost estimation
    res_img = client.get("/api/cost/estimate", params={
        "model": "dola-seedream-5-0-pro-260628",
        "resolution": "2K",
        "clips": 4
    })
    assert res_img.status_code == 200
    assert res_img.json()["cost"] == "0.180-0.360 USD"








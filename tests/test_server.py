"""Tests for FastAPI backend server routes, settings management, and studio separation."""

import os
import pytest
from starlette.testclient import TestClient
from src.server import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

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
    data = client.get("/api/models").json()
    video_ids = [m["id"] for m in data["catalog"]["video"]]
    assert "grok-imagine-video-1.5" in video_ids
    grok = next(m for m in data["catalog"]["video"] if m["id"] == "grok-imagine-video-1.5")
    assert grok["provider"] == "grok"
    assert 15 in grok["durations"]


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




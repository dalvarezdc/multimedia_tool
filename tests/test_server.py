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
    assert "RetroArk Console" in response.text
    assert "Video Studio" in response.text
    assert "RPG Studio" in response.text
    assert "Ref-to-video" in response.text

def test_console_routes(client):
    for route in ["/", "/video", "/rpg", "/api-keys", "/docs", "/settings", "/usage"]:
        response = client.get(route)
        assert response.status_code == 200
        assert "RetroArk Console" in response.text

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
    # Without keys
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    res = client.post("/api/settings/test-connection", json={"provider": "seedance"})
    assert res.status_code == 200
    assert res.json()["status"] == "error"

    # With keys
    monkeypatch.setenv("ARK_API_KEY", "test_mock_api_key_valid")
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

def test_api_models_endpoint(client):
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert data["total_models"] == 24
    assert "video" in data["catalog"]
    assert "director_llm" in data["catalog"]
    assert data["active_video_model"] == "dreamina-seedance-2-5-260628"

def test_settings_update_models(client, monkeypatch):
    payload = {
        "director_model": "seed-2-0-pro-260328",
        "video_model": "dreamina-seedance-2-0-fast-260128"
    }
    response = client.post("/api/settings", json=payload)
    assert response.status_code == 200
    assert os.getenv("ARK_LLM_MODEL") == "seed-2-0-pro-260328"
    assert os.getenv("ARK_SEEDANCE_MODEL") == "dreamina-seedance-2-0-fast-260128"


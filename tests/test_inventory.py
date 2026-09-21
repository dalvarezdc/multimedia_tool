"""Unit tests for Model Inventory & Dynamic Discovery Service (mm-ic9)."""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from src.inventory import (
    ModelInventoryManager,
    infer_model_capabilities,
    fetch_byteplus_models,
    fetch_xai_models,
)
from src.models_registry import MODEL_CATALOG


def test_infer_model_capabilities_seedance_family():
    info_25 = infer_model_capabilities("custom-seedance-2.5-turbo", provider="seedance")
    assert info_25.category == "video"
    assert info_25.ui_layout_type == "video_ref"
    assert "1080p" in info_25.resolutions
    assert info_25.supports_audio is True

    info_15 = infer_model_capabilities("seedance-1.5-custom", provider="seedance")
    assert info_15.category == "video"
    assert info_15.ui_layout_type == "video_first_last"
    assert info_15.supports_draft is True

    info_mini = infer_model_capabilities("seedance-fast-motion", provider="seedance")
    assert info_mini.category == "video"
    assert info_mini.ui_layout_type == "video_first"


def test_infer_model_capabilities_image_and_llm():
    info_img = infer_model_capabilities("seedream-custom-v5", provider="seedance")
    assert info_img.category == "image"
    assert info_img.ui_layout_type == "image_standard"
    assert "4K" in info_img.resolutions

    info_llm = infer_model_capabilities("deepseek-v4-reasoning", provider="seedance")
    assert info_llm.category == "director_llm"
    assert info_llm.icon_type == "llm"


def test_fetch_byteplus_models_mock():
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "data": [
            {"id": "dreamina-seedance-2-5-260628", "name": "Seedance 2.5 Live"},
            {"id": "new-future-seedance-3-0", "name": "Seedance 3.0 Experimental"}
        ]
    }

    with patch("requests.get", return_value=fake_resp):
        models = fetch_byteplus_models(api_key="mock_key", base_url="https://ark.test/api/v3")
        assert len(models) >= 2
        assert any(m["id"] == "new-future-seedance-3-0" for m in models)


def test_fetch_xai_models_mock():
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "data": [
            {"id": "grok-imagine-video-1.5"},
            {"id": "grok-imagine-video-2.0"}
        ]
    }

    with patch("requests.get", return_value=fake_resp):
        models = fetch_xai_models(api_key="mock_key", base_url="https://api.x.ai/v1")
        assert len(models) == 2
        assert models[0]["id"] == "grok-imagine-video-1.5"


def test_inventory_merge_live_and_presets(tmp_path):
    mgr = ModelInventoryManager()

    live_models = [
        {"id": "dreamina-seedance-2-5-260628", "display_name": "Dreamina 2.5 Verified", "provider": "seedance"},
        {"id": "ep-2026-custom-video-stream", "display_name": "Dedicated EP", "provider": "seedance"}
    ]
    custom_models = [
        {"id": "my-private-lora", "display_name": "Private LoRA", "category": "video", "is_custom": True, "source": "custom_endpoint"}
    ]

    merged = mgr.merge_inventory(live_models, custom_models)

    # dreamina-seedance-2-5 should be marked live
    assert merged["dreamina-seedance-2-5-260628"]["is_live"] is True
    assert merged["dreamina-seedance-2-5-260628"]["source"] == "live_api"

    # ep-2026... was inferred as video
    assert merged["ep-2026-custom-video-stream"]["is_live"] is True
    assert merged["ep-2026-custom-video-stream"]["category"] == "video"

    # my-private-lora is custom
    assert merged["my-private-lora"]["is_custom"] is True

    # Other presets exist with is_live=False
    assert "bytedance-seedance-1-5-pro-251215" in merged
    assert merged["bytedance-seedance-1-5-pro-251215"]["is_live"] is False
    assert merged["bytedance-seedance-1-5-pro-251215"]["source"] == "catalog_preset"


def test_custom_model_save_and_delete(tmp_path, monkeypatch):
    custom_file = str(tmp_path / "custom.json")
    cache_file = str(tmp_path / "cache.json")
    monkeypatch.setattr("src.inventory.CUSTOM_MODELS_FILE", custom_file)
    monkeypatch.setattr("src.inventory.CACHE_FILE", cache_file)

    mgr = ModelInventoryManager()
    created = mgr.save_custom_model({
        "id": "ep-dedicated-endpoint-001",
        "display_name": "Company HQ Dedicated Seedance",
        "category": "video"
    })
    assert created["id"] == "ep-dedicated-endpoint-001"
    assert created["is_custom"] is True

    loaded = mgr.get_custom_models()
    assert len(loaded) == 1
    assert loaded[0]["id"] == "ep-dedicated-endpoint-001"

    deleted = mgr.delete_custom_model("ep-dedicated-endpoint-001")
    assert deleted is True
    assert len(mgr.get_custom_models()) == 0


def test_infer_grok_imagine_image_is_not_video():
    info = infer_model_capabilities("grok-imagine-image-2.0", provider="grok")
    assert info.category == "image"
    assert info.provider == "grok"
    assert info.ui_layout_type == "image_standard"
    vid = infer_model_capabilities("grok-imagine-video-1.5", provider="grok")
    assert vid.category == "video"


def test_infer_model_capabilities_3d():
    info = infer_model_capabilities("studio-hyper3d-mesh", provider="seedance")
    assert info.category == "3d"


def test_fetch_byteplus_endpoints_and_errors():
    def fake_get(url, headers=None, timeout=None):
        resp = MagicMock()
        if url.endswith("/endpoints"):
            resp.status_code = 200
            resp.json.return_value = {
                "data": [
                    {"id": "ep-unique-1", "name": "Dedicated", "model_id": "seedance"},
                    {"id": "dreamina-seedance-2-5-260628", "name": "dup"},
                ]
            }
            return resp
        resp.status_code = 200
        resp.json.return_value = {"data": [{"id": "dreamina-seedance-2-5-260628", "name": "Live"}]}
        return resp

    with patch("requests.get", side_effect=fake_get):
        models = fetch_byteplus_models(api_key="k", base_url="https://ark.test/api/v3/")
        ids = [m["id"] for m in models]
        assert "ep-unique-1" in ids
        assert ids.count("dreamina-seedance-2-5-260628") == 1


def test_fetch_byteplus_endpoints_exception_and_non_200():
    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/endpoints"):
            raise RuntimeError("no endpoints")
        resp = MagicMock()
        resp.status_code = 500
        return resp

    with patch("requests.get", side_effect=fake_get):
        assert fetch_byteplus_models(api_key="k", base_url="https://ark.test/api/v3") == []


def test_fetch_xai_non_200_and_exception():
    resp = MagicMock()
    resp.status_code = 403
    with patch("requests.get", return_value=resp):
        assert fetch_xai_models(api_key="k") == []
    with patch("requests.get", side_effect=RuntimeError("net")):
        assert fetch_xai_models(api_key="k") == []


def test_custom_and_cache_error_paths(tmp_path, monkeypatch):
    custom_file = tmp_path / "custom.json"
    cache_file = tmp_path / "cache.json"
    monkeypatch.setattr("src.inventory.CUSTOM_MODELS_FILE", str(custom_file))
    monkeypatch.setattr("src.inventory.CACHE_FILE", str(cache_file))
    mgr = ModelInventoryManager()

    custom_file.write_text("{not-json")
    assert mgr.get_custom_models() == []
    custom_file.write_text('{"id": "not-a-list"}')
    assert mgr.get_custom_models() == []

    with pytest.raises(ValueError, match="Model ID"):
        mgr.save_custom_model({"display_name": "no id"})

    assert mgr.delete_custom_model("missing") is False
    assert mgr.load_cached_snapshot() is None
    cache_file.write_text("nope")
    assert mgr.load_cached_snapshot() is None

    cache_dir = tmp_path / "blocked.json"
    cache_dir.mkdir()
    monkeypatch.setattr("src.inventory.CACHE_FILE", str(cache_dir))
    mgr.save_cached_snapshot({"ok": True})

    monkeypatch.setattr("src.inventory.CACHE_FILE", str(tmp_path / "absent.json"))
    monkeypatch.setattr(mgr, "refresh_inventory", lambda **k: {"total_models": 3})
    assert mgr.get_inventory()["total_models"] == 3


def test_refresh_unknown_category(tmp_path, monkeypatch):
    custom_file = str(tmp_path / "custom.json")
    cache_file = str(tmp_path / "cache.json")
    monkeypatch.setattr("src.inventory.CUSTOM_MODELS_FILE", custom_file)
    monkeypatch.setattr("src.inventory.CACHE_FILE", cache_file)
    monkeypatch.setattr("src.inventory.fetch_byteplus_models", lambda *a, **k: [])
    monkeypatch.setattr("src.inventory.fetch_xai_models", lambda *a, **k: [])
    mgr = ModelInventoryManager()
    mgr.save_custom_model({"id": "ep-audio-1", "display_name": "Audio", "category": "audio"})
    snap = mgr.refresh_inventory()
    assert any(m["id"] == "ep-audio-1" for m in snap["catalog"]["audio"])

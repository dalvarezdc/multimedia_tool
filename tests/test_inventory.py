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

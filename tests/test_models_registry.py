"""Tests for BytePlus ModelArk complete catalog, layout profiles, and model selection."""

import os
import pytest
from src.models_registry import (
    MODEL_CATALOG,
    DEFAULT_VIDEO_MODEL,
    DEFAULT_DIRECTOR_MODEL,
    DEFAULT_IMAGE_MODEL,
    get_models_by_category,
    get_all_models_grouped,
    get_model_info
)

def test_model_catalog_completeness():
    assert len(MODEL_CATALOG) == 28
    
    expected_ids = [
        "skylark-embedding-vision-251215",
        "seedream-5-0-260128",
        "seed-2-0-mini-260215",
        "seed-2-0-lite-260228",
        "dreamina-seedance-2-0-260128",
        "dreamina-seedance-2-0-fast-260128",
        "seed-2-0-pro-260328",
        "hyper3d-gen2-260112",
        "hitem3d-2-0-251223",
        "seed-2-0-code-preview-260328",
        "seedream-4-0-20260415",
        "seed-2-0-mini-260428",
        "seed-2-0-lite-260428",
        "deepseek-v4-pro-260425",
        "deepseek-v4-flash-260425",
        "dreamina-seedance-2-0-mini-260615",
        "glm-5-2-260617",
        "dreamina-seedance-2-5-260628",
        "dola-seedream-5-0-pro-260628",
        "dola-seed-2-1-turbo-260628",
        "deepseek-v4-flash-ga-260731",
        "deepseek-v4-pro-ga-260813",
        "glm-5-3-flash-260828",
        "deepseek-v4-1-flash-260910",
        "bytedance-seedance-1-0-pro-fast-251015",
        "bytedance-seedance-1-5-pro-251215",
        "bytedance-seedream-4-5-251128",
        "grok-imagine-video-1.5",
    ]
    for mid in expected_ids:
        assert mid in MODEL_CATALOG, f"Missing model {mid} in catalog"

def test_categories_grouping():
    grouped = get_all_models_grouped()
    assert len(grouped["video"]) == 7
    assert len(grouped["director_llm"]) == 14
    assert len(grouped["image"]) == 4
    assert len(grouped["3d"]) == 2
    assert len(grouped["vision_embedding"]) == 1

def test_grok_video_capabilities():
    grok = get_model_info("grok-imagine-video-1.5")
    assert grok is not None
    assert grok.category == "video"
    assert grok.provider == "grok"
    assert 15 in grok.durations
    assert "16:9" in grok.ratios
    assert grok.resolutions == []


def test_seedance_25_capability_controls():
    m = get_model_info("dreamina-seedance-2-5-260628")
    assert "1080p" in m.resolutions
    assert 10 in m.durations
    assert m.supports_audio is True
    assert m.provider == "seedance"


def test_defaults():
    assert DEFAULT_VIDEO_MODEL == "dreamina-seedance-2-5-260628"
    assert DEFAULT_DIRECTOR_MODEL == "seed-2-0-lite-260228"
    assert DEFAULT_IMAGE_MODEL == "dola-seedream-5-0-pro-260628"

def test_ui_layout_profiles():
    # 1. Ref-to-video layout
    seedance20 = get_model_info("dreamina-seedance-2-0-fast-260128")
    assert seedance20.ui_layout_type == "video_ref"
    assert "Experience video generation" in seedance20.headline
    assert "@to quickly reference" in seedance20.placeholder
    assert seedance20.sample_cost == "USD 0.6048"

    # 2. First/Last frame layout
    seedance15 = get_model_info("bytedance-seedance-1-5-pro-251215")
    assert seedance15.ui_layout_type == "video_first_last"
    assert len(seedance15.input_slots) == 2
    assert seedance15.has_template_library is True
    assert seedance15.sample_cost == "USD 0.2592"

    # 3. First frame layout
    seedance10 = get_model_info("bytedance-seedance-1-0-pro-fast-251015")
    assert seedance10.ui_layout_type == "video_first"
    assert seedance10.sample_cost == "USD 0.1030"

    # 4. Image standard layout
    seedream50 = get_model_info("dola-seedream-5-0-pro-260628")
    assert seedream50.ui_layout_type == "image_standard"
    assert "Shake up your creativity with image generation" in seedream50.headline
    assert "0.180-0.360 USD" in seedream50.sample_cost

    # 5. Image group diagram layout
    seedream45 = get_model_info("bytedance-seedream-4-5-251128")
    assert seedream45.ui_layout_type == "image_group"
    assert "Generate group diagram" in seedream45.mode_selector["default"]
    assert "0.160 USD" in seedream45.sample_cost

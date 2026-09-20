"""Tests for BytePlus ModelArk 24-model catalog and model selection."""

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
    assert len(MODEL_CATALOG) == 24
    
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
        "deepseek-v4-1-flash-260910"
    ]
    for mid in expected_ids:
        assert mid in MODEL_CATALOG, f"Missing model {mid} in catalog"

def test_categories_grouping():
    grouped = get_all_models_grouped()
    assert len(grouped["video"]) == 4
    assert len(grouped["director_llm"]) == 14
    assert len(grouped["image"]) == 3
    assert len(grouped["3d"]) == 2
    assert len(grouped["vision_embedding"]) == 1

def test_defaults():
    assert DEFAULT_VIDEO_MODEL == "dreamina-seedance-2-5-260628"
    assert DEFAULT_DIRECTOR_MODEL == "seed-2-0-lite-260228"
    assert DEFAULT_IMAGE_MODEL == "seedream-5-0-260128"

def test_get_model_info():
    info = get_model_info("dreamina-seedance-2-5-260628")
    assert info is not None
    assert info.category == "video"
    assert "Flagship" in info.display_name

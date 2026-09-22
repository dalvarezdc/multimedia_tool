"""Model Inventory & Dynamic Discovery Service for BytePlus ModelArk and xAI APIs.

Provides:
1. Live model fetching from upstream BytePlus ModelArk and xAI endpoints.
2. Intelligent capability overlay mapping (ratios, durations, resolutions, layouts).
3. Snapshot caching to data/models_cache.json with graceful offline fallback.
4. Custom endpoint registration (for private or dedicated ep-... endpoints).
"""

import os
import json
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import asdict
import requests

from src.models_registry import (
    MODEL_CATALOG,
    ModelInfo,
    SAMPLE_INSPIRATIONS,
    DEFAULT_VIDEO_MODEL,
    DEFAULT_DIRECTOR_MODEL,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_AUDIO_MODEL,
)

logger = logging.getLogger("model_inventory")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CACHE_FILE = os.path.join(DATA_DIR, "models_cache.json")
CUSTOM_MODELS_FILE = os.path.join(DATA_DIR, "custom_models.json")


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def fetch_byteplus_models(api_key: str, base_url: str) -> List[Dict[str, Any]]:
    """Queries BytePlus ModelArk /api/v3/models and /api/v3/endpoints."""
    models = []
    headers = {"Authorization": f"Bearer {api_key}"}
    clean_base = base_url.rstrip("/")

    # 1. Standard /models list
    try:
        url = f"{clean_base}/models"
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            raw_list = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for item in raw_list:
                m_id = item.get("id") if isinstance(item, dict) else str(item)
                if m_id:
                    models.append({
                        "id": m_id,
                        "display_name": item.get("name") or m_id,
                        "provider": "seedance",
                        "created": item.get("created"),
                        "raw": item
                    })
        else:
            logger.info(f"BytePlus /models returned HTTP {resp.status_code}")
    except Exception as exc:
        logger.warning(f"Failed to fetch BytePlus models: {exc}")

    # 2. Deployed /endpoints list (if supported by account)
    try:
        url = f"{clean_base}/endpoints"
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            raw_list = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for item in raw_list:
                ep_id = item.get("id") or item.get("endpoint_id")
                if ep_id and not any(m["id"] == ep_id for m in models):
                    models.append({
                        "id": ep_id,
                        "display_name": item.get("name") or f"Endpoint {ep_id}",
                        "provider": "seedance",
                        "model_reference": item.get("model_id"),
                        "raw": item
                    })
    except Exception as exc:
        logger.debug(f"BytePlus /endpoints query: {exc}")

    return models


def fetch_xai_models(api_key: str, base_url: str = "https://api.x.ai/v1") -> List[Dict[str, Any]]:
    """Queries xAI /v1/models endpoint."""
    models = []
    headers = {"Authorization": f"Bearer {api_key}"}
    clean_base = base_url.rstrip("/")

    try:
        url = f"{clean_base}/models"
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            raw_list = data.get("data", []) if isinstance(data, dict) else []
            for item in raw_list:
                m_id = item.get("id")
                if m_id:
                    models.append({
                        "id": m_id,
                        "display_name": m_id.replace("-", " ").title(),
                        "provider": "grok",
                        "created": item.get("created"),
                        "raw": item
                    })
        else:
            logger.info(f"xAI /models returned HTTP {resp.status_code}")
    except Exception as exc:
        logger.warning(f"Failed to fetch xAI models: {exc}")

    return models


def infer_model_capabilities(model_id: str, provider: str = "seedance", display_name: Optional[str] = None) -> ModelInfo:
    """Infers rich capability overlay for any newly discovered or custom model."""
    mid = model_id.lower()
    name = display_name or model_id

    # 0. Grok Imagine stills — must run before the "imagine" video keyword
    if "grok" in mid and "image" in mid and "video" not in mid:
        return ModelInfo(
            id=model_id,
            display_name=name,
            category="image",
            description="xAI Grok Imagine image generation and editing model.",
            recommended_for="Text-to-image and reference-image edits on an xAI key.",
            ui_layout_type="image_standard",
            headline="Generate images with Grok Imagine",
            icon_type="image",
            placeholder="Describe the image. Attach references with @Pictures N.",
            input_slots=[{"id": "image", "label": "Image", "icon": "image"}],
            mode_selector={"enabled": True, "default": "Image generation", "options": ["Image generation", "Image edit"]},
            sample_cost="USD 0.0200",
            sample_examples=SAMPLE_INSPIRATIONS,
            provider=provider if provider in ("grok", "xai") else "grok",
            ratios=["16:9", "9:16", "1:1", "3:2", "2:3"],
            resolutions=["1K", "2K"],
            clip_counts=[1],
        )

    # 1. Video Models
    if any(k in mid for k in ["seedance", "video", "imagine", "animate", "motion"]):
        if any(k in mid for k in ["2.5", "2-5"]):
            return ModelInfo(
                id=model_id,
                display_name=name,
                category="video",
                description="BytePlus Seedance 2.5 Flagship Video Generation Model.",
                recommended_for="High-fidelity cinematic cutscenes, 1080p, audio generation.",
                ui_layout_type="video_ref",
                headline="Experience video generation and let creativity shake",
                icon_type="video",
                placeholder="Use @ to quickly reference uploaded files (e.g. @Pictures 1, @Video 1).",
                input_slots=[{"id": "reference", "label": "Reference", "icon": "plus"}],
                mode_selector={"enabled": True, "default": "Ref-to-video", "options": ["Ref-to-video", "Text-to-video"]},
                sample_cost="USD 0.6048",
                sample_examples=SAMPLE_INSPIRATIONS,
                provider=provider,
                ratios=["16:9", "9:16", "1:1", "4:3", "21:9"],
                resolutions=["720p", "1080p"],
                durations=[5, 10],
                supports_audio=True,
                clip_counts=[1]
            )
        elif any(k in mid for k in ["1.5", "1-5", "first-last"]):
            return ModelInfo(
                id=model_id,
                display_name=name,
                category="video",
                description="Seedance 1.5 Pro Keyframe Interpolation Model.",
                recommended_for="Controlled first-to-last frame morphing and draft workflows.",
                ui_layout_type="video_first_last",
                headline="Experience video generation and let creativity shake",
                icon_type="video",
                placeholder="Enter content screen you want to generate, or creative description in combination with frames.",
                input_slots=[
                    {"id": "first_frame", "label": "first frame", "icon": "plus"},
                    {"id": "last_frame", "label": "last frame", "icon": "plus"}
                ],
                sample_cost="USD 0.2592",
                has_template_library=True,
                sample_examples=SAMPLE_INSPIRATIONS,
                provider=provider,
                ratios=["16:9", "9:16", "1:1"],
                resolutions=["720p", "1080p"],
                durations=[5, 10],
                supports_audio=True,
                supports_draft=True,
                clip_counts=[1]
            )
        elif any(k in mid for k in ["fast", "mini", "1.0", "1-0"]):
            return ModelInfo(
                id=model_id,
                display_name=name,
                category="video",
                description="High-throughput fast video generation pipeline.",
                recommended_for="Rapid prototyping, quick cutscene drafts.",
                ui_layout_type="video_first",
                headline="Experience video generation and let creativity shake",
                icon_type="video",
                placeholder="Enter description based on image.",
                input_slots=[{"id": "first_frame", "label": "first frame", "icon": "plus"}],
                sample_cost="USD 0.1030",
                sample_examples=SAMPLE_INSPIRATIONS,
                provider=provider,
                ratios=["16:9", "9:16", "1:1"],
                resolutions=["720p"],
                durations=[5],
                supports_audio=False,
                clip_counts=[1]
            )
        else:
            # Generic Video
            return ModelInfo(
                id=model_id,
                display_name=name,
                category="video",
                description=f"{provider.capitalize()} Video Generation Model.",
                recommended_for="Video generation and dynamic cutscene rendering.",
                ui_layout_type="video_ref",
                headline="Experience video generation and let creativity shake",
                icon_type="video",
                placeholder="Enter description or reference assets with @Pictures 1 or @Video 1.",
                input_slots=[{"id": "reference", "label": "Reference", "icon": "plus"}],
                sample_cost="USD 0.4500",
                sample_examples=SAMPLE_INSPIRATIONS,
                provider=provider,
                ratios=["16:9", "9:16", "1:1"],
                resolutions=["720p", "1080p"],
                durations=[5, 10],
                supports_audio=True,
                clip_counts=[1]
            )

    # 2. Image Models
    if any(k in mid for k in ["seedream", "image", "dola", "diffusion", "sd"]):
        return ModelInfo(
            id=model_id,
            display_name=name,
            category="image",
            description=f"{provider.capitalize()} High-Fidelity Image Generation Model.",
            recommended_for="Character anchors, environmental textures, group diagram generation.",
            ui_layout_type="image_standard",
            headline="Shake up your creativity with image generation",
            icon_type="image",
            placeholder="Combine picture and enter creative description.",
            input_slots=[{"id": "image", "label": "Image", "icon": "image"}],
            mode_selector={"enabled": True, "default": "Image generation", "options": ["Image generation", "Group diagram"]},
            sample_cost="0.180-0.360 USD",
            sample_examples=SAMPLE_INSPIRATIONS,
            provider=provider,
            ratios=["16:9", "1:1", "9:16", "4:3", "3:4"],
            resolutions=["2K", "4K"],
            clip_counts=[1, 4]
        )

    # 3. Director / Planning LLMs
    if any(k in mid for k in ["seed-", "deepseek", "glm", "llm", "chat", "grok-2", "gpt", "claude"]):
        return ModelInfo(
            id=model_id,
            display_name=name,
            category="director_llm",
            description=f"{provider.capitalize()} Reasoning & Director Language Model.",
            recommended_for="Autonomous storyboard writing, quest structuring, dialogue logic.",
            ui_layout_type="generic",
            headline="Director Storyboard Intelligence",
            icon_type="llm",
            provider=provider
        )

    # 4. 3D Models
    if any(k in mid for k in ["3d", "hyper3d", "hitem", "mesh"]):
        return ModelInfo(
            id=model_id,
            display_name=name,
            category="3d",
            description="3D Asset & Mesh Generation Model.",
            recommended_for="Interactive RPG prop synthesis and character models.",
            ui_layout_type="generic",
            headline="3D Asset Generation",
            icon_type="3d",
            provider=provider
        )

    # 5. Audio / Music Models
    if "mureka" in mid or any(k in mid for k in ["audio", "song", "soundtrack", "instrumental", "bgm"]):
        return ModelInfo(
            id=model_id,
            display_name=name,
            category="audio",
            description=f"{provider.capitalize()} Audio & Music Generation Model ({model_id}).",
            recommended_for="Vocal songs, soundtracks, and background music.",
            ui_layout_type="audio_music",
            headline="Experience music generation and let melodies flow",
            icon_type="audio",
            placeholder="Describe your song theme, mood, tempo, or instrumentation.",
            input_slots=[{"id": "reference", "label": "Audio Ref", "icon": "plus"}],
            sample_cost="10 credits (~$0.10)",
            provider=provider if provider in ("mureka", "skywork") else "mureka",
            clip_counts=[1, 2, 3]
        )

    # Default fallback: Treat as video if provider is seedance/grok, else generic
    return ModelInfo(
        id=model_id,
        display_name=name,
        category="video" if provider in ("seedance", "grok") else "generic",
        description=f"Active {provider.capitalize()} Model Endpoint ({model_id}).",
        recommended_for="General multimedia generation.",
        ui_layout_type="video_ref" if provider in ("seedance", "grok") else "generic",
        headline="Experience multimedia generation",
        icon_type="video" if provider in ("seedance", "grok") else "generic",
        provider=provider
    )


class ModelInventoryManager:
    """Manages live API inventory, capability overlay merging, and disk persistence."""

    def __init__(self):
        _ensure_data_dir()

    def get_custom_models(self) -> List[Dict[str, Any]]:
        """Reads custom registered model endpoints."""
        if not os.path.exists(CUSTOM_MODELS_FILE):
            return []
        try:
            with open(CUSTOM_MODELS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Failed to read custom models file: {e}")
            return []

    def save_custom_model(self, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """Registers a custom model endpoint (e.g. ep-...) and persists it."""
        model_id = model_data.get("id")
        if not model_id:
            raise ValueError("Model ID is required")

        customs = self.get_custom_models()
        # Remove existing if overwriting
        customs = [m for m in customs if m.get("id") != model_id]

        provider = model_data.get("provider", "seedance")
        display_name = model_data.get("display_name", model_id)
        category = model_data.get("category")

        inferred = infer_model_capabilities(model_id, provider=provider, display_name=display_name)
        inferred_dict = asdict(inferred)
        if category:
            inferred_dict["category"] = category
        inferred_dict["is_custom"] = True
        inferred_dict["source"] = "custom_endpoint"
        inferred_dict["is_live"] = True

        customs.append(inferred_dict)
        with open(CUSTOM_MODELS_FILE, "w", encoding="utf-8") as f:
            json.dump(customs, f, indent=2)

        # Invalidate/refresh snapshot cache
        self.refresh_inventory()
        return inferred_dict

    def delete_custom_model(self, model_id: str) -> bool:
        """Removes a custom registered model endpoint."""
        customs = self.get_custom_models()
        initial_len = len(customs)
        customs = [m for m in customs if m.get("id") != model_id]
        if len(customs) == initial_len:
            return False
        with open(CUSTOM_MODELS_FILE, "w", encoding="utf-8") as f:
            json.dump(customs, f, indent=2)
        self.refresh_inventory()
        return True

    def load_cached_snapshot(self) -> Optional[Dict[str, Any]]:
        """Loads cached snapshot from disk if present."""
        if not os.path.exists(CACHE_FILE):
            return None
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.warning(f"Failed to read cache file: {e}")
            return None

    def save_cached_snapshot(self, snapshot: Dict[str, Any]):
        """Persists snapshot to cache file."""
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save models cache: {e}")

    def sync_from_apis(
        self,
        ark_key: Optional[str] = None,
        xai_key: Optional[str] = None,
        ark_base_url: Optional[str] = None,
        xai_base_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Queries active upstream APIs and returns raw discovered model records."""
        discovered = []

        ark_key = ark_key or os.getenv("ARK_API_KEY")
        ark_base = ark_base_url or os.getenv("ARK_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")
        if ark_key:
            bp_models = fetch_byteplus_models(api_key=ark_key, base_url=ark_base)
            discovered.extend(bp_models)

        xai_key = xai_key or os.getenv("XAI_API_KEY")
        xai_base = xai_base_url or os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
        if xai_key:
            x_models = fetch_xai_models(api_key=xai_key, base_url=xai_base)
            discovered.extend(x_models)

        return discovered

    def merge_inventory(
        self,
        live_models: List[Dict[str, Any]],
        custom_models: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Merges live models, custom models, and capability overlay catalog.
        Returns a dictionary of model_id -> model_dict.
        """
        catalog_map: Dict[str, Dict[str, Any]] = {}

        # 1. Seed with known capability overlay presets
        for mid, minfo in MODEL_CATALOG.items():
            mdict = asdict(minfo)
            mdict["source"] = "catalog_preset"
            mdict["is_live"] = False
            catalog_map[mid] = mdict

        # 2. Merge Live Models from API
        for live in live_models:
            mid = live["id"]
            if mid in catalog_map:
                # Matched known catalog model: mark as live!
                catalog_map[mid]["is_live"] = True
                catalog_map[mid]["source"] = "live_api"
                if live.get("display_name") and live["display_name"] != mid:
                    catalog_map[mid]["display_name"] = live["display_name"]
            else:
                # Newly discovered live model or endpoint ID: infer capabilities
                inferred = infer_model_capabilities(
                    model_id=mid,
                    provider=live.get("provider", "seedance"),
                    display_name=live.get("display_name")
                )
                mdict = asdict(inferred)
                mdict["source"] = "live_api"
                mdict["is_live"] = True
                catalog_map[mid] = mdict

        # 3. Merge User Custom Endpoints
        for cust in custom_models:
            mid = cust["id"]
            catalog_map[mid] = cust

        return catalog_map

    def refresh_inventory(
        self,
        ark_key: Optional[str] = None,
        xai_key: Optional[str] = None,
        ark_base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetches from live APIs, merges with capability overlay, and caches snapshot."""
        live_models = self.sync_from_apis(
            ark_key=ark_key,
            xai_key=xai_key,
            ark_base_url=ark_base_url
        )
        custom_models = self.get_custom_models()
        merged_map = self.merge_inventory(live_models, custom_models)

        # Categorize
        grouped: Dict[str, List[Dict[str, Any]]] = {
            "video": [],
            "image": [],
            "audio": [],
            "director_llm": [],
            "3d": [],
            "vision_embedding": [],
            "generic": []
        }

        live_count = 0
        for m in merged_map.values():
            cat = m.get("category", "generic")
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(m)
            if m.get("is_live"):
                live_count += 1

        snapshot = {
            "last_synced_at": time.time(),
            "last_synced_str": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "total_models": len(merged_map),
            "live_count": live_count,
            "custom_count": len(custom_models),
            "providers_checked": {
                "byteplus": bool(ark_key or os.getenv("ARK_API_KEY")),
                "xai": bool(xai_key or os.getenv("XAI_API_KEY")),
                "mureka": bool(os.getenv("MUREKA_API_KEY"))
            },
            "catalog": grouped,
            "all_models": list(merged_map.values()),
            "active_video_model": os.getenv("ARK_SEEDANCE_MODEL", DEFAULT_VIDEO_MODEL),
            "active_director_model": os.getenv("ARK_LLM_MODEL", DEFAULT_DIRECTOR_MODEL),
            "active_image_model": os.getenv("ARK_SEEDREAM_MODEL", DEFAULT_IMAGE_MODEL),
            "active_audio_model": os.getenv("MUREKA_MODEL", DEFAULT_AUDIO_MODEL)
        }

        self.save_cached_snapshot(snapshot)
        return snapshot

    def get_inventory(self) -> Dict[str, Any]:
        """Returns the current inventory from cache, or performs an initial sync."""
        cached = self.load_cached_snapshot()
        if cached:
            return cached
        return self.refresh_inventory()


# Global singleton
inventory_manager = ModelInventoryManager()

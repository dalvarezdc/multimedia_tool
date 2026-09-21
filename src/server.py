"""FastAPI Backend Server for the Multimedia Tool Studio.

Exposes REST endpoints for:
1. Settings & API Key Configuration (/api/settings)
2. ModelArk Catalog (/api/models)
3. Director Storyboard Planning (/api/plan)
4. Seedance / Grok Cutscene Generation (/api/cutscenes/generate)
5. Task Status Polling (/api/cutscenes/status/{id})
6. Web App & Landing Page Serving (/ and /app) when SERVE_UI=1
"""

import os
import json
import logging
import time
import uuid
import shutil
from typing import Optional, Dict, Any, List
import requests
from pydantic import BaseModel, Field
from src.director.planner import DirectorPlanner
from src.generators import get_video_generator, get_image_generator
from src.qa.audit import VideoQAAgent
from src.models_registry import (
    MODEL_CATALOG,
    DEFAULT_DIRECTOR_MODEL,
    DEFAULT_VIDEO_MODEL,
    DEFAULT_IMAGE_MODEL,
    get_all_models_grouped,
    calculate_model_cost,
)
from src.inventory import inventory_manager
from src.auth import AuthStore, build_auth_router, current_user, load_or_create_secret, persist_generation


def _env_enabled(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
except ImportError:
    FastAPI = None


logger = logging.getLogger("multimedia_server")

class SettingsRequest(BaseModel):
    ark_api_key: Optional[str] = None
    xai_api_key: Optional[str] = None
    ark_base_url: Optional[str] = None
    provider: Optional[str] = None
    director_model: Optional[str] = None
    video_model: Optional[str] = None
    rpg_resolution: Optional[str] = None
    chapter_count: Optional[int] = Field(default=None, ge=2, le=8)

class CustomModelRequest(BaseModel):
    id: str
    display_name: Optional[str] = None
    category: Optional[str] = "video"
    provider: Optional[str] = "seedance"


class PlanRequest(BaseModel):
    topic: str = ""
    global_context: Optional[Dict[str, str]] = None
    character_profile: Optional[Dict[str, Any]] = None
    chapter_count: int = Field(default=4, ge=2, le=8)
    api_key: Optional[str] = None
    director_model: Optional[str] = None
    purpose: str = "storyboard"
    storyboard: Optional[Dict[str, Any]] = None
    instruction: Optional[str] = None

class CutsceneGenerateRequest(BaseModel):
    chapter_id: int
    prompt: str
    duration_seconds: int = 5
    character_reference_image: Optional[str] = None
    provider: str = Field(default="seedance", description="'seedance' (BytePlus) or 'grok' (xAI)")
    generation_mode: str = Field(default="ref_to_video", description="'ref_to_video', 'first_last_frame', or 'ip_effects'")
    first_frame_image: Optional[str] = None
    last_frame_image: Optional[str] = None
    ip_effect_name: Optional[str] = None
    api_key: Optional[str] = None
    video_model: Optional[str] = None
    ratio: str = "16:9"
    resolution: str = "720p"
    generate_audio: bool = True
    draft_mode: bool = False
    reference_assets: Optional[List[Dict[str, Any]]] = None

class ImageGenerateRequest(BaseModel):
    task_id: Optional[str] = None
    chapter_id: Optional[int] = None
    prompt: str
    image_model: Optional[str] = None
    model: Optional[str] = None
    ratio: str = "16:9"
    resolution: str = "2K"
    provider: str = "seedream"
    reference_assets: Optional[List[Dict[str, Any]]] = None
    api_key: Optional[str] = None
    watermark: bool = False

class MasterRenderRequest(BaseModel):
    storyboard: Dict[str, Any]
    output_filename: str = "master_video.mp4"

def create_app():
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Run 'uv pip install -r requirements.txt' to use the web server.")

    app = FastAPI(
        title="Multimedia Tool Studio API",
        description="Backend API for Retro Pixel Animation & Multimodal Video Generation with ByteDance Seedance & SeeDream",
        version="0.3.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url="/api/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    store = {
        "storyboard": None,
        "tasks": {},
        "usage_records": [],
        "reference_assets": []
    }

    ui_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")
    data_dir = os.getenv("MULTIMEDIA_DATA_DIR") or os.path.join(os.path.dirname(ui_dir), "data")
    uploads_dir = os.getenv("MULTIMEDIA_UPLOADS_DIR") or os.path.join(os.path.dirname(ui_dir), "uploads", "reference_assets")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(uploads_dir, exist_ok=True)
    assets_db_path = os.path.join(data_dir, "reference_assets.json")
    auth_store = AuthStore(data_dir)
    app.include_router(build_auth_router(auth_store, load_or_create_secret(data_dir)))

    def _save_reference_assets():
        try:
            os.makedirs(data_dir, exist_ok=True)
            with open(assets_db_path, "w", encoding="utf-8") as f:
                json.dump(store["reference_assets"], f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist reference assets: {e}")

    def _load_reference_assets():
        loaded = []
        if os.path.exists(assets_db_path):
            try:
                with open(assets_db_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load persisted reference assets: {e}")
                loaded = []

        valid_records = []
        for item in loaded:
            lp = item.get("local_path")
            if lp and os.path.exists(lp):
                valid_records.append(item)
            else:
                fn = os.path.basename(item.get("url") or item.get("filename") or "")
                fallback_path = os.path.join(uploads_dir, fn)
                if fn and os.path.exists(fallback_path):
                    item["local_path"] = fallback_path
                    valid_records.append(item)

        existing_filenames = {os.path.basename(r.get("local_path", "")) for r in valid_records}
        if os.path.exists(uploads_dir):
            video_extensions = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
            image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
            disk_files = sorted(os.listdir(uploads_dir))
            for df in disk_files:
                if df.startswith(".") or df in existing_filenames:
                    continue
                ext = os.path.splitext(df)[1].lower()
                if ext not in video_extensions and ext not in image_extensions:
                    continue
                file_path = os.path.join(uploads_dir, df)
                if not os.path.isfile(file_path):
                    continue

                parts = df.split("_", 1)
                if len(parts) == 2 and len(parts[0]) == 8:
                    uid = parts[0]
                    orig_name = parts[1]
                else:
                    uid = str(uuid.uuid4())[:8]
                    orig_name = df

                is_video = ext in video_extensions
                asset_type = "video" if is_video else "image"
                valid_records.append({
                    "id": uid,
                    "filename": orig_name,
                    "type": asset_type,
                    "token": "",
                    "url": f"/uploads/reference_assets/{df}",
                    "local_path": file_path,
                    "size": os.path.getsize(file_path),
                    "uploaded_at": os.path.getmtime(file_path)
                })
                existing_filenames.add(df)

        img_idx = 1
        vid_idx = 1
        for a in valid_records:
            if a["type"] == "image":
                a["token"] = f"@Pictures {img_idx}"
                img_idx += 1
            else:
                a["token"] = f"@Video {vid_idx}"
                vid_idx += 1

        store["reference_assets"] = valid_records
        _save_reference_assets()
        return store["reference_assets"]

    _load_reference_assets()

    # =========================================================================
    # 1. SETTINGS & CREDENTIALS API
    # =========================================================================
    @app.get("/api/settings")
    def get_settings():
        """Returns configured status of keys and active models without exposing secrets."""
        ark_key = os.getenv("ARK_API_KEY", "")
        xai_key = os.getenv("XAI_API_KEY", "")
        return {
            "has_ark_key": bool(ark_key),
            "has_xai_key": bool(xai_key),
            "ark_base_url": os.getenv("ARK_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3"),
            "provider": os.getenv("DEFAULT_VIDEO_PROVIDER", "seedance"),
            "director_model": os.getenv("ARK_LLM_MODEL", DEFAULT_DIRECTOR_MODEL),
            "video_model": os.getenv("ARK_SEEDANCE_MODEL", DEFAULT_VIDEO_MODEL),
            "image_model": os.getenv("ARK_SEEDREAM_MODEL", DEFAULT_IMAGE_MODEL),
            "rpg_resolution": os.getenv("RPG_CANVAS_RESOLUTION", "1080p"),
            "chapter_count": int(os.getenv("RPG_CHAPTER_COUNT", "4")),
            "ark_key_masked": f"...{ark_key[-4:]}" if len(ark_key) >= 4 else ("✓ Configured" if ark_key else ""),
            "xai_key_masked": f"...{xai_key[-4:]}" if len(xai_key) >= 4 else ("✓ Configured" if xai_key else "")
        }

    @app.post("/api/settings")
    def update_settings(req: SettingsRequest):
        """Allows setting API keys, endpoints, and active models manually."""
        updated = []
        if req.ark_api_key and req.ark_api_key.strip():
            os.environ["ARK_API_KEY"] = req.ark_api_key.strip()
            updated.append("BytePlus ARK_API_KEY")
        if req.xai_api_key and req.xai_api_key.strip():
            os.environ["XAI_API_KEY"] = req.xai_api_key.strip()
            updated.append("xAI XAI_API_KEY")
        if req.ark_base_url and req.ark_base_url.strip():
            os.environ["ARK_BASE_URL"] = req.ark_base_url.strip()
            updated.append("ARK_BASE_URL")
        if req.provider and req.provider.strip():
            os.environ["DEFAULT_VIDEO_PROVIDER"] = req.provider.strip()
            updated.append("DEFAULT_VIDEO_PROVIDER")
        if req.director_model and req.director_model.strip():
            os.environ["ARK_LLM_MODEL"] = req.director_model.strip()
            updated.append(f"Director Model ({req.director_model.strip()})")
        if req.video_model and req.video_model.strip():
            os.environ["ARK_SEEDANCE_MODEL"] = req.video_model.strip()
            updated.append(f"Video Model ({req.video_model.strip()})")
        if req.rpg_resolution and req.rpg_resolution.strip():
            os.environ["RPG_CANVAS_RESOLUTION"] = req.rpg_resolution.strip()
            updated.append(f"RPG Resolution ({req.rpg_resolution.strip()})")
        if req.chapter_count:
            os.environ["RPG_CHAPTER_COUNT"] = str(req.chapter_count)
            updated.append(f"Chapter Count ({req.chapter_count})")

        logger.info(f"Updated runtime settings: {', '.join(updated)}")
        return {
            "status": "success",
            "message": f"Updated {len(updated)} settings successfully.",
            "updated": updated
        }

    @app.post("/api/settings/test-connection")
    def test_connection(req: SettingsRequest):
        """Hits the provider base URL with the configured key. 401 means a bad key."""
        provider = (req.provider or os.getenv("DEFAULT_VIDEO_PROVIDER", "seedance")).lower()
        if provider in ("seedance", "byteplus", "bytedance"):
            key = req.ark_api_key or os.getenv("ARK_API_KEY")
            base = req.ark_base_url or os.getenv("ARK_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")
            label = "BytePlus ModelArk"
        else:
            key = req.xai_api_key or os.getenv("XAI_API_KEY")
            base = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
            label = "xAI"
        if not key:
            return {"status": "error", "message": f"{label} API key is not configured."}
        try:
            resp = requests.get(
                base.rstrip("/"),
                headers={"Authorization": f"Bearer {key}"},
                timeout=8,
            )
            if resp.status_code == 401:
                return {"status": "error", "message": f"{label} rejected the API key (401)."}
            return {
                "status": "success",
                "message": f"{label} reachable (HTTP {resp.status_code}). Key was sent."
            }
        except requests.RequestException as exc:
            return {"status": "error", "message": f"Could not reach {label}: {exc}"}

    @app.get("/api/usage")
    def get_usage(request: Request):
        """Returns usage records and system metrics."""
        user = current_user(request, auth_store)
        if user:
            hist = auth_store.list_history(user["id"])
            records = [
                {
                    "id": h["id"],
                    "timestamp": time.strftime("%Y-%m-%d %H:%M", time.localtime(h["created_at"])),
                    "service": "Multimedia Studio",
                    "model": h.get("model"),
                    "mode": h.get("mode"),
                    "prompt": h.get("prompt"),
                    "duration": f"{h.get('elapsed_seconds') or 0}s",
                    "status": "succeeded",
                    "path": h.get("path"),
                    "watermark_free": True,
                }
                for h in hist
            ]
        else:
            records = store["usage_records"]
        total = len(records)
        wm = sum(1 for r in records if r.get("watermark_free"))
        return {
            "total_generations": total,
            "video_generations": sum(1 for r in records if r["service"] == "AI Video Studio"),
            "rpg_renders": sum(1 for r in records if r["service"] == "RPG Studio"),
            "watermark_free_rate": f"{int(100 * wm / total)}%" if total else "n/a",
            "active_tasks": len([t for t in store["tasks"].values() if t.get("status") == "processing"]),
            "records": records
        }

    @app.get("/api/cost/estimate")
    def estimate_cost(
        model: str,
        duration: int = 5,
        resolution: str = "720p",
        clips: int = 1,
        audio: bool = True,
        draft: bool = False,
        ref_count: int = 0
    ):
        """Returns accurate cost estimate based on official BytePlus ModelArk and xAI pricing."""
        cost_str = calculate_model_cost(
            model_id=model,
            duration=duration,
            resolution=resolution,
            clip_count=clips,
            audio=audio,
            draft_mode=draft,
            reference_asset_count=ref_count
        )
        return {
            "model": model,
            "cost": cost_str,
            "duration": duration,
            "resolution": resolution,
            "clips": clips
        }

    # =========================================================================
    # 2. MODELARK CATALOG & LIVE INVENTORY API
    # =========================================================================
    @app.get("/api/models")
    def list_available_models():
        """Returns dynamic merged model inventory with live API status."""
        return inventory_manager.get_inventory()

    @app.post("/api/models/refresh")
    def refresh_models(req: Optional[SettingsRequest] = None):
        """Fetches live models from BytePlus ModelArk and xAI APIs,
        merges with capability overlays, and caches snapshot.
        """
        ark_key = (req.ark_api_key if req else None) or os.getenv("ARK_API_KEY")
        xai_key = (req.xai_api_key if req else None) or os.getenv("XAI_API_KEY")
        ark_base = (req.ark_base_url if req else None) or os.getenv("ARK_BASE_URL")
        snapshot = inventory_manager.refresh_inventory(
            ark_key=ark_key,
            xai_key=xai_key,
            ark_base_url=ark_base
        )
        return {
            "status": "success",
            "message": f"Synced {snapshot['total_models']} models ({snapshot['live_count']} live in API).",
            "snapshot": snapshot
        }

    @app.post("/api/models/custom")
    def add_custom_model(req: CustomModelRequest):
        """Registers a custom model ID or deployed endpoint ID (e.g. ep-...)."""
        if not req.id.strip():
            raise HTTPException(status_code=400, detail="Model/Endpoint ID is required.")
        created = inventory_manager.save_custom_model(req.model_dump())
        return {"status": "success", "model": created}

    @app.delete("/api/models/custom/{model_id}")
    def delete_custom_model(model_id: str):
        """Deletes a custom registered model endpoint."""
        deleted = inventory_manager.delete_custom_model(model_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Custom model endpoint not found.")
        return {"status": "success", "message": f"Custom model {model_id} removed."}


    # =========================================================================
    # 3. STORYBOARD PLANNING API
    # =========================================================================
    @app.post("/api/plan")
    def plan_storyboard(req: PlanRequest):
        """Invokes Director LLM to generate an initial roadmap from topic and context."""
        api_key = req.api_key or os.getenv("ARK_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail="ARK_API_KEY is required to generate a storyboard. Please set it in API Keys or in .env."
            )
        if not req.storyboard and not req.topic.strip():
            raise HTTPException(status_code=400, detail="Provide a topic, or an existing storyboard to improve.")

        model_id = req.director_model or os.getenv("ARK_LLM_MODEL", DEFAULT_DIRECTOR_MODEL)

        try:
            planner = DirectorPlanner(api_key=api_key, model_id=model_id)
            if req.storyboard:
                storyboard = planner.improve_storyboard(
                    req.storyboard,
                    instruction=req.instruction,
                )
            else:
                storyboard = planner.plan_storyboard(
                    topic_or_transcript=req.topic,
                    global_context=req.global_context,
                    character_profile=req.character_profile,
                    chapter_count=req.chapter_count,
                    purpose=req.purpose,
                )
            store["storyboard"] = storyboard
            store["usage_records"].insert(0, {
                "id": f"rpg-{int(time.time())}",
                "timestamp": time.strftime("%Y-%m-%d %H:%M"),
                "service": "RPG Studio",
                "model": model_id,
                "mode": "improve" if req.storyboard else req.purpose,
                "prompt": req.topic or storyboard.get("theme", "storyboard"),
                "duration": f"{len(storyboard.get('chapters', []))} shrines",
                "status": "succeeded",
                "watermark_free": False
            })
            return {"status": "success", "storyboard": storyboard, "director_model": model_id}
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/storyboard")
    def get_storyboard():
        """Returns the active storyboard."""
        if not store["storyboard"]:
            raise HTTPException(status_code=404, detail="No active storyboard. Plan one first via /api/plan.")
        return store["storyboard"]

    @app.post("/api/storyboard/update")
    def update_storyboard(storyboard: Dict[str, Any]):
        """Updates the active storyboard in memory."""
        store["storyboard"] = storyboard
        return {"status": "updated", "storyboard": storyboard}

    # =========================================================================
    # 3.5. ASSET UPLOAD & MULTIMODAL REFERENCE API
    # =========================================================================
    @app.post("/api/upload")
    def upload_reference_assets(files: list[UploadFile] = File(...)):
        """Uploads one or more reference images/videos for Ref-to-video mode.
        Assigns standard ByteDance ModelArk reference tokens (@Pictures N, @Video N).
        """
        uploaded_assets = []
        video_extensions = {".mp4", ".mov", ".webm", ".avi", ".mkv"}

        for file in files:
            original_name = file.filename or "upload.bin"
            ext = os.path.splitext(original_name)[1].lower()
            is_video = ext in video_extensions or (file.content_type and "video" in file.content_type)

            asset_type = "video" if is_video else "image"

            existing_type_count = sum(1 for a in store["reference_assets"] if a["type"] == asset_type)
            new_idx = existing_type_count + 1
            token = f"@Video {new_idx}" if asset_type == "video" else f"@Pictures {new_idx}"

            unique_id = str(uuid.uuid4())[:8]
            safe_basename = os.path.basename(original_name).replace(" ", "_")
            safe_filename = f"{unique_id}_{safe_basename}"
            target_path = os.path.join(uploads_dir, safe_filename)

            with open(target_path, "wb") as f_out:
                shutil.copyfileobj(file.file, f_out)

            file_size = os.path.getsize(target_path)

            asset_record = {
                "id": unique_id,
                "filename": original_name,
                "type": asset_type,
                "token": token,
                "url": f"/uploads/reference_assets/{safe_filename}",
                "local_path": target_path,
                "size": file_size,
                "uploaded_at": time.time()
            }
            store["reference_assets"].append(asset_record)
            uploaded_assets.append(asset_record)

        _save_reference_assets()
        return {
            "status": "success",
            "uploaded": uploaded_assets,
            "assets": store["reference_assets"]
        }

    @app.get("/api/upload/assets")
    def get_reference_assets():
        """Returns all imported reference assets, synced with disk."""
        _load_reference_assets()
        return {"assets": store["reference_assets"]}

    @app.delete("/api/upload/assets/{asset_id}")
    def delete_reference_asset(asset_id: str):
        """Removes a reference asset and re-indexes tokens."""
        target = next((a for a in store["reference_assets"] if a["id"] == asset_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Asset not found")

        if "local_path" in target and os.path.exists(target["local_path"]):
            try:
                os.remove(target["local_path"])
            except OSError as e:
                logger.warning(f"Failed to delete {target['local_path']}: {e}")

        store["reference_assets"] = [a for a in store["reference_assets"] if a["id"] != asset_id]

        # Re-index tokens for remaining assets
        img_idx = 1
        vid_idx = 1
        for a in store["reference_assets"]:
            if a["type"] == "image":
                a["token"] = f"@Pictures {img_idx}"
                img_idx += 1
            else:
                a["token"] = f"@Video {vid_idx}"
                vid_idx += 1

        _save_reference_assets()
        return {"status": "deleted", "assets": store["reference_assets"]}

    @app.delete("/api/upload/assets")
    def clear_all_reference_assets():
        """Clears all reference assets."""
        for a in store["reference_assets"]:
            if "local_path" in a and os.path.exists(a["local_path"]):
                try:
                    os.remove(a["local_path"])
                except OSError as e:
                    logger.warning(f"Failed to clear {a['local_path']}: {e}")
        store["reference_assets"] = []
        _save_reference_assets()
        return {"status": "cleared", "assets": []}


    # =========================================================================
    # 4. MULTIMEDIA GENERATION API (SEEDANCE / SEEDREAM / GROK)
    # =========================================================================
    @app.get("/api/history")
    def list_generation_history(request: Request):
        user = current_user(request, auth_store)
        if not user:
            return {"authenticated": False, "records": []}
        return {"authenticated": True, "records": auth_store.list_history(user["id"])}

    @app.post("/api/images/generate")
    def generate_image(req: ImageGenerateRequest, background_tasks: BackgroundTasks, request: Request):
        """Submits an asynchronous image generation task (SeeDream or Grok Imagine)."""
        history_user_id = (current_user(request, auth_store) or {}).get("id")
        image_model_id = req.image_model or req.model or DEFAULT_IMAGE_MODEL
        provider = (req.provider or "").lower()
        is_grok = provider in ("grok", "xai") or "grok" in (image_model_id or "").lower()
        if is_grok:
            xai_key = req.api_key or os.getenv("XAI_API_KEY")
            if not xai_key:
                raise HTTPException(status_code=400, detail="XAI_API_KEY missing. Please configure in Settings.")
            image_provider = "grok"
        else:
            ark_key = req.api_key or os.getenv("ARK_API_KEY")
            if not ark_key:
                raise HTTPException(status_code=400, detail="ARK_API_KEY missing. Please configure in Settings.")
            image_provider = "seedream"

        img_dir = os.path.join(os.path.dirname(ui_dir), "renders", "images")
        os.makedirs(img_dir, exist_ok=True)

        cid = req.chapter_id if req.chapter_id is not None else (int(req.task_id) if (req.task_id and req.task_id.isdigit()) else int(time.time() * 1000) % 100000)
        task_id = str(cid)
        img_path = os.path.join(img_dir, f"img_{task_id}.png")
        start_ts = time.time()

        task_entry = {
            "status": "generating",
            "stage": "submitting",
            "stage_label": "Submitting…",
            "elapsed_seconds": 0,
            "path": None,
            "started_at": start_ts,
            "generation_mode": "image_generation",
            "model": image_model_id,
            "model_used": image_model_id,
            "watermark_free": True,
            "type": "image"
        }
        store["tasks"][cid] = task_entry
        store["tasks"][task_id] = task_entry

        def _on_status(stage: str, meta: Dict[str, Any]):
            elapsed = int(time.time() - start_ts)
            msg = meta.get("message") or f"{stage.capitalize()}..."
            t = store["tasks"].get(cid, {})
            t.update({
                "status": "processing",
                "stage": stage,
                "stage_label": msg,
                "elapsed_seconds": elapsed,
                "model": image_model_id,
                "type": "image"
            })
            store["tasks"][cid] = t
            store["tasks"][task_id] = t

        def _worker():
            try:
                generator = get_image_generator(
                    provider=image_provider,
                    api_key=req.api_key,
                    model_id=image_model_id
                )

                resolved_assets = []
                for ref in (req.reference_assets or []):
                    if not isinstance(ref, dict):
                        continue
                    asset_id = ref.get("id")
                    stored = next((a for a in store["reference_assets"] if a["id"] == asset_id), None)
                    if stored:
                        resolved_assets.append(stored)
                    else:
                        local_path = ref.get("local_path")
                        if not local_path or not os.path.exists(local_path):
                            cand_name = os.path.basename(ref.get("url") or ref.get("filename") or "")
                            cand_path = os.path.join(uploads_dir, cand_name)
                            if cand_name and os.path.exists(cand_path):
                                local_path = cand_path
                        if local_path and os.path.exists(local_path):
                            resolved_assets.append({
                                "id": asset_id or str(uuid.uuid4())[:8],
                                "filename": ref.get("filename") or os.path.basename(local_path),
                                "type": ref.get("type", "image"),
                                "token": ref.get("token", ""),
                                "local_path": local_path,
                                "url": ref.get("url", f"/uploads/reference_assets/{os.path.basename(local_path)}")
                            })

                generator.generate_image(
                    prompt=req.prompt,
                    output_path=img_path,
                    reference_assets=resolved_assets or None,
                    ratio=req.ratio,
                    resolution=req.resolution,
                    watermark=req.watermark,
                    status_callback=_on_status
                )

                public_path = f"/renders/images/img_{task_id}.png"
                total_elapsed = int(time.time() - start_ts)
                success_entry = {
                    "status": "succeeded",
                    "stage": "complete",
                    "stage_label": "Ready",
                    "elapsed_seconds": total_elapsed,
                    "path": public_path,
                    "generation_mode": "image_generation",
                    "model": image_model_id,
                    "model_used": image_model_id,
                    "type": "image"
                }
                store["tasks"][cid] = success_entry
                est_cost = calculate_model_cost(
                    model_id=image_model_id,
                    resolution=req.resolution,
                    clip_count=1,
                    reference_asset_count=len(resolved_assets) if resolved_assets else 0
                )
                store["usage_records"].insert(0, {
                    "id": f"img-{task_id}",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M"),
                    "service": "Multimedia Studio",
                    "model": image_model_id,
                    "mode": "image_generation",
                    "prompt": req.prompt,
                    "duration": "image",
                    "cost": est_cost,
                    "status": "succeeded",
                    "watermark_free": True
                })
                persist_generation(auth_store, history_user_id, {
                    "id": f"img-{task_id}",
                    "title": (req.prompt or "Generated image")[:80],
                    "prompt": req.prompt,
                    "model": image_model_id,
                    "mode": "image_generation",
                    "media_type": "image",
                    "path": public_path,
                    "elapsed_seconds": total_elapsed,
                })
            except Exception as e:
                logger.error(f"Image generation failed for task {task_id}: {e}", exc_info=True)
                err_entry = {
                    "status": "failed",
                    "stage": "failed",
                    "stage_label": "Failed",
                    "error": str(e),
                    "model": image_model_id,
                    "type": "image"
                }
                store["tasks"][cid] = err_entry
                store["tasks"][task_id] = err_entry

        background_tasks.add_task(_worker)
        return {
            "status": "started",
            "task_id": task_id,
            "chapter_id": cid,
            "model": image_model_id,
            "type": "image"
        }

    @app.post("/api/cutscenes/generate")
    def generate_cutscene(req: CutsceneGenerateRequest, background_tasks: BackgroundTasks, request: Request):
        """Submits an asynchronous cutscene or image generation task with zero watermark guarantee."""
        history_user_id = (current_user(request, auth_store) or {}).get("id")
        provider = req.provider.lower()

        # Seamless routing to image generation if an image model or mode is requested
        is_image_req = (
            provider in ("seedream", "image")
            or (req.video_model and (
                "seedream" in req.video_model.lower()
                or "dola" in req.video_model.lower()
                or "grok-imagine-image" in req.video_model.lower()
            ))
            or req.generation_mode == "image_generation"
        )
        if is_image_req:
            img_req = ImageGenerateRequest(
                task_id=str(req.chapter_id),
                chapter_id=req.chapter_id,
                prompt=req.prompt,
                image_model=req.video_model or "dola-seedream-5-0-pro-260628",
                model=req.video_model,
                ratio=req.ratio,
                resolution=req.resolution,
                provider="seedream",
                reference_assets=req.reference_assets,
                api_key=req.api_key,
                watermark=False
            )
            return generate_image(img_req, background_tasks, request)

        # Validate API keys before backgrounding
        if provider in ("seedance", "byteplus", "bytedance"):
            ark_key = req.api_key or os.getenv("ARK_API_KEY")
            if not ark_key:
                raise HTTPException(status_code=400, detail="ARK_API_KEY missing. Please configure in Settings.")
        elif provider == "grok":
            xai_key = req.api_key or os.getenv("XAI_API_KEY")
            if not xai_key:
                raise HTTPException(status_code=400, detail="XAI_API_KEY missing. Please configure in Settings.")

        clip_dir = os.path.join(os.path.dirname(ui_dir), "renders", "cutscenes")
        os.makedirs(clip_dir, exist_ok=True)
        clip_path = os.path.join(clip_dir, f"chapter_{req.chapter_id}.mp4")

        video_model_id = req.video_model or (
            "grok-imagine-video-1.5" if provider == "grok" else "dreamina-seedance-2-5-260628"
        )
        start_ts = time.time()

        task_entry = {
            "status": "generating",
            "stage": "submitting",
            "stage_label": "Submitting…",
            "elapsed_seconds": 0,
            "path": None,
            "started_at": start_ts,
            "generation_mode": req.generation_mode,
            "model": video_model_id,
            "model_used": video_model_id,
            "watermark_free": True
        }
        if req.chapter_id is not None:
            store["tasks"][req.chapter_id] = task_entry

        def _on_status(stage: str, meta: Dict[str, Any]):
            elapsed = int(time.time() - start_ts)
            msg = meta.get("message") or f"{stage.capitalize()}..."
            task_entry = store["tasks"].get(req.chapter_id, {})
            task_entry.update({
                "status": "processing",
                "stage": stage,
                "stage_label": msg,
                "elapsed_seconds": elapsed,
                "upstream_task_id": meta.get("task_id") or meta.get("request_id"),
                "model": video_model_id,
            })
            store["tasks"][req.chapter_id] = task_entry

        def _worker():
            try:
                generator = get_video_generator(
                    provider=provider,
                    api_key=req.api_key,
                    model_id=video_model_id
                )

                resolved_assets = []
                for ref in (req.reference_assets or []):
                    if not isinstance(ref, dict):
                        continue
                    asset_id = ref.get("id")
                    stored = next((a for a in store["reference_assets"] if a["id"] == asset_id), None)
                    if stored:
                        resolved_assets.append({
                            "id": stored["id"],
                            "filename": stored.get("filename", ""),
                            "type": stored["type"],
                            "token": stored["token"],
                            "local_path": stored["local_path"],
                            "url": stored.get("url", "")
                        })
                    else:
                        local_path = ref.get("local_path")
                        if not local_path or not os.path.exists(local_path):
                            cand_name = os.path.basename(ref.get("url") or ref.get("filename") or "")
                            cand_path = os.path.join(uploads_dir, cand_name)
                            if cand_name and os.path.exists(cand_path):
                                local_path = cand_path
                        if local_path and os.path.exists(local_path):
                            resolved_assets.append({
                                "id": asset_id or str(uuid.uuid4())[:8],
                                "filename": ref.get("filename") or os.path.basename(local_path),
                                "type": ref.get("type") or ("video" if any(local_path.lower().endswith(ext) for ext in [".mp4", ".mov", ".webm", ".avi", ".mkv"]) else "image"),
                                "token": ref.get("token") or f"@Pictures {len(resolved_assets)+1}",
                                "local_path": local_path,
                                "url": ref.get("url") or f"/uploads/reference_assets/{os.path.basename(local_path)}",
                            })

                gen_kwargs = {
                    "prompt": req.prompt,
                    "output_path": clip_path,
                    "character_reference_image": req.character_reference_image,
                    "watermark": False,
                    "duration": req.duration_seconds,
                    "ratio": req.ratio,
                    "status_callback": _on_status,
                }
                if provider in ("seedance", "byteplus", "bytedance"):
                    gen_kwargs.update({
                        "generation_mode": req.generation_mode,
                        "first_frame_image": req.first_frame_image,
                        "last_frame_image": req.last_frame_image,
                        "ip_effect_name": req.ip_effect_name,
                        "reference_assets": resolved_assets or None,
                        "resolution": req.resolution,
                        "generate_audio": req.generate_audio,
                        "draft_mode": req.draft_mode,
                    })

                generator.generate_video(**gen_kwargs)

                _on_status("auditing", {"message": "Running QA audit & validation..."})
                qa = VideoQAAgent()
                passed, reason = qa.audit_clip(clip_path)
                public_path = f"/renders/cutscenes/chapter_{req.chapter_id}.mp4"
                total_elapsed = int(time.time() - start_ts)
                store["tasks"][req.chapter_id] = {
                    "status": "succeeded" if passed else "qa_warning",
                    "stage": "complete",
                    "stage_label": "Ready",
                    "elapsed_seconds": total_elapsed,
                    "path": public_path,
                    "reason": reason,
                    "generation_mode": req.generation_mode,
                    "model": video_model_id,
                    "model_used": video_model_id
                }
                est_cost = calculate_model_cost(
                    model_id=video_model_id,
                    duration=req.duration_seconds,
                    resolution=req.resolution,
                    clip_count=1,
                    audio=req.generate_audio,
                    draft_mode=req.draft_mode,
                    reference_asset_count=len(resolved_assets) if resolved_assets else 0
                )
                store["usage_records"].insert(0, {
                    "id": f"gen-{req.chapter_id}",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M"),
                    "service": "Multimedia Studio",
                    "model": video_model_id,
                    "mode": req.generation_mode,
                    "prompt": req.prompt,
                    "duration": f"{req.duration_seconds}s",
                    "cost": est_cost,
                    "status": "succeeded" if passed else "qa_warning",
                    "watermark_free": True
                })
                persist_generation(auth_store, history_user_id, {
                    "id": f"gen-{req.chapter_id}",
                    "title": (req.prompt or "Generated clip")[:80],
                    "prompt": req.prompt,
                    "model": video_model_id,
                    "mode": req.generation_mode,
                    "media_type": "video",
                    "path": public_path,
                    "elapsed_seconds": total_elapsed,
                })
            except Exception as exc:
                logger.error(f"Error generating video cutscene for chapter {req.chapter_id}: {exc}", exc_info=True)
                store["tasks"][req.chapter_id] = {
                    "status": "failed",
                    "stage": "failed",
                    "stage_label": "Failed",
                    "elapsed_seconds": int(time.time() - start_ts),
                    "error": str(exc)
                }

        store["tasks"][req.chapter_id] = {
            "status": "processing",
            "stage": "preparing",
            "stage_label": "Preparing assets & prompt...",
            "elapsed_seconds": 0,
            "started_at": start_ts,
            "model": video_model_id
        }
        background_tasks.add_task(_worker)
        return {"status": "started", "chapter_id": req.chapter_id, "provider": provider, "model": video_model_id}

    @app.get("/api/cutscenes/status/{chapter_id}")
    @app.get("/api/generation/status/{chapter_id}")
    def get_cutscene_status(chapter_id: str):
        """Returns status of a specific generation task (cutscene or image)."""
        cid = int(chapter_id) if chapter_id.isdigit() else chapter_id
        task = store["tasks"].get(cid) or store["tasks"].get(str(chapter_id))
        if not task:
            return {"status": "not_started"}
        if task.get("status") == "processing" and "started_at" in task:
            task["elapsed_seconds"] = int(time.time() - task["started_at"])
        return task

    @app.get("/api/health")
    def health():
        """Liveness probe for Docker / CI. Does not check upstream provider keys."""
        return {"status": "ok", "service": "api"}

    # =========================================================================
    # 5. PAGES ROUTING: UNIFIED CONSOLE & SERVICES
    # In Docker, nginx serves ui/ and proxies /api, /uploads, /renders here.
    # =========================================================================
    serve_ui = _env_enabled("SERVE_UI", "1")
    if serve_ui:
        @app.get("/")
        @app.get("/app")
        @app.get("/video")
        @app.get("/multimedia")
        @app.get("/rpg")
        @app.get("/api-keys")
        @app.get("/docs")
        @app.get("/settings")
        @app.get("/usage")
        def serve_console():
            app_file = os.path.join(ui_dir, "app.html")
            if os.path.exists(app_file):
                return FileResponse(app_file)
            return FileResponse(os.path.join(ui_dir, "index.html"))

        @app.get("/portal")
        @app.get("/landing")
        def serve_landing_portal():
            landing_file = os.path.join(ui_dir, "index.html")
            if os.path.exists(landing_file):
                return FileResponse(landing_file)
            return FileResponse(os.path.join(ui_dir, "app.html"))

        if os.path.exists(ui_dir):
            app.mount("/static", StaticFiles(directory=ui_dir), name="static")

    renders_dir = os.path.join(os.path.dirname(ui_dir), "renders")
    os.makedirs(renders_dir, exist_ok=True)
    app.mount("/renders", StaticFiles(directory=renders_dir), name="renders")

    uploads_base = os.path.join(os.path.dirname(ui_dir), "uploads")
    os.makedirs(uploads_base, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_base), name="uploads")

    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:create_app", factory=True, host="0.0.0.0", port=8000, reload=True)

"""FastAPI Backend Server for the Multimedia Tool Studio.

Exposes REST endpoints for:
1. Settings & API Key Configuration (/api/settings)
2. ModelArk Catalog (/api/models)
3. Director Storyboard Planning (/api/plan)
4. Seedance / Grok Cutscene Generation (/api/cutscenes/generate)
5. Task Status Polling (/api/cutscenes/status/{id})
6. Web App & Landing Page Serving (/ and /app)
"""

import os
import logging
import time
from typing import Optional, Dict, Any
import requests
from pydantic import BaseModel, Field
from src.director.planner import DirectorPlanner
from src.generators import get_video_generator
from src.qa.audit import VideoQAAgent
from src.models_registry import (
    MODEL_CATALOG,
    DEFAULT_DIRECTOR_MODEL,
    DEFAULT_VIDEO_MODEL,
    DEFAULT_IMAGE_MODEL,
    get_all_models_grouped,
)

try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks
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
        docs_url="/api/docs"
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
        "usage_records": []
    }

    ui_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")

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
    def get_usage():
        """Returns usage records and system metrics."""
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

    # =========================================================================
    # 2. MODELARK CATALOG API
    # =========================================================================
    @app.get("/api/models")
    def list_available_models():
        """Returns all 24 BytePlus ModelArk models organized by functional category."""
        return {
            "catalog": get_all_models_grouped(),
            "total_models": len(MODEL_CATALOG),
            "active_director_model": os.getenv("ARK_LLM_MODEL", DEFAULT_DIRECTOR_MODEL),
            "active_video_model": os.getenv("ARK_SEEDANCE_MODEL", DEFAULT_VIDEO_MODEL),
            "active_image_model": os.getenv("ARK_SEEDREAM_MODEL", DEFAULT_IMAGE_MODEL)
        }

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
    # 4. CUTSCENE GENERATION API (SEEDANCE / GROK)
    # =========================================================================
    @app.post("/api/cutscenes/generate")
    def generate_cutscene(req: CutsceneGenerateRequest, background_tasks: BackgroundTasks):
        """Submits an asynchronous cutscene generation task with zero watermark guarantee."""
        provider = req.provider.lower()

        # Validate API keys before backgrounding
        if provider in ("seedance", "byteplus", "bytedance"):
            ark_key = req.api_key or os.getenv("ARK_API_KEY")
            if not ark_key:
                raise HTTPException(
                    status_code=400,
                    detail="BytePlus ARK_API_KEY is required for Seedance video generation. Please enter it in Settings (⚙)."
                )
        elif provider in ("grok", "xai"):
            xai_key = req.api_key or os.getenv("XAI_API_KEY")
            if not xai_key:
                raise HTTPException(
                    status_code=400,
                    detail="XAI_API_KEY is required for Grok Imagine video generation. Please enter it in Settings (⚙)."
                )

        if provider in ("grok", "xai"):
            video_model_id = req.video_model or os.getenv("XAI_VIDEO_MODEL", "grok-imagine-video-1.5")
        else:
            video_model_id = req.video_model or os.getenv("ARK_SEEDANCE_MODEL", DEFAULT_VIDEO_MODEL)

        out_dir = "./renders/cutscenes"
        os.makedirs(out_dir, exist_ok=True)
        clip_path = os.path.join(out_dir, f"chapter_{req.chapter_id}.mp4")

        def _worker():
            try:
                generator = get_video_generator(
                    provider=provider,
                    api_key=req.api_key,
                    model_id=video_model_id
                )

                gen_kwargs = {
                    "prompt": req.prompt,
                    "output_path": clip_path,
                    "character_reference_image": req.character_reference_image,
                    "watermark": False,
                    "duration": req.duration_seconds,
                    "ratio": req.ratio,
                }
                if provider in ("seedance", "byteplus", "bytedance"):
                    gen_kwargs.update({
                        "generation_mode": req.generation_mode,
                        "first_frame_image": req.first_frame_image,
                        "last_frame_image": req.last_frame_image,
                        "ip_effect_name": req.ip_effect_name,
                        "resolution": req.resolution,
                        "generate_audio": req.generate_audio,
                        "draft_mode": req.draft_mode
                    })

                generator.generate_video(**gen_kwargs)
                qa = VideoQAAgent()
                passed, reason = qa.audit_clip(clip_path)
                public_path = f"/renders/cutscenes/chapter_{req.chapter_id}.mp4"
                store["tasks"][req.chapter_id] = {
                    "status": "succeeded" if passed else "qa_warning",
                    "path": public_path,
                    "reason": reason,
                    "generation_mode": req.generation_mode,
                    "model_used": video_model_id
                }
                store["usage_records"].insert(0, {
                    "id": f"gen-{req.chapter_id}",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M"),
                    "service": "AI Video Studio",
                    "model": video_model_id,
                    "mode": req.generation_mode,
                    "prompt": req.prompt,
                    "duration": f"{req.duration_seconds}s",
                    "status": "succeeded" if passed else "qa_warning",
                    "watermark_free": True
                })
            except Exception as exc:
                store["tasks"][req.chapter_id] = {
                    "status": "failed",
                    "error": str(exc)
                }

        store["tasks"][req.chapter_id] = {"status": "processing", "model": video_model_id}
        background_tasks.add_task(_worker)
        return {"status": "started", "chapter_id": req.chapter_id, "provider": provider, "model": video_model_id}

    @app.get("/api/cutscenes/status/{chapter_id}")
    def get_cutscene_status(chapter_id: int):
        """Returns status of a specific chapter cutscene task."""
        if chapter_id not in store["tasks"]:
            return {"status": "not_started"}
        return store["tasks"][chapter_id]

    # =========================================================================
    # 5. PAGES ROUTING: UNIFIED CONSOLE & SERVICES
    # =========================================================================
    @app.get("/")
    @app.get("/app")
    @app.get("/video")
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

    return app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:create_app", factory=True, host="0.0.0.0", port=8000, reload=True)

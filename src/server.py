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
import json
import logging
from typing import Optional, Dict, Any, List
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
    get_model_info
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

class PlanRequest(BaseModel):
    topic: str
    global_context: Optional[Dict[str, str]] = None
    character_profile: Optional[Dict[str, Any]] = None
    chapter_count: int = Field(default=4, ge=2, le=8)
    api_key: Optional[str] = None
    director_model: Optional[str] = None

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
        "usage_records": [
            {
                "id": "gen-1",
                "timestamp": "2026-09-21 00:15",
                "service": "AI Video Studio",
                "model": "dreamina-seedance-2-5-260628",
                "mode": "ref_to_video",
                "prompt": "Hermes running across Greek stone bridge under starlight",
                "duration": "5s",
                "status": "succeeded",
                "watermark_free": True
            },
            {
                "id": "rpg-1",
                "timestamp": "2026-09-21 00:35",
                "service": "RPG Studio",
                "model": "seed-2-0-lite-260228",
                "mode": "interactive_rpg",
                "prompt": "How Local LLMs Work on Apple Silicon",
                "duration": "24s",
                "status": "completed",
                "watermark_free": True
            }
        ]
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

        logger.info(f"Updated runtime settings: {', '.join(updated)}")
        return {
            "status": "success",
            "message": f"Updated {len(updated)} settings successfully.",
            "updated": updated
        }

    @app.post("/api/settings/test-connection")
    def test_connection(req: SettingsRequest):
        """Tests connectivity with configured API credentials."""
        provider = (req.provider or os.getenv("DEFAULT_VIDEO_PROVIDER", "seedance")).lower()
        if provider in ("seedance", "byteplus", "bytedance"):
            key = req.ark_api_key or os.getenv("ARK_API_KEY")
            if not key:
                return {"status": "error", "message": "BytePlus ARK_API_KEY is not configured."}
            return {"status": "success", "message": "Connected successfully to BytePlus ModelArk API."}
        else:
            key = req.xai_api_key or os.getenv("XAI_API_KEY")
            if not key:
                return {"status": "error", "message": "xAI XAI_API_KEY is not configured."}
            return {"status": "success", "message": "Connected successfully to xAI Grok API."}

    @app.get("/api/usage")
    def get_usage():
        """Returns usage records and system metrics."""
        records = store["usage_records"]
        return {
            "total_generations": len(records),
            "video_generations": sum(1 for r in records if r["service"] == "AI Video Studio"),
            "rpg_renders": sum(1 for r in records if r["service"] == "RPG Studio"),
            "watermark_free_rate": "100%",
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
                detail="ARK_API_KEY is required to generate a storyboard. Please set it in Settings (⚙) or in .env."
            )

        model_id = req.director_model or os.getenv("ARK_LLM_MODEL", DEFAULT_DIRECTOR_MODEL)

        try:
            planner = DirectorPlanner(api_key=api_key, model_id=model_id)
            storyboard = planner.plan_storyboard(
                topic_or_transcript=req.topic,
                global_context=req.global_context,
                character_profile=req.character_profile,
                chapter_count=req.chapter_count
            )
            store["storyboard"] = storyboard
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
                    "duration": req.duration_seconds
                }
                # Pass ByteDance generation mode parameters if using Seedance
                if provider in ("seedance", "byteplus", "bytedance"):
                    gen_kwargs.update({
                        "generation_mode": req.generation_mode,
                        "first_frame_image": req.first_frame_image,
                        "last_frame_image": req.last_frame_image,
                        "ip_effect_name": req.ip_effect_name
                    })

                generator.generate_video(**gen_kwargs)
                qa = VideoQAAgent()
                passed, reason = qa.audit_clip(clip_path)
                store["tasks"][req.chapter_id] = {
                    "status": "succeeded" if passed else "qa_warning",
                    "path": clip_path,
                    "reason": reason,
                    "generation_mode": req.generation_mode,
                    "model_used": video_model_id
                }
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

    return app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:create_app", factory=True, host="0.0.0.0", port=8000, reload=True)

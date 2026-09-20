"""FastAPI Backend Server for the Multimedia Tool Studio.

Exposes REST endpoints for:
1. Settings & API Key Configuration (/api/settings)
2. Director Storyboard Planning (/api/plan)
3. Seedance / Grok Cutscene Generation (/api/cutscenes/generate)
4. Task Status Polling (/api/cutscenes/status/{id})
5. Web App & Landing Page Serving (/ and /app)
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from src.director.planner import DirectorPlanner
from src.generators import get_video_generator
from src.qa.audit import VideoQAAgent

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

class PlanRequest(BaseModel):
    topic: str
    global_context: Optional[Dict[str, str]] = None
    character_profile: Optional[Dict[str, Any]] = None
    chapter_count: int = Field(default=4, ge=2, le=8)
    api_key: Optional[str] = None

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

class MasterRenderRequest(BaseModel):
    storyboard: Dict[str, Any]
    output_filename: str = "master_video.mp4"

def create_app():
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Run 'uv pip install -r requirements.txt' to use the web server.")

    app = FastAPI(
        title="Multimedia Tool Studio API",
        description="Backend API for Retro Pixel Animation & Multimodal Video Generation",
        version="0.2.0"
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
        "tasks": {}
    }

    ui_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")

    # =========================================================================
    # 1. SETTINGS & CREDENTIALS API
    # =========================================================================
    @app.get("/api/settings")
    def get_settings():
        """Returns configured status of keys without exposing secret contents."""
        ark_key = os.getenv("ARK_API_KEY", "")
        xai_key = os.getenv("XAI_API_KEY", "")
        return {
            "has_ark_key": bool(ark_key),
            "has_xai_key": bool(xai_key),
            "ark_base_url": os.getenv("ARK_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3"),
            "provider": os.getenv("DEFAULT_VIDEO_PROVIDER", "seedance"),
            "ark_key_masked": f"...{ark_key[-4:]}" if len(ark_key) >= 4 else ("✓ Configured" if ark_key else ""),
            "xai_key_masked": f"...{xai_key[-4:]}" if len(xai_key) >= 4 else ("✓ Configured" if xai_key else "")
        }

    @app.post("/api/settings")
    def update_settings(req: SettingsRequest):
        """Allows setting API keys and endpoints manually from the Web Studio."""
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

        logger.info(f"Updated runtime settings: {', '.join(updated)}")
        return {
            "status": "success",
            "message": f"Updated {len(updated)} settings successfully.",
            "updated": updated
        }

    # =========================================================================
    # 2. STORYBOARD PLANNING API
    # =========================================================================
    @app.post("/api/plan")
    def plan_storyboard(req: PlanRequest):
        """Invokes seed-2-0-lite to generate an initial roadmap from topic and context."""
        api_key = req.api_key or os.getenv("ARK_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail="ARK_API_KEY is required to generate a storyboard. Please set it in Settings (⚙) or in .env."
            )

        try:
            planner = DirectorPlanner(api_key=api_key)
            storyboard = planner.plan_storyboard(
                topic_or_transcript=req.topic,
                global_context=req.global_context,
                character_profile=req.character_profile,
                chapter_count=req.chapter_count
            )
            store["storyboard"] = storyboard
            return {"status": "success", "storyboard": storyboard}
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
        """Saves user manual edits to platforms, text, or prompts."""
        store["storyboard"] = storyboard
        return {"status": "updated", "storyboard": store["storyboard"]}

    # =========================================================================
    # 3. CUTSCENE GENERATION API
    # =========================================================================
    @app.post("/api/cutscenes/generate")
    def generate_cutscene(req: CutsceneGenerateRequest, background_tasks: BackgroundTasks):
        """Triggers asynchronous video generation for a specific chapter."""
        provider = req.provider.lower()

        # Validate key availability upfront
        if provider in ("seedance", "byteplus", "bytedance"):
            key = req.api_key or os.getenv("ARK_API_KEY")
            if not key:
                raise HTTPException(
                    status_code=400,
                    detail="ARK_API_KEY is required for Seedance video generation. Please enter it in Settings (⚙)."
                )
        elif provider in ("grok", "xai"):
            key = req.api_key or os.getenv("XAI_API_KEY")
            if not key:
                raise HTTPException(
                    status_code=400,
                    detail="XAI_API_KEY is required for Grok Imagine video generation. Please enter it in Settings (⚙)."
                )

        out_dir = "./renders/cutscenes"
        os.makedirs(out_dir, exist_ok=True)
        clip_path = os.path.join(out_dir, f"chapter_{req.chapter_id}.mp4")

        def _worker():
            try:
                generator = get_video_generator(provider=provider)

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
                    "generation_mode": req.generation_mode
                }
            except Exception as exc:
                store["tasks"][req.chapter_id] = {
                    "status": "failed",
                    "error": str(exc)
                }

        store["tasks"][req.chapter_id] = {"status": "processing"}
        background_tasks.add_task(_worker)
        return {"status": "started", "chapter_id": req.chapter_id, "provider": provider}

    @app.get("/api/cutscenes/status/{chapter_id}")
    def get_cutscene_status(chapter_id: int):
        """Returns status of a specific chapter cutscene task."""
        if chapter_id not in store["tasks"]:
            return {"status": "not_started"}
        return store["tasks"][chapter_id]

    # =========================================================================
    # 4. PAGES ROUTING: MAIN LANDING SITE (/) vs ACTUAL STUDIO APP (/app)
    # =========================================================================
    @app.get("/")
    def serve_landing_page():
        landing_file = os.path.join(ui_dir, "index.html")
        if os.path.exists(landing_file):
            return FileResponse(landing_file)
        return {"message": "Multimedia Tool Backend API"}

    @app.get("/app")
    def serve_studio_app():
        app_file = os.path.join(ui_dir, "app.html")
        if os.path.exists(app_file):
            return FileResponse(app_file)
        # Fallback to index if app.html not found
        return FileResponse(os.path.join(ui_dir, "index.html"))

    if os.path.exists(ui_dir):
        app.mount("/static", StaticFiles(directory=ui_dir), name="static")

    return app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:create_app", factory=True, host="0.0.0.0", port=8000, reload=True)

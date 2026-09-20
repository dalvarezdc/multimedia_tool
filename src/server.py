"""FastAPI Backend Server for the Multimedia Tool Studio.

Exposes REST endpoints for:
1. Director Storyboard Planning (with context & character consistency)
2. Seedance Cutscene Generation (watermark-free)
3. Task Status Polling
4. Remotion Master Video Rendering
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from src.director.planner import DirectorPlanner
from src.seedance.client import SeedanceClient
from src.qa.audit import VideoQAAgent

try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
except ImportError:
    FastAPI = None

logger = logging.getLogger("multimedia_server")

class PlanRequest(BaseModel):
    topic: str
    global_context: Optional[Dict[str, str]] = None
    character_profile: Optional[Dict[str, Any]] = None
    chapter_count: int = Field(default=4, ge=2, le=8)

class CutsceneGenerateRequest(BaseModel):
    chapter_id: int
    prompt: str
    duration_seconds: int = 5
    character_reference_image: Optional[str] = None
    provider: str = Field(default="seedance", description="'seedance' (BytePlus) or 'grok' (xAI)")

class MasterRenderRequest(BaseModel):
    storyboard: Dict[str, Any]
    output_filename: str = "master_video.mp4"

def create_app():
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Run 'uv pip install -r requirements.txt' to use the web server.")

    app = FastAPI(
        title="Multimedia Tool Studio API",
        description="Backend API for Retro Pixel Animation & BytePlus Seedance Video Generation",
        version="0.1.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # In-memory store for active storyboard and task statuses
    store = {
        "storyboard": None,
        "tasks": {}
    }

    @app.post("/api/plan")
    def plan_storyboard(req: PlanRequest):
        """Invokes seed-2-0-lite to generate an initial roadmap from topic and context."""
        try:
            planner = DirectorPlanner()
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

    @app.post("/api/cutscenes/generate")
    def generate_cutscene(req: CutsceneGenerateRequest, background_tasks: BackgroundTasks):
        """Triggers asynchronous Seedance generation for a specific chapter."""
        out_dir = "./renders/cutscenes"
        os.makedirs(out_dir, exist_ok=True)
        clip_path = os.path.join(out_dir, f"chapter_{req.chapter_id}.mp4")

        def _worker():
            try:
                from src.generators import get_video_generator
                generator = get_video_generator(provider=req.provider)
                generator.generate_video(
                    prompt=req.prompt,
                    output_path=clip_path,
                    character_reference_image=req.character_reference_image,
                    watermark=False,  # Enforces no watermark
                    duration=req.duration_seconds
                )
                qa = VideoQAAgent()
                passed, reason = qa.audit_clip(clip_path)
                store["tasks"][req.chapter_id] = {
                    "status": "succeeded" if passed else "qa_warning",
                    "path": clip_path,
                    "reason": reason
                }
            except Exception as exc:
                store["tasks"][req.chapter_id] = {
                    "status": "failed",
                    "error": str(exc)
                }

        store["tasks"][req.chapter_id] = {"status": "processing"}
        background_tasks.add_task(_worker)
        return {"status": "started", "chapter_id": req.chapter_id}

    @app.get("/api/cutscenes/status/{chapter_id}")
    def get_cutscene_status(chapter_id: int):
        """Returns status of a specific chapter cutscene task."""
        if chapter_id not in store["tasks"]:
            return {"status": "not_started"}
        return store["tasks"][chapter_id]

    # Mount UI static directory if it exists
    ui_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")
    if os.path.exists(ui_dir):
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")

    return app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:create_app", factory=True, host="0.0.0.0", port=8000, reload=True)


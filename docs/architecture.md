# System Architecture: Autonomous Retro Pixel & AI Video Engine

## 1. Executive Summary

This system is an automated, multimodal video generation platform designed to create high-engagement educational and technical explainer videos. 

It combines two visual paradigms into a unified, seamless cinematic experience:
1. **A Retro 16-Bit Pixel-Art Platformer Level**: Functions as the overarching narrative spine and progression roadmap. An animated avatar (e.g., Hermes/Messenger) navigates sequential floating stone platforms, each adorned with illuminated wooden scroll signs representing key milestones or concepts.
2. **Watermark-Free Photorealistic/Cinematic AI Cutscenes**: Generated autonomously using ByteDance's **Seedance API** via **BytePlus ModelArk** (`arkruntime`), illustrating each milestone in vivid detail without visual degradation or platform watermarks.

---

## 2. High-Level Architecture

```mermaid
flowchart TB
    subgraph Input ["1. Ingestion Layer"]
        RAW[Raw Topic / Script / Article]
        CFG[User Preferences & Style Config]
    end

    subgraph DirectorTier ["2. Director & Planning Tier (BytePlus ModelArk)"]
        LLM[seed-2-0-lite-260228 Engine]
        DECOMP[Topic Decomposer & Storyboarder]
        PROMPTGEN[Seedance Visual Prompt Synthesizer]
        LAYOUT[Platform Spatial Coordinates Calculator]
    end

    subgraph VideoGenTier ["3. Watermark-Free Video Gen Subsystem"]
        SDK[BytePlus arkruntime Client]
        SEEDANCE[Seedance 2.0 / 2.5 API]
        POLL[Asynchronous Task Poller]
        WM_GUARD[Watermark Nullifier & Negative Filter]
        CACHE[Cutscene Asset Cache]
    end

    subgraph PixelEngineTier ["4. Retro Animation Tier (Remotion + TypeScript)"]
        TILE[Tilemap & Parallax Background Renderer]
        NODE[Signpost & Scroll Milestone System]
        PHYSICS[Sprite State Machine & Jump Arc Physics]
        CAM[Cinematic Camera Tracking / Lerp]
    end

    subgraph AudioTier ["5. Audio & Voiceover Subsystem"]
        TTS[TTS Voice Synthesizer]
        SFX[8-Bit Retro Sound Generator (Jump, Chime, Land)]
        BGM[Dynamic Chiptune BGM Looper]
    end

    subgraph CompositingTier ["6. Hybrid Compositor & Exporter"]
        TRANS[Retro Pixel-Dissolve Transition Module]
        STITCH[Remotion / FFmpeg Frame Bundler]
        EXPORT[Master 4K / 1080p MP4 Video]
    end

    RAW --> DECOMP
    CFG --> DECOMP
    DECOMP --> LLM
    LLM --> PROMPTGEN
    LLM --> LAYOUT

    PROMPTGEN --> WM_GUARD --> SDK
    SDK --> SEEDANCE --> POLL --> CACHE

    LAYOUT --> NODE
    LAYOUT --> PHYSICS
    TILE --> CAM
    NODE --> CAM

    CACHE --> TRANS
    CAM --> TRANS
    TRANS --> STITCH

    LLM --> TTS
    PHYSICS --> SFX
    TTS --> STITCH
    SFX --> STITCH
    BGM --> STITCH

    STITCH --> EXPORT
```

---

## 3. Subsystem Breakdown

### 3.1. Director & Planning Tier (`seed-2-0-lite-260228`)
* **Role**: Acts as the executive director, story editor, and layout coordinator.
* **Model**: BytePlus ModelArk `seed-2-0-lite-260228` invoked through `client.responses.create`.
* **Functions**:
  * Ingests arbitrary input text (e.g. documentation, technical articles, user scripts).
  * Divides content into discrete, bite-sized **Chapters / Milestones** (typically 3–6 per video).
  * Calculates spatial layout coordinates $(x, y)$ for each floating stone platform so jumps follow realistic parabolic curves without overlapping.
  * Formulates highly descriptive, camera-directed visual prompts for the Seedance diffusion model.

### 3.2. Retro Platformer Animation Engine (Remotion + TypeScript)
* **Role**: Renders deterministic, frame-accurate 60 FPS video of the retro video game world.
* **Aesthetic Structure**:
  * **Parallax Sky Layer**: Deep night sky palette (`#080c24`), procedural twinkling stars at varying speeds.
  * **Midground Silhouette**: Mountain range and ruined castle silhouette with winding paths.
  * **Foreground Terrain**: Greek pillars, mossy stone bricks, and platform pedestals.
  * **Interactive Milestone Signs**: Inactive signs appear weathered and dark. When the player character reaches the platform, the sign triggers an activation animation (gold boundary gleam, animated text banner expansion, particle emission).
  * **Avatar State Machine**:
    $$\text{Idle} \longrightarrow \text{Run} \longrightarrow \text{Jump (Parabola)} \longrightarrow \text{Land} \longrightarrow \text{Present Sign}$$
    The jump trajectory is modeled mathematically:
    $$y(t) = y_0 + v_0 t - \frac{1}{2} g t^2$$
  * **Camera Tracking**: The viewport coordinates smoothly follow the player using linear interpolation (`lerp` with easing) to create cinematic framing.

### 3.3. Watermark-Free Seedance Video Pipeline
* **Role**: High-fidelity AI video generation illustrating each technical milestone.
* **Integration**: BytePlus ModelArk SDK (`from arkruntime import Ark`).
* **Watermark Suppression Protocol**:
  1. **API Flag**: `watermark=False` explicitly passed to `client.content_generation.tasks.create`.
  2. **Negative Constraint Injection**: Every prompt automatically appends:
     ```text
     --no watermark, logo, text overlay, timestamps, subtitles, UI elements, border
     ```
  3. **Verification Hook**: An automated frame analysis check verifies the bottom-right quadrant of the generated clip for luminance variance / logo stamps before admitting the file into the rendering cache.
* **Lifecycle**:
  * Tasks are submitted asynchronously to the BytePlus API.
  * A non-blocking background poller queries `client.content_generation.tasks.get(task_id=...)` with exponential backoff until `status == "succeeded"`.
  * Outputs are downloaded to `cutscenes/chapter_{id}.mp4`.

### 3.4. Audio & Soundscape Synthesis
* **Voiceover**: Generates natural speech synchronized to each chapter segment using ElevenLabs or native TTS.
* **Chiptune & 8-Bit SFX**:
  * `jump.wav`: Triggered when the character leaps off a platform.
  * `land.wav`: Low-pitch impact thud when character connects with stone.
  * `sign_chime.wav`: Retro arcade success chime when a signpost illuminates.
* **Audio Ducking**: Automatically ducks background music by $-14\text{ dB}$ whenever speech narration is active.

### 3.5. Transition & Compositing Subsystem
The engine supports two primary cutscene integration modes:
1. **Full-Screen Pixel Dissolve Cutscene**:
   * As the character reaches the sign, the camera zooms in slightly, triggering a retro mosaic/pixel-dissolve transition directly into the 16:9 Seedance AI video.
   * After the video segment concludes, the mosaic resolves back into the game world, and the avatar sets off toward the next node.
2. **In-World Picture-in-Picture (Crystal Portal / Magic Mirror)**:
   * A framed ancient artifact or hovering rune on the platform acts as a projection screen, playing the Seedance video directly inside the 2D pixel world while the avatar gestures toward it.

---

## 4. Data Specifications & Schemas

### 4.1. Storyboard Specification (`storyboard.json`)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "StoryboardSpec",
  "type": "object",
  "required": ["project_id", "theme", "resolution", "fps", "chapters"],
  "properties": {
    "project_id": { "type": "string" },
    "theme": { "type": "string", "enum": ["greek_night_sky", "cyberpunk_ruins", "dungeon_keep"] },
    "resolution": {
      "type": "object",
      "properties": {
        "width": { "type": "integer", "default": 1920 },
        "height": { "type": "integer", "default": 1080 }
      }
    },
    "fps": { "type": "integer", "default": 60 },
    "chapters": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "title", "narration_text", "platform", "seedance_prompt", "cutscene_mode"],
        "properties": {
          "id": { "type": "integer" },
          "title": { "type": "string" },
          "narration_text": { "type": "string" },
          "platform": {
            "type": "object",
            "required": ["x", "y", "width"],
            "properties": {
              "x": { "type": "number" },
              "y": { "type": "number" },
              "width": { "type": "number" }
            }
          },
          "seedance_prompt": { "type": "string" },
          "cutscene_mode": { "type": "string", "enum": ["fullscreen_dissolve", "in_world_screen"] },
          "duration_seconds": { "type": "number", "default": 6.0 }
        }
      }
    }
  }
}
```

---

## 5. Security, Secrets & Environment

* **API Keys**: Never hardcoded. Injected through `.env` and validated at pipeline startup.
* **Sandbox Isolation**: Media rendering and FFmpeg processing run in isolated temporary working directories (`temp/renders/`) to prevent workspace corruption.
* **Storage**: Video binaries and heavy renders are excluded from Git via `.gitignore`. Only static reusable pixel sprite templates are committed.

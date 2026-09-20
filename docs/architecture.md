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

### 3.3. Multi-Provider AI Video Generation Subsystem (Seedance & Grok)
* **Role**: High-fidelity AI video generation illustrating each technical milestone with zero watermarking.
* **Supported Video Providers**:
  1. **BytePlus ModelArk (Seedance 2.0 / 2.5)**:
     * High multimodal fidelity, up to 30s clips, precise camera control.
     * Enforced watermark-free execution via `watermark=False` API parameter and negative constraints.
  2. **xAI Grok Imagine (Video 1.5 via api.x.ai)**:
     * Fast, cinematic video generation, native audio synthesis, 1–15 second durations.
     * Native clean API output without overlays or watermarks.
     * Multimodal character consistency through image input references.
* **Unified Factory (`src.generators.get_video_generator`)**:
  * Seamless runtime switching via `--provider {seedance,grok}` or environment variable `DEFAULT_VIDEO_PROVIDER`.
* **Verification Hook**: Automated computer vision frame analysis audits corner quadrants for luminance variance, ensuring zero watermarks before admitting clips into the render cache.

### 3.4. Audio & Soundscape Synthesis
* **Voiceover**: Generates natural speech synchronized to each chapter segment using ElevenLabs or native TTS.
* **Chiptune & 8-Bit SFX**:
  * `jump.wav`: Triggered when the character leaps off a platform.
  * `land.wav`: Low-pitch impact thud when character connects with stone.
  * `sign_chime.wav`: Retro arcade success chime when a signpost illuminates.
* **Audio Ducking**: Automatically ducks background music by $-14\text{ dB}$ whenever speech narration is active.

### 3.6. Global Context & Knowledge Ingestion Subsystem
* **Role**: Ensures generated video content reflects extensive technical documentation, lore, project whitepapers, or specific tone guidelines rather than isolated prompts.
* **Mechanism**:
  * The user inputs raw domain materials (e.g. system design docs, research papers, scripts, brand guidelines).
  * The **Director Agent** (`seed-2-0-lite-260228`) maintains this context in its system prompt window.
  * Extracted chapter titles, technical explanations, and visual prompts for Seedance inherit contextual continuity, maintaining terminology, tone, and visual symbolism throughout the entire video.

### 3.7. Multimodal Character Consistency Subsystem
Character consistency operates across both visual realms:
1. **2D Pixel World Consistency**:
   * A unified sprite profile (e.g., Hermes: golden winged helmet, blue tunic, golden caduceus) is loaded from the asset registry.
   * Remotion uses identical sprite sheets, bounding boxes, and palette animations across every platform hop.
2. **Seedance AI Cutscene Character Consistency**:
   * **Multimodal Reference Ingestion**: When calling `client.content_generation.tasks.create` via `arkruntime`, the client passes a canonical character reference image (`character_reference.png` via public URL or asset library reference).
   * **Omni-Reference Prompting**: The text prompt references the image explicitly:
     ```text
     "Featuring the character shown in Image 1, wearing the golden winged helmet and blue tunic, standing inside a high-tech datacenter..."
     ```
   * **Persistent Character Tokenizer**: A structured character definition (hair style, color, equipment, clothing colors, facial structure) is injected into every chapter prompt to guarantee identity preservation across cuts.

### 3.8. Web Frontend Architecture & Interactive Studio
To provide a non-CLI, interactive creator experience, the platform includes a modern web studio:
* **Technology Stack**:
  * **Framework**: React / Next.js with Tailwind CSS.
  * **Live Video Engine**: `@remotion/player` for client-side zero-latency video scrubbing, frame-stepping, and playback without rendering MP4s.
  * **API Layer**: Lightweight FastAPI / Next.js API endpoints handling pipeline actions.
* **Studio Modules**:
  1. **Context & Lore Ingestion Panel**: Rich text input for technical docs, style tags, and target audience settings.
  2. **Character Consistency Studio**: Reference image uploader, trait tag editor, and sprite selector.
  3. **Interactive Visual Storyboard**: Drag-and-drop platform node reordering, sign label editing, and prompt tweaking.
  4. **Live Remotion Player**: Real-time canvas preview of pixel jumps, sign illumination, and transition effects.
  5. **Cutscene Inspector & Re-roll**: Preview generated watermark-free Seedance clips; one-click re-generation for individual chapters.
  6. **Render & Export Hub**: Trigger headless Remotion export with real-time progress bar.

---

## 4. Data Specifications & Schemas

### 4.1. Master Storyboard Specification (`storyboard.json`)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "StoryboardSpec",
  "type": "object",
  "required": ["project_id", "theme", "global_context", "character_profile", "resolution", "fps", "chapters"],
  "properties": {
    "project_id": { "type": "string" },
    "theme": { "type": "string", "enum": ["greek_night_sky", "cyberpunk_ruins", "dungeon_keep"] },
    "global_context": {
      "type": "object",
      "properties": {
        "domain_notes": { "type": "string" },
        "tone": { "type": "string" },
        "target_audience": { "type": "string" }
      }
    },
    "character_profile": {
      "type": "object",
      "required": ["name", "reference_image_url", "prompt_tokens", "sprite_id"],
      "properties": {
        "name": { "type": "string" },
        "reference_image_url": { "type": "string" },
        "prompt_tokens": { "type": "string" },
        "sprite_id": { "type": "string" }
      }
    },
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

* **API Keys**: Injected through `.env` (`ARK_API_KEY`) and validated at pipeline startup.
* **Asset Privacy**: Character reference images and generated cutscenes are held in local cache directories excluded from version control.
* **Sandbox Isolation**: Media rendering and FFmpeg processing execute in isolated working directories (`temp/renders/`).


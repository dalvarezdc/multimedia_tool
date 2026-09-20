# Web Frontend Studio Specification

## 1. Vision & Architecture

The Multimedia Tool Studio is a browser-based creator dashboard that turns technical knowledge into animated retro-game explainer videos without requiring manual editing or command-line scripting.

```
+------------------------------------------------------------------------------------+
|                               MULTIMEDIA TOOL STUDIO                               |
+------------------------------------+-----------------------------------------------+
|  1. Context & Character Sidebar    |  3. Live Remotion Player (Live 60 FPS Canvas) |
|  - Topic & Project Title           |     [Parallax Sky]                            |
|  - Domain Knowledge / Doc Paste    |     [Floating Stone Platforms & Scrolls]      |
|  - Character Reference Image       |     [Hermes Avatar Jumping Animation]         |
|  - Character Trait Tokens          |     [▶ Play] [⏸ Pause] [━━●━━━━] 00:14 / 00:30 |
|                                    +-----------------------------------------------+
|  2. Storyboard Node Editor         |  4. Seedance Cutscenes & QA Inspector         |
|  - [Node 1: Hardware Choices]      |     - Clip 1: [Preview Video] [QA: PASS (No WM)]|
|    Prompt: "The character in..."   |     - Clip 2: [Preview Video] [QA: PASS (No WM)]|
|    [Re-Roll Cutscene]              |     - Clip 3: [Generating...] (42% Polling)    |
|  - [Node 2: Download & Setup]      +-----------------------------------------------+
|  - [+ Add Milestone Platform]      |  5. Export & Render                           |
|                                    |     [🚀 Render Master 4K / 1080p MP4]         |
+------------------------------------+-----------------------------------------------+
```

---

## 2. Technology Stack

* **UI Framework**: Next.js 14 / React 18 with Tailwind CSS & Lucide Icons.
* **Live Video Playback**: `@remotion/player`
  * Embeds the Remotion composition directly in the React DOM.
  * Allows instantaneous scrubbing across the timeline without encoding video files.
* **Backend API**: FastAPI (Python) or Next.js Route Handlers:
  * Bridges UI controls directly to `DirectorPlanner` and `SeedanceClient`.
  * Manages asynchronous tasks with SSE (Server-Sent Events) or WebSockets for live generation progress.

---

## 3. Core Frontend Panels

### 3.1. Context & Lore Studio
* **Context Ingestion**:
  * Dual-mode input: raw text paste or drag-and-drop `.md`/`.pdf`/`.txt` file upload.
  * Presets for tone: *Retro Tech Explainer*, *Epic Lore*, *Deep-Dive Tutorial*, *Speedrun Briefing*.
* **Character Consistency Manager**:
  * Image dropzone for **Canonical Character Reference** (`.png`, `.jpg`).
  * Live base64/URL preview.
  * Visual trait tagger (e.g. `[Winged Helmet]`, `[Blue Tunic]`, `[Caduceus Staff]`).
  * Sprite selector for the 2D world (Hermes, Cyber Knight, Wizard, Custom).

### 3.2. Visual Storyboard & Level Layout Editor
* **Interactive Canvas**:
  * Displays the 1920x1080 level layout.
  * Drag-to-position platforms: Adjust $(x, y)$ platform heights and distances visually.
  * Real-time calculation of jump arcs to ensure parabolic feasibility.
* **Chapter Cards**:
  * Edit signpost labels in real time.
  * Edit narration voiceover scripts.
  * Inspect and adjust Seedance visual prompts before dispatching.

### 3.3. Embedded Remotion Live Player
* Uses `@remotion/player` component:
  ```tsx
  <Player
    component={MasterRoadmapVideo}
    inputProps={{ storyboard }}
    durationInFrames={totalFrames}
    fps={60}
    compositionWidth={1920}
    compositionHeight={1080}
    style={{ width: '100%', aspectRatio: '16/9' }}
    controls
  />
  ```
* Provides immediate visual feedback of platform lighting, star twinkling, avatar jump animations, and video cutaway transitions.

### 3.4. Seedance Cutscene Studio & Watermark QA
* Per-chapter cutscene cards showing:
  * Video thumbnail / inline player.
  * Generation status indicator (`PENDING`, `POLLING`, `SUCCEEDED`, `FAILED`).
  * **QA Watermark Badge**: Green shield `PASS: Zero Watermark` or warning `AUDIT DETECTED`.
  * **One-Click Re-roll**: Regenerate an individual chapter's clip with updated prompts or seeds without touching the rest of the video.

### 3.5. Master Export Manager
* Triggers server-side headless Remotion execution (`remotion render`).
* Live progress bar reporting frame encoding velocity and remaining time.
* Download button for the completed high-bitrate MP4.

---

## 4. API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/plan` | Ingests topic, global context, and character specs; returns structured `storyboard.json` |
| `POST` | `/api/storyboard/update` | Saves user manual edits to platforms, text, or prompts |
| `POST` | `/api/cutscenes/generate` | Dispatches Seedance tasks with `watermark=False` and character reference |
| `GET` | `/api/cutscenes/status/:taskId` | Polls live status of BytePlus generation task |
| `POST` | `/api/render/master` | Initiates Remotion headless rendering of the full video |
| `GET` | `/api/render/progress` | Server-Sent Event (SSE) stream of frame rendering progress |

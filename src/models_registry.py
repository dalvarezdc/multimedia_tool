"""BytePlus ModelArk & Seedance Complete Model Catalog.

Defines available BytePlus ModelArk models across:
1. Video Generation (Seedance 2.5, 2.0, 1.5 Pro, 1.0 Fast, Mini)
2. Director & Planning LLMs (Seed 2.0, DeepSeek V4, GLM-5)
3. Image & Character Anchor Generation (SeeDream 5.0, DOLA SeeDream Pro, SeeDream 4.5)
4. 3D Asset & Item Generation (Hyper3D, Hitem3D)
5. Vision Embedding (Skylark Vision)

Includes dynamic UI profile metadata matching BytePlus ModelArk console layouts:
- headline, placeholder, input_slots, pills, sample_cost, mode_selector, template_library
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict, field

@dataclass
class ModelInfo:
    id: str
    display_name: str
    category: str
    description: str
    recommended_for: str
    is_default: bool = False
    ui_layout_type: str = "video_ref"  # 'video_ref', 'video_first_last', 'video_first', 'image_standard', 'image_group', 'generic'
    headline: str = "Experience video generation and let creativity shake"
    icon_type: str = "video"  # 'video', 'image', 'llm', '3d', 'vision'
    placeholder: str = "Use @to quickly reference uploaded files, such as referring to actions in @Video 1 to generate videos of characters fighting in @Pictures 2 and @Pictures 3."
    ref_placeholder: str = "Use @to quickly reference uploaded files, such as referring to actions in @Video 1 to generate videos of characters fighting in @Pictures 2 and @Pictures 3."
    first_last_placeholder: str = "Enter the content screen you want to generate, or enter a creative description in combination with the image (optional)."
    input_slots: List[Dict[str, str]] = field(default_factory=lambda: [{"id": "reference", "label": "Reference", "icon": "plus"}])
    mode_selector: Optional[Dict[str, Any]] = None
    pills: List[str] = field(default_factory=list)
    sample_cost: str = "USD 0.6048"
    has_template_library: bool = False
    sample_examples: List[Dict[str, str]] = field(default_factory=list)
    provider: str = "seedance"
    ratios: List[str] = field(default_factory=lambda: ["16:9", "9:16", "1:1"])
    resolutions: List[str] = field(default_factory=lambda: ["720p"])
    durations: List[int] = field(default_factory=lambda: [5, 10])
    supports_audio: bool = False
    supports_draft: bool = False
    clip_counts: List[int] = field(default_factory=lambda: [1])

SAMPLE_INSPIRATIONS = [
    {
        "title": "Cyberpunk Neon Runner",
        "prompt": "Hermes sprinting across rain-slick neon alleyway with winged holographic sandals and volumetric reflections, 60fps cinematic",
        "thumbnail": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=300&q=80"
    },
    {
        "title": "Celestial Starlight Bridge",
        "prompt": "Hermes running across ancient Greek marble bridge hovering above purple nebula starlight, glowing cyan aura",
        "thumbnail": "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?w=300&q=80"
    },
    {
        "title": "Golden Caduceus Shrine",
        "prompt": "Golden staff emitting solar rays before celestial temple pillars, hyper-detailed retro fantasy realism",
        "thumbnail": "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?w=300&q=80"
    },
    {
        "title": "Anime Shockwave Burst",
        "prompt": "Hero summoning celestial lightning against obsidian monoliths, high octane dynamic camera sweep",
        "thumbnail": "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=300&q=80"
    }
]

MODEL_CATALOG: Dict[str, ModelInfo] = {
    # -------------------------------------------------------------------------
    # 1. VIDEO GENERATION MODELS (SEEDANCE FAMILY)
    # -------------------------------------------------------------------------
    "dreamina-seedance-2-5-260628": ModelInfo(
        id="dreamina-seedance-2-5-260628",
        display_name="Dreamina-Seedance-2.5 260628",
        category="video",
        description="Flagship video generation model with superior character coherence, 1080p, and complex physics.",
        recommended_for="Final production cutscenes, complex camera pans, hero narrative shots.",
        is_default=True,
        ui_layout_type="video_ref",
        headline="Experience video generation and let creativity shake",
        icon_type="video",
        placeholder="Use @to quickly reference uploaded files, such as referring to actions in @Video 1 to generate videos of characters fighting in @Pictures 2 and @Pictures 3.",
        input_slots=[{"id": "reference", "label": "Reference", "icon": "plus"}],
        mode_selector={"enabled": True, "default": "Ref-to-video", "options": ["Ref-to-video", "First/last frame"]},
        sample_cost="USD 0.6048",
        sample_examples=SAMPLE_INSPIRATIONS,
        provider="seedance",
        ratios=["16:9", "9:16", "1:1", "4:3", "21:9"],
        resolutions=["720p", "1080p"],
        durations=[5, 10],
        supports_audio=True,
        clip_counts=[1],
    ),
    "dreamina-seedance-2-0-fast-260128": ModelInfo(
        id="dreamina-seedance-2-0-fast-260128",
        display_name="Dreamina-Seedance-2.0-fast 260128",
        category="video",
        description="Accelerated video generation pipeline with reduced generation latency.",
        recommended_for="Rapid prototyping, storyboard previews, fast drafting.",
        ui_layout_type="video_ref",
        headline="Experience video generation and let creativity shake",
        icon_type="video",
        placeholder="Use @to quickly reference uploaded files, such as referring to actions in @Video 1 to generate videos of characters fighting in @Pictures 2 and @Pictures 3.",
        input_slots=[{"id": "reference", "label": "Reference", "icon": "plus"}],
        mode_selector={"enabled": True, "default": "Ref-to-video", "options": ["Ref-to-video", "First/last frame"]},
        sample_cost="USD 0.6048",
        sample_examples=SAMPLE_INSPIRATIONS,
        provider="seedance",
        ratios=["16:9", "9:16", "1:1"],
        resolutions=["480p", "720p"],
        durations=[5, 10],
        supports_audio=True,
        clip_counts=[1],
    ),
    "bytedance-seedance-1-5-pro-251215": ModelInfo(
        id="bytedance-seedance-1-5-pro-251215",
        display_name="ByteDance-Seedance-1.5-pro 251215",
        category="video",
        description="Professional keyframe interpolation model with first-to-last frame morphing and draft mode.",
        recommended_for="Controlled start-to-end character transitions, action choreography.",
        ui_layout_type="video_first_last",
        headline="Experience video generation and let creativity shake",
        icon_type="video",
        placeholder="Enter the content screen you want to generate, or enter a creative description in combination with the image (optional).",
        input_slots=[
            {"id": "first_frame", "label": "first frame", "icon": "plus"},
            {"id": "last_frame", "label": "last frame", "icon": "plus"}
        ],
        mode_selector={"enabled": True, "default": "First/last frame", "options": ["Ref-to-video", "First/last frame"]},
        sample_cost="USD 0.2592",
        has_template_library=True,
        sample_examples=SAMPLE_INSPIRATIONS,
        provider="seedance",
        ratios=["16:9", "9:16", "1:1"],
        resolutions=["720p", "1080p"],
        durations=[5, 10],
        supports_audio=True,
        supports_draft=True,
        clip_counts=[1],
    ),
    "bytedance-seedance-1-0-pro-fast-251015": ModelInfo(
        id="bytedance-seedance-1-0-pro-fast-251015",
        display_name="ByteDance-Seedance-1.0-pro-fast 251015",
        category="video",
        description="Ultra-fast first-frame image-to-video generator with high throughput.",
        recommended_for="High-frequency short clip rendering, instant motion previews.",
        ui_layout_type="video_first",
        headline="Experience video generation and let creativity shake",
        icon_type="video",
        placeholder="(Optional) Enter the description based on the image.",
        input_slots=[{"id": "first_frame", "label": "first frame", "icon": "plus"}],
        sample_cost="USD 0.1030",
        sample_examples=SAMPLE_INSPIRATIONS,
        provider="seedance",
        ratios=["16:9", "9:16", "1:1"],
        resolutions=["720p"],
        durations=[5],
        supports_audio=False,
        clip_counts=[1],
    ),
    "dreamina-seedance-2-0-260128": ModelInfo(
        id="dreamina-seedance-2-0-260128",
        display_name="Dreamina-Seedance-2.0 260128",
        category="video",
        description="Standard Seedance 2.0 video model supporting ref-to-video, first/last frame, and IP effects.",
        recommended_for="General cutscenes and multi-asset reference generation.",
        ui_layout_type="video_ref",
        headline="Experience video generation and let creativity shake",
        icon_type="video",
        placeholder="Use @to quickly reference uploaded files, such as referring to actions in @Video 1 to generate videos of characters fighting in @Pictures 2 and @Pictures 3.",
        input_slots=[{"id": "reference", "label": "Reference", "icon": "plus"}],
        mode_selector={"enabled": True, "default": "Ref-to-video", "options": ["Ref-to-video", "First/last frame"]},
        sample_cost="USD 0.4500",
        sample_examples=SAMPLE_INSPIRATIONS,
        provider="seedance",
        ratios=["16:9", "9:16", "1:1", "4:3"],
        resolutions=["720p", "1080p"],
        durations=[5, 10],
        supports_audio=True,
        clip_counts=[1],
    ),
    "dreamina-seedance-2-0-mini-260615": ModelInfo(
        id="dreamina-seedance-2-0-mini-260615",
        display_name="Dreamina-Seedance-2.0-mini 260615",
        category="video",
        description="Lightweight and cost-efficient video model for high-frequency rendering.",
        recommended_for="Preview thumbnails and low-cost exploration.",
        ui_layout_type="video_ref",
        headline="Experience video generation and let creativity shake",
        icon_type="video",
        placeholder="Enter creative description for quick mini generation.",
        input_slots=[{"id": "reference", "label": "Reference", "icon": "plus"}],
        sample_cost="USD 0.0800",
        sample_examples=SAMPLE_INSPIRATIONS,
        provider="seedance",
        ratios=["16:9", "9:16", "1:1"],
        resolutions=["720p"],
        durations=[5],
        supports_audio=False,
        clip_counts=[1],
    ),

    "grok-imagine-video-1.5": ModelInfo(
        id="grok-imagine-video-1.5",
        display_name="Grok Imagine Video 1.5",
        category="video",
        description="xAI Grok Imagine video generation via api.x.ai.",
        recommended_for="Prompt-to-video when using an xAI key instead of BytePlus.",
        ui_layout_type="video_ref",
        headline="Generate video with Grok Imagine",
        icon_type="video",
        placeholder="Describe the shot. Optional reference image is attached as image_url.",
        input_slots=[{"id": "reference", "label": "Reference", "icon": "plus"}],
        mode_selector={"enabled": True, "default": "Ref-to-video", "options": ["Ref-to-video", "Text-to-video"]},
        sample_cost="",
        sample_examples=SAMPLE_INSPIRATIONS,
        provider="grok",
        ratios=["16:9", "9:16", "1:1", "4:3", "3:2", "2:3"],
        resolutions=[],
        durations=[5, 10, 15],
        supports_audio=False,
        clip_counts=[1],
    ),
    "grok-imagine-video": ModelInfo(
        id="grok-imagine-video",
        display_name="Grok Imagine Video",
        category="video",
        description="xAI Grok Imagine video (legacy SKU). Prefer grok-imagine-video-1.5 for 1080p.",
        recommended_for="Prompt-to-video on an xAI key when 1.5 is unavailable.",
        ui_layout_type="video_ref",
        headline="Generate video with Grok Imagine",
        icon_type="video",
        placeholder="Describe the shot. Optional reference image is attached as image_url.",
        input_slots=[{"id": "reference", "label": "Reference", "icon": "plus"}],
        mode_selector={"enabled": True, "default": "Ref-to-video", "options": ["Ref-to-video", "Text-to-video"]},
        sample_cost="USD 0.3500",
        sample_examples=SAMPLE_INSPIRATIONS,
        provider="grok",
        ratios=["16:9", "9:16", "1:1", "4:3", "3:2", "2:3"],
        resolutions=["480p", "720p"],
        durations=[5, 10],
        supports_audio=False,
        clip_counts=[1],
    ),

    # -------------------------------------------------------------------------
    # 2. IMAGE GENERATION MODELS (SEEDREAM + GROK IMAGINE)
    # -------------------------------------------------------------------------
    "grok-imagine-image-2.0": ModelInfo(
        id="grok-imagine-image-2.0",
        display_name="Grok Imagine Image 2.0",
        category="image",
        description="xAI Grok Imagine 2.0 text-to-image and multi-image editing (up to 5 refs). Recommended Grok image model.",
        recommended_for="High-fidelity stills, style transfer, and compositing on an xAI key.",
        ui_layout_type="image_standard",
        headline="Generate images with Grok Imagine 2.0",
        icon_type="image",
        placeholder="Describe the image. Attach up to 5 references with @Pictures N to edit or composite.",
        input_slots=[{"id": "image", "label": "Image", "icon": "image"}],
        mode_selector={"enabled": True, "default": "Image generation", "options": ["Image generation", "Image edit"]},
        pills=["16:9", "2K"],
        sample_cost="from USD 0.0400",
        sample_examples=SAMPLE_INSPIRATIONS,
        provider="grok",
        ratios=["16:9", "9:16", "1:1", "4:3", "3:2", "2:3", "21:9"],
        resolutions=["1K", "2K"],
        clip_counts=[1],
    ),
    "grok-imagine-image": ModelInfo(
        id="grok-imagine-image",
        display_name="Grok Imagine Image",
        category="image",
        description="xAI Grok Imagine speed image model. Flat $0.02 per image at 1K or 2K.",
        recommended_for="Fast drafts and cheap stills on an xAI key.",
        ui_layout_type="image_standard",
        headline="Generate images with Grok Imagine",
        icon_type="image",
        placeholder="Describe the image. Optional @Pictures N reference for edits.",
        input_slots=[{"id": "image", "label": "Image", "icon": "image"}],
        mode_selector={"enabled": True, "default": "Image generation", "options": ["Image generation", "Image edit"]},
        pills=["16:9", "2K"],
        sample_cost="USD 0.0200",
        sample_examples=SAMPLE_INSPIRATIONS,
        provider="grok",
        ratios=["16:9", "9:16", "1:1", "3:2", "2:3"],
        resolutions=["1K", "2K"],
        clip_counts=[1],
    ),
    "grok-imagine-image-quality": ModelInfo(
        id="grok-imagine-image-quality",
        display_name="Grok Imagine Image Quality",
        category="image",
        description="xAI higher-fidelity Grok Imagine image SKU. Retires 2026-11-02; prefer grok-imagine-image-2.0.",
        recommended_for="Maximum visual fidelity until the quality SKU is retired.",
        ui_layout_type="image_standard",
        headline="Generate images with Grok Imagine Quality",
        icon_type="image",
        placeholder="Describe the image. Optional @Pictures N reference for edits.",
        input_slots=[{"id": "image", "label": "Image", "icon": "image"}],
        mode_selector={"enabled": True, "default": "Image generation", "options": ["Image generation", "Image edit"]},
        pills=["16:9", "2K"],
        sample_cost="USD 0.0500",
        sample_examples=SAMPLE_INSPIRATIONS,
        provider="grok",
        ratios=["16:9", "9:16", "1:1", "3:2", "2:3"],
        resolutions=["1K", "2K"],
        clip_counts=[1],
    ),

    "dola-seedream-5-0-pro-260628": ModelInfo(
        id="dola-seedream-5-0-pro-260628",
        display_name="Dola-Seedream-5.0-pro 260628",
        category="image",
        description="Pro-tier multimodal image model with advanced identity preservation and style transfer.",
        recommended_for="Character turnarounds, consistent multi-angle reference sheets.",
        ui_layout_type="image_standard",
        headline="Shake up your creativity with image generation",
        icon_type="image",
        placeholder="Combine the picture and enter the creative description.",
        input_slots=[{"id": "image", "label": "Image", "icon": "image"}],
        mode_selector={"enabled": True, "default": "Image generation", "options": ["Image generation", "Image expansion"]},
        pills=["Smart ratio", "2K", "4piece"],
        sample_cost="0.180-0.360 USD",
        sample_examples=SAMPLE_INSPIRATIONS
    ),
    "bytedance-seedream-4-5-251128": ModelInfo(
        id="bytedance-seedream-4-5-251128",
        display_name="ByteDance-Seedream-4.5 251128",
        category="image",
        description="High-resolution SeeDream 4.5 supporting group diagram generation and multi-character composition.",
        recommended_for="Multi-subject story scenes, group diagrams, character turnarounds.",
        ui_layout_type="image_group",
        headline="Shake up your creativity with image generation",
        icon_type="image",
        placeholder="Combine the picture and enter the creative description.",
        input_slots=[{"id": "image", "label": "Image", "icon": "image"}],
        mode_selector={"enabled": True, "default": "Generate group diagram", "options": ["Generate group diagram", "Image generation"]},
        pills=["Smart ratio", "4K", "4piece"],
        sample_cost="estimated cost 0.160 USD",
        sample_examples=SAMPLE_INSPIRATIONS
    ),
    "seedream-5-0-260128": ModelInfo(
        id="seedream-5-0-260128",
        display_name="SeeDream-5.0 260128",
        category="image",
        description="Flagship text-to-image generator for crisp 2D retro sprites and character reference sheets.",
        recommended_for="Hermes character anchor generation and first/last keyframe images.",
        is_default=True,
        ui_layout_type="image_standard",
        headline="Shake up your creativity with image generation",
        icon_type="image",
        placeholder="Combine the picture and enter the creative description.",
        input_slots=[{"id": "image", "label": "Image", "icon": "image"}],
        mode_selector={"enabled": True, "default": "Image generation", "options": ["Image generation", "Image expansion"]},
        pills=["Smart ratio", "2K", "4piece"],
        sample_cost="USD 0.2000",
        sample_examples=SAMPLE_INSPIRATIONS
    ),
    "seedream-4-0-20260415": ModelInfo(
        id="seedream-4-0-20260415",
        display_name="SeeDream-4.0 20260415",
        category="image",
        description="Standard SeeDream image generator.",
        recommended_for="Standard image generation.",
        ui_layout_type="image_standard",
        headline="Shake up your creativity with image generation",
        icon_type="image",
        placeholder="Combine the picture and enter the creative description.",
        input_slots=[{"id": "image", "label": "Image", "icon": "image"}],
        mode_selector={"enabled": True, "default": "Image generation", "options": ["Image generation"]},
        pills=["Smart ratio", "1K", "2piece"],
        sample_cost="USD 0.1200",
        sample_examples=SAMPLE_INSPIRATIONS
    ),

    # -------------------------------------------------------------------------
    # 3. DIRECTOR & STORYBOARD PLANNING LLMs (SEED, DEEPSEEK, GLM)
    # -------------------------------------------------------------------------
    "seed-2-0-lite-260228": ModelInfo(
        id="seed-2-0-lite-260228",
        display_name="Seed 2.0 Lite (260228)",
        category="director_llm",
        description="Fast, reliable reasoning model natively supporting deep thinking and strict JSON outputs.",
        recommended_for="Default Director Agent for storyboard breakdown and milestone coordinates.",
        is_default=True,
        ui_layout_type="generic",
        headline="Plan Storyboards with ByteDance Seed 2.0",
        icon_type="llm"
    ),
    "seed-2-0-lite-260428": ModelInfo(
        id="seed-2-0-lite-260428",
        display_name="Seed 2.0 Lite (260428)",
        category="director_llm",
        description="Updated Seed 2.0 Lite checkpoint with improved schema adherence and context compression.",
        recommended_for="Technical documentation ingestion and structured storyboard generation.",
        ui_layout_type="generic",
        headline="Plan Storyboards with ByteDance Seed 2.0 Lite",
        icon_type="llm"
    ),
    "seed-2-0-pro-260328": ModelInfo(
        id="seed-2-0-pro-260328",
        display_name="Seed 2.0 Pro (260328)",
        category="director_llm",
        description="High-capability reasoning model with deep creative writing and architectural synthesis.",
        recommended_for="Complex narrative storyboarding, multi-scene cinematography, and in-depth prompt engineering.",
        ui_layout_type="generic",
        headline="Plan Storyboards with ByteDance Seed 2.0 Pro",
        icon_type="llm"
    ),
    "seed-2-0-mini-260215": ModelInfo(
        id="seed-2-0-mini-260215",
        display_name="Seed 2.0 Mini (260215)",
        category="director_llm",
        description="Compact, low-cost LLM for lightweight script and title generation.",
        recommended_for="Quick milestone title and narration generation.",
        ui_layout_type="generic",
        headline="Fast Storyboard Planning with Seed Mini",
        icon_type="llm"
    ),
    "seed-2-0-mini-260428": ModelInfo(
        id="seed-2-0-mini-260428",
        display_name="Seed 2.0 Mini (260428)",
        category="director_llm",
        description="Updated lightweight model for high-throughput roadmap generation.",
        recommended_for="Fast, low-latency topic decomposition.",
        ui_layout_type="generic",
        headline="Fast Storyboard Planning with Seed Mini",
        icon_type="llm"
    ),
    "dola-seed-2-1-turbo-260628": ModelInfo(
        id="dola-seed-2-1-turbo-260628",
        display_name="DOLA Seed 2.1 Turbo (260628)",
        category="director_llm",
        description="Next-generation Seed 2.1 Turbo with DOLA decoding for ultra-low latency.",
        recommended_for="Real-time interactive directing in the studio.",
        ui_layout_type="generic",
        headline="Ultra-low Latency Storyboarding with DOLA Seed 2.1 Turbo",
        icon_type="llm"
    ),
    "seed-2-0-code-preview-260328": ModelInfo(
        id="seed-2-0-code-preview-260328",
        display_name="Seed 2.0 Code Preview (260328)",
        category="director_llm",
        description="Specialized code intelligence model for Remotion TSX, shaders, and easing curves.",
        recommended_for="Remotion React/TSX animation component code generation.",
        ui_layout_type="generic",
        headline="Generate Remotion React TSX Code with Seed Code Preview",
        icon_type="llm"
    ),
    "deepseek-v4-1-flash-260910": ModelInfo(
        id="deepseek-v4-1-flash-260910",
        display_name="DeepSeek V4.1 Flash (260910)",
        category="director_llm",
        description="State-of-the-art DeepSeek V4.1 Flash checkpoint on BytePlus ModelArk with extreme token generation speed.",
        recommended_for="Massive documentation ingestion and high-speed multi-chapter planning.",
        ui_layout_type="generic",
        headline="DeepSeek V4.1 Flash High-Speed Intelligence",
        icon_type="llm"
    ),
    "deepseek-v4-pro-ga-260813": ModelInfo(
        id="deepseek-v4-pro-ga-260813",
        display_name="DeepSeek V4 Pro GA (260813)",
        category="director_llm",
        description="Flagship DeepSeek V4 Pro General Availability model with profound technical comprehension.",
        recommended_for="Highly technical architecture whitepapers and deep developer explainers.",
        ui_layout_type="generic",
        headline="DeepSeek V4 Pro GA Deep Architectural Planning",
        icon_type="llm"
    ),
    "deepseek-v4-flash-ga-260731": ModelInfo(
        id="deepseek-v4-flash-ga-260731",
        display_name="DeepSeek V4 Flash GA (260731)",
        category="director_llm",
        description="General Availability release of DeepSeek V4 Flash.",
        recommended_for="Production-grade fast planning.",
        ui_layout_type="generic",
        headline="DeepSeek V4 Flash Planning",
        icon_type="llm"
    ),
    "deepseek-v4-pro-260425": ModelInfo(
        id="deepseek-v4-pro-260425",
        display_name="DeepSeek V4 Pro (260425)",
        category="director_llm",
        description="DeepSeek V4 Pro foundation checkpoint.",
        recommended_for="Technical context analysis.",
        ui_layout_type="generic",
        headline="DeepSeek V4 Pro Context Analysis",
        icon_type="llm"
    ),
    "deepseek-v4-flash-260425": ModelInfo(
        id="deepseek-v4-flash-260425",
        display_name="DeepSeek V4 Flash (260425)",
        category="director_llm",
        description="DeepSeek V4 Flash foundation checkpoint.",
        recommended_for="Fast token streaming.",
        ui_layout_type="generic",
        headline="DeepSeek V4 Flash Fast Planning",
        icon_type="llm"
    ),
    "glm-5-3-flash-260828": ModelInfo(
        id="glm-5-3-flash-260828",
        display_name="GLM 5.3 Flash (260828)",
        category="director_llm",
        description="High-speed bilingual reasoning model with outstanding English and multilingual proficiency.",
        recommended_for="Multilingual storyboard planning and localized narration.",
        ui_layout_type="generic",
        headline="GLM 5.3 Flash Multilingual Planning",
        icon_type="llm"
    ),
    "glm-5-2-260617": ModelInfo(
        id="glm-5-2-260617",
        display_name="GLM 5.2 (260617)",
        category="director_llm",
        description="Robust bilingual foundation model.",
        recommended_for="Bilingual prompt generation.",
        ui_layout_type="generic",
        headline="GLM 5.2 Storyboard Planning",
        icon_type="llm"
    ),

    # -------------------------------------------------------------------------
    # 4. 3D ASSET & ITEM GENERATION
    # -------------------------------------------------------------------------
    "hyper3d-gen2-260112": ModelInfo(
        id="hyper3d-gen2-260112",
        display_name="Hyper3D Gen-2 (260112)",
        category="3d",
        description="3D mesh and environment generator from text prompts or single images.",
        recommended_for="Generating 3D floating stone platform assets and Greek temple structures.",
        ui_layout_type="generic",
        headline="Generate 3D Spatial Meshes with Hyper3D Gen-2",
        icon_type="3d"
    ),
    "hitem3d-2-0-251223": ModelInfo(
        id="hitem3d-2-0-251223",
        display_name="Hitem3D 2.0 (251223)",
        category="3d",
        description="Specialized 3D prop and item generator with clean topology.",
        recommended_for="Hero props: golden caduceus, winged sandals, parchment scroll meshes.",
        ui_layout_type="generic",
        headline="Generate 3D Hero Props with Hitem3D 2.0",
        icon_type="3d"
    ),

    # -------------------------------------------------------------------------
    # 5. VISION EMBEDDING & AUDITING
    # -------------------------------------------------------------------------
    "skylark-embedding-vision-251215": ModelInfo(
        id="skylark-embedding-vision-251215",
        display_name="Skylark Vision Embedding (251215)",
        category="vision_embedding",
        description="Dense visual embedding model for character likeness auditing and semantic frame verification.",
        recommended_for="Automated QA consistency checking and visual similarity validation.",
        ui_layout_type="generic",
        headline="Audit Visual Consistency with Skylark Vision",
        icon_type="vision"
    ),

    # -------------------------------------------------------------------------
    # 6. AUDIO & MUSIC GENERATION (MUREKA FAMILY)
    # -------------------------------------------------------------------------
    "mureka-9.5": ModelInfo(
        id="mureka-9.5",
        display_name="Mureka 9.5 (Flagship Music)",
        category="audio",
        description="Mureka flagship music model delivering high-fidelity vocals, rich instrumentation, and diverse styles.",
        recommended_for="Professional song generation, radio-ready vocal tracks.",
        is_default=True,
        ui_layout_type="audio_music",
        headline="Experience music generation and let melodies flow",
        icon_type="audio",
        placeholder="Describe your song theme, mood, tempo, or instrumentation (e.g., 'An energetic retro synthwave track with soaring lead melodies and driving 80s bassline').",
        input_slots=[{"id": "reference", "label": "Audio Ref", "icon": "plus"}],
        sample_cost="USD 0.30 lyrics-to-song / USD 1.00 prompt-to-song (2 songs)",
        provider="mureka",
        clip_counts=[1, 2, 3]
    ),
    "mureka-9": ModelInfo(
        id="mureka-9",
        display_name="Mureka 9.0",
        category="audio",
        description="High-fidelity music generation with nuanced genre blending.",
        recommended_for="General song production and background music.",
        ui_layout_type="audio_music",
        headline="Experience music generation and let melodies flow",
        icon_type="audio",
        placeholder="Describe your song theme, mood, tempo, or instrumentation.",
        input_slots=[{"id": "reference", "label": "Audio Ref", "icon": "plus"}],
        sample_cost="Price unavailable",
        provider="mureka",
        clip_counts=[1, 2, 3]
    ),
    "mureka-8": ModelInfo(
        id="mureka-8",
        display_name="Mureka 8.0 (Extension Specialist)",
        category="audio",
        description="High-coherence music model uniquely optimized for forward and backward song extensions (head/tail).",
        recommended_for="Extending tracks, expanding intros, building long-form music.",
        ui_layout_type="audio_music",
        headline="Experience music generation and let melodies flow",
        icon_type="audio",
        placeholder="Enter lyrics and style to extend the track.",
        input_slots=[{"id": "reference", "label": "Song Ref", "icon": "plus"}],
        sample_cost="Price unavailable",
        provider="mureka",
        clip_counts=[1, 2, 3]
    ),
    "mureka-7.6": ModelInfo(
        id="mureka-7.6",
        display_name="Mureka 7.6",
        category="audio",
        description="Fast, reliable music generator with strong lyrical adherence.",
        recommended_for="Fast song generation and classic tail extension.",
        ui_layout_type="audio_music",
        headline="Experience music generation and let melodies flow",
        icon_type="audio",
        placeholder="Describe your song theme or enter lyrics.",
        input_slots=[{"id": "reference", "label": "Audio Ref", "icon": "plus"}],
        sample_cost="Price unavailable",
        provider="mureka",
        clip_counts=[1, 2, 3]
    ),
    "mureka-soundtrack": ModelInfo(
        id="mureka-soundtrack",
        display_name="Mureka Soundtrack & BGM",
        category="audio",
        description="Specialized soundtrack and background music generation synced to visual scenes and timing cues.",
        recommended_for="Game background music, cutscene scores, and ambient themes.",
        ui_layout_type="audio_soundtrack",
        headline="Generate cinematic soundtracks and background scores",
        icon_type="audio",
        placeholder="Describe the mood, emotion, and scene ambiance for your soundtrack.",
        input_slots=[{"id": "scene_ref", "label": "Scene Ref", "icon": "plus"}],
        sample_cost="Price unavailable",
        provider="mureka",
        clip_counts=[1, 2, 3]
    ),
    "mureka-instrumental": ModelInfo(
        id="mureka-instrumental",
        display_name="Mureka Instrumental",
        category="audio",
        description="Pure instrumental audio generation without vocal synthesis.",
        recommended_for="Lo-fi beats, ambient soundscapes, orchestral pieces.",
        ui_layout_type="audio_music",
        headline="Generate pure instrumental arrangements",
        icon_type="audio",
        placeholder="Describe the instrumental arrangement, instruments, and style.",
        input_slots=[{"id": "reference", "label": "Audio Ref", "icon": "plus"}],
        sample_cost="Price unavailable",
        provider="mureka",
        clip_counts=[1, 2, 3]
    )
}

DEFAULT_VIDEO_MODEL = "dreamina-seedance-2-5-260628"
DEFAULT_DIRECTOR_MODEL = "seed-2-0-lite-260228"
DEFAULT_IMAGE_MODEL = "dola-seedream-5-0-pro-260628"
DEFAULT_AUDIO_MODEL = "mureka-9.5"

def get_models_by_category(category: str) -> List[Dict[str, Any]]:
    """Returns all models under a specific category as dicts."""
    return [
        asdict(m) for m in MODEL_CATALOG.values()
        if m.category == category
    ]

def get_all_models_grouped() -> Dict[str, List[Dict[str, Any]]]:
    """Returns all models organized by functional category."""
    grouped: Dict[str, List[Dict[str, Any]]] = {
        "video": [],
        "image": [],
        "audio": [],
        "director_llm": [],
        "3d": [],
        "vision_embedding": []
    }
    for m in MODEL_CATALOG.values():
        if m.category in grouped:
            grouped[m.category].append(asdict(m))
    return grouped


def get_model_info(model_id: str) -> Optional[ModelInfo]:
    """Returns metadata for a specific model ID."""
    return MODEL_CATALOG.get(model_id)


def calculate_model_cost(
    model_id: str,
    duration: int = 5,
    resolution: str = "720p",
    clip_count: int = 1,
    audio: bool = True,
    draft_mode: bool = False,
    reference_asset_count: int = 0,
    mode: str = "song_generate"
) -> str:
    """Calculates accurate expected cost for video and image model generations

    based on official BytePlus ModelArk and xAI API pricing schedules.
    """
    mid = (model_id or "").lower()
    res = (resolution or "720p").lower()
    clips = max(1, int(clip_count or 1))
    dur = max(1, int(duration or 5))
    # 0. Mureka Audio Models. Rates inferred from the account's observed
    # two-song Mureka 9.5 charges; Mureka bills per generated song.
    if "mureka" in mid or "soundtrack" in mid or "instrumental" in mid:
        audio_mode = (mode or "song_generate").lower()
        if mid == "mureka-9.5" and audio_mode in ("song", "song_generate", "lyrics_to_song"):
            return f"USD {0.15 * clips:.2f} estimated ({clips} song{'s' if clips != 1 else ''})"
        if mid == "mureka-9.5" and audio_mode in ("easy_generate", "prompt_to_song"):
            return f"USD {0.50 * clips:.2f} estimated ({clips} song{'s' if clips != 1 else ''})"
        return "Price unavailable — check Mureka billing"

    # 1. xAI Grok Imagine images (must beat generic "image" and grok video)
    if "grok" in mid and "image" in mid:
        is_2k = "2k" in res or "4k" in res or "1080" in res
        refs = max(0, int(reference_asset_count or 0))
        if "2.0" in mid or "2-0" in mid:
            rate = 0.0600 if is_2k else 0.0400
            input_fee = 0.0100 * refs
        elif "quality" in mid:
            rate = 0.0700 if is_2k else 0.0500
            input_fee = 0.0100 * refs
        else:
            rate = 0.0200
            input_fee = 0.0020 * refs
        cost = (rate + input_fee) * clips
        return f"USD {cost:.4f}"

    # 2. Image Models (SeeDream family)
    if any(k in mid for k in ["seedream", "image", "dola"]):
        if "5-0" in mid or "5.0" in mid:
            # Dola-Seedream-5.0-pro: 2K is 0.045-0.090 USD per piece, 4K is 0.060-0.120 USD per piece
            is_4k = "4k" in res
            min_rate = 0.060 if is_4k else 0.045
            max_rate = 0.120 if is_4k else 0.090
            min_cost = min_rate * clips
            max_cost = max_rate * clips
            return f"{min_cost:.3f}-{max_cost:.3f} USD"
        elif "4-5" in mid or "4.5" in mid:
            # ByteDance-Seedream-4.5: 2K is 0.030 USD, 4K is 0.040 USD per piece
            is_4k = "4k" in res
            rate = 0.040 if is_4k else 0.030
            cost = rate * clips
            return f"estimated cost {cost:.3f} USD"
        else:
            # Generic/3.0 image model
            is_4k = "4k" in res
            rate = 0.035 if is_4k else 0.025
            cost = rate * clips
            return f"USD {cost:.4f}"

    # 3. xAI Grok Family (Video)
    if "grok" in mid:
        if "1.5" in mid or "1-5" in mid:
            # grok-imagine-video-1.5: 480p: $0.08/s, 720p: $0.14/s, 1080p: $0.25/s, +$0.01 per ref image
            if "1080" in res:
                rate_per_sec = 0.2500
            elif "480" in res:
                rate_per_sec = 0.0800
            else:
                rate_per_sec = 0.1400
            image_charge = 0.0100 * max(0, reference_asset_count)
            cost = ((rate_per_sec * dur) + image_charge) * clips
            return f"USD {cost:.4f}"
        else:
            # grok-imagine-video: 480p: $0.05/s, 720p: $0.07/s
            rate_per_sec = 0.0500 if "480" in res else 0.0700
            cost = (rate_per_sec * dur) * clips
            return f"USD {cost:.4f}"

    # 3. BytePlus Seedance Family (Video)
    if "2-5" in mid or "2.5" in mid or "2-0-fast" in mid or "2.0-fast" in mid:
        # Seedance 2.5 and 2.0-fast: 5s 720p with sound = 0.6048 USD (rate = 0.12096/sec)
        if "1080" in res:
            rate_per_sec = 0.24192
        elif "480" in res:
            rate_per_sec = 0.08000
        else:
            rate_per_sec = 0.12096
    elif "2-0-mini" in mid or "2.0-mini" in mid:
        # Seedance 2.0-mini: 5s 720p = 0.0800 USD (rate = 0.01600/sec)
        if "480" in res:
            rate_per_sec = 0.01000
        else:
            rate_per_sec = 0.01600
    elif "1-5" in mid or "1.5" in mid:
        # Seedance 1.5-pro: 5s 720p with sound = 0.2592 USD (rate = 0.05184/sec)
        if "1080" in res:
            rate_per_sec = 0.10300
        elif "480" in res:
            rate_per_sec = 0.03500
        else:
            rate_per_sec = 0.05184
    elif "1-0-pro-fast" in mid or "1.0-pro-fast" in mid:
        # Seedance 1.0-pro-fast: 5s 720p = 0.1030 USD (rate = 0.02060/sec)
        if "480" in res:
            rate_per_sec = 0.01500
        else:
            rate_per_sec = 0.02060
    elif "1-0" in mid or "1.0" in mid:
        # Seedance 1.0-pro: 5s 720p = 0.2000 USD (rate = 0.04000/sec)
        if "480" in res:
            rate_per_sec = 0.02500
        else:
            rate_per_sec = 0.04000
    else:
        # Default video model
        if "1080" in res:
            rate_per_sec = 0.18000
        elif "480" in res:
            rate_per_sec = 0.05000
        else:
            rate_per_sec = 0.09000

    multiplier = 0.5 if draft_mode else 1.0
    cost = rate_per_sec * dur * multiplier * clips
    return f"USD {cost:.4f}"

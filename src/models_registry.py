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
    input_slots: List[Dict[str, str]] = field(default_factory=lambda: [{"id": "reference", "label": "Reference", "icon": "plus"}])
    mode_selector: Optional[Dict[str, Any]] = None
    pills: List[str] = field(default_factory=lambda: ["16:9", "720P", "5 seconds", "1 videos"])
    sample_cost: str = "USD 0.6048"
    has_template_library: bool = False
    sample_examples: List[Dict[str, str]] = field(default_factory=list)

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
        mode_selector={"enabled": True, "default": "Ref-to-video", "options": ["Ref-to-video", "Text-to-video"]},
        pills=["16:9", "1080P", "5 seconds", "sound", "1 videos"],
        sample_cost="USD 0.6048",
        sample_examples=SAMPLE_INSPIRATIONS
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
        mode_selector={"enabled": True, "default": "Ref-to-video", "options": ["Ref-to-video", "Text-to-video"]},
        pills=["16:9", "720P", "5 seconds", "sound", "1 videos"],
        sample_cost="USD 0.6048",
        sample_examples=SAMPLE_INSPIRATIONS
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
        pills=["16:9", "720P", "5 seconds", "sound", "1 videos", "Draft mode", "offline generation"],
        sample_cost="USD 0.2592",
        has_template_library=True,
        sample_examples=SAMPLE_INSPIRATIONS
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
        pills=["16:9", "720P", "5 seconds", "1 videos"],
        sample_cost="USD 0.1030",
        sample_examples=SAMPLE_INSPIRATIONS
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
        mode_selector={"enabled": True, "default": "Ref-to-video", "options": ["Ref-to-video", "First/last frame", "IP effects"]},
        pills=["16:9", "720P", "5 seconds", "sound", "1 videos"],
        sample_cost="USD 0.4500",
        sample_examples=SAMPLE_INSPIRATIONS
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
        pills=["16:9", "720P", "5 seconds", "1 videos"],
        sample_cost="USD 0.0800",
        sample_examples=SAMPLE_INSPIRATIONS
    ),

    # -------------------------------------------------------------------------
    # 2. IMAGE GENERATION MODELS (SEEDREAM FAMILY)
    # -------------------------------------------------------------------------
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
    )
}

DEFAULT_VIDEO_MODEL = "dreamina-seedance-2-5-260628"
DEFAULT_DIRECTOR_MODEL = "seed-2-0-lite-260228"
DEFAULT_IMAGE_MODEL = "dola-seedream-5-0-pro-260628"

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

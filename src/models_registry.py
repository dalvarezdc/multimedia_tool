"""BytePlus ModelArk & Seedance Complete Model Catalog.

Defines all 24 available BytePlus ModelArk models across:
1. Video Generation (Seedance 2.5, 2.0, Fast, Mini)
2. Director & Planning LLMs (Seed 2.0, DeepSeek V4, GLM-5)
3. Image & Character Anchor Generation (SeeDream 5.0, DOLA SeeDream Pro)
4. 3D Asset & Item Generation (Hyper3D, Hitem3D)
5. Vision Embedding (Skylark Vision)
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class ModelInfo:
    id: str
    display_name: str
    category: str
    description: str
    recommended_for: str
    is_default: bool = False

MODEL_CATALOG: Dict[str, ModelInfo] = {
    # -------------------------------------------------------------------------
    # 1. VIDEO GENERATION MODELS (SEEDANCE FAMILY)
    # -------------------------------------------------------------------------
    "dreamina-seedance-2-5-260628": ModelInfo(
        id="dreamina-seedance-2-5-260628",
        display_name="Seedance 2.5 Flagship (260628)",
        category="video",
        description="Flagship video generation model with superior character coherence, 1080p, and complex physics.",
        recommended_for="Final production cutscenes, complex camera pans, hero narrative shots.",
        is_default=True
    ),
    "dreamina-seedance-2-0-260128": ModelInfo(
        id="dreamina-seedance-2-0-260128",
        display_name="Seedance 2.0 Standard (260128)",
        category="video",
        description="Standard Seedance 2.0 video model supporting ref-to-video, first/last frame, and IP effects.",
        recommended_for="General cutscenes and multi-asset reference generation."
    ),
    "dreamina-seedance-2-0-fast-260128": ModelInfo(
        id="dreamina-seedance-2-0-fast-260128",
        display_name="Seedance 2.0 Fast (260128)",
        category="video",
        description="Accelerated video generation pipeline with reduced generation latency.",
        recommended_for="Rapid prototyping, storyboard previews, fast drafting."
    ),
    "dreamina-seedance-2-0-mini-260615": ModelInfo(
        id="dreamina-seedance-2-0-mini-260615",
        display_name="Seedance 2.0 Mini (260615)",
        category="video",
        description="Lightweight and cost-efficient video model for high-frequency rendering.",
        recommended_for="Preview thumbnails and low-cost exploration."
    ),

    # -------------------------------------------------------------------------
    # 2. DIRECTOR & STORYBOARD PLANNING LLMs (SEED, DEEPSEEK, GLM)
    # -------------------------------------------------------------------------
    "seed-2-0-lite-260228": ModelInfo(
        id="seed-2-0-lite-260228",
        display_name="Seed 2.0 Lite (260228)",
        category="director_llm",
        description="Fast, reliable reasoning model natively supporting deep thinking and strict JSON outputs.",
        recommended_for="Default Director Agent for storyboard breakdown and milestone coordinates.",
        is_default=True
    ),
    "seed-2-0-lite-260428": ModelInfo(
        id="seed-2-0-lite-260428",
        display_name="Seed 2.0 Lite (260428)",
        category="director_llm",
        description="Updated Seed 2.0 Lite checkpoint with improved schema adherence and context compression.",
        recommended_for="Technical documentation ingestion and structured storyboard generation."
    ),
    "seed-2-0-pro-260328": ModelInfo(
        id="seed-2-0-pro-260328",
        display_name="Seed 2.0 Pro (260328)",
        category="director_llm",
        description="High-capability reasoning model with deep creative writing and architectural synthesis.",
        recommended_for="Complex narrative storyboarding, multi-scene cinematography, and in-depth prompt engineering."
    ),
    "seed-2-0-mini-260215": ModelInfo(
        id="seed-2-0-mini-260215",
        display_name="Seed 2.0 Mini (260215)",
        category="director_llm",
        description="Compact, low-cost LLM for lightweight script and title generation.",
        recommended_for="Quick milestone title and narration generation."
    ),
    "seed-2-0-mini-260428": ModelInfo(
        id="seed-2-0-mini-260428",
        display_name="Seed 2.0 Mini (260428)",
        category="director_llm",
        description="Updated lightweight model for high-throughput roadmap generation.",
        recommended_for="Fast, low-latency topic decomposition."
    ),
    "dola-seed-2-1-turbo-260628": ModelInfo(
        id="dola-seed-2-1-turbo-260628",
        display_name="DOLA Seed 2.1 Turbo (260628)",
        category="director_llm",
        description="Next-generation Seed 2.1 Turbo with DOLA decoding for ultra-low latency.",
        recommended_for="Real-time interactive directing in the studio."
    ),
    "seed-2-0-code-preview-260328": ModelInfo(
        id="seed-2-0-code-preview-260328",
        display_name="Seed 2.0 Code Preview (260328)",
        category="director_llm",
        description="Specialized code intelligence model for Remotion TSX, shaders, and easing curves.",
        recommended_for="Remotion React/TSX animation component code generation."
    ),
    "deepseek-v4-1-flash-260910": ModelInfo(
        id="deepseek-v4-1-flash-260910",
        display_name="DeepSeek V4.1 Flash (260910)",
        category="director_llm",
        description="State-of-the-art DeepSeek V4.1 Flash checkpoint on BytePlus ModelArk with extreme token generation speed.",
        recommended_for="Massive documentation ingestion and high-speed multi-chapter planning."
    ),
    "deepseek-v4-pro-ga-260813": ModelInfo(
        id="deepseek-v4-pro-ga-260813",
        display_name="DeepSeek V4 Pro GA (260813)",
        category="director_llm",
        description="Flagship DeepSeek V4 Pro General Availability model with profound technical comprehension.",
        recommended_for="Highly technical architecture whitepapers and deep developer explainers."
    ),
    "deepseek-v4-flash-ga-260731": ModelInfo(
        id="deepseek-v4-flash-ga-260731",
        display_name="DeepSeek V4 Flash GA (260731)",
        category="director_llm",
        description="General Availability release of DeepSeek V4 Flash.",
        recommended_for="Production-grade fast planning."
    ),
    "deepseek-v4-pro-260425": ModelInfo(
        id="deepseek-v4-pro-260425",
        display_name="DeepSeek V4 Pro (260425)",
        category="director_llm",
        description="DeepSeek V4 Pro foundation checkpoint.",
        recommended_for="Technical context analysis."
    ),
    "deepseek-v4-flash-260425": ModelInfo(
        id="deepseek-v4-flash-260425",
        display_name="DeepSeek V4 Flash (260425)",
        category="director_llm",
        description="DeepSeek V4 Flash foundation checkpoint.",
        recommended_for="Fast token streaming."
    ),
    "glm-5-3-flash-260828": ModelInfo(
        id="glm-5-3-flash-260828",
        display_name="GLM 5.3 Flash (260828)",
        category="director_llm",
        description="High-speed bilingual reasoning model with outstanding English and multilingual proficiency.",
        recommended_for="Multilingual storyboard planning and localized narration."
    ),
    "glm-5-2-260617": ModelInfo(
        id="glm-5-2-260617",
        display_name="GLM 5.2 (260617)",
        category="director_llm",
        description="Robust bilingual foundation model.",
        recommended_for="Bilingual prompt generation."
    ),

    # -------------------------------------------------------------------------
    # 3. IMAGE & CHARACTER ANCHOR GENERATION (SEEDREAM FAMILY)
    # -------------------------------------------------------------------------
    "seedream-5-0-260128": ModelInfo(
        id="seedream-5-0-260128",
        display_name="SeeDream 5.0 (260128)",
        category="image",
        description="Flagship text-to-image generator for crisp 2D retro sprites and character reference sheets.",
        recommended_for="Hermes character anchor generation and first/last keyframe images.",
        is_default=True
    ),
    "dola-seedream-5-0-pro-260628": ModelInfo(
        id="dola-seedream-5-0-pro-260628",
        display_name="DOLA SeeDream 5.0 Pro (260628)",
        category="image",
        description="Pro-tier multimodal image model with advanced identity preservation and style transfer.",
        recommended_for="Character turnarounds, consistent multi-angle reference sheets."
    ),
    "seedream-4-0-20260415": ModelInfo(
        id="seedream-4-0-20260415",
        display_name="SeeDream 4.0 (20260415)",
        category="image",
        description="Previous generation SeeDream image generator.",
        recommended_for="Standard image generation."
    ),

    # -------------------------------------------------------------------------
    # 4. 3D ASSET & ITEM GENERATION
    # -------------------------------------------------------------------------
    "hyper3d-gen2-260112": ModelInfo(
        id="hyper3d-gen2-260112",
        display_name="Hyper3D Gen-2 (260112)",
        category="3d",
        description="3D mesh and environment generator from text prompts or single images.",
        recommended_for="Generating 3D floating stone platform assets and Greek temple structures."
    ),
    "hitem3d-2-0-251223": ModelInfo(
        id="hitem3d-2-0-251223",
        display_name="Hitem3D 2.0 (251223)",
        category="3d",
        description="Specialized 3D prop and item generator with clean topology.",
        recommended_for="Hero props: golden caduceus, winged sandals, parchment scroll meshes."
    ),

    # -------------------------------------------------------------------------
    # 5. VISION EMBEDDING & AUDITING
    # -------------------------------------------------------------------------
    "skylark-embedding-vision-251215": ModelInfo(
        id="skylark-embedding-vision-251215",
        display_name="Skylark Vision Embedding (251215)",
        category="vision_embedding",
        description="Dense visual embedding model for character likeness auditing and semantic frame verification.",
        recommended_for="Automated QA consistency checking and visual similarity validation."
    )
}

DEFAULT_VIDEO_MODEL = "dreamina-seedance-2-5-260628"
DEFAULT_DIRECTOR_MODEL = "seed-2-0-lite-260228"
DEFAULT_IMAGE_MODEL = "seedream-5-0-260128"

def get_models_by_category(category: str) -> List[Dict[str, Any]]:
    """Returns all models under a specific category as dicts."""
    return [
        asdict(m) for m in MODEL_CATALOG.values()
        if m.category == category
    ]

def get_all_models_grouped() -> Dict[str, List[Dict[str, Any]]]:
    """Returns all 24 models organized by functional category."""
    grouped: Dict[str, List[Dict[str, Any]]] = {
        "video": [],
        "director_llm": [],
        "image": [],
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

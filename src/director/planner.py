"""Director & Storyboard Planning Agent.

Uses BytePlus ModelArk seed-2-0-lite-260228 to decompose high-level topics or transcripts
into structured milestone roadmaps, platform coordinates, and visual cutscene prompts,
with full support for global domain context and character consistency.
"""

import os
import json
import logging
import re
from typing import Dict, Any, Optional
from arkruntime import Ark

logger = logging.getLogger(__name__)

class DirectorPlanner:
    """Orchestrates topic breakdown, context integration, and storyboard generation using seed-2-0-lite."""

    FALLBACK_MODELS = [
        "seed-2-0-lite-260428",
        "seed-2-0-lite-260228",
        "deepseek-v4-1-flash-260910",
        "seed-2-0-pro-260328",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://ark.ap-southeast.bytepluses.com/api/v3",
        model_id: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("ARK_API_KEY")
        if not self.api_key:
            raise ValueError("ARK_API_KEY must be provided or set in environment variables.")

        self.base_url = os.getenv("ARK_BASE_URL", base_url)
        self.model_id = model_id or os.getenv("ARK_LLM_MODEL") or "seed-2-0-lite-260228"
        self.active_model_used = self.model_id

        self.client = Ark(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    def plan_storyboard(
        self,
        topic_or_transcript: str,
        global_context: Optional[Dict[str, str]] = None,
        character_profile: Optional[Dict[str, Any]] = None,
        chapter_count: int = 4,
        purpose: str = "storyboard",
    ) -> Dict[str, Any]:
        """Decomposes the input content into sequential milestone platforms and video prompts.

        Args:
            topic_or_transcript: Main topic, title, or transcript to explain.
            global_context: Detailed background notes, technical documentation, tone, or lore.
            character_profile: Consistent character definition (name, reference image, traits).
            chapter_count: Number of roadmap milestones to generate (default: 4).

        Returns:
            Dictionary matching the Master StoryboardSpec schema.
        """
        char = character_profile or {
            "name": "Hermes",
            "reference_image_url": "assets/characters/hermes_reference.png",
            "prompt_tokens": "chibi young hero with golden winged helmet, blue messenger tunic, and golden caduceus",
            "sprite_id": "hermes_pixel"
        }

        ctx_str = ""
        if global_context:
            domain_notes = global_context.get("domain_notes", "")
            tone = global_context.get("tone", "educational, retro gaming, epic")
            audience = global_context.get("target_audience", "developers and tech enthusiasts")
            ctx_str = f"""
            GLOBAL CONTEXT & DOMAIN KNOWLEDGE:
            {domain_notes}
            
            TONE: {tone}
            TARGET AUDIENCE: {audience}
            """

        user_prompt = f"""
        You are an expert director for automated educational technical animations.
        Break down the following topic into {chapter_count} sequential milestones for a 2D retro platformer level:
        TOPIC: "{topic_or_transcript}"

        {ctx_str}

        CHARACTER CONSISTENCY REQUIREMENT:
        The protagonist is '{char['name']}', described as: {char['prompt_tokens']}.
        In each chapter's 'seedance_prompt', you MUST feature this exact character (referencing 'Image 1' character reference) 
        interacting with the concept or environment to maintain visual continuity across every cutscene.

        Each milestone represents a floating stone platform with a signpost that the character visits.
        For each milestone, provide:
        1. 'title': Very concise signpost label (max 3 words, e.g., 'Hardware Choices').
        2. 'speaker': Who speaks at this shrine (usually {char['name']}, or a named guide).
        3. 'narration_text': 2-sentence in-world spoken explanation the player hears at the shrine.
        4. 'platform': object with x (350-1750, spaced at least 350px apart left-to-right), y (420-700), width (160-200).
        5. 'seedance_prompt': A vivid, cinematic visual prompt describing a 5-second video illustrating the concept featuring the character in Image 1. Do NOT mention text, captions, or UI.
        {"" if purpose != "rpg" else "This will be played as an in-browser RPG: keep titles signpost-short, dialogue spoken aloud, and platforms walkable left-to-right."}

        Return strictly valid JSON matching this schema:
        {{
          "project_id": "proj_001",
          "theme": "greek_night_sky",
          "global_context": {{
            "domain_notes": "{global_context.get('domain_notes', '') if global_context else ''}",
            "tone": "{global_context.get('tone', '') if global_context else 'educational'}",
            "target_audience": "{global_context.get('target_audience', '') if global_context else 'general'}"
          }},
          "character_profile": {{
            "name": "{char['name']}",
            "reference_image_url": "{char['reference_image_url']}",
            "prompt_tokens": "{char['prompt_tokens']}",
            "sprite_id": "{char['sprite_id']}"
          }},
          "resolution": {{"width": 1920, "height": 1080}},
          "fps": 60,
          "chapters": [
            {{
              "id": 1,
              "title": "...",
              "speaker": "{char['name']}",
              "narration_text": "...",
              "platform": {{"x": 350, "y": 620, "width": 180}},
              "seedance_prompt": "Cinematic shot of the character in Image 1...",
              "cutscene_mode": "fullscreen_dissolve",
              "duration_seconds": 6
            }}
          ]
        }}
        """

        logger.info(f"Invoking Director Model {self.model_id} ({purpose}) with context & character consistency...")
        try:
            storyboard = self._complete_json(user_prompt)
            storyboard["_director_mode"] = "cloud_llm"
            storyboard["_director_model_used"] = getattr(self, "active_model_used", self.model_id)
            return storyboard
        except Exception as exc:
            logger.warning(
                f"Director cloud LLM call failed ({exc}); falling back to deterministic pedagogical generator."
            )
            storyboard = self._generate_heuristic_storyboard(
                topic_or_transcript=topic_or_transcript,
                global_context=global_context,
                character_profile=char,
                chapter_count=chapter_count,
                purpose=purpose,
            )
            storyboard["_director_mode"] = "heuristic_fallback"
            storyboard["_director_note"] = (
                f"Storyboard planned via local Director engine. Cloud model '{self.model_id}' "
                f"was not accessible (404/NotFound). You can configure a custom endpoint in Settings."
            )
            return storyboard

    def improve_storyboard(
        self,
        storyboard: Dict[str, Any],
        instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Rewrites an existing storyboard in-place: clearer shrine titles, dialogue, and spacing."""
        hint = instruction or (
            "Tighten pedagogy. Make shrine titles max 3 words, dialogue two spoken sentences, "
            "and space platform x values left-to-right with at least 350px between shrines."
        )
        user_prompt = f"""
        You are revising an educational RPG storyboard. Return STRICTLY valid JSON in the same schema.
        Do not drop chapters. Improve titles, speaker names, narration_text (in-world dialogue),
        platform coordinates, and seedance_prompt quality.

        REVISION GOAL:
        {hint}

        CURRENT STORYBOARD JSON:
        {json.dumps(storyboard, indent=2)}
        """
        logger.info(f"Improving storyboard with Director Model {self.model_id}...")
        try:
            improved = self._complete_json(user_prompt)
            improved["_director_mode"] = "cloud_llm"
            improved["_director_model_used"] = getattr(self, "active_model_used", self.model_id)
            return improved
        except Exception as exc:
            logger.warning(f"Director cloud improve call failed ({exc}); applying rule-based polishing.")
            return self._improve_heuristic_storyboard(storyboard, instruction=hint)

    def _call_remote(self, model_id: str, prompt: str) -> str:
        """Attempts completion via chat.completions, then responses.create."""
        last_err = None
        if hasattr(self.client, "chat") and hasattr(self.client.chat, "completions"):
            try:
                resp = self.client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                )
                if hasattr(resp, "choices") and resp.choices:
                    choice = resp.choices[0]
                    if hasattr(choice, "message") and hasattr(choice.message, "content"):
                        content = choice.message.content
                        if content:
                            return content
            except Exception as e_chat:
                last_err = e_chat
                logger.debug(f"chat.completions failed for {model_id}: {e_chat}, trying responses.create...")

        if hasattr(self.client, "responses") and hasattr(self.client.responses, "create"):
            try:
                resp = self.client.responses.create(
                    model=model_id,
                    input=prompt,
                )
                if hasattr(resp, "output") and resp.output:
                    return resp.output[0].text
                return str(resp)
            except Exception as e_resp:
                last_err = e_resp
                logger.debug(f"responses.create failed for {model_id}: {e_resp}")

        if last_err:
            raise last_err
        raise RuntimeError("No suitable LLM completion method available on Ark client.")

    def _complete_json(self, user_prompt: str) -> Dict[str, Any]:
        """Runs prompt through primary model with fallback candidate models on 404/NotFound."""
        candidates = [self.model_id] + [m for m in self.FALLBACK_MODELS if m != self.model_id]
        last_exc: Optional[Exception] = None

        for model in candidates:
            try:
                logger.info(f"Attempting Director LLM call with model {model}...")
                raw_output = self._call_remote(model, user_prompt)
                parsed = _parse_json_object(raw_output)
                self.active_model_used = model
                return parsed
            except Exception as exc:
                err_str = str(exc)
                last_exc = exc
                is_not_found = (
                    "NotFound" in err_str
                    or "404" in err_str
                    or "does not exist" in err_str
                    or "do not have access" in err_str
                )
                if is_not_found:
                    logger.warning(f"Model {model} unavailable (404/NotFound). Checking fallback candidates...")
                    continue
                # If it's a parsing error or other error, try next candidate
                logger.warning(f"Model {model} failed: {exc}. Trying next candidate...")

        if last_exc:
            raise last_exc
        raise RuntimeError("Failed to complete Director LLM prompt across all candidates.")

    def _generate_heuristic_storyboard(
        self,
        topic_or_transcript: str,
        global_context: Optional[Dict[str, str]] = None,
        character_profile: Optional[Dict[str, Any]] = None,
        chapter_count: int = 4,
        purpose: str = "storyboard",
    ) -> Dict[str, Any]:
        """Generates a high-quality pedagogical storyboard when cloud LLMs are unavailable."""
        char = character_profile or {
            "name": "Hermes",
            "reference_image_url": "assets/characters/hermes_reference.png",
            "prompt_tokens": "chibi young hero with golden winged helmet, blue messenger tunic, and golden caduceus",
            "sprite_id": "hermes_pixel"
        }
        topic_clean = topic_or_transcript.strip() or "Foundations of Technology"
        is_apple_silicon = "apple" in topic_clean.lower() or "silicon" in topic_clean.lower() or "llm" in topic_clean.lower()

        if is_apple_silicon:
            templates = [
                {
                    "title": "Unified Memory",
                    "narration": f"Apple Silicon combines CPU and GPU memory into a single high-bandwidth unified pool. {char['name']} inspects the unified RAM bus where weights reside without PCIe bottlenecks.",
                    "prompt": f"Cinematic shot of {char['name']} with {char['prompt_tokens']} (referencing Image 1) examining glowing unified memory circuits in a celestial workshop, volumetric starlight, 60fps cinematic"
                },
                {
                    "title": "Quantization Core",
                    "narration": f"Model weights are compressed down to 4-bit and 8-bit GGUF representations. This allows multi-billion parameter LLMs to fit directly inside system RAM.",
                    "prompt": f"Cinematic shot of {char['name']} with {char['prompt_tokens']} (referencing Image 1) manipulating floating holographic crystalline tensor blocks, glowing cyber runes, 60fps cinematic"
                },
                {
                    "title": "Metal & Neural Core",
                    "narration": f"Apple Metal Performance Shaders and Neural Engine cores compute matrix multiplications in parallel. On-die execution maximizes tokens per second with minimal power.",
                    "prompt": f"Cinematic shot of {char['name']} with {char['prompt_tokens']} (referencing Image 1) channeling cyan energy into floating silicon chip architectures, volumetric smoke, 60fps cinematic"
                },
                {
                    "title": "Local Autoregression",
                    "narration": f"The key-value cache continuously stores attention states for instant token output. Local inference keeps all data private while delivering blazing interactive speeds.",
                    "prompt": f"Cinematic hero shot of {char['name']} with {char['prompt_tokens']} (referencing Image 1) at a celestial mountaintop watching golden token streams orbit an ancient temple, 60fps cinematic"
                },
                {
                    "title": "On-Device Mastery",
                    "narration": f"Developers harness local agents and fine-tuned models directly on their workstation. Complete autonomy and zero latency unlock the next era of computing.",
                    "prompt": f"Cinematic wide shot of {char['name']} with {char['prompt_tokens']} (referencing Image 1) raising the golden caduceus above a futuristic marble horizon, golden sunrise, 60fps cinematic"
                }
            ]
        else:
            words = [w.capitalize() for w in re.findall(r"[A-Za-z0-9]+", topic_clean) if len(w) > 2]
            key_kw = words[0] if words else "System"
            templates = [
                {
                    "title": f"{key_kw} Foundations",
                    "narration": f"Welcome to the study of {topic_clean}. {char['name']} steps forward to examine the foundational building blocks and core principles.",
                    "prompt": f"Cinematic shot of {char['name']} with {char['prompt_tokens']} (referencing Image 1) at the first marble milestone shrine in a starlit realm, 60fps cinematic"
                },
                {
                    "title": "Core Architecture",
                    "narration": f"Understanding the inner workings is critical for mastery. Here, {char['name']} observes how data, state, and execution flows interact seamlessly.",
                    "prompt": f"Cinematic shot of {char['name']} with {char['prompt_tokens']} (referencing Image 1) analyzing luminous floating diagrams of {topic_clean}, 60fps cinematic"
                },
                {
                    "title": "Performance Tuning",
                    "narration": f"Optimization transforms theoretical designs into responsive realities. Every bottleneck is systematically measured and tuned for peak efficiency.",
                    "prompt": f"Cinematic shot of {char['name']} with {char['prompt_tokens']} (referencing Image 1) calibrating glowing ancient clockwork mechanisms, 60fps cinematic"
                },
                {
                    "title": "Production Deployment",
                    "narration": f"With every milestone conquered, the complete architecture operates autonomously. {char['name']} celebrates the journey from initial concept to full realization.",
                    "prompt": f"Cinematic grand finale shot of {char['name']} with {char['prompt_tokens']} (referencing Image 1) reaching the summit shrine overlooking a starlit aurora, 60fps cinematic"
                },
                {
                    "title": "Future Horizons",
                    "narration": f"The knowledge gained opens new doors to scalable innovation. Forward progress continues with each new exploration.",
                    "prompt": f"Cinematic shot of {char['name']} with {char['prompt_tokens']} (referencing Image 1) looking outward into infinite starlight horizons, 60fps cinematic"
                }
            ]

        selected_templates = templates[:max(1, min(chapter_count, len(templates)))]
        # If chapter_count > len(templates), cycle or pad
        while len(selected_templates) < chapter_count:
            idx = len(selected_templates) + 1
            selected_templates.append({
                "title": f"Milestone {idx}",
                "narration": f"Advancing through stage {idx} of {topic_clean}. {char['name']} uncovers deeper technical insights.",
                "prompt": f"Cinematic shot of {char['name']} with {char['prompt_tokens']} (referencing Image 1) at shrine {idx}, 60fps cinematic"
            })

        chapters = []
        for i, t in enumerate(selected_templates):
            x_coord = 350 + i * 360
            y_coord = 620 - (i % 2) * 50
            chapters.append({
                "id": i + 1,
                "title": t["title"],
                "speaker": char["name"],
                "narration_text": t["narration"],
                "platform": {"x": x_coord, "y": y_coord, "width": 180},
                "seedance_prompt": t["prompt"],
                "cutscene_mode": "fullscreen_dissolve",
                "duration_seconds": 6
            })

        return {
            "project_id": "proj_001",
            "theme": "greek_night_sky",
            "global_context": {
                "domain_notes": global_context.get("domain_notes", topic_clean) if global_context else topic_clean,
                "tone": global_context.get("tone", "educational retro rpg") if global_context else "educational retro rpg",
                "target_audience": global_context.get("target_audience", "developers") if global_context else "developers"
            },
            "character_profile": {
                "name": char["name"],
                "reference_image_url": char.get("reference_image_url", "assets/characters/hermes_reference.png"),
                "prompt_tokens": char.get("prompt_tokens", "chibi young hero with winged helmet"),
                "sprite_id": char.get("sprite_id", "hermes_pixel")
            },
            "resolution": {"width": 1920, "height": 1080},
            "fps": 60,
            "chapters": chapters
        }

    def _improve_heuristic_storyboard(
        self,
        storyboard: Dict[str, Any],
        instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """Polishes and tightens titles, narration, and platform spacing without cloud LLM."""
        improved = dict(storyboard)
        chapters = list(improved.get("chapters", []))
        char_name = improved.get("character_profile", {}).get("name", "Hermes")

        for i, ch in enumerate(chapters):
            # 1. Platform spacing
            ch["platform"] = {
                "x": 350 + i * 360,
                "y": 620 - (i % 2) * 50,
                "width": 180
            }
            # 2. Title tightening (max 3 words)
            raw_title = ch.get("title", f"Milestone {i+1}").strip()
            words = raw_title.split()
            ch["title"] = " ".join(words[:3]) if len(words) > 3 else raw_title
            # 3. Speaker
            if not ch.get("speaker"):
                ch["speaker"] = char_name
            # 4. Narration formatting
            narr = ch.get("narration_text", "").strip()
            if narr and not narr.endswith("."):
                narr += "."
            ch["narration_text"] = narr or f"{ch['speaker']} visits the {ch['title']} shrine."

        improved["chapters"] = chapters
        improved["_director_mode"] = "heuristic_fallback"
        return improved


def _parse_json_object(raw_output: str) -> Dict[str, Any]:
    cleaned = raw_output.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError("Director LLM did not return a JSON object.")
    snippet = cleaned[start:end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse LLM output as JSON: {snippet[:500]}")
        raise RuntimeError(f"Director LLM did not return valid JSON: {exc}") from exc

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
        # Sensible defaults for character consistency if not specified
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
        return self._complete_json(user_prompt)

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
        return self._complete_json(user_prompt)

    def _complete_json(self, user_prompt: str) -> Dict[str, Any]:
        response = self.client.responses.create(
            model=self.model_id,
            input=user_prompt,
        )
        if hasattr(response, "output") and response.output:
            raw_output = response.output[0].text
        else:
            raw_output = str(response)
        return _parse_json_object(raw_output)


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

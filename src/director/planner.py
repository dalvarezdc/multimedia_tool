"""Director & Storyboard Planning Agent.

Uses BytePlus ModelArk seed-2-0-lite-260228 to decompose high-level topics or transcripts
into structured milestone roadmaps, platform coordinates, and visual cutscene prompts.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from arkruntime import Ark

logger = logging.getLogger(__name__)

class DirectorPlanner:
    """Orchestrates topic breakdown and storyboard generation using seed-2-0-lite."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://ark.ap-southeast.bytepluses.com/api/v3",
        model_id: str = "seed-2-0-lite-260228"
    ):
        self.api_key = api_key or os.getenv("ARK_API_KEY")
        if not self.api_key:
            raise ValueError("ARK_API_KEY must be provided or set in environment variables.")

        self.base_url = os.getenv("ARK_BASE_URL", base_url)
        self.model_id = os.getenv("ARK_LLM_MODEL", model_id)

        self.client = Ark(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    def plan_storyboard(self, topic_or_transcript: str, chapter_count: int = 4) -> Dict[str, Any]:
        """Decomposes the input content into sequential milestone platforms and video prompts.

        Args:
            topic_or_transcript: Raw text topic, script, or documentation to explain.
            chapter_count: Number of roadmap milestones to generate (default: 4).

        Returns:
            Dictionary matching the StoryboardSpec schema.
        """
        system_instruction = (
            "You are an expert video director for educational technical animations. "
            "Your output must be strictly valid JSON without explanations or markdown formatting."
        )

        user_prompt = f"""
        Break down the following topic into {chapter_count} sequential milestones for a 2D retro platformer level:
        "{topic_or_transcript}"

        Each milestone represents a floating stone platform with a signpost that the character visits.
        For each milestone, provide:
        1. 'title': Very concise signpost label (max 3 words, e.g., 'Hardware Choices').
        2. 'narration_text': 1-2 sentence spoken explanation of this milestone.
        3. 'platform_x': Horizontal pixel coordinate across a 1920x1080 canvas (spaced sequentially from left to right, e.g. 100 to 1700).
        4. 'platform_y': Vertical coordinate between 300 and 700.
        5. 'seedance_prompt': A vivid, cinematic visual prompt describing a 5-second video illustrating the concept. Do NOT mention text, captions, or UI.

        Return JSON matching this schema:
        {{
          "theme": "greek_night_sky",
          "resolution": {{"width": 1920, "height": 1080}},
          "fps": 60,
          "chapters": [
            {{
              "id": 1,
              "title": "...",
              "narration_text": "...",
              "platform": {{"x": 150, "y": 420, "width": 180}},
              "seedance_prompt": "Cinematic shot of...",
              "duration_seconds": 6
            }}
          ]
        }}
        """

        logger.info(f"Invoking Director Model {self.model_id}...")
        response = self.client.responses.create(
            model=self.model_id,
            input=user_prompt,
        )

        raw_output = ""
        if hasattr(response, "output") and response.output:
            raw_output = response.output[0].text
        else:
            raw_output = str(response)

        # Parse JSON and clean any accidental markdown wraps
        cleaned = raw_output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            plan = json.loads(cleaned)
            return plan
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse LLM output as JSON: {cleaned}")
            raise RuntimeError(f"Director LLM did not return valid JSON: {exc}")

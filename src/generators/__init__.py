"""Unified video generator factory supporting BytePlus Seedance and xAI Grok."""

import os
from typing import Union, Optional
from src.seedance.client import SeedanceClient
from src.grok.client import GrokVideoClient

def get_video_generator(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model_id: Optional[str] = None
) -> Union[SeedanceClient, GrokVideoClient]:
    """Factory function returning the configured video generation client.

    Args:
        provider: 'seedance' (BytePlus ModelArk) or 'grok' (xAI).
                  Defaults to the DEFAULT_VIDEO_PROVIDER env variable or 'seedance'.
        api_key: Optional runtime API key to override environment variables.
        model_id: Optional model identifier (e.g., 'dreamina-seedance-2-5-260628').

    Returns:
        An instance of SeedanceClient or GrokVideoClient.
    """
    selected_provider = (provider or os.getenv("DEFAULT_VIDEO_PROVIDER", "seedance")).lower()

    if selected_provider in ("grok", "xai"):
        return GrokVideoClient(api_key=api_key, model_id=model_id)
    if selected_provider in ("seedance", "byteplus", "bytedance"):
        return SeedanceClient(api_key=api_key, model_id=model_id)
    raise ValueError(f"Unknown video provider '{selected_provider}'. Choose 'seedance' or 'grok'.")

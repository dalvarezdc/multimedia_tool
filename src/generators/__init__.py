"""Unified video generator factory supporting BytePlus Seedance and xAI Grok."""

import os
from typing import Union
from src.seedance.client import SeedanceClient
from src.grok.client import GrokVideoClient

def get_video_generator(provider: str = None) -> Union[SeedanceClient, GrokVideoClient]:
    """Factory function returning the configured video generation client.

    Args:
        provider: 'seedance' (BytePlus ModelArk) or 'grok' (xAI).
                  Defaults to the DEFAULT_VIDEO_PROVIDER env variable or 'seedance'.

    Returns:
        An instance of SeedanceClient or GrokVideoClient.
    """
    selected_provider = (provider or os.getenv("DEFAULT_VIDEO_PROVIDER", "seedance")).lower()

    if selected_provider in ("grok", "xai"):
        return GrokVideoClient()
    elif selected_provider in ("seedance", "byteplus", "bytedance"):
        return SeedanceClient()
    else:
        raise ValueError(f"Unknown video provider '{selected_provider}'. Choose 'seedance' or 'grok'.")

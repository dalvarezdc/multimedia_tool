"""Unified multimedia generator factory supporting BytePlus Seedance, SeeDream, and xAI Grok."""

import os
from typing import Union, Optional
from src.seedance.client import SeedanceClient
from src.grok.client import GrokVideoClient, GrokImageClient
from src.seedream.client import SeeDreamClient

from src.mureka.client import MurekaAudioClient

def get_video_generator(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model_id: Optional[str] = None
) -> Union[SeedanceClient, GrokVideoClient]:
    """Factory function returning the configured video generation client."""
    selected_provider = (provider or os.getenv("DEFAULT_VIDEO_PROVIDER", "seedance")).lower()

    if selected_provider in ("grok", "xai"):
        return GrokVideoClient(api_key=api_key, model_id=model_id)
    if selected_provider in ("seedance", "byteplus", "bytedance"):
        return SeedanceClient(api_key=api_key, model_id=model_id)
    raise ValueError(f"Unknown video provider '{selected_provider}'. Choose 'seedance' or 'grok'.")


def get_image_generator(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model_id: Optional[str] = None
) -> Union[SeeDreamClient, GrokImageClient]:
    """Factory function returning the configured image generation client."""
    selected_provider = (provider or "seedream").lower()
    mid = (model_id or "").lower()
    if selected_provider in ("grok", "xai") or "grok-imagine-image" in mid:
        return GrokImageClient(api_key=api_key, model_id=model_id)
    if selected_provider in ("seedream", "seedance", "byteplus", "bytedance"):
        return SeeDreamClient(api_key=api_key, model_id=model_id)
    raise ValueError(f"Unknown image provider '{selected_provider}'. Choose 'seedream' or 'grok'.")


def get_audio_generator(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model_id: Optional[str] = None
) -> MurekaAudioClient:
    """Factory function returning the configured audio generation client."""
    selected_provider = (provider or os.getenv("DEFAULT_AUDIO_PROVIDER", "mureka")).lower()
    if selected_provider in ("mureka", "skywork"):
        return MurekaAudioClient(api_key=api_key, base_url=base_url, model_id=model_id)
    raise ValueError(f"Unknown audio provider '{selected_provider}'. Choose 'mureka'.")



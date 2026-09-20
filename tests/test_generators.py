"""Tests for video generator clients (BytePlus Seedance & xAI Grok)."""

import os
import pytest
from src.generators import get_video_generator
from src.seedance.client import SeedanceClient
from src.grok.client import GrokVideoClient

def test_factory_seedance():
    os.environ["ARK_API_KEY"] = "mock_ark_key"
    client = get_video_generator("seedance")
    assert isinstance(client, SeedanceClient)
    assert client.api_key == "mock_ark_key"

def test_factory_grok():
    os.environ["XAI_API_KEY"] = "mock_xai_key"
    client = get_video_generator("grok")
    assert isinstance(client, GrokVideoClient)
    assert client.api_key == "mock_xai_key"

def test_factory_invalid_provider():
    with pytest.raises(ValueError, match="Unknown video provider"):
        get_video_generator("unsupported_provider")

def test_grok_missing_api_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="XAI_API_KEY must be provided"):
        GrokVideoClient()

def test_seedance_modes_configuration():
    os.environ["ARK_API_KEY"] = "mock_ark_key"
    client = SeedanceClient()
    assert client.model_id is not None
    # Verify helper parses local or remote refs correctly
    assert client._prepare_image_reference("https://example.com/ref.png") == "https://example.com/ref.png"


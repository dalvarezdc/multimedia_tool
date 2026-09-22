"""Comprehensive test suite for Mureka Audio Generator service, client, and API routes."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from src.mureka.client import (
    MurekaAudioClient,
    MurekaAPIError,
    resolve_mureka_base_url,
)
from src.generators import get_audio_generator
from src.models_registry import (
    get_model_info,
    get_all_models_grouped,
    calculate_model_cost,
    DEFAULT_AUDIO_MODEL,
)
from src.inventory import infer_model_capabilities, ModelInventoryManager
from src.server import create_app


# =========================================================================
# 1. CLIENT UNIT TESTS
# =========================================================================

def test_mureka_base_url_allowlist():
    assert resolve_mureka_base_url("https://api.mureka.ai") == "https://api.mureka.ai/v1"
    assert resolve_mureka_base_url("https://api.mureka.ai/v1") == "https://api.mureka.ai/v1"
    for raw in (
        "http://api.mureka.ai/v1",
        "https://api.mureka.ai.evil.com/v1",
        "https://127.0.0.1/v1",
        "https://user:pass@api.mureka.ai/v1",
        "https://api.mureka.ai/v1/song/query",
        "https://api.mureka.ai/v1?next=https://evil.example",
    ):
        with pytest.raises(ValueError):
            resolve_mureka_base_url(raw)


def test_mureka_client_rejects_offhost_base_url():
    with pytest.raises(ValueError):
        MurekaAudioClient(api_key="test_key", base_url="https://attacker.example/v1")


def test_mureka_client_init_with_key():
    client = MurekaAudioClient(api_key="test_mureka_token", base_url="https://api.mureka.ai/v1")
    assert client.api_key == "test_mureka_token"
    assert client.base_url == "https://api.mureka.ai/v1"
    assert client.default_model == "mureka-9.5"


def test_mureka_client_init_from_env(monkeypatch):
    monkeypatch.setenv("MUREKA_API_KEY", "env_mureka_token")
    client = MurekaAudioClient()
    assert client.api_key == "env_mureka_token"


def test_mureka_client_missing_key(monkeypatch):
    monkeypatch.delenv("MUREKA_API_KEY", raising=False)
    with pytest.raises(ValueError, match="MUREKA_API_KEY must be provided"):
        MurekaAudioClient()


@patch("requests.post")
def test_easy_generate(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "id": "task_12345",
        "status": "preparing",
        "choices": [],
    }

    client = MurekaAudioClient(api_key="test_key")
    res = client.easy_generate(
        prompt="A synthwave track",
        styles=["electronic", "synthwave"],
        model="mureka-9.5",
        n=2,
    )
    assert res["id"] == "task_12345"
    assert res["status"] == "preparing"

    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://api.mureka.ai/v1/song/easy-generate"
    payload = call_args[1]["json"]
    assert payload["prompt"] == "A synthwave track"
    assert payload["styles"] == ["electronic", "synthwave"]
    assert payload["model"] == "mureka-9.5"
    assert payload["n"] == 2
    assert "Authorization" in call_args[1]["headers"]
    assert call_args[1]["headers"]["Authorization"] == "Bearer test_key"


@patch("requests.post")
def test_generate_soundtrack(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "id": "soundtrack_task_001",
        "status": "queued",
    }

    client = MurekaAudioClient(api_key="test_key")
    res = client.generate_soundtrack(
        prompt="Epic orchestral boss theme",
        model="mureka-soundtrack",
        audio_start=0,
        audio_end=60,
    )
    assert res["id"] == "soundtrack_task_001"
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://api.mureka.ai/v1/soundtrack/generate"
    payload = call_args[1]["json"]
    assert payload["prompt"] == "Epic orchestral boss theme"
    assert payload["model"] == "mureka-soundtrack"
    assert payload["audio_start"] == 0
    assert payload["audio_end"] == 60


@patch("requests.post")
def test_generate_song_lyrics(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "id": "song_task_002",
        "status": "running",
    }

    client = MurekaAudioClient(api_key="test_key")
    res = client.generate_song(
        lyrics="[Verse]\nRunning through the rain\n[Chorus]\nSun shines again",
        prompt="Acoustic Folk",
        gender="female",
    )
    assert res["id"] == "song_task_002"
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://api.mureka.ai/v1/song/generate"
    payload = call_args[1]["json"]
    assert "[Verse]" in payload["lyrics"]
    assert payload["prompt"] == "Acoustic Folk"
    assert payload["gender"] == "female"


@patch("requests.post")
def test_extend_song(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "id": "extend_task_003",
        "status": "preparing",
    }

    client = MurekaAudioClient(api_key="test_key")
    res = client.extend_song(
        lyrics="[Outro]\nFading to the stars",
        extend_at=45000,
        song_id="orig_song_999",
        model="mureka-8",
    )
    assert res["id"] == "extend_task_003"
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://api.mureka.ai/v1/song/extend"
    payload = call_args[1]["json"]
    assert payload["song_id"] == "orig_song_999"
    assert payload["extend_at"] == 45000
    assert payload["model"] == "mureka-8"


@patch("requests.post")
def test_generate_instrumental(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "id": "inst_task_004",
        "status": "preparing",
    }

    client = MurekaAudioClient(api_key="test_key")
    res = client.generate_instrumental(prompt="Jazz piano trio", model="mureka-instrumental")
    assert res["id"] == "inst_task_004"
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://api.mureka.ai/v1/instrumental/generate"


@patch("requests.post")
def test_generate_lyrics(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "text": "[Verse 1]\nNeon light reflections...",
    }

    client = MurekaAudioClient(api_key="test_key")
    res = client.generate_lyrics(prompt="A song about neon dreams")
    assert "lyrics" in res
    assert "[Verse 1]" in res["lyrics"]
    mock_post.assert_called_once()
    assert mock_post.call_args[0][0] == "https://api.mureka.ai/v1/lyrics/generate"


@patch("requests.get")
def test_query_task(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "id": "task_12345",
        "status": "succeeded",
        "choices": [{"url": "https://cdn.mureka.ai/song1.mp3", "duration": 180}],
    }

    client = MurekaAudioClient(api_key="test_key")
    res = client.query_task("task_12345")
    assert res["status"] == "succeeded"
    assert len(res["choices"]) == 1
    assert res["choices"][0]["duration"] == 180
    mock_get.assert_called_once()
    assert "song/query/task_12345" in mock_get.call_args[0][0]


@patch("requests.get")
def test_poll_song_success(mock_get):
    mock_get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"id": "task_1", "status": "running"}),
        MagicMock(
            status_code=200,
            json=lambda: {
                "id": "task_1",
                "status": "succeeded",
                "choices": [{"url": "https://cdn.mureka.ai/song1.mp3"}],
            },
        ),
    ]

    client = MurekaAudioClient(api_key="test_key")
    res = client.poll_song("task_1", poll_interval=0.01, timeout_seconds=5)
    assert res["status"] == "succeeded"
    assert res["choices"][0]["url"] == "https://cdn.mureka.ai/song1.mp3"


@patch("requests.get")
def test_poll_song_failure(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"id": "task_1", "status": "failed", "failed_reason": "Content filtered"},
    )

    client = MurekaAudioClient(api_key="test_key")
    with pytest.raises(MurekaAPIError, match="Content filtered"):
        client.poll_song("task_1", poll_interval=0.01, timeout_seconds=5)


@patch("requests.get")
def test_get_billing(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "points": 500,
        "vip_expire_time": "2026-12-31",
    }

    client = MurekaAudioClient(api_key="test_key")
    res = client.get_billing()
    assert res["points"] == 500
    assert mock_get.call_args[0][0] == "https://api.mureka.ai/v1/account/billing"


def test_factory_get_audio_generator():
    client = get_audio_generator(api_key="my_factory_key", model_id="mureka-soundtrack")
    assert isinstance(client, MurekaAudioClient)
    assert client.api_key == "my_factory_key"
    assert client.default_model == "mureka-soundtrack"


# =========================================================================
# 2. MODEL REGISTRY & INVENTORY TESTS
# =========================================================================

def test_mureka_models_registered():
    info = get_model_info("mureka-9.5")
    assert info is not None
    assert info.category == "audio"
    assert info.provider == "mureka"
    assert info.sample_cost == "USD 0.30 lyrics-to-song / USD 1.00 prompt-to-song (2 songs)"

    groups = get_all_models_grouped()
    assert "audio" in groups
    audio_ids = [m["id"] for m in groups["audio"]]
    assert "mureka-9.5" in audio_ids
    assert "mureka-soundtrack" in audio_ids
    assert "mureka-instrumental" in audio_ids


def test_mureka_cost_calculation():
    assert calculate_model_cost("mureka-9.5", clip_count=2, mode="song_generate") == "USD 0.30 estimated (2 songs)"
    assert calculate_model_cost("mureka-9.5", clip_count=2, mode="easy_generate") == "USD 1.00 estimated (2 songs)"
    assert calculate_model_cost("mureka-9.5", clip_count=1, mode="easy_generate") == "USD 0.50 estimated (1 song)"
    assert calculate_model_cost("mureka-9.5", clip_count=2, mode="instrumental") == "USD 0.30 estimated (2 songs)"
    assert calculate_model_cost("mureka-9", clip_count=2, mode="song_generate") == "USD 0.09 estimated (2 songs)"
    assert calculate_model_cost("mureka-8", clip_count=2, mode="easy_generate") == "USD 0.60 estimated (2 songs)"
    assert calculate_model_cost("mureka-7.6", clip_count=2, mode="song_generate") == "USD 0.06 estimated (2 songs)"
    assert calculate_model_cost("mureka-soundtrack", clip_count=2, mode="soundtrack") == "USD 0.20 estimated (2 songs)"
    assert calculate_model_cost("mureka-instrumental", clip_count=2, mode="instrumental") == "USD 0.30 estimated (2 songs)"
    assert calculate_model_cost("mureka-8", mode="extend") == "USD 0.100 estimated (1 extension)"
    assert calculate_model_cost("mureka-7.6", mode="extend") == "USD 0.036 estimated (1 extension)"


def test_mureka_pricing_endpoint_by_mode(app_client):
    lyrics = app_client.get("/api/cost/estimate", params={"model": "mureka-9.5", "mode": "song_generate", "clips": 2})
    prompt = app_client.get("/api/cost/estimate", params={"model": "mureka-9.5", "mode": "easy_generate", "clips": 2})
    soundtrack = app_client.get("/api/cost/estimate", params={"model": "mureka-soundtrack", "mode": "soundtrack", "clips": 2})
    assert lyrics.json()["cost"] == "USD 0.30 estimated (2 songs)"
    assert prompt.json()["cost"] == "USD 1.00 estimated (2 songs)"
    assert soundtrack.json()["cost"] == "USD 0.20 estimated (2 songs)"


@patch.object(MurekaAudioClient, "generate_soundtrack")
@patch.object(MurekaAudioClient, "generate_instrumental")
def test_audio_category_models_resolve_to_mureka_models(mock_instrumental, mock_soundtrack, app_client):
    mock_soundtrack.return_value = {"id": "soundtrack_task", "status": "preparing"}
    mock_instrumental.return_value = {"id": "instrumental_task", "status": "preparing"}
    soundtrack = app_client.post("/api/audio/generate", json={
        "mode": "soundtrack", "prompt": "Cinematic score", "model": "mureka-soundtrack", "api_key": "test_key",
    })
    instrumental = app_client.post("/api/audio/generate", json={
        "mode": "instrumental", "prompt": "Jazz piano", "model": "mureka-instrumental", "api_key": "test_key",
    })
    assert soundtrack.status_code == 200
    assert instrumental.status_code == 200
    assert mock_soundtrack.call_args.kwargs["model"] == "mureka-9"
    assert mock_instrumental.call_args.kwargs["model"] == "mureka-9.5"


def test_inventory_audio_capabilities():
    cap = infer_model_capabilities("mureka-soundtrack", provider="mureka")
    assert cap.category == "audio"
    assert cap.provider == "mureka"
    assert cap.ui_layout_type == "audio_music"

    inv = ModelInventoryManager().refresh_inventory()
    assert "audio" in inv["catalog"]
    audio_ids = [m["id"] for m in inv["catalog"]["audio"]]
    assert "mureka-9.5" in audio_ids


# =========================================================================
# 3. SERVER API ROUTE TESTS
# =========================================================================

@pytest.fixture
def app_client(tmp_path, monkeypatch):
    test_uploads = tmp_path / "uploads"
    test_data = tmp_path / "data"
    test_uploads.mkdir(parents=True, exist_ok=True)
    test_data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MULTIMEDIA_UPLOADS_DIR", str(test_uploads))
    monkeypatch.setenv("MULTIMEDIA_DATA_DIR", str(test_data))
    app = create_app()
    return TestClient(app)


def test_audio_generate_missing_key(app_client, monkeypatch):
    monkeypatch.delenv("MUREKA_API_KEY", raising=False)
    res = app_client.post(
        "/api/audio/generate",
        json={"mode": "easy_generate", "prompt": "Lo-Fi beat"},
    )
    assert res.status_code == 400
    assert "MUREKA_API_KEY is not configured" in res.json()["detail"]


@patch.object(MurekaAudioClient, "easy_generate")
def test_audio_generate_endpoint_success(mock_easy, app_client):
    mock_easy.return_value = {"id": "task_abc123", "status": "preparing"}

    res = app_client.post(
        "/api/audio/generate",
        json={
            "mode": "easy_generate",
            "prompt": "Retro electro track",
            "styles": ["synthwave", "80s"],
            "api_key": "test_request_key",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["task_id"] == "task_abc123"
    assert data["id"] == "task_abc123"
    assert data["status"] == "started"
    mock_easy.assert_called_once()


@patch.object(MurekaAudioClient, "generate_song")
def test_audio_generate_with_three_prompts(mock_song, app_client):
    mock_song.return_value = {"id": "song_task_999", "status": "preparing"}

    res = app_client.post(
        "/api/audio/generate",
        json={
            "mode": "song_generate",
            "title": "Neon Horizon",
            "prompt": "Melodic synthwave with warm analog synthesizers and 80s drums",
            "lyrics": "[Verse 1]\nCity lights are shining in the dark\n[Chorus]\nWe are electric souls",
            "api_key": "test_request_key",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "song_task_999"
    assert data["title"] == "Neon Horizon"
    assert data["status"] == "started"
    mock_song.assert_called_once()
    kwargs = mock_song.call_args[1]
    assert kwargs["lyrics"] == "[Verse 1]\nCity lights are shining in the dark\n[Chorus]\nWe are electric souls"
    assert kwargs["prompt"] == "Melodic synthwave with warm analog synthesizers and 80s drums"


def test_audio_generate_character_limits_enforced(app_client):
    # 1. Title > 100 characters should fail validation
    long_title = "A" * 101
    res = app_client.post(
        "/api/audio/generate",
        json={"mode": "song_generate", "title": long_title, "api_key": "test_key"},
    )
    assert res.status_code == 422

    # 2. Style Prompt > 1024 characters should fail validation
    long_prompt = "P" * 1025
    res = app_client.post(
        "/api/audio/generate",
        json={"mode": "song_generate", "prompt": long_prompt, "api_key": "test_key"},
    )
    assert res.status_code == 422

    # 3. Lyrics > 5000 characters should fail validation
    long_lyrics = "L" * 5001
    res = app_client.post(
        "/api/audio/generate",
        json={"mode": "song_generate", "lyrics": long_lyrics, "api_key": "test_key"},
    )
    assert res.status_code == 422


@patch.object(MurekaAudioClient, "query_task")
@patch.object(MurekaAudioClient, "easy_generate")
def test_audio_status_endpoint(mock_easy, mock_query, app_client, monkeypatch):
    monkeypatch.setenv("MUREKA_API_KEY", "mock_key")
    mock_easy.return_value = {"id": "task_abc123", "status": "preparing"}
    gen_res = app_client.post(
        "/api/audio/generate",
        json={"mode": "easy_generate", "prompt": "Retro electro track", "api_key": "mock_key"}
    )
    assert gen_res.status_code == 200
    body = gen_res.json()
    token = body["access_token"]
    assert "access_token" not in body["data"]

    denied = app_client.get("/api/audio/status/task_abc123")
    assert denied.status_code == 404
    queried = app_client.get("/api/audio/status/task_abc123", params={"api_key": "stolen-key"})
    assert queried.status_code == 404
    mock_query.assert_not_called()

    mock_query.return_value = {
        "id": "task_abc123",
        "status": "succeeded",
        "choices": [{"url": "https://cdn.mureka.ai/song.mp3", "duration": 120}],
    }

    res = app_client.get("/api/audio/status/task_abc123", headers={"X-Audio-Token": token})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "succeeded"
    assert len(data["choices"]) == 1
    assert "access_token" not in data
    assert "user_id" not in data


@patch.object(MurekaAudioClient, "generate_lyrics")
def test_lyrics_generate_endpoint_with_title(mock_gen_lyrics, app_client):
    mock_gen_lyrics.return_value = {
        "title": "Midnight Mirage",
        "lyrics": "[Verse]\nShadows on the wall\n[Chorus]\nCalling out my name"
    }

    res = app_client.post(
        "/api/lyrics/generate",
        json={"prompt": "Synthwave night drive", "api_key": "mock_lyrics_key"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "Midnight Mirage"
    assert body["lyrics"] == "[Verse]\nShadows on the wall\n[Chorus]\nCalling out my name"


@patch.object(MurekaAudioClient, "generate_lyrics")
def test_lyrics_generate_endpoint(mock_gen_lyrics, app_client):
    mock_gen_lyrics.return_value = {"lyrics": "[Verse]\nHello world"}

    res = app_client.post(
        "/api/lyrics/generate",
        json={"prompt": "Write a song about stars", "api_key": "mock_lyrics_key"},
    )
    assert res.status_code == 200
    assert res.json()["lyrics"] == "[Verse]\nHello world"


@patch("requests.get")
def test_test_connection_mureka_success(mock_get, app_client):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"points": 450}

    res = app_client.post(
        "/api/settings/test-connection",
        json={"provider": "mureka", "mureka_api_key": "valid_token"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "Mureka Audio Platform reachable" in data["message"]


@patch("requests.get")
def test_test_connection_mureka_failure(mock_get, app_client):
    mock_get.return_value.status_code = 401
    mock_get.return_value.text = "Unauthorized"

    res = app_client.post(
        "/api/settings/test-connection",
        json={"provider": "mureka", "mureka_api_key": "bad_token"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "error"
    assert "401" in data["message"]


def test_settings_mureka_keys_persistence(app_client):
    res = app_client.post(
        "/api/settings",
        json={
            "mureka_api_key": "mureka_secret_12345678",
            "mureka_api_url": "https://api.mureka.ai/v1",
        },
    )
    assert res.status_code == 200

    get_res = app_client.get("/api/settings")
    assert get_res.status_code == 200
    settings = get_res.json()
    assert settings["has_mureka_key"] is True
    assert settings["mureka_key_masked"] == "...5678"
    assert settings["mureka_api_url"] == "https://api.mureka.ai/v1"


def test_settings_rejects_untrusted_mureka_url(app_client, monkeypatch):
    monkeypatch.setenv("MUREKA_API_KEY", "already-set")
    monkeypatch.setenv("MUREKA_API_URL", "https://api.mureka.ai/v1")
    res = app_client.post(
        "/api/settings",
        json={
            "mureka_api_key": "replacement-secret",
            "mureka_api_url": "https://attacker.example/v1",
        },
    )
    assert res.status_code == 400
    assert os.environ["MUREKA_API_KEY"] == "already-set"
    assert os.environ["MUREKA_API_URL"] == "https://api.mureka.ai/v1"


@patch("requests.get")
def test_mureka_connection_test_does_not_call_offhost(mock_get, app_client):
    res = app_client.post(
        "/api/settings/test-connection",
        json={
            "provider": "mureka",
            "mureka_api_key": "valid_token",
            "mureka_api_url": "http://127.0.0.1:9/v1",
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "error"
    mock_get.assert_not_called()


def test_audio_route_serves_console(app_client):
    res = app_client.get("/audio")
    assert res.status_code == 200
    assert "Audio Studio" in res.text
    assert "Vision Studio" in res.text
    assert "audio-select-mode" in res.text


# =========================================================================
# 5. AUDIO UPLOAD & ANALYSIS TESTS (RECOGNIZE, DESCRIBE, TRANSCRIBE)
# =========================================================================

def test_format_recognized_lyrics():
    from src.mureka.client import format_recognized_lyrics
    assert format_recognized_lyrics(None) == ""
    assert format_recognized_lyrics([]) == ""

    sections = [
        {
            "start": 0.0,
            "end": 12.5,
            "lines": [
                {"start": 0.0, "end": 5.0, "text": "Walking down the neon street"},
                {"start": 5.1, "end": 12.5, "text": "Synthesizers in the beat"},
            ]
        },
        {
            "start": 12.6,
            "end": 25.0,
            "lines": [
                {"start": 12.6, "end": 20.0, "text": "Electric dreams will never fade"},
            ]
        }
    ]
    formatted = format_recognized_lyrics(sections)
    assert "[Section 1]" in formatted
    assert "Walking down the neon street" in formatted
    assert "Synthesizers in the beat" in formatted
    assert "[Section 2]" in formatted
    assert "Electric dreams will never fade" in formatted


@patch("requests.post")
def test_client_upload_file(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "id": "file_upload_abc123",
        "filename": "track.mp3",
        "bytes": 5000,
        "object": "file",
        "purpose": "audio"
    }

    client = MurekaAudioClient(api_key="test_key")
    res = client.upload_file(
        file_content=b"dummy_mp3_binary_data",
        filename="track.mp3",
        purpose="audio",
        mime_type="audio/mpeg"
    )
    assert res["id"] == "file_upload_abc123"
    assert res["filename"] == "track.mp3"
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "files/upload" in args[0]
    assert kwargs["data"] == {"purpose": "audio"}
    assert "file" in kwargs["files"]


@patch("requests.post")
def test_client_recognize_song(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "duration": 145.2,
        "lyrics_sections": [
            {"start": 0.0, "end": 15.0, "lines": [{"start": 0.0, "end": 10.0, "text": "Hello world"}]}
        ]
    }

    client = MurekaAudioClient(api_key="test_key")
    res = client.recognize_song("audio_upload_999")
    assert res["duration"] == 145.2
    assert len(res["lyrics_sections"]) == 1

    with pytest.raises(ValueError, match="upload_audio_id is required"):
        client.recognize_song("")


@patch("requests.post")
def test_client_describe_song(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "description": "Upbeat electronic disco track with punchy bass.",
        "genres": ["Electronic", "Nu-Disco"],
        "instrument": ["Synthesizer", "Drum Machine"],
        "tags": ["Energetic", "Dance", "80s"]
    }

    client = MurekaAudioClient(api_key="test_key")
    res = client.describe_song("data:audio/mp3;base64,AAAA")
    assert "Nu-Disco" in res["genres"]
    assert "Synthesizer" in res["instrument"]

    with pytest.raises(ValueError, match="url"):
        client.describe_song("")


@patch("requests.post")
def test_client_transcribe_song(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "zip_url": "https://cdn.mureka.ai/transcribe/score_123.zip",
        "expires_at": 1740000000
    }

    client = MurekaAudioClient(api_key="test_key")
    res = client.transcribe_song(upload_audio_id="audio_id_123", title="My Song")
    assert "score_123.zip" in res["zip_url"]

    with pytest.raises(ValueError, match="Either upload_audio_id"):
        client.transcribe_song()


def test_server_upload_audio_unsupported_format(app_client):
    files = {"file": ("document.txt", b"not audio data", "text/plain")}
    res = app_client.post("/api/audio/upload", files=files, data={"api_key": "test_key"})
    assert res.status_code == 400
    assert "Unsupported audio format" in res.json()["detail"]


def test_server_upload_audio_exceeds_10mb(app_client):
    big_content = b"x" * (10 * 1024 * 1024 + 10)
    files = {"file": ("giant_track.mp3", big_content, "audio/mpeg")}
    res = app_client.post("/api/audio/upload", files=files, data={"api_key": "test_key"})
    assert res.status_code == 400
    assert "exceeds the maximum allowed 10MB limit" in res.json()["detail"]


def test_server_upload_audio_missing_api_key(app_client, monkeypatch):
    monkeypatch.delenv("MUREKA_API_KEY", raising=False)
    files = {"file": ("song.mp3", b"dummy_data", "audio/mpeg")}
    res = app_client.post("/api/audio/upload", files=files)
    assert res.status_code == 400
    assert "MUREKA_API_KEY is not configured" in res.json()["detail"]


@patch.object(MurekaAudioClient, "upload_file")
@patch.object(MurekaAudioClient, "recognize_song")
@patch.object(MurekaAudioClient, "describe_song")
@patch.object(MurekaAudioClient, "transcribe_song")
def test_server_upload_audio_full_pipeline_success(
    mock_transcribe, mock_describe, mock_recognize, mock_upload, app_client
):
    mock_upload.return_value = {"id": "mureka_audio_file_001", "filename": "test_song.mp3", "bytes": 100}
    mock_recognize.return_value = {
        "duration": 60.0,
        "lyrics_sections": [
            {"start": 0.0, "end": 10.0, "lines": [{"start": 0.0, "end": 5.0, "text": "La la la"}]}
        ]
    }
    mock_describe.return_value = {
        "description": "Groovy synthpop vibe",
        "genres": ["Pop", "Synthpop"],
        "instrument": ["Synth", "Bass"],
        "tags": ["Catchy", "Retro"]
    }
    mock_transcribe.return_value = {
        "zip_url": "https://cdn.mureka.ai/transcribe/test_song.zip",
        "expires_at": 1750000000
    }

    files = {"file": ("test_song.mp3", b"valid_audio_bytes", "audio/mpeg")}
    data = {
        "api_key": "mureka_mock_key",
        "auto_recognize": "true",
        "auto_describe": "true",
        "auto_transcribe": "true"
    }
    res = app_client.post("/api/audio/upload", files=files, data=data)
    assert res.status_code == 200
    body = res.json()

    assert body["upload_audio_id"] == "mureka_audio_file_001"
    assert body["filename"] == "test_song.mp3"
    assert body["local_url"].startswith("/uploads/audio/")

    # Recognize
    assert body["recognize"]["duration"] == 60.0
    assert "La la la" in body["recognize"]["formatted_lyrics"]

    # Describe
    assert body["describe"]["description"] == "Groovy synthpop vibe"
    assert "Synthpop" in body["describe"]["genres"]

    # Transcribe
    assert "test_song.zip" in body["transcribe"]["zip_url"]


@patch.object(MurekaAudioClient, "recognize_song")
def test_server_standalone_recognize(mock_recognize, app_client):
    mock_recognize.return_value = {
        "duration": 42.0,
        "lyrics_sections": [{"start": 0.0, "end": 10.0, "lines": [{"start": 0.0, "end": 5.0, "text": "Echoes in the dark"}]}]
    }
    res = app_client.post(
        "/api/audio/recognize",
        json={"upload_audio_id": "aud_123", "api_key": "mock_key"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["duration"] == 42.0
    assert "Echoes in the dark" in data["formatted_lyrics"]


@patch.object(MurekaAudioClient, "describe_song")
def test_server_standalone_describe(mock_describe, app_client):
    mock_describe.return_value = {
        "description": "Chill lofi hip-hop beat",
        "genres": ["Lo-Fi", "Hip-Hop"],
        "instrument": ["Piano", "Drums"],
        "tags": ["Relaxing", "Study"]
    }
    res = app_client.post(
        "/api/audio/describe",
        json={"url": "https://example.com/audio.mp3", "api_key": "mock_key"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "Lo-Fi" in data["genres"]


@patch.object(MurekaAudioClient, "transcribe_song")
def test_server_standalone_transcribe(mock_transcribe, app_client):
    mock_transcribe.return_value = {
        "zip_url": "https://cdn.mureka.ai/transcribe/scores.zip",
        "expires_at": 1750000000
    }
    res = app_client.post(
        "/api/audio/transcribe",
        json={"upload_audio_id": "aud_123", "title": "Piano Sonata", "api_key": "mock_key"}
    )
    assert res.status_code == 200
    assert "scores.zip" in res.json()["zip_url"]

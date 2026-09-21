"""CLI pipeline tests with mocked planner, generator, and QA."""

import json
import sys
from src.cli import main


STORYBOARD = {
    "theme": "greek_night_sky",
    "chapters": [
        {
            "id": 1,
            "title": "Hardware",
            "seedance_prompt": "Hermes inspects a chip",
            "duration_seconds": 4,
        },
        {
            "id": 2,
            "title": "Runtime",
            "seedance_prompt": "Hermes opens a terminal",
        },
    ],
}


class _FakePlanner:
    def __init__(self, *args, **kwargs):
        pass

    def plan_storyboard(self, **kwargs):
        _FakePlanner.last = kwargs
        return STORYBOARD


class _FakeGenerator:
    def __init__(self):
        self.calls = []

    def generate_video(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs["output_path"]


def test_cli_skip_video_writes_storyboard(tmp_path, monkeypatch):
    ctx = tmp_path / "notes.md"
    ctx.write_text("Apple Silicon details")
    out = tmp_path / "renders"
    monkeypatch.setattr(sys, "argv", [
        "multimedia",
        "--topic", "Local LLMs",
        "--context", "inline notes",
        "--context-file", str(ctx),
        "--character-name", "Hermes",
        "--character-prompt", "golden helmet",
        "--chapters", "3",
        "--skip-video-gen",
        "--output-dir", str(out),
    ])
    monkeypatch.setattr("src.cli.DirectorPlanner", _FakePlanner)
    main()
    saved = json.loads((out / "storyboard.json").read_text())
    assert saved["theme"] == "greek_night_sky"
    assert _FakePlanner.last["chapter_count"] == 3
    assert "Apple Silicon" in _FakePlanner.last["global_context"]["domain_notes"]
    assert "inline notes" in _FakePlanner.last["global_context"]["domain_notes"]


def test_cli_generates_and_logs_qa_failure(tmp_path, monkeypatch, caplog):
    caplog.set_level("INFO")
    out = tmp_path / "renders"
    hero = tmp_path / "hero.png"
    hero.write_bytes(b"png")
    gen = _FakeGenerator()

    class FailQA:
        def audit_clip(self, path):
            return False, "too small"

    monkeypatch.setattr(sys, "argv", [
        "multimedia",
        "--topic", "Chips",
        "--provider", "seedance",
        "--character-image", str(hero),
        "--output-dir", str(out),
    ])
    monkeypatch.setenv("ARK_API_KEY", "k")
    monkeypatch.setattr("src.cli.DirectorPlanner", _FakePlanner)
    monkeypatch.setattr("src.generators.get_video_generator", lambda **k: gen)
    monkeypatch.setattr("src.cli.VideoQAAgent", FailQA)
    main()
    assert len(gen.calls) == 2
    assert gen.calls[0]["character_reference_image"] == str(hero)
    assert gen.calls[0]["duration"] == 4
    assert gen.calls[1]["duration"] == 5
    assert "failed QA" in caplog.text


def test_cli_grok_provider_qa_pass(tmp_path, monkeypatch, caplog):
    caplog.set_level("INFO", logger="multimedia_tool")
    out = tmp_path / "renders"
    gen = _FakeGenerator()

    class PassQA:
        def audit_clip(self, path):
            return True, "Passed QA audit."

    monkeypatch.setattr(sys, "argv", [
        "multimedia",
        "--topic", "Grok path",
        "--provider", "grok",
        "--output-dir", str(out),
    ])
    monkeypatch.setenv("XAI_API_KEY", "x")
    monkeypatch.setattr("src.cli.DirectorPlanner", _FakePlanner)
    monkeypatch.setattr("src.generators.get_video_generator", lambda provider, **k: gen)
    monkeypatch.setattr("src.cli.VideoQAAgent", PassQA)
    main()
    assert len(gen.calls) == 2
    assert "passed QA" in caplog.text
    assert "Pipeline Completed Successfully" in caplog.text

"""Director planner JSON parsing helpers and DirectorPlanner with mocked Ark."""

import pytest
from src.director.planner import DirectorPlanner, _parse_json_object


def test_parse_json_object_strips_fences():
    raw = """```json
    {"theme": "greek_night_sky", "chapters": [{"id": 1}]}
    ```"""
    data = _parse_json_object(raw)
    assert data["theme"] == "greek_night_sky"
    assert data["chapters"][0]["id"] == 1


def test_parse_json_object_extracts_embedded_object():
    raw = "Here you go:\n{\"title\": \"Hardware\"}\nThanks"
    data = _parse_json_object(raw)
    assert data["title"] == "Hardware"


def test_parse_json_object_rejects_garbage():
    with pytest.raises(RuntimeError, match="JSON object"):
        _parse_json_object("no json here")


def test_parse_json_object_invalid_json_inside_braces():
    with pytest.raises(RuntimeError, match="valid JSON"):
        _parse_json_object("prefix {not json} suffix")


class _Item:
    def __init__(self, text):
        self.text = text


class _Resp:
    def __init__(self, text=None, raw=None):
        if text is not None:
            self.output = [_Item(text)]
        else:
            self.output = None
            self._raw = raw

    def __str__(self):
        return self._raw


def _planner(monkeypatch, response):
    monkeypatch.setenv("ARK_API_KEY", "mock_ark")

    class FakeArk:
        def __init__(self, **kwargs):
            self.responses = self

        def create(self, **kwargs):
            return response

    monkeypatch.setattr("src.director.planner.Ark", FakeArk)
    return DirectorPlanner(api_key="mock_ark", model_id="seed-2-0-lite-260228")


def test_planner_requires_api_key(monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ARK_API_KEY"):
        DirectorPlanner()


def test_plan_storyboard_with_context_and_rpg_purpose(monkeypatch):
    planner = _planner(monkeypatch, _Resp(text='```json\n{"theme": "greek_night_sky", "chapters": []}\n```'))
    captured = {}

    def wrap(user_prompt):
        captured["prompt"] = user_prompt
        return DirectorPlanner._complete_json(planner, user_prompt)

    monkeypatch.setattr(planner, "_complete_json", wrap)
    data = planner.plan_storyboard(
        "Local LLMs",
        global_context={"domain_notes": "M-series", "tone": "epic", "target_audience": "devs"},
        character_profile={
            "name": "Hermes",
            "reference_image_url": "assets/h.png",
            "prompt_tokens": "winged helmet",
            "sprite_id": "hermes_pixel",
        },
        chapter_count=3,
        purpose="rpg",
    )
    assert data["theme"] == "greek_night_sky"
    assert "in-browser RPG" in captured["prompt"]
    assert "M-series" in captured["prompt"]


def test_plan_storyboard_defaults_and_str_response(monkeypatch):
    planner = _planner(monkeypatch, _Resp(raw='here {"ok": true, "chapters": [1]} done'))
    data = planner.plan_storyboard("Hardware")
    assert data["ok"] is True


def test_improve_storyboard_with_and_without_instruction(monkeypatch):
    planner = _planner(monkeypatch, _Resp(text='{"improved": true, "chapters": []}'))
    captured = []
    orig = planner._complete_json

    def wrap(user_prompt):
        captured.append(user_prompt)
        return orig(user_prompt)

    monkeypatch.setattr(planner, "_complete_json", wrap)
    assert planner.improve_storyboard({"chapters": [{"id": 1}]})["improved"] is True
    assert "Tighten pedagogy" in captured[0]
    planner.improve_storyboard({"chapters": []}, instruction="Make it funnier")
    assert "Make it funnier" in captured[1]

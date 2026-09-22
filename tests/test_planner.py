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


def test_grok_director_uses_xai_chat_completions(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "mock_xai")
    captured = {}

    class FakeResponse:
        ok = True
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": '{"theme":"grok_world","chapters":[]}'}}]}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return FakeResponse()

    monkeypatch.setattr("src.director.planner.requests.post", fake_post)
    planner = DirectorPlanner(model_id="grok-4-fast")
    result = planner.plan_storyboard("A clockwork kingdom", purpose="rpg")
    assert result["theme"] == "grok_world"
    assert planner.provider == "xai"
    assert captured["url"].endswith("/chat/completions")
    assert captured["json"]["response_format"] == {"type": "json_object"}


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


def test_plan_storyboard_falls_back_to_candidate_on_404(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "mock_ark")

    attempts = []

    class FakeCompletions:
        def create(self, model, messages):
            attempts.append(model)
            if model == "seed-2-0-lite-260228":
                raise RuntimeError("404: The model or endpoint seed-2-0-lite-260228 does not exist or you do not have access to it.")
            # Fallback model succeeds
            class Msg:
                content = '{"theme": "fallback_sky", "chapters": [{"id": 1}]}'
            class Choice:
                message = Msg()
            class ChatResp:
                choices = [Choice()]
            return ChatResp()

    class FakeArk:
        def __init__(self, **kwargs):
            self.chat = self
            self.completions = FakeCompletions()
            self.responses = self

    monkeypatch.setattr("src.director.planner.Ark", FakeArk)
    planner = DirectorPlanner(api_key="mock_ark", model_id="seed-2-0-lite-260228")
    result = planner.plan_storyboard("How Local LLMs Work on Apple Silicon")
    assert result["theme"] == "fallback_sky"
    assert result["_director_mode"] == "cloud_llm"
    assert "seed-2-0-lite-260228" in attempts
    assert "seed-2-0-lite-260428" in attempts


def test_plan_storyboard_falls_back_to_heuristic_when_all_fail(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "mock_ark")

    class FakeArk:
        def __init__(self, **kwargs):
            self.chat = self
            self.completions = self
            self.responses = self

        def create(self, **kwargs):
            raise RuntimeError("404: InvalidEndpointOrModel.NotFound")

    monkeypatch.setattr("src.director.planner.Ark", FakeArk)
    planner = DirectorPlanner(api_key="mock_ark", model_id="seed-2-0-lite-260228")
    result = planner.plan_storyboard("How Local LLMs Work on Apple Silicon", chapter_count=4)
    assert result["_director_mode"] == "heuristic_fallback"
    assert len(result["chapters"]) == 4
    # Character consistency
    for ch in result["chapters"]:
        assert "Hermes" in ch["speaker"] or "Hermes" in ch["narration_text"]
        assert "Image 1" in ch["seedance_prompt"]
        assert ch["platform"]["width"] >= 160


def test_improve_storyboard_heuristic_fallback(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "mock_ark")

    class FakeArk:
        def __init__(self, **kwargs):
            self.chat = self
            self.completions = self
            self.responses = self

        def create(self, **kwargs):
            raise RuntimeError("API unavailable")

    monkeypatch.setattr("src.director.planner.Ark", FakeArk)
    planner = DirectorPlanner(api_key="mock_ark", model_id="seed-2-0-lite-260228")
    existing = {
        "theme": "greek_night_sky",
        "character_profile": {"name": "Hermes"},
        "chapters": [
            {"id": 1, "title": "A Very Long Title That Needs Tightening", "narration_text": "Spoken text"}
        ]
    }
    improved = planner.improve_storyboard(existing)
    assert improved["_director_mode"] == "heuristic_fallback"
    assert len(improved["chapters"][0]["title"].split()) <= 3
    assert improved["chapters"][0]["platform"]["x"] == 350

"""Director planner JSON parsing helpers."""

import pytest
from src.director.planner import _parse_json_object


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

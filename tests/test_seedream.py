"""Tests for BytePlus SeeDream image client and image generator factory."""

import base64
import pytest
import requests
from src.seedream.client import SeeDreamClient
from src.generators import get_image_generator


class _Item:
    def __init__(self, url=None, b64_json=None):
        self.url = url
        self.b64_json = b64_json


class _GenResp:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error


class _Http:
    def __init__(self, body=b"img-bytes"):
        self._body = body

    def raise_for_status(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, chunk_size=8192):
        yield self._body


def test_seedream_missing_api_key(monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ARK_API_KEY"):
        SeeDreamClient()


def test_get_image_generator_factory(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "k")
    client = get_image_generator("seedream", api_key="k", model_id="dola-seedream-5-0-pro-260628")
    assert isinstance(client, SeeDreamClient)
    assert client.model_id == "dola-seedream-5-0-pro-260628"
    assert isinstance(get_image_generator("byteplus", api_key="k"), SeeDreamClient)
    with pytest.raises(ValueError, match="Unknown image provider"):
        get_image_generator("unknown", api_key="k")


def test_prepare_image_reference(monkeypatch, tmp_path):
    monkeypatch.setenv("ARK_API_KEY", "k")
    client = SeeDreamClient(api_key="k")
    assert client._prepare_image_reference("") == ""
    assert client._prepare_image_reference("data:image/png;base64,xx") == "data:image/png;base64,xx"
    assert client._prepare_image_reference("https://x/a.png") == "https://x/a.png"
    assert client._prepare_image_reference("no-such.png") == "no-such.png"
    img = tmp_path / "a.png"
    img.write_bytes(b"png")
    uri = client._prepare_image_reference(str(img))
    assert uri.startswith("data:image/png;base64,")

    nested = tmp_path / "uploads" / "nested.jpg"
    nested.parent.mkdir()
    nested.write_bytes(b"jpg")
    monkeypatch.chdir(tmp_path)
    uri2 = client._prepare_image_reference("/uploads/nested.jpg")
    assert uri2.startswith("data:")

    asset_dir = tmp_path / "uploads" / "reference_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "cov_ref.png").write_bytes(b"png")
    uri3 = client._prepare_image_reference("missing-dir/cov_ref.png")
    assert uri3.startswith("data:")


def test_generate_image_from_url_and_references(monkeypatch, tmp_path):
    monkeypatch.setenv("ARK_API_KEY", "k")
    client = SeeDreamClient(api_key="k")
    captured = {}
    stages = []
    img = tmp_path / "ref.png"
    img.write_bytes(b"png")
    out = tmp_path / "renders" / "out.png"

    class FakeImages:
        def generate(self, **kwargs):
            captured.update(kwargs)
            return _GenResp(data=[_Item(url="https://cdn/out.png")])

    client.client.images = FakeImages()
    monkeypatch.setattr("src.seedream.client.requests.get", lambda *a, **k: _Http(b"downloaded"))

    path = client.generate_image(
        prompt="  a temple  ",
        output_path=str(out),
        reference_assets=[
            {"local_path": str(img)},
            {"filename": ""},
            {"url": "https://cdn/ref2.png"},
        ],
        ratio="1:1",
        resolution="2K",
        status_callback=lambda stage, meta: stages.append(stage),
    )
    assert path == str(out)
    assert out.read_bytes() == b"downloaded"
    assert captured["size"] == "1024x1024"
    assert isinstance(captured["image"], list)
    assert "preparing" in stages and "submitting" in stages and "downloading" in stages


def test_generate_image_b64_and_empty_and_unexpected(monkeypatch, tmp_path):
    monkeypatch.setenv("ARK_API_KEY", "k")
    client = SeeDreamClient(api_key="k")
    payload = base64.b64encode(b"raw-png").decode()

    class FakeImages:
        def __init__(self, resp):
            self._resp = resp

        def generate(self, **kwargs):
            return self._resp

    client.client.images = FakeImages(_GenResp(data=[_Item(b64_json=payload)]))
    out = tmp_path / "b64.png"
    client.generate_image("p", str(out), ratio="21:9")
    assert out.read_bytes() == b"raw-png"

    client.client.images = FakeImages(_GenResp(data=[], error="nope"))
    with pytest.raises(RuntimeError, match="nope"):
        client.generate_image("p", str(tmp_path / "x.png"))

    client.client.images = FakeImages(_GenResp(data=[_Item()]))
    with pytest.raises(RuntimeError, match="Unexpected image item"):
        client.generate_image("p", str(tmp_path / "y.png"))

"""VideoQAAgent integrity checks."""

from src.qa.audit import VideoQAAgent


def test_audit_missing_file():
    ok, reason = VideoQAAgent().audit_clip("/tmp/definitely-missing-clip.mp4")
    assert ok is False
    assert "does not exist" in reason


def test_audit_file_too_small(tmp_path):
    clip = tmp_path / "tiny.mp4"
    clip.write_bytes(b"ftypisom")
    ok, reason = VideoQAAgent().audit_clip(str(clip))
    assert ok is False
    assert "too small" in reason


def test_audit_missing_ftyp(tmp_path):
    clip = tmp_path / "notmp4.mp4"
    clip.write_bytes(b"JUNK" + b"\x00" * (51 * 1024))
    ok, reason = VideoQAAgent().audit_clip(str(clip))
    assert ok is False
    assert "ftyp" in reason


def test_audit_valid_mp4(tmp_path):
    clip = tmp_path / "ok.mp4"
    clip.write_bytes(b"\x00\x00\x00 ftypisom" + b"\x00" * (51 * 1024))
    ok, reason = VideoQAAgent().audit_clip(str(clip))
    assert ok is True
    assert "Passed" in reason

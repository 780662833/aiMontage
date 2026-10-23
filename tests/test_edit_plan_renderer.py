from pathlib import Path

import pytest

from aimontage.edit_plan_renderer import validate_approved_edit_plan
from aimontage.ffmpeg_renderer import RenderError


def _plan():
    return {
        "schema_version": "aimontage.shot_edit_plan.v1",
        "source": {"sha256": "abc"},
        "output": {"width": 1080, "height": 1920, "fps": 30, "video_codec": "h264", "audio_codec": "aac"},
        "acceptance": {"editor_approved": False, "render_approved": False, "reviewer": ""},
        "shots": [{
            "shot_id": "SHOT-001", "order": 0, "review_status": "REVIEW_REQUIRED",
            "source": {"start_frame_no": 0, "end_frame_no_exclusive": 60, "start_seconds": 0.0, "end_seconds": 2.0},
            "target": {"start_frame_no": 0, "end_frame_no_exclusive": 60},
            "transition": {"type": "cut", "duration_frames": 0},
            "reframe": {"mode": "contain", "crop": None},
            "subtitles": {"enabled": False},
        }],
    }


def test_draft_plan_is_not_renderable(tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    with pytest.raises(RenderError, match="not explicitly approved"):
        validate_approved_edit_plan(source, _plan())


def test_plan_requires_per_shot_approval_and_reviewer(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    plan = _plan()
    plan["acceptance"].update(editor_approved=True, render_approved=True, reviewer="reviewer")
    plan["source"]["sha256"] = __import__("hashlib").sha256(b"source").hexdigest()
    with pytest.raises(RenderError, match="not individually approved"):
        validate_approved_edit_plan(source, plan)
    plan["shots"][0]["review_status"] = "APPROVED"
    assert len(validate_approved_edit_plan(source, plan)) == 1


def test_renderer_rejects_hash_mismatch(tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    plan = _plan()
    plan["acceptance"].update(editor_approved=True, render_approved=True, reviewer="reviewer")
    plan["shots"][0]["review_status"] = "APPROVED"
    with pytest.raises(RenderError, match="SHA-256"):
        validate_approved_edit_plan(source, plan)

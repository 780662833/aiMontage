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

def test_approved_plan_renders_real_trim_with_ffmpeg(tmp_path: Path):
    import json
    import shutil
    import subprocess

    from aimontage.edit_plan_renderer import render_approved_edit_plan

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg/ffprobe are required for the integration test")
    source = tmp_path / "source.mp4"
    generated = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-y", "-v", "error",
            "-f", "lavfi", "-i", "color=c=red:s=320x180:r=10:d=2",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(source),
        ],
        capture_output=True, text=True,
    )
    assert generated.returncode == 0, generated.stderr

    plan = _plan()
    plan["output"].update(width=320, height=180, fps=10)
    plan["acceptance"].update(
        editor_approved=True, render_approved=True, reviewer="integration-test"
    )
    plan["source"]["sha256"] = __import__("hashlib").sha256(source.read_bytes()).hexdigest()
    first = plan["shots"][0]
    first.update(order=0, review_status="APPROVED", shot_id="SHOT-LATE")
    first["source"].update(
        start_frame_no=10, end_frame_no_exclusive=15, start_seconds=1.0, end_seconds=1.5
    )
    first["target"].update(start_frame_no=0, end_frame_no_exclusive=5)
    second = json.loads(json.dumps(first))
    second.update(order=1, shot_id="SHOT-EARLY")
    second["source"].update(
        start_frame_no=0, end_frame_no_exclusive=5, start_seconds=0.0, end_seconds=0.5
    )
    second["target"].update(start_frame_no=5, end_frame_no_exclusive=10)
    plan["shots"] = [first, second]
    output = tmp_path / "assembled.mp4"
    report = render_approved_edit_plan(source, output, plan)

    assert output.is_file()
    assert report["render_mode"] == "approved_shot_assembly_hard_cuts"
    assert report["creative_reconstruction_claimed"] is False
    assert abs(float(report["output"]["probe"]["format"]["duration"]) - 1.0) <= 0.15
    streams = report["output"]["probe"]["streams"]
    assert any(s.get("codec_type") == "video" for s in streams)
    assert any(s.get("codec_type") == "audio" for s in streams)
    assert report["edit_plan"]["reviewer"] == "integration-test"
    assert report["audio_policy"] == "source_audio_cut_and_concatenated_per_shot"
    assert [shot["shot_id"] for shot in report["shots"]] == ["SHOT-LATE", "SHOT-EARLY"]


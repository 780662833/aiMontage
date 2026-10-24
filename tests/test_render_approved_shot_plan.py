from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import scripts.render_approved_shot_plan as renderer


def source_file(tmp_path: Path) -> Path:
    path = tmp_path / "a.mp4"
    path.write_bytes(b"fake-video-bytes-for-unit-test")
    return path


def plan_for(source: Path) -> dict:
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    return {
        "schema_version": "aimontage.shot_edit_plan.v1",
        "source": {"sha256": sha, "path": "a.mp4", "duration_seconds": 2.0},
        "output_spec": {"aspect_ratio": "9:16", "resolution": {"width": 1080, "height": 1920}},
        "shots": [{
            "shot_id": "SHOT-001",
            "source_range": {"in_seconds": 0.0, "out_seconds": 2.0},
            "edit_decision": {"production_method": "reuse + trim"},
            "qa": {
                "timing_confirmed": True,
                "story_function_preserved": True,
                "visual_continuity_passed": True,
                "audio_checked": True,
            },
        }],
        "validation": {"ready_for_render": True},
    }


def test_render_blocked_when_plan_is_not_approved(tmp_path: Path):
    source = source_file(tmp_path)
    plan = plan_for(source)
    plan["validation"]["ready_for_render"] = False
    with pytest.raises(ValueError, match="ready_for_render"):
        renderer.build_compose_inputs(plan, source, tmp_path / "out.mp4")


def test_render_blocked_when_source_sha_does_not_match(tmp_path: Path):
    source = source_file(tmp_path)
    plan = plan_for(source)
    plan["source"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        renderer.build_compose_inputs(plan, source, tmp_path / "out.mp4")


def test_render_blocked_until_every_qa_gate_is_approved(tmp_path: Path):
    source = source_file(tmp_path)
    plan = plan_for(source)
    plan["shots"][0]["qa"]["audio_checked"] = False
    with pytest.raises(ValueError, match="QA gates"):
        renderer.build_compose_inputs(plan, source, tmp_path / "out.mp4")


def test_builds_pinned_composer_payload_for_approved_plan(tmp_path: Path):
    source = source_file(tmp_path)
    plan = plan_for(source)
    payload = renderer.build_compose_inputs(plan, source, tmp_path / "out.mp4")
    assert payload["operation"] == "compose"
    assert payload["edit_decisions"]["cuts"] == [{
        "source": str(source.resolve()),
        "in_seconds": 0.0,
        "out_seconds": 2.0,
        "speed": 1.0,
    }]
    assert payload["edit_decisions"]["metadata"]["compose_target"] == {
        "width": 1080, "height": 1920, "fit": "cover"
    }


def test_render_plan_uses_upstream_tool_and_requires_nonempty_output(tmp_path: Path, monkeypatch):
    source = source_file(tmp_path)
    plan = plan_for(source)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    output = tmp_path / "render.mp4"
    calls = {}

    def fake_run(tool_name, inputs, *, repo_root):
        calls["tool_name"] = tool_name
        calls["inputs"] = inputs
        output.write_bytes(b"rendered")
        return {"success": True, "data": {"output": str(output)}}

    monkeypatch.setattr(renderer, "run_upstream_tool", fake_run)
    result = renderer.render_plan(plan_path, source, output, tmp_path / "vendor")
    assert calls["tool_name"] == "video_compose"
    assert result["status"] == "rendered_pending_qa"
    assert result["ready_for_delivery"] is False

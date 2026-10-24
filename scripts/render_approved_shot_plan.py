"""Render only an explicitly approved shot plan through OpenMontage's FFmpeg composer.

This adapter performs no decoding, sampling, scene detection, or semantic inference.
It validates source identity and review gates, then delegates video composition to the
pinned OpenMontage submodule.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from aimontage.evidence import sha256_file
from aimontage.upstream import run_upstream_tool


REQUIRED_QA_FLAGS = (
    "timing_confirmed",
    "story_function_preserved",
    "visual_continuity_passed",
    "audio_checked",
)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def build_compose_inputs(
    plan: dict[str, Any], source_video: Path, output_video: Path
) -> dict[str, Any]:
    if plan.get("schema_version") != "aimontage.shot_edit_plan.v1":
        raise ValueError("Unsupported shot edit plan schema")
    validation = plan.get("validation")
    if not isinstance(validation, dict) or validation.get("ready_for_render") is not True:
        raise ValueError("Render blocked: validation.ready_for_render must be true after human approval")
    source = plan.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("sha256"), str):
        raise ValueError("Shot plan is missing source.sha256")
    if not source_video.is_file():
        raise FileNotFoundError(f"Source video not found: {source_video}")
    actual_sha = sha256_file(source_video)
    if actual_sha != source["sha256"]:
        raise ValueError("Source SHA-256 mismatch; refusing to render a different source video")

    spec = plan.get("output_spec")
    if not isinstance(spec, dict) or spec.get("aspect_ratio") != "9:16":
        raise ValueError("Only an explicitly approved 9:16 output spec is supported")
    resolution = spec.get("resolution")
    if not isinstance(resolution, dict) or resolution.get("width") != 1080 or resolution.get("height") != 1920:
        raise ValueError("Approved output resolution must be 1080x1920")

    shots = plan.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ValueError("Shot plan must contain at least one shot")
    cuts = []
    previous_end = 0.0
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            raise ValueError(f"shots[{index}] must be an object")
        qa = shot.get("qa")
        if not isinstance(qa, dict) or any(qa.get(flag) is not True for flag in REQUIRED_QA_FLAGS):
            raise ValueError(f"{shot.get('shot_id', index)}: timing/story/continuity/audio QA gates are not all approved")
        decision = shot.get("edit_decision")
        if not isinstance(decision, dict):
            raise ValueError(f"{shot.get('shot_id', index)}: edit_decision is required")
        method = decision.get("production_method")
        if not isinstance(method, str) or not method.strip() or any(
            marker in method.lower() for marker in ("choose", "decide", "tbd", "unknown")
        ):
            raise ValueError(f"{shot.get('shot_id', index)}: production_method must be an explicit reviewed choice")
        source_range = shot.get("source_range")
        if not isinstance(source_range, dict):
            raise ValueError(f"{shot.get('shot_id', index)}: source_range is required")
        start, end = source_range.get("in_seconds"), source_range.get("out_seconds")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or start < 0 or end <= start:
            raise ValueError(f"{shot.get('shot_id', index)}: invalid source in/out range")
        if start < previous_end - 0.001:
            raise ValueError("Shot source ranges overlap or are out of chronological order")
        previous_end = float(end)
        cuts.append({
            "source": str(source_video.resolve()),
            "in_seconds": float(start),
            "out_seconds": float(end),
            "speed": 1.0,
        })

    output_video.parent.mkdir(parents=True, exist_ok=True)
    edit_decisions = {
        "cuts": cuts,
        "subtitles": {},
        "metadata": {
            "compose_target": {"width": 1080, "height": 1920, "fit": "cover"},
            "aiMontage_plan_schema": plan["schema_version"],
            "source_sha256": actual_sha,
        },
    }
    return {
        "operation": "compose",
        "input_path": str(source_video.resolve()),
        "output_path": str(output_video.resolve()),
        "edit_decisions": edit_decisions,
        "codec": "libx264",
        "crf": 18,
        "preset": "medium",
    }


def render_plan(
    plan_path: Path,
    source_video: Path,
    output_video: Path,
    repo_root: Path,
) -> dict[str, Any]:
    plan = read_json(plan_path)
    inputs = build_compose_inputs(plan, source_video.resolve(), output_video.resolve())
    result = run_upstream_tool("video_compose", inputs, repo_root=repo_root)
    if result.get("success") is not True:
        raise RuntimeError(f"OpenMontage video_compose failed: {result.get('error') or result}")
    if not output_video.is_file() or output_video.stat().st_size == 0:
        raise RuntimeError("Composer reported success but output file is missing or empty")
    return {
        "schema_version": "aimontage.render_handoff_result.v1",
        "status": "rendered_pending_qa",
        "source_sha256": plan["source"]["sha256"],
        "output_path": str(output_video.resolve()),
        "composer": "pinned OpenMontage tools.video.video_compose.VideoCompose",
        "output_spec": plan["output_spec"],
        "shot_count": len(plan["shots"]),
        "qa_required": True,
        "ready_for_delivery": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved-plan", required=True, type=Path)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("vendor/OpenMontage"))
    args = parser.parse_args()
    result = render_plan(args.approved_plan, args.video, args.out, args.repo_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

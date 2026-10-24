"""Convert OpenMontage's official scene list into reviewable L2 event candidates.

This adapter preserves upstream scene descriptions as unverified candidates. It does not
claim semantic verification, infer frame numbers, or make the result render-ready.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "aimontage.l2_event_timeline.v1"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def build_event_draft(brief: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    source = manifest.get("source", {})
    source_sha = source.get("sha256")
    if not isinstance(source_sha, str) or not source_sha:
        raise ValueError("Analysis manifest is missing source.sha256")

    manifest_status = manifest.get("status")
    manifest_validation = manifest.get("validation", {})
    if manifest_status not in {"passed", "review_required"}:
        raise ValueError("Analysis manifest status must be passed or review_required")
    if manifest_validation.get("official_brief_shape_valid") is False:
        raise ValueError("Cannot build event candidates from an invalid official brief")

    brief_source = brief.get("source", {})
    structure = brief.get("structure_analysis", {})
    scenes = structure.get("scenes", [])
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("OpenMontage brief contains no structure_analysis.scenes")
    duration = brief_source.get("duration_seconds")
    if not isinstance(duration, (int, float)) or duration <= 0:
        raise ValueError("OpenMontage brief source.duration_seconds must be positive")

    events = []
    duration_warnings: list[str] = []
    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            raise ValueError(f"scene[{i}] must be an object")
        start = scene.get("start_time")
        end = scene.get("end_time")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            raise ValueError(f"scene[{i}] requires numeric start_time and end_time")
        if start < 0 or end <= start:
            raise ValueError(
                f"scene[{i}] has an invalid interval: start_time={start!r}, "
                f"end_time={end!r}"
            )
        # Upstream scene boundaries and the brief's declared source duration can
        # disagree. Preserve internally valid boundaries as unverified candidates,
        # but surface the mismatch instead of silently discarding the scene.
        if end > duration + 1e-6:
            duration_warnings.append(
                f"scene[{i}] end_time ({end}) exceeds source.duration_seconds ({duration})"
            )
        description = scene.get("description")
        events.append({
            "event_id": f"OM-SCENE-{i + 1:03d}",
            "label": f"Scene candidate {i + 1}",
            "narrative_role": "upstream_scene_candidate",
            "user_asserted_summary": description if isinstance(description, str) else None,
            "visual_status": "needs_review",
            "start_seconds": None,
            "end_seconds": None,
            "start_frame_no": None,
            "end_frame_no": None,
            "evidence": [{
                "evidence_id": f"openmontage-scene-{i}",
                "artifact": "video_analysis_brief.json",
                "json_pointer": f"/structure_analysis/scenes/{i}",
                "source": "upstream_scene_analysis",
                "status": "unreviewed_candidate",
            }],
            "candidate_intervals": [{
                "start_seconds": round(float(start), 6),
                "end_seconds": round(float(end), 6),
                "source": "OpenMontage structure_analysis.scenes",
                "status": "candidate_timing_not_verified",
            }],
            "notes": [
                "Description and interval are copied from upstream analysis, not human-verified.",
                "Confirm visible action and timing against source frames before production use.",
            ],
        })

    return {
        "schema_version": SCHEMA,
        "status": "review_required",
        "source": {
            "sha256": source_sha,
            "path": source.get("path"),
            "duration_seconds": round(float(duration), 6),
            "sample_count": None,
            "first_sample_seconds": None,
            "last_sample_seconds": None,
        },
        "story_truth_source": "OpenMontage video_analysis_brief.json (unreviewed scene candidates)",
        "separation_policy": {
            "upstream_scene_description": "preserved as an unverified candidate; not asserted as ground truth",
            "candidate_timing": "available for reviewer navigation; not promoted to verified event timing",
            "frame_numbers": "null because this adapter has no timestamp-audited frame mapping",
            "unknown_timing": "represented as null in verified fields; candidate interval retained separately",
        },
        "events": events,
        "global_motion_candidates": [],
        "validation": {
            "warnings": duration_warnings,
            "event_count": len(events),
            "verified_event_count": 0,
            "events_requiring_review": len(events),
            "motion_candidate_count": 0,
            "ready_for_blueprint": False,
            "reason": "Upstream scene candidates are not reviewed semantic events; verify timing and visible actions before Blueprint production use."
            + (" Source-duration mismatch detected; inspect validation.warnings." if duration_warnings else ""),
        },
        "upstream": {
            "tool": manifest.get("upstream", {}).get("tool"),
            "revision": manifest.get("upstream", {}).get("revision"),
            "manifest_status": manifest_status,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", type=Path, required=True, help="video_analysis_brief.json")
    parser.add_argument("--manifest", type=Path, required=True, help="analysis_run_manifest.json")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = build_event_draft(read_json(args.brief), read_json(args.manifest))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "event_count": result["validation"]["event_count"],
        "verified_event_count": result["validation"]["verified_event_count"],
        "ready_for_blueprint": result["validation"]["ready_for_blueprint"],
        "output": args.out.as_posix(),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

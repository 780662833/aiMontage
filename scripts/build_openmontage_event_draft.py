"""Adapt OpenMontage's official brief into a rich, evidence-linked L2 draft.

OpenMontage remains the analysis engine. This adapter preserves its scene metadata,
global content analysis, and keyframe references without inventing per-scene semantics
or modifying the official brief.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SCHEMA = "aimontage.l2_event_timeline.v2"
DURATION_TOLERANCE_SECONDS = 1e-4


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def _nonempty_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _keyframe_evidence(brief: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose upstream keyframes as references; do not infer source frame numbers."""
    raw = brief.get("keyframes", [])
    if not isinstance(raw, list):
        return []
    result: list[dict[str, Any]] = []
    for index, keyframe in enumerate(raw):
        if not isinstance(keyframe, dict):
            continue
        timestamp = None
        for key in ("timestamp", "time", "time_seconds", "source_time", "start_time"):
            candidate = keyframe.get(key)
            if _finite_number(candidate):
                timestamp = float(candidate)
                break
        result.append({
            "evidence_id": f"openmontage-keyframe-{index}",
            "artifact": "video_analysis_brief.json",
            "json_pointer": f"/keyframes/{index}",
            "timestamp_seconds": timestamp,
            "image_path": next(
                (keyframe.get(k) for k in ("path", "image_path", "file_path", "filename")
                 if isinstance(keyframe.get(k), str)),
                None,
            ),
            "description": _nonempty_text(keyframe.get("description"))
                or _nonempty_text(keyframe.get("caption")),
            "status": "upstream_keyframe_unreviewed",
            "upstream_keyframe": keyframe,
        })
    return result


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
    if not _finite_number(duration) or duration <= 0:
        raise ValueError("OpenMontage brief source.duration_seconds must be positive")

    duration = float(duration)
    duration_warnings: list[str] = []
    events: list[dict[str, Any]] = []
    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            raise ValueError(f"scene[{i}] must be an object")
        start, end = scene.get("start_time"), scene.get("end_time")
        if not _finite_number(start) or not _finite_number(end):
            raise ValueError(f"scene[{i}] requires finite numeric start_time and end_time")
        if start < 0 or end <= start:
            raise ValueError(
                f"scene[{i}] has an invalid interval: start_time={start!r}, end_time={end!r}"
            )

        if end > duration + DURATION_TOLERANCE_SECONDS:
            duration_warnings.append(
                f"scene[{i}] end_time ({end}) exceeds source.duration_seconds ({duration})"
            )
        elif end > duration:
            duration_warnings.append(
                f"scene[{i}] end_time ({end}) exceeds source duration only within "
                f"precision tolerance ({DURATION_TOLERANCE_SECONDS}s); preserved as upstream value"
            )

        description = _nonempty_text(scene.get("description"))
        # Keep a copy of the complete upstream scene object so that useful fields such
        # as visual_type, energy_level, motion_type, flow_variance, and future fields survive.
        events.append({
            "event_id": f"OM-SCENE-{i + 1:03d}",
            "label": f"Scene candidate {i + 1}",
            "narrative_role": "upstream_scene_candidate",
            "summary": description,
            "summary_source": "OpenMontage structure_analysis.scenes.description"
                if description else None,
            "user_asserted_summary": None,
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
            "upstream_scene": scene,
            "scene_signals": {
                key: scene[key] for key in
                ("visual_type", "energy_level", "motion_type", "flow_variance")
                if key in scene
            },
            "notes": [
                "Upstream scene metadata is preserved; it has not been independently verified.",
                "Use linked keyframes and source video to confirm actions before final production.",
            ],
        })

    content_analysis = brief.get("content_analysis", {})
    if not isinstance(content_analysis, dict):
        content_analysis = {}
    keyframes = _keyframe_evidence(brief)
    global_summary = _nonempty_text(content_analysis.get("summary"))
    global_topics = content_analysis.get("topics")
    global_audience = content_analysis.get("target_audience")

    return {
        "schema_version": SCHEMA,
        "status": "review_required",
        "source": {
            "sha256": source_sha,
            "path": source.get("path"),
            "duration_seconds": round(duration, 6),
            "sample_count": len(keyframes),
            "first_sample_seconds": next(
                (k["timestamp_seconds"] for k in keyframes if k["timestamp_seconds"] is not None),
                None,
            ),
            "last_sample_seconds": next(
                (k["timestamp_seconds"] for k in reversed(keyframes)
                 if k["timestamp_seconds"] is not None),
                None,
            ),
        },
        "upstream_context": {
            "summary": global_summary,
            "topics": global_topics,
            "target_audience": global_audience,
            "pacing_profile": structure.get("pacing_profile"),
            "content_analysis": content_analysis,
            "source": "OpenMontage video_analysis_brief.json",
            "status": "upstream_analysis_unreviewed",
        },
        "keyframe_evidence": keyframes,
        "story_truth_source": "OpenMontage official brief; all semantic fields remain unreviewed",
        "separation_policy": {
            "upstream_scene_metadata": "preserved verbatim in each event.upstream_scene",
            "global_content_analysis": "preserved under upstream_context, not copied into individual scene summaries",
            "keyframes": "referenced as upstream evidence; timestamps and paths are not treated as audited source-frame mappings",
            "candidate_timing": "available for navigation; not promoted to verified event timing",
            "frame_numbers": "null because no timestamp-audited frame mapping is provided by this adapter",
            "semantic_review": "required before claiming scene-level actions as verified facts",
        },
        "events": events,
        "global_motion_candidates": [],
        "validation": {
            "warnings": duration_warnings,
            "event_count": len(events),
            "verified_event_count": 0,
            "events_requiring_review": len(events),
            "motion_candidate_count": 0,
            "keyframe_evidence_count": len(keyframes),
            "has_global_summary": global_summary is not None,
            "has_scene_descriptions": sum(bool(_nonempty_text(s.get("description"))) for s in scenes),
            "ready_for_blueprint": False,
            "reason": "Analysis content and evidence are now preserved for downstream automation; scene-level semantic verification and audited frame mapping are still required for production Blueprint approval.",
        },
        "upstream": {
            "repository": manifest.get("upstream", {}).get("repository"),
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
        "keyframe_evidence_count": result["validation"]["keyframe_evidence_count"],
        "has_global_summary": result["validation"]["has_global_summary"],
        "scene_descriptions": result["validation"]["has_scene_descriptions"],
        "verified_event_count": result["validation"]["verified_event_count"],
        "ready_for_blueprint": result["validation"]["ready_for_blueprint"],
        "output": args.out.as_posix(),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

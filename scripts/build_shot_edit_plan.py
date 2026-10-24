"""Build a shot-by-shot edit/reconstruction plan from reviewed semantic evidence.

No media analysis is performed here. This stage validates reviewer claims and creates
an actionable timeline scaffold while keeping creative production choices explicit.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "aimontage.shot_edit_plan.v1"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def build_shot_edit_plan(review_doc: dict[str, Any]) -> dict[str, Any]:
    if review_doc.get("schema_version") != "aimontage.semantic_review_template.v1":
        raise ValueError("Unsupported semantic review schema; expected aimontage.semantic_review_template.v1")
    source = review_doc.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("sha256"), str) or not source["sha256"]:
        raise ValueError("Semantic review is missing source.sha256")
    raw_events = review_doc.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        raise ValueError("Semantic review must contain at least one event")

    planned = []
    errors: list[str] = []
    last_start = -1.0
    for idx, event in enumerate(raw_events):
        if not isinstance(event, dict):
            errors.append(f"event[{idx}] is not an object")
            continue
        event_id = event.get("event_id") or f"REVIEW-{idx + 1:03d}"
        interval = event.get("candidate_interval")
        interval = interval if isinstance(interval, dict) else {}
        start, end = interval.get("start_seconds"), interval.get("end_seconds")
        if not (_finite(start) and _finite(end) and 0 <= start < end):
            errors.append(f"{event_id}: valid candidate start_seconds/end_seconds required")
            continue
        if start < last_start:
            errors.append(f"{event_id}: events must be ordered by source start time")
        last_start = float(start)

        review = event.get("review")
        review = review if isinstance(review, dict) else {}
        if review.get("status") != "reviewed":
            errors.append(f"{event_id}: review.status must be 'reviewed'")
        entities = review.get("visible_entities")
        actions = review.get("observable_actions")
        preserve = review.get("must_preserve")
        cited = review.get("evidence_sample_indices")
        if not isinstance(entities, list) or not entities:
            errors.append(f"{event_id}: visible_entities must be a non-empty list")
        if not isinstance(actions, list) or not actions:
            errors.append(f"{event_id}: observable_actions must be a non-empty list")
        if not isinstance(preserve, list) or not preserve:
            errors.append(f"{event_id}: must_preserve must be a non-empty list")
        if not isinstance(cited, list) or not cited or any(not isinstance(x, int) or x < 0 for x in cited):
            errors.append(f"{event_id}: evidence_sample_indices must contain non-negative integers")
        confidence = review.get("confidence")
        if not _finite(confidence) or not 0 <= confidence <= 1:
            errors.append(f"{event_id}: confidence must be numeric from 0 to 1")
        if not isinstance(review.get("story_function"), str) or not review["story_function"].strip():
            errors.append(f"{event_id}: story_function is required")
        evidence = event.get("evidence", [])
        valid_indices = {
            sample.get("sample_index") for sample in evidence
            if isinstance(sample, dict) and isinstance(sample.get("sample_index"), int)
        } if isinstance(evidence, list) else set()
        if isinstance(cited, list) and any(x not in valid_indices for x in cited):
            errors.append(f"{event_id}: cited evidence_sample_indices must exist in this event's evidence")

        if not (_finite(start) and _finite(end) and 0 <= start < end):
            continue
        duration = round(float(end) - float(start), 3)
        planned.append({
            "shot_id": f"SHOT-{len(planned) + 1:03d}",
            "source_event_id": event_id,
            "source_range": {
                "in_seconds": round(float(start), 3),
                "out_seconds": round(float(end), 3),
                "duration_seconds": duration,
                "timing_status": "candidate_only_requires_playback_confirmation",
            },
            "story": {
                "function": review.get("story_function"),
                "visible_entities": entities if isinstance(entities, list) else [],
                "observable_actions": actions if isinstance(actions, list) else [],
                "before_state": review.get("before_state"),
                "after_state": review.get("after_state"),
                "cause_and_reaction": review.get("cause_and_reaction"),
                "must_preserve": preserve if isinstance(preserve, list) else [],
                "uncertainty": review.get("uncertain_or_unobservable", []),
                "confidence": confidence,
                "evidence_sample_indices": cited if isinstance(cited, list) else [],
            },
            "edit_decision": {
                "source_use": "decide_after_playback_review",
                "production_method": "reuse_crop | trim | reorder | regenerate | hybrid (choose during edit review)",
                "composition_9_16": "subject_and_action_safe_area_required",
                "transition_in": "decide",
                "transition_out": "decide",
                "audio": "inspect source audio; preserve only if story-relevant and technically clean",
                "subtitle": "derive from approved script/voiceover only; do not invent dialogue",
            },
            "qa": {
                "timing_confirmed": False,
                "story_function_preserved": False,
                "visual_continuity_passed": False,
                "audio_checked": False,
                "human_review_required": True,
            },
        })

    if errors:
        raise ValueError("Cannot build edit plan until semantic review is complete:\n- " + "\n- ".join(errors))

    ordered = sorted(planned, key=lambda item: item["source_range"]["in_seconds"])
    cursor = 0.0
    for shot in ordered:
        shot["output_range"] = {
            "start_seconds": round(cursor, 3),
            "end_seconds": round(cursor + shot["source_range"]["duration_seconds"], 3),
        }
        cursor += shot["source_range"]["duration_seconds"]

    return {
        "schema_version": SCHEMA,
        "source": {
            "sha256": source["sha256"],
            "path": source.get("path"),
            "duration_seconds": source.get("duration_seconds"),
        },
        "output_spec": {
            "aspect_ratio": "9:16",
            "resolution": {"width": 1080, "height": 1920},
            "fps": None,
            "target_duration_seconds": round(cursor, 3),
            "target_duration_policy": "sum of selected source intervals; revise only in explicit creative edit",
            "audio_policy": "preserve/rebuild only after source audio inspection; run loudness and clipping QA",
        },
        "shots": ordered,
        "validation": {
            "shot_count": len(ordered),
            "all_semantic_reviews_accepted": True,
            "all_shots_require_timing_and_qa_confirmation": True,
            "ready_for_render": False,
            "blocking_gates": [
                "Confirm candidate in/out points by playback",
                "Choose production method and transitions per shot",
                "Verify 9:16 composition and narrative continuity",
                "Check audio loudness/clipping and subtitle/script consistency",
                "Complete human content review",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semantic-review", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = build_shot_edit_plan(read_json(args.semantic_review))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps({"schema_version": SCHEMA, "out": str(args.out), **result["validation"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

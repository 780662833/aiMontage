"""Create a human/multimodal semantic-review template from the evidence packet.

The template exposes traceable sample references and leaves story claims blank.
It does not interpret image content or convert scene candidates into verified events.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "aimontage.semantic_review_template.v1"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def build_review_template(packet: dict[str, Any]) -> dict[str, Any]:
    if packet.get("schema_version") != "aimontage.story_evidence_packet.v1":
        raise ValueError("Unsupported evidence packet schema; expected aimontage.story_evidence_packet.v1")
    source = packet.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("sha256"), str) or not source["sha256"]:
        raise ValueError("Evidence packet is missing source.sha256")
    raw_events = packet.get("events")
    if not isinstance(raw_events, list):
        raise ValueError("Evidence packet events must be a list")

    events = []
    for idx, raw in enumerate(raw_events):
        if not isinstance(raw, dict):
            raise ValueError(f"Event {idx} must be an object")
        interval = raw.get("candidate_interval")
        if not isinstance(interval, dict):
            interval = {}
        start, end = interval.get("start_seconds"), interval.get("end_seconds")
        valid = (
            isinstance(start, (int, float)) and math.isfinite(start)
            and isinstance(end, (int, float)) and math.isfinite(end)
            and 0 <= start < end
        )
        samples = raw.get("linked_dense_samples", [])
        if not isinstance(samples, list):
            samples = []
        evidence = []
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            evidence.append({
                "sample_index": sample.get("sample_index"),
                "timestamp_seconds": sample.get("timestamp_seconds"),
                "frame_no": sample.get("frame_no"),
                "relative_path": sample.get("relative_path"),
                "image_sha256": sample.get("image_sha256"),
                "association_status": sample.get("association_status"),
            })
        events.append({
            "event_id": raw.get("event_id") or f"REVIEW-{idx + 1:03d}",
            "candidate_interval": {
                "start_seconds": float(start) if valid else None,
                "end_seconds": float(end) if valid else None,
                "status": "candidate_only" if valid else "missing_or_invalid",
            },
            "upstream_summary": raw.get("upstream_summary"),
            "scene_signals": raw.get("scene_signals", {}),
            "evidence": evidence,
            "review": {
                "status": "needs_review",
                "visible_entities": [],
                "observable_actions": [],
                "before_state": None,
                "after_state": None,
                "cause_and_reaction": None,
                "story_function": None,
                "must_preserve": [],
                "uncertain_or_unobservable": [],
                "reviewer_notes": None,
                "confidence": None,
                "evidence_sample_indices": [],
            },
        })

    return {
        "schema_version": SCHEMA,
        "source": {
            "sha256": source["sha256"],
            "path": source.get("path"),
            "duration_seconds": source.get("duration_seconds"),
        },
        "review_policy": {
            "only_observable_claims": True,
            "cite_sample_indices": True,
            "uncertainty_is_allowed": True,
            "do_not_infer_offscreen_audio_or_intent": True,
            "candidate_scene_boundaries_are_not_verified_story_boundaries": True,
        },
        "events": events,
        "validation": {
            "event_count": len(events),
            "events_needing_review": len(events),
            "semantically_reviewed_count": 0,
            "ready_for_edit_plan": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-packet", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = build_review_template(read_json(args.evidence_packet))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps({"schema_version": SCHEMA, "out": str(args.out), **result["validation"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

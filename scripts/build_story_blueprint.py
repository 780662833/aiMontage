"""Create an evidence-linked story Blueprint skeleton from the OpenMontage L2 draft.

This stage deliberately does not invent actions or causal relationships. It carries
forward scene time candidates and keyframe references so a multimodal review step can
fill in semantic fields with traceable evidence.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "aimontage.story_blueprint.v1"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def build_story_blueprint(event_draft: dict[str, Any]) -> dict[str, Any]:
    if event_draft.get("schema_version") != "aimontage.l2_event_timeline.v2":
        raise ValueError("Unsupported event draft schema; expected aimontage.l2_event_timeline.v2")
    source = event_draft.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("sha256"), str) or not source["sha256"]:
        raise ValueError("Event draft is missing source.sha256")
    raw_events = event_draft.get("events")
    if not isinstance(raw_events, list):
        raise ValueError("Event draft events must be a list")
    keyframes = event_draft.get("keyframe_evidence", [])
    if not isinstance(keyframes, list):
        keyframes = []

    events: list[dict[str, Any]] = []
    for idx, raw in enumerate(raw_events):
        if not isinstance(raw, dict):
            continue
        intervals = raw.get("candidate_intervals", [])
        if not isinstance(intervals, list):
            intervals = []
        interval = next((v for v in intervals if isinstance(v, dict)), {})
        start = interval.get("start_seconds") if isinstance(interval, dict) else None
        end = interval.get("end_seconds") if isinstance(interval, dict) else None
        if not _number(start) or not _number(end) or end <= start:
            start = raw.get("start_seconds")
            end = raw.get("end_seconds")
        evidence_ids: list[str] = []
        if _number(start) and _number(end):
            for frame in keyframes:
                if not isinstance(frame, dict):
                    continue
                ts = frame.get("timestamp_seconds")
                if _number(ts) and start <= ts <= end:
                    eid = frame.get("evidence_id")
                    if isinstance(eid, str):
                        evidence_ids.append(eid)
        events.append({
            "event_id": raw.get("event_id") or f"EV-{idx + 1:03d}",
            "time_candidate": {
                "start_seconds": float(start) if _number(start) else None,
                "end_seconds": float(end) if _number(end) else None,
                "source": "OpenMontage scene interval candidate" if _number(start) and _number(end) else None,
                "status": "candidate_not_verified" if _number(start) and _number(end) else "missing",
            },
            "narrative_role": None,
            "action": None,
            "actor_id": None,
            "target_id": None,
            "before_state": None,
            "after_state": None,
            "reaction_to": [],
            "must_preserve": None,
            "confidence": None,
            "evidence_ids": evidence_ids,
            "source_scene_summary": raw.get("summary"),
            "review_status": "needs_semantic_review",
        })

    return {
        "schema_version": SCHEMA,
        "source": {
            "sha256": source["sha256"],
            "path": source.get("path"),
            "duration_seconds": event_draft.get("source", {}).get("duration_seconds"),
        },
        "upstream": {
            "schema_version": event_draft.get("schema_version"),
            "analysis_manifest": event_draft.get("analysis_manifest"),
        },
        "keyframe_evidence": keyframes,
        "events": events,
        "validation": {
            "event_count": len(events),
            "events_with_time_candidates": sum(
                e["time_candidate"]["status"] == "candidate_not_verified" for e in events
            ),
            "events_semantically_verified": 0,
            "ready_for_remake_plan": False,
            "policy": "No action, actor, causal link, or confidence is inferred by this deterministic adapter.",
            "warnings": [
                "Scene boundaries are not necessarily story-event boundaries.",
                "Semantic fields must be populated from visual/audio evidence before remake planning.",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-draft", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = build_story_blueprint(read_json(args.event_draft))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": SCHEMA, "out": str(args.out), **result["validation"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Build a frame-linked manual review packet for the four known story beats.

Candidate windows are navigation hints from the previously reviewed contact sheet,
not verified event boundaries. This tool never marks an event as visually verified.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "aimontage.l2_event_review_packet.v1"

# Approximate navigation windows from the existing contact-sheet review.
# They intentionally remain broad and are not used as event start/end times.
DEFAULT_WINDOWS = {
    "E01": (0.0, 3.0),
    "E02": (3.0, 5.0),
    "E03": (7.5, 12.0),
    "E04": (7.5, 12.0),
}


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def build(timeline_path: Path, evidence_path: Path) -> dict[str, Any]:
    timeline = read_json(timeline_path)
    evidence = read_json(evidence_path)
    source = evidence.get("source") or {}
    source_sha = source.get("sha256")
    if not source_sha:
        raise ValueError("Evidence is missing source.sha256")

    timeline_source = timeline.get("source") or {}
    if timeline_source.get("sha256") != source_sha:
        raise ValueError("Timeline and dense evidence source SHA-256 do not match")

    samples = evidence.get("samples") or []
    if not samples:
        raise ValueError("Evidence contains no samples")
    for sample in samples:
        if sample.get("source_sha256") != source_sha:
            raise ValueError("A sample source SHA-256 does not match the evidence source")

    events_by_id = {str(e.get("event_id")): e for e in timeline.get("events", [])}
    packet_events = []
    for event_id, (window_start, window_end) in DEFAULT_WINDOWS.items():
        event = events_by_id.get(event_id)
        if not event:
            raise ValueError(f"Timeline is missing expected event {event_id}")
        selected = []
        for sample in samples:
            t = float(sample.get("source_pts_time"))
            if window_start <= t <= window_end:
                selected.append({
                    "sample_index": sample.get("sample_index"),
                    "source_pts_time": t,
                    "frame_no": sample.get("frame_no"),
                    "relative_path": sample.get("relative_path"),
                    "image_sha256": sample.get("image_sha256") or sample.get("sha256"),
                })
        selected.sort(key=lambda item: (item["source_pts_time"], item["sample_index"] or 0))
        packet_events.append({
            "event_id": event_id,
            "label": event.get("label"),
            "candidate_window_seconds": {
                "start": window_start,
                "end": window_end,
                "status": "navigation_hint_not_verified_boundary",
            },
            "visual_status": "needs_review",
            "event_start_seconds": None,
            "event_end_seconds": None,
            "evidence_samples": selected,
            "review_checklist": [
                "Confirm the visible action against the original video, not motion score alone.",
                "Record the first frame that clearly shows the action beginning.",
                "Record the key-action frame(s) and the last frame needed to establish continuity.",
                "Keep times null and visual_status needs_review until reviewed.",
            ],
        })

    return {
        "schema_version": SCHEMA,
        "source": {
            "sha256": source_sha,
            "sample_count": len(samples),
            "first_sample_seconds": min(float(s["source_pts_time"]) for s in samples),
            "last_sample_seconds": max(float(s["source_pts_time"]) for s in samples),
        },
        "purpose": "Manual review packet only; not a verified timeline or Blueprint.",
        "candidate_window_basis": "Approximate ranges from prior contact-sheet notes; refine by inspecting frames/source video.",
        "events": packet_events,
        "validation": {
            "event_count": len(packet_events),
            "verified_event_count": 0,
            "ready_for_blueprint": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    packet = build(args.timeline, args.evidence)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema_version": packet["schema_version"],
        "event_count": packet["validation"]["event_count"],
        "verified_event_count": packet["validation"]["verified_event_count"],
        "frames_per_event": {e["event_id"]: len(e["evidence_samples"]) for e in packet["events"]},
        "ready_for_blueprint": packet["validation"]["ready_for_blueprint"],
        "output": args.out.as_posix(),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

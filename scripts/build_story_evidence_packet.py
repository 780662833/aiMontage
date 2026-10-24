"""Join OpenMontage scene candidates to timestamped dense-frame evidence.

This deterministic join creates a compact, traceable packet for later multimodal
semantic review. It does not infer actions or promote scene boundaries to story events.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "aimontage.story_evidence_packet.v1"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def build_packet(event_draft: dict[str, Any], dense: dict[str, Any], motion: dict[str, Any] | None = None) -> dict[str, Any]:
    if event_draft.get("schema_version") != "aimontage.l2_event_timeline.v2":
        raise ValueError("Unsupported event draft schema")
    if dense.get("schema_version") != "aimontage.dense_frame_evidence.v1":
        raise ValueError("Unsupported dense evidence schema")
    event_source = event_draft.get("source", {})
    dense_source = dense.get("source", {})
    expected_sha = event_source.get("sha256")
    actual_sha = dense_source.get("sha256")
    if not isinstance(expected_sha, str) or not expected_sha:
        raise ValueError("Event draft is missing source.sha256")
    if expected_sha != actual_sha:
        raise ValueError("Source SHA-256 mismatch between event draft and dense evidence")

    samples = dense.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("Dense evidence contains no samples")
    normalized: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in samples:
        if not isinstance(row, dict):
            raise ValueError("Dense sample must be an object")
        idx, ts = row.get("sample_index"), row.get("source_pts_time")
        if not isinstance(idx, int) or idx in seen:
            raise ValueError("Dense samples require unique integer sample_index values")
        if not _finite(ts) or ts < 0:
            raise ValueError(f"Sample {idx} has invalid source_pts_time")
        if row.get("source_sha256") != expected_sha:
            raise ValueError(f"Sample {idx} source SHA-256 does not match source")
        seen.add(idx)
        normalized.append({
            "sample_index": idx,
            "timestamp_seconds": float(ts),
            "frame_no": row.get("frame_no"),
            "relative_path": row.get("relative_path"),
            "image_sha256": row.get("image_sha256"),
            "association_status": row.get("association_status"),
            "association_key": row.get("association_key"),
        })
    normalized.sort(key=lambda x: (x["timestamp_seconds"], x["sample_index"]))

    raw_events = event_draft.get("events")
    if not isinstance(raw_events, list):
        raise ValueError("Event draft events must be a list")
    events = []
    for raw in raw_events:
        if not isinstance(raw, dict):
            continue
        intervals = raw.get("candidate_intervals", [])
        interval = next((i for i in intervals if isinstance(i, dict)), {}) if isinstance(intervals, list) else {}
        start, end = interval.get("start_seconds"), interval.get("end_seconds")
        valid = _finite(start) and _finite(end) and 0 <= start < end
        linked = [
            sample for sample in normalized
            if valid and start <= sample["timestamp_seconds"] <= end
        ]
        events.append({
            "event_id": raw.get("event_id"),
            "candidate_interval": {
                "start_seconds": float(start) if valid else None,
                "end_seconds": float(end) if valid else None,
                "source": interval.get("source") if valid else None,
                "status": "candidate_only" if valid else "missing_or_invalid",
            },
            "upstream_summary": raw.get("summary"),
            "scene_signals": raw.get("scene_signals", {}),
            "linked_dense_samples": linked,
            "linked_sample_count": len(linked),
            "semantic_review": {
                "action": None,
                "actor_id": None,
                "target_id": None,
                "before_state": None,
                "after_state": None,
                "reaction_to": [],
                "must_preserve": None,
                "confidence": None,
                "status": "needs_multimodal_review",
            },
        })

    motion_intervals = []
    if isinstance(motion, dict):
        if motion.get("source_sha256") != expected_sha:
            raise ValueError("Source SHA-256 mismatch between motion report and event draft")
        raw_intervals = motion.get("intervals", [])
        if isinstance(raw_intervals, list):
            motion_intervals = [
                item for item in raw_intervals
                if isinstance(item, dict) and item.get("motion_candidate") is True
            ]

    return {
        "schema_version": SCHEMA,
        "source": {
            "sha256": expected_sha,
            "path": event_source.get("path") or dense_source.get("path"),
            "duration_seconds": event_source.get("duration_seconds"),
        },
        "evidence_policy": {
            "time_authority": "dense samples.source_pts_time",
            "identity_key": "source_sha256 + frame_no",
            "scene_intervals": "navigation candidates only; not verified story-event boundaries",
            "semantic_fields": "null until reviewed against the linked images and source video",
        },
        "sampling": {
            "sample_count": len(normalized),
            "first_timestamp_seconds": normalized[0]["timestamp_seconds"],
            "last_timestamp_seconds": normalized[-1]["timestamp_seconds"],
            "chronological": True,
        },
        "events": events,
        "motion_candidates": motion_intervals,
        "validation": {
            "event_count": len(events),
            "events_with_linked_samples": sum(bool(e["linked_dense_samples"]) for e in events),
            "linked_sample_total": sum(e["linked_sample_count"] for e in events),
            "semantic_event_count": 0,
            "ready_for_remake_plan": False,
            "warnings": [
                "One dense sample may be linked to multiple overlapping scene candidates.",
                "A scene candidate is not automatically a semantic story event.",
                "Optical-flow candidates are review hints, not verified object actions.",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-draft", required=True, type=Path)
    parser.add_argument("--dense-evidence", required=True, type=Path)
    parser.add_argument("--motion-report", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    motion = read_json(args.motion_report) if args.motion_report else None
    packet = build_packet(read_json(args.event_draft), read_json(args.dense_evidence), motion)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": SCHEMA, "out": str(args.out), **packet["validation"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

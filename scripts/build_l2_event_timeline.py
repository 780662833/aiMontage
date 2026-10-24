"""Build an evidence-linked L2 event timeline from reviewed story truth and L1 evidence.

This is a deterministic scaffold, not an automatic vision model. It never upgrades a
user-provided story beat or optical-flow candidate into a visually verified fact.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "aimontage.l2_event_timeline.v1"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def build(story_path: Path, evidence_path: Path, motion_path: Path | None) -> dict[str, Any]:
    story = load_json(story_path)
    evidence = load_json(evidence_path)
    source = evidence.get("source", {})
    source_sha = source.get("sha256")
    if not source_sha:
        raise ValueError("Dense evidence is missing source.sha256")
    if story.get("source_sha256") and story["source_sha256"] != source_sha:
        raise ValueError("Story truth and dense evidence source SHA-256 do not match")

    samples = sorted(
        evidence.get("samples", []),
        key=lambda s: (float(s.get("source_pts_time", 0)), int(s.get("sample_index", 0))),
    )
    if not samples:
        raise ValueError("Dense evidence contains no samples")
    for sample in samples:
        if sample.get("source_sha256") != source_sha:
            raise ValueError("Sample source SHA-256 does not match evidence source")

    motion = load_json(motion_path) if motion_path else None
    if motion and motion.get("source_sha256") != source_sha:
        raise ValueError("Motion report and dense evidence source SHA-256 do not match")

    intervals = motion.get("intervals", []) if motion else []
    events = []
    for beat in story.get("beats", []):
        beat_id = str(beat["id"])
        # The story truth supplies narrative intent; only a reviewer may confirm visual timing.
        events.append({
            "event_id": beat_id,
            "label": beat["label"],
            "narrative_role": beat.get("narrative_role", "story_beat"),
            "user_asserted_summary": beat["summary"],
            "visual_status": "needs_review",
            "start_seconds": None,
            "end_seconds": None,
            "start_frame_no": None,
            "end_frame_no": None,
            "evidence": [],
            "candidate_intervals": [],
            "notes": [
                "Timing and visible action are not confirmed by this deterministic builder.",
                "Review the source video around the candidate intervals before marking verified."
            ],
        })

    # Attach motion intervals as review leads only; never infer which semantic event they prove.
    for event in events:
        event["candidate_intervals"] = [
            {
                "start_seconds": item.get("start_seconds"),
                "end_seconds": item.get("end_seconds"),
                "start_sample_index": item.get("start_sample_index"),
                "end_sample_index": item.get("end_sample_index"),
                "mean_flow_magnitude_px": item.get("mean_flow_magnitude_px"),
                "status": "motion_candidate_not_semantic_proof",
            }
            for item in intervals if item.get("motion_candidate")
        ]

    return {
        "schema_version": SCHEMA,
        "source": {
            "sha256": source_sha,
            "path": source.get("path"),
            "sample_count": len(samples),
            "first_sample_seconds": float(samples[0]["source_pts_time"]),
            "last_sample_seconds": float(samples[-1]["source_pts_time"]),
        },
        "story_truth_source": story.get("source", "user-provided narrative"),
        "separation_policy": {
            "user_asserted_story": "preserved as narrative intent",
            "visual_observation": "must be reviewed against source frames/video",
            "motion_candidates": "navigation hints only; not semantic evidence",
            "unknown_timing": "represented as null; never fabricated",
        },
        "events": events,
        "validation": {
            "event_count": len(events),
            "verified_event_count": 0,
            "events_requiring_review": len(events),
            "motion_candidate_count": sum(1 for item in intervals if item.get("motion_candidate")),
            "ready_for_blueprint": False,
            "reason": "Blueprint generation is gated until event timing and visual evidence are reviewed.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", type=Path, required=True, help="Reviewed story truth JSON")
    parser.add_argument("--evidence", type=Path, required=True, help="dense_frame_evidence.json")
    parser.add_argument("--motion-report", type=Path, help="optional motion_dense_review.json")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.story, args.evidence, args.motion_report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema_version": result["schema_version"],
        "event_count": result["validation"]["event_count"],
        "verified_event_count": result["validation"]["verified_event_count"],
        "ready_for_blueprint": result["validation"]["ready_for_blueprint"],
        "output": args.out.as_posix(),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

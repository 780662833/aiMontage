"""Prepare a review template that links each Blueprint shot to sampled source frames."""
from __future__ import annotations

from typing import Any


def build_visual_review_template(
    visual_bundle: dict[str, Any],
    blueprint: dict[str, Any],
) -> dict[str, Any]:
    visual_sha = visual_bundle.get("fixture", {}).get("sha256")
    blueprint_sha = blueprint.get("source", {}).get("sha256")
    if not visual_sha or visual_sha != blueprint_sha:
        raise ValueError("Visual review inputs do not refer to the same source video")

    sampled_frames = visual_bundle.get("normalized", {}).get("sampled_frames", [])
    if not sampled_frames:
        raise ValueError("Visual evidence bundle contains no sampled frames")

    frames_by_no: dict[int, dict[str, Any]] = {}
    for frame in sampled_frames:
        frame_no = int(frame["frame_no"])
        if frame.get("source_sha256") != visual_sha:
            raise ValueError(f"Sampled frame {frame_no} source hash mismatch")
        if frame.get("association_status") != "aligned":
            raise ValueError(f"Sampled frame {frame_no} is not aligned to source PTS")
        frames_by_no[frame_no] = {
            "frame_no": frame_no,
            "sample_timestamp_seconds": frame.get("sample_timestamp_seconds"),
            "source_pts_time": frame.get("source_pts_time"),
            "mapping_delta_seconds": frame.get("mapping_delta_seconds"),
            "relative_path": frame.get("relative_path"),
            "image_sha256": frame.get("image_sha256"),
            "source_sha256": frame.get("source_sha256"),
            "association_key": frame.get("association_key"),
            "association_status": frame.get("association_status"),
        }

    review_shots = []
    for shot in blueprint.get("shots", []):
        interval = shot.get("source_frame_interval", {})
        start_frame = int(interval["start_frame_no"])
        end_frame = int(interval["end_frame_no"])
        evidence_frames = [
            frames_by_no[frame_no]
            for frame_no in sorted(frames_by_no)
            if start_frame <= frame_no < end_frame
        ]
        review_shots.append({
            "shot_id": shot["shot_id"],
            "start_seconds": shot["start_seconds"],
            "end_seconds": shot["end_seconds"],
            "source_frame_interval": interval,
            "evidence_frames": evidence_frames,
            "annotation": {
                "visual_description": None,
                "subject": None,
                "action": None,
                "camera_motion": None,
                "composition": None,
                "lighting_and_color": None,
                "edit_intent": None,
                "confidence": None,
                "evidence_frame_nos": [],
                "review_status": "not_reviewed",
                "annotator_note": None,
            },
            "review_instructions": [
                "Only describe details visible in the linked evidence frames.",
                "Use unknown/null when evidence is insufficient; do not infer unseen actions.",
                "Treat camera motion as a hypothesis unless supported by multiple frames.",
                "Keep source frame numbers and evidence paths unchanged.",
            ],
        })

    blockers = []
    for shot in review_shots:
        if not shot["evidence_frames"]:
            blockers.append(f"{shot['shot_id']} has no sampled frames inside its source-frame interval")

    return {
        "schema_version": "aimontage.visual_review_template.v1",
        "status": "pending_human_or_model_review",
        "source": {
            "sha256": visual_sha,
            "path": visual_bundle.get("fixture", {}).get("path"),
        },
        "policy": {
            "evidence_first": True,
            "semantic_fields_are_unfilled": True,
            "frame_intervals_are_half_open": True,
            "source_pts_is_authoritative": True,
        },
        "shots": review_shots,
        "validation": {
            "source_identity_matches": True,
            "shot_count": len(review_shots),
            "sampled_frame_count": len(frames_by_no),
            "shots_without_sampled_frames": len(blockers),
            "review_complete": False,
            "blockers": blockers,
        },
        "limitations": [
            "This template does not perform visual recognition or claim semantic correctness.",
            "Sparse sampled frames may not capture all actions or camera motion in a shot.",
            "Review completion requires evidence-backed annotations and a separate validation step.",
        ],
    }

"""Merge reviewed visual annotations and a render target into a reviewable Blueprint candidate."""
from __future__ import annotations

from typing import Any

from .render_spec import validate_render_spec
from .visual_review_validation import visual_review_completion


def build_reconstruction_candidate(
    blueprint_draft: dict[str, Any],
    visual_review: dict[str, Any],
    render_spec: dict[str, Any],
) -> dict[str, Any]:
    source_sha = blueprint_draft.get("source", {}).get("sha256")
    if not source_sha or source_sha != visual_review.get("source", {}).get("sha256"):
        raise ValueError("Blueprint and visual review must refer to the same source video")
    review_result = visual_review_completion(visual_review)
    if not review_result["valid"]:
        raise ValueError("Visual review is invalid: " + "; ".join(review_result["errors"]))
    if not review_result["review_complete"]:
        raise ValueError("Visual review must be complete before candidate promotion")
    render_errors = validate_render_spec(render_spec)
    if render_errors:
        raise ValueError("Invalid render spec: " + "; ".join(render_errors))

    draft_shots = blueprint_draft.get("shots", [])
    reviewed_shots = visual_review.get("shots", [])
    draft_by_id = {shot.get("shot_id"): shot for shot in draft_shots}
    review_by_id = {shot.get("shot_id"): shot for shot in reviewed_shots}
    if set(draft_by_id) != set(review_by_id) or not draft_by_id:
        raise ValueError("Blueprint and visual review shot IDs must match exactly")

    merged = []
    for shot in draft_shots:
        sid = shot["shot_id"]
        reviewed = review_by_id[sid]
        if (shot.get("start_seconds"), shot.get("end_seconds")) != (
            reviewed.get("start_seconds"), reviewed.get("end_seconds")
        ):
            raise ValueError(f"{sid} time interval differs between Blueprint and visual review")
        annotation = reviewed["annotation"]
        interval = shot["source_frame_interval"]
        linked_frames = [
            {
                "frame_no": frame["frame_no"],
                "source_pts_time": frame["source_pts_time"],
                "relative_path": frame["relative_path"],
                "image_sha256": frame["image_sha256"],
            }
            for frame in reviewed.get("evidence_frames", [])
        ]
        merged.append({
            **shot,
            "visual_description": annotation["visual_description"],
            "subject": annotation["subject"],
            "action": annotation["action"],
            "camera_motion": annotation["camera_motion"],
            "composition": annotation["composition"],
            "lighting_and_color": annotation["lighting_and_color"],
            "edit_intent": annotation["edit_intent"],
            "annotation_confidence": annotation["confidence"],
            "semantic_status": "reviewed",
            "annotation_evidence_frame_nos": annotation["evidence_frame_nos"],
            "sampled_frame_evidence": linked_frames,
            "source_frame_interval": interval,
        })

    blockers = [
        "Motion-dense event sampling has not yet been validated; sparse sampled frames may miss intermediate actions.",
        "Creative edit intent is interpretive and requires final editorial approval.",
        "Render and post-render technical/content QA have not been executed.",
    ]
    return {
        "schema_version": "aimontage.reconstruction_blueprint_candidate.v1",
        "status": "reviewable_candidate",
        "source": blueprint_draft["source"],
        "audio": blueprint_draft["audio"],
        "render_spec": render_spec,
        "shots": merged,
        "event_timeline_ref": blueprint_draft.get("event_timeline_ref"),
        "acceptance": {
            "source_identity_matches": True,
            "visual_review_complete": True,
            "render_spec_valid": True,
            "music_only_transcript_excluded": (
                blueprint_draft.get("audio", {}).get("classification") != "music_only"
                or blueprint_draft.get("audio", {}).get("spoken_transcript") is None
            ),
            "render_ready": False,
            "production_ready": False,
            "blockers": blockers,
        },
        "limitations": [
            "This candidate combines reviewed visual descriptions with a target render profile; it does not render a video.",
            "Camera-motion descriptions are limited to what sparse sampled frames support.",
            "No transcript or dialogue is invented for the music-only source.",
        ],
    }

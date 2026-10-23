"""Build an evidence-linked Blueprint draft without inventing semantic scene descriptions."""
from __future__ import annotations

from typing import Any


def build_blueprint_draft(
    visual_bundle: dict[str, Any],
    cross_modal_timeline: dict[str, Any],
    audio_review: dict[str, Any],
) -> dict[str, Any]:
    fixture = visual_bundle.get("fixture", {})
    source_sha = fixture.get("sha256")
    timeline_sha = cross_modal_timeline.get("source", {}).get("sha256")
    if not source_sha or source_sha != timeline_sha:
        raise ValueError("Blueprint inputs do not refer to the same source video")
    classification = audio_review.get("classification")
    if classification not in {"music_only", "speech_only", "music_and_speech", "unknown"}:
        raise ValueError("Audio review classification is missing or unsupported")
    if audio_review.get("transcript_included_in_blueprint") and classification == "music_only":
        raise ValueError("Music-only audio review cannot include a spoken transcript")

    scenes = visual_bundle.get("normalized", {}).get("scenes", [])
    if not scenes:
        raise ValueError("Blueprint requires normalized visual scene evidence")
    shots = []
    previous_end = None
    for scene in scenes:
        start, end = float(scene["start_seconds"]), float(scene["end_seconds"])
        if end <= start:
            raise ValueError("Blueprint scene interval must have positive duration")
        if previous_end is not None and abs(start - previous_end) > 1e-6:
            raise ValueError("Blueprint scene intervals must be contiguous")
        previous_end = end
        shots.append({
            "shot_id": f"SHOT-{int(scene['scene_index']) + 1:03d}",
            "start_seconds": round(start, 6),
            "end_seconds": round(end, 6),
            "duration_seconds": round(end - start, 6),
            "source_frame_interval": {
                "start_frame_no": int(scene["start_frame_no"]),
                "end_frame_no": int(scene["end_frame_no"]),
                "semantics": "[start_frame_no, end_frame_no)",
            },
            "visual_description": None,
            "camera_motion": None,
            "edit_intent": None,
            "evidence_refs": [
                f"real-a-mp4:scene_detect",
                f"real-a-mp4:source-frame-pts-audit",
            ],
            "semantic_status": "not_yet_annotated",
        })

    audio_policy = audio_review.get("blueprint_audio_policy")
    if classification == "music_only" and audio_policy != "music_timeline_only_no_spoken_transcript":
        raise ValueError("Music-only review must explicitly exclude spoken transcript")
    blockers = [
        "Visual semantics, subject/action descriptions, and camera motion require evidence-based annotation.",
        "Creative edit intent and target output specification have not yet been authored.",
    ]
    if classification == "unknown":
        blockers.append("Audio classification is unknown; audio-dependent creative fields remain blocked.")
    if classification in {"speech_only", "music_and_speech"} and audio_review.get("transcript_status") != "QA_PASS_REQUIRES_CONTENT_SPOT_CHECK":
        blockers.append("Speech transcript is not cleared for use; human content review is required.")

    return {
        "schema_version": "aimontage.blueprint_draft.v1",
        "status": "evidence_aligned_draft",
        "source": {
            "path": fixture.get("path"),
            "sha256": source_sha,
            "duration_seconds": cross_modal_timeline.get("source", {}).get("duration_seconds"),
        },
        "audio": {
            "classification": classification,
            "policy": audio_policy,
            "spoken_transcript": None if classification == "music_only" else "not_attached",
            "music_timeline_ref": "music_timeline_evidence",
            "cross_modal_timeline_ref": "cross_modal_timeline",
        },
        "shots": shots,
        "event_timeline_ref": "cross_modal_timeline",
        "acceptance": {
            "source_identity_matches": True,
            "scene_intervals_contiguous": True,
            "music_only_transcript_excluded": classification != "music_only" or audio_review.get("transcript_included_in_blueprint") is False,
            "creative_blueprint_ready": False,
            "blockers": blockers,
        },
        "limitations": [
            "This is an evidence-aligned draft, not a semantically complete production Blueprint.",
            "Null semantic fields are intentionally left unfilled rather than guessed.",
        ],
    }

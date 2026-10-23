"""Build an explicit, review-gated per-shot edit plan from the reviewed candidate."""
from __future__ import annotations

from typing import Any


def build_edit_plan(candidate: dict[str, Any]) -> dict[str, Any]:
    if candidate.get("schema_version") != "aimontage.reconstruction_blueprint_candidate.v1":
        raise ValueError("unsupported reconstruction candidate schema")
    acceptance = candidate.get("acceptance", {})
    if acceptance.get("visual_review_complete") is not True:
        raise ValueError("complete visual review is required")
    source = candidate.get("source", {})
    source_sha = source.get("sha256")
    if not source_sha:
        raise ValueError("source SHA-256 is required")
    spec = candidate.get("render_spec", {})
    output = spec.get("output", {})
    fps = int(output.get("fps", 0))
    if fps <= 0:
        raise ValueError("render spec must declare a positive frame rate")
    shots = candidate.get("shots", [])
    if not shots:
        raise ValueError("candidate contains no shots")

    plan_shots = []
    cursor = 0
    for index, shot in enumerate(shots):
        interval = shot.get("source_frame_interval", {})
        start = int(interval.get("start_frame_no", -1))
        end = int(interval.get("end_frame_no", -1))
        if start < 0 or end <= start:
            raise ValueError(f"{shot.get('shot_id', index)} has invalid half-open source frame interval")
        duration = float(shot.get("end_seconds", 0)) - float(shot.get("start_seconds", 0))
        if duration <= 0:
            raise ValueError(f"{shot.get('shot_id', index)} has invalid source duration")
        target_frames = max(1, round(duration * fps))
        plan_shots.append({
            "shot_id": shot.get("shot_id", f"SHOT-{index + 1:03d}"),
            "order": index,
            "source": {
                "sha256": source_sha,
                "start_frame_no": start,
                "end_frame_no_exclusive": end,
                "start_seconds": shot["start_seconds"],
                "end_seconds": shot["end_seconds"],
                "interval_convention": "[start_frame_no, end_frame_no_exclusive)",
                "evidence_frame_nos": shot.get("annotation_evidence_frame_nos", []),
            },
            "target": {
                "start_frame_no": cursor,
                "end_frame_no_exclusive": cursor + target_frames,
                "duration_seconds": target_frames / fps,
                "fps": fps,
            },
            "reframe": {
                "mode": "contain",
                "crop": None,
                "subject_protection": "no_crop_without_bbox_or_manual_approval",
                "background_fill": spec.get("fit_policy", {}).get("background_fill", "review_required"),
                "status": "REVIEW_REQUIRED",
            },
            "transition": {
                "type": "cut",
                "duration_frames": 0,
                "status": "conservative_default_requires_editor_approval",
            },
            "subtitles": {
                "enabled": bool(spec.get("subtitles", {}).get("burn_in", False)),
                "source": spec.get("subtitles", {}).get("source", "none_until_verified"),
                "segments": [],
                "status": "disabled_until_verified",
            },
            "audio": {
                "source_audio_policy": "preserve_source_music" if spec.get("audio", {}).get("preserve_source_music") else "review_required",
                "music_edit": "continuous_source_audio_no_beat_sync_claim",
                "gain_db": 0.0,
                "fade_in_seconds": 0.0,
                "fade_out_seconds": 0.0,
                "status": "REVIEW_REQUIRED",
            },
            "visual_intent": {
                "description": shot.get("visual_description"),
                "subject": shot.get("subject"),
                "action": shot.get("action"),
                "camera_motion": shot.get("camera_motion"),
                "composition": shot.get("composition"),
                "edit_intent": shot.get("edit_intent"),
            },
            "review_status": "REVIEW_REQUIRED",
        })
        cursor += target_frames

    return {
        "schema_version": "aimontage.shot_edit_plan.v1",
        "status": "draft_requires_editor_approval",
        "source": source,
        "output": {
            "width": output.get("width"),
            "height": output.get("height"),
            "fps": fps,
            "container": output.get("container", "mp4"),
            "video_codec": output.get("video_codec", "h264"),
            "audio_codec": output.get("audio_codec", "aac"),
            "planned_frame_count": cursor,
            "planned_duration_seconds": cursor / fps,
            "duration_policy": output.get("duration_policy", "preserve_source"),
        },
        "shots": plan_shots,
        "global_audio_policy": candidate.get("audio", {}),
        "editorial_constraints": [
            "This plan is derived from sparse evidence; motion-dense sampling and intermediate actions remain unverified.",
            "Do not enable subtitles until text and timings are verified against source evidence.",
            "Do not crop the subject without a reviewed bounding box or explicit approval.",
            "Transitions default to hard cuts; change only with editorial approval.",
            "Source music is continuous by default; beat alignment is not inferred from energy transients alone.",
        ],
        "acceptance": {
            "editor_approval_required": True,
            "motion_evidence_complete": False,
            "render_approved": False,
            "production_ready": False,
        },
    }

"""Validate the evidence-aligned Blueprint draft before any creative handoff."""
from __future__ import annotations

from typing import Any


def validate_blueprint_draft(blueprint: dict[str, Any]) -> list[str]:
    """Return validation errors; an evidence-aligned draft is not production-ready."""
    errors: list[str] = []
    if blueprint.get("schema_version") != "aimontage.blueprint_draft.v1":
        errors.append("unsupported schema_version")
    if blueprint.get("status") != "evidence_aligned_draft":
        errors.append("status must be evidence_aligned_draft")

    source = blueprint.get("source")
    if not isinstance(source, dict) or not source.get("sha256"):
        errors.append("source.sha256 is required")

    audio = blueprint.get("audio")
    if not isinstance(audio, dict):
        errors.append("audio object is required")
        audio = {}
    classification = audio.get("classification")
    if classification not in {"music_only", "speech_only", "music_and_speech", "unknown"}:
        errors.append("audio.classification is unsupported")
    if classification == "music_only":
        if audio.get("spoken_transcript") is not None:
            errors.append("music_only Blueprint must not contain a spoken transcript")
        if audio.get("policy") != "music_timeline_only_no_spoken_transcript":
            errors.append("music_only audio policy must explicitly exclude transcript")

    shots = blueprint.get("shots")
    if not isinstance(shots, list) or not shots:
        errors.append("at least one shot is required")
        shots = []
    seen_ids: set[str] = set()
    previous_end: float | None = None
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            errors.append(f"shots[{index}] must be an object")
            continue
        shot_id = shot.get("shot_id")
        if not isinstance(shot_id, str) or not shot_id:
            errors.append(f"shots[{index}].shot_id is required")
        elif shot_id in seen_ids:
            errors.append(f"duplicate shot_id: {shot_id}")
        else:
            seen_ids.add(shot_id)
        try:
            start, end = float(shot["start_seconds"]), float(shot["end_seconds"])
            if start < 0 or end <= start:
                errors.append(f"{shot_id or index} has invalid time interval")
            if previous_end is not None and abs(start - previous_end) > 1e-6:
                errors.append(f"{shot_id or index} breaks contiguous shot timing")
            previous_end = end
        except (KeyError, TypeError, ValueError):
            errors.append(f"{shot_id or index} requires numeric start_seconds/end_seconds")
            continue
        frame_interval = shot.get("source_frame_interval")
        if not isinstance(frame_interval, dict):
            errors.append(f"{shot_id or index} requires source_frame_interval")
        else:
            try:
                frame_start = int(frame_interval["start_frame_no"])
                frame_end = int(frame_interval["end_frame_no"])
                if frame_start < 0 or frame_end <= frame_start:
                    errors.append(f"{shot_id or index} has invalid half-open frame interval")
                if frame_interval.get("semantics") != "[start_frame_no, end_frame_no)":
                    errors.append(f"{shot_id or index} frame interval semantics are not explicit")
            except (KeyError, TypeError, ValueError):
                errors.append(f"{shot_id or index} frame interval requires integer boundaries")
        if not isinstance(shot.get("evidence_refs"), list) or not shot["evidence_refs"]:
            errors.append(f"{shot_id or index} requires evidence_refs")
        if shot.get("semantic_status") == "not_yet_annotated":
            for field in ("visual_description", "camera_motion", "edit_intent"):
                if shot.get(field) is not None:
                    errors.append(f"{shot_id or index} has unreviewed {field} despite not_yet_annotated status")

    acceptance = blueprint.get("acceptance")
    if not isinstance(acceptance, dict):
        errors.append("acceptance object is required")
    elif acceptance.get("creative_blueprint_ready") is not False:
        errors.append("evidence-aligned draft must not claim creative_blueprint_ready")

    return errors


def require_valid_blueprint_draft(blueprint: dict[str, Any]) -> None:
    """Raise a readable ValueError when validation errors exist."""
    errors = validate_blueprint_draft(blueprint)
    if errors:
        raise ValueError("Invalid Blueprint draft: " + "; ".join(errors))

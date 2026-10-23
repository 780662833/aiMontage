"""Validate evidence-backed visual annotations before promoting a Blueprint."""
from __future__ import annotations

from typing import Any


_REQUIRED_ANNOTATION_FIELDS = (
    "visual_description",
    "subject",
    "action",
    "camera_motion",
    "composition",
    "lighting_and_color",
    "edit_intent",
)


def validate_visual_review(review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if review.get("schema_version") != "aimontage.visual_review_template.v1":
        errors.append("unsupported schema_version")
    source = review.get("source")
    if not isinstance(source, dict) or not source.get("sha256"):
        errors.append("source.sha256 is required")

    shots = review.get("shots")
    if not isinstance(shots, list) or not shots:
        errors.append("at least one shot is required")
        shots = []

    seen: set[str] = set()
    previous_end: float | None = None
    for i, shot in enumerate(shots):
        if not isinstance(shot, dict):
            errors.append(f"shots[{i}] must be an object")
            continue
        sid = shot.get("shot_id", f"shots[{i}]")
        if sid in seen:
            errors.append(f"duplicate shot_id: {sid}")
        seen.add(sid)
        try:
            start, end = float(shot["start_seconds"]), float(shot["end_seconds"])
            if start < 0 or end <= start:
                errors.append(f"{sid} has invalid time interval")
            if previous_end is not None and abs(start - previous_end) > 1e-6:
                errors.append(f"{sid} breaks contiguous shot timing")
            previous_end = end
            interval = shot["source_frame_interval"]
            frame_start, frame_end = int(interval["start_frame_no"]), int(interval["end_frame_no"])
            if frame_start < 0 or frame_end <= frame_start:
                errors.append(f"{sid} has invalid half-open source frame interval")
            if interval.get("semantics") != "[start_frame_no, end_frame_no)":
                errors.append(f"{sid} has no explicit half-open frame semantics")
        except (KeyError, TypeError, ValueError):
            errors.append(f"{sid} requires valid time and frame intervals")
            continue

        frames = shot.get("evidence_frames")
        if not isinstance(frames, list) or not frames:
            errors.append(f"{sid} requires linked evidence frames")
            frames = []
        evidence_nos: set[int] = set()
        for j, frame in enumerate(frames):
            try:
                no = int(frame["frame_no"])
                if no < frame_start or no >= frame_end:
                    errors.append(f"{sid} evidence frame {no} lies outside its shot interval")
                if no in evidence_nos:
                    errors.append(f"{sid} duplicates evidence frame {no}")
                evidence_nos.add(no)
                if frame.get("association_status") != "aligned":
                    errors.append(f"{sid} evidence frame {no} is not aligned")
                if not frame.get("image_sha256") or not frame.get("relative_path"):
                    errors.append(f"{sid} evidence frame {no} lacks image hash or relative path")
                if source and frame.get("source_sha256") != source.get("sha256"):
                    errors.append(f"{sid} evidence frame {no} source hash mismatch")
            except (KeyError, TypeError, ValueError):
                errors.append(f"{sid} evidence frame {j} has invalid provenance fields")

        annotation = shot.get("annotation")
        if not isinstance(annotation, dict):
            errors.append(f"{sid} annotation object is required")
            continue
        status = annotation.get("review_status")
        if status not in {"not_reviewed", "partially_reviewed", "reviewed", "needs_more_evidence"}:
            errors.append(f"{sid} has unsupported review_status")
        if status == "reviewed":
            for field in _REQUIRED_ANNOTATION_FIELDS:
                value = annotation.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{sid} reviewed annotation requires {field}")
            confidence = annotation.get("confidence")
            if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                errors.append(f"{sid} reviewed annotation confidence must be between 0 and 1")
            if not annotation.get("evidence_frame_nos"):
                errors.append(f"{sid} reviewed annotation must cite evidence_frame_nos")
            else:
                for no in annotation["evidence_frame_nos"]:
                    if no not in evidence_nos:
                        errors.append(f"{sid} annotation cites unlinked evidence frame {no}")

    return errors


def visual_review_completion(review: dict[str, Any]) -> dict[str, Any]:
    errors = validate_visual_review(review)
    shots = review.get("shots", []) if isinstance(review.get("shots"), list) else []
    reviewed = sum(
        1 for shot in shots
        if isinstance(shot, dict)
        and isinstance(shot.get("annotation"), dict)
        and shot["annotation"].get("review_status") == "reviewed"
    )
    return {
        "valid": not errors,
        "shot_count": len(shots),
        "reviewed_shot_count": reviewed,
        "review_complete": bool(shots) and reviewed == len(shots) and not errors,
        "errors": errors,
        "production_ready": False,
        "note": "Semantic annotation completion alone does not validate edit intent or output specification.",
    }

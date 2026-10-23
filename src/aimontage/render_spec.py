"""Validation helpers for a target social-video render specification."""
from __future__ import annotations

from typing import Any


def validate_render_spec(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if spec.get("schema_version") != "aimontage.render_spec.v1":
        errors.append("unsupported render spec schema_version")
    output = spec.get("output")
    if not isinstance(output, dict):
        errors.append("output object is required")
        output = {}
    try:
        width, height = int(output["width"]), int(output["height"])
        if width <= 0 or height <= 0:
            errors.append("output width and height must be positive")
        target = output.get("aspect_ratio")
        if target != "9:16":
            errors.append("output.aspect_ratio must be 9:16 for this profile")
        elif width > 0 and height > 0 and abs(width / height - 9 / 16) > 0.002:
            errors.append("output dimensions do not match declared 9:16 aspect ratio")
    except (KeyError, TypeError, ValueError):
        errors.append("output width and height must be integers")
    try:
        fps = float(output["fps"])
        if fps <= 0:
            errors.append("output.fps must be positive")
    except (KeyError, TypeError, ValueError):
        errors.append("output.fps is required and must be numeric")
    if output.get("container") != "mp4":
        errors.append("output.container must be mp4")
    if output.get("video_codec") not in {"h264", "hevc"}:
        errors.append("output.video_codec must be h264 or hevc")
    if output.get("audio_codec") not in {"aac", "none"}:
        errors.append("output.audio_codec must be aac or none")
    if output.get("duration_policy") not in {"preserve_source", "fixed_target"}:
        errors.append("output.duration_policy must be preserve_source or fixed_target")
    if output.get("duration_policy") == "fixed_target":
        try:
            if float(output["target_duration_seconds"]) <= 0:
                errors.append("target_duration_seconds must be positive")
        except (KeyError, TypeError, ValueError):
            errors.append("fixed_target requires target_duration_seconds")

    safe = spec.get("safe_area")
    if not isinstance(safe, dict):
        errors.append("safe_area object is required")
    else:
        try:
            top, right, bottom, left = (float(safe[k]) for k in ("top_pct", "right_pct", "bottom_pct", "left_pct"))
            if any(v < 0 or v >= 50 for v in (top, right, bottom, left)):
                errors.append("safe-area percentages must be in [0, 50)")
            if top + bottom >= 100 or left + right >= 100:
                errors.append("safe-area margins leave no usable canvas")
        except (KeyError, TypeError, ValueError):
            errors.append("safe_area requires numeric top/right/bottom/left percentages")

    if spec.get("subtitles", {}).get("burn_in") not in {True, False}:
        errors.append("subtitles.burn_in must be explicit")
    return errors

"""Post-render technical QA for deterministic profile-conformance renders."""
from __future__ import annotations

from typing import Any


def validate_render_report(report: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    output = report.get("output", {})
    probe = output.get("probe", {})
    streams = probe.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    expected = spec["output"]
    if video is None:
        errors.append("output video stream missing")
    else:
        if int(video.get("width", 0)) != int(expected["width"]):
            errors.append("output width does not match render spec")
        if int(video.get("height", 0)) != int(expected["height"]):
            errors.append("output height does not match render spec")
        rate = video.get("avg_frame_rate") or video.get("r_frame_rate")
        try:
            numerator, denominator = rate.split("/", 1)
            actual_fps = float(numerator) / float(denominator)
            if abs(actual_fps - float(expected["fps"])) > 0.02:
                errors.append(f"output fps {actual_fps:g} does not match target {expected['fps']}")
        except (AttributeError, ValueError, ZeroDivisionError):
            errors.append("output frame rate is unavailable")
    if expected.get("audio_codec") != "none" and report.get("source", {}).get("probe", {}).get("streams"):
        source_has_audio = any(s.get("codec_type") == "audio" for s in report["source"]["probe"]["streams"])
        if source_has_audio and audio is None:
            errors.append("source audio exists but output audio is missing")
    try:
        source_duration = float(report["source"]["duration_seconds"])
        output_duration = float(probe["format"]["duration"])
        tolerance = max(0.1, 2 / float(expected["fps"]))
        if abs(source_duration - output_duration) > tolerance:
            errors.append(f"duration drift exceeds tolerance ({source_duration:.3f}s vs {output_duration:.3f}s)")
    except (KeyError, TypeError, ValueError):
        errors.append("source/output duration is unavailable")
    return {
        "schema_version": "aimontage.render_qa.v1",
        "status": "PASS" if not errors else "FAIL",
        "automated_checks": {
            "dimensions": "PASS" if video and not any("width" in e or "height" in e for e in errors) else "FAIL",
            "frame_rate": "PASS" if video and not any("fps" in e or "frame rate" in e for e in errors) else "FAIL",
            "audio_presence": "PASS" if not any("audio" in e for e in errors) else "FAIL",
            "duration": "PASS" if not any("duration" in e for e in errors) else "FAIL",
        },
        "manual_review_required": True,
        "manual_review_items": [
            "Check subject integrity, color, scaling artifacts, and composition.",
            "Check for unintended black frames/freezes and audio glitches.",
            "Confirm shot pacing and creative intent; this transcode does not reconstruct actions.",
        ],
        "errors": errors,
    }

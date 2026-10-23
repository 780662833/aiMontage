"""Deterministic FFmpeg transcode for a reviewed reconstruction candidate.

This is a profile-conformance render, not a claim that source footage has been
creatively reconstructed from the Blueprint.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


class RenderError(ValueError):
    """Raised when input evidence or render output violates the contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_json(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RenderError(f"command did not return JSON: {command[0]}") from exc


def probe_media(path: Path) -> dict[str, Any]:
    return _run_json([
        "ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)
    ])


def _ratio(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    try:
        numerator, denominator = value.split("/", 1)
        return float(numerator) / float(denominator) if float(denominator) else None
    except (ValueError, ZeroDivisionError):
        return None


def render_source_preserving(
    source: Path, output: Path, candidate: dict[str, Any], render_spec: dict[str, Any]
) -> dict[str, Any]:
    """Re-encode source to target profile, enforcing source SHA and no-crop policy."""
    from aimontage.render_spec import validate_render_spec

    if not source.is_file():
        raise RenderError(f"source does not exist: {source}")
    if validate_render_spec(render_spec):
        raise RenderError("invalid render spec: " + "; ".join(validate_render_spec(render_spec)))
    source_hash = sha256_file(source)
    if candidate.get("source", {}).get("sha256") != source_hash:
        raise RenderError("source SHA-256 does not match reconstruction candidate")
    if candidate.get("acceptance", {}).get("visual_review_complete") is not True:
        raise RenderError("visual review is not complete")
    if candidate.get("acceptance", {}).get("render_ready") is True:
        # Current MVP deliberately remains conservative; render is profile smoke test.
        pass

    source_probe = probe_media(source)
    streams = source_probe.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video:
        raise RenderError("source has no video stream")
    width, height = int(video["width"]), int(video["height"])
    duration = float(source_probe.get("format", {}).get("duration", 0))
    if duration <= 0:
        raise RenderError("source duration is missing or non-positive")

    out = render_spec["output"]
    target_w, target_h = int(out["width"]), int(out["height"])
    source_ratio = width / height
    target_ratio = target_w / target_h
    if abs(source_ratio - target_ratio) > 0.002:
        raise RenderError(
            "source aspect ratio differs from target; this MVP refuses implicit crop/pad. "
            "Create a reviewed framing plan before rendering."
        )
    fps = float(out["fps"])
    video_codec = {"h264": "libx264", "hevc": "libx265"}[out["video_codec"]]
    command = [
        "ffmpeg", "-hide_banner", "-y", "-v", "error", "-i", str(source),
        "-map", "0:v:0", "-map", "0:a:0?", "-vf",
        f"scale={target_w}:{target_h}:flags=lanczos,fps={fps:g}",
        "-c:v", video_codec, "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18",
    ]
    if out["audio_codec"] == "none":
        command += ["-an"]
    else:
        command += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    command += ["-t", f"{duration:.6f}", "-movflags", "+faststart", str(output)]
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RenderError(f"ffmpeg failed ({result.returncode}): {result.stderr[-3000:]}")
    output_probe = probe_media(output)
    out_video = next((s for s in output_probe.get("streams", []) if s.get("codec_type") == "video"), None)
    if not out_video:
        raise RenderError("render produced no video stream")
    report = {
        "schema_version": "aimontage.render_report.v1",
        "render_mode": "source_preserving_vertical_transcode",
        "creative_reconstruction_claimed": False,
        "source": {"path": source.as_posix(), "sha256": source_hash, "width": width,
                   "height": height, "duration_seconds": duration, "probe": source_probe},
        "output": {"path": output.as_posix(), "sha256": sha256_file(output),
                   "probe": output_probe},
        "render_spec": render_spec,
        "decision": {"framing": "uniform_scale_no_crop", "source_aspect_ratio": source_ratio,
                     "target_aspect_ratio": target_ratio, "fps": fps},
        "command": command,
    }
    return report

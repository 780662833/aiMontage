"""Render an explicitly approved shot edit plan by deterministic FFmpeg assembly."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from aimontage.ffmpeg_renderer import RenderError, probe_media, sha256_file


def validate_approved_edit_plan(source: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate approval, source identity, and conservative cut-only MVP constraints."""
    if not source.is_file():
        raise RenderError(f"source does not exist: {source}")
    if plan.get("schema_version") != "aimontage.shot_edit_plan.v1":
        raise RenderError("unsupported edit plan schema")
    acceptance = plan.get("acceptance", {})
    if acceptance.get("editor_approved") is not True or acceptance.get("render_approved") is not True:
        raise RenderError("edit plan is not explicitly approved by an editor")
    if not str(acceptance.get("reviewer", "")).strip():
        raise RenderError("approved edit plan must record acceptance.reviewer")
    source_hash = sha256_file(source)
    if plan.get("source", {}).get("sha256") != source_hash:
        raise RenderError("source SHA-256 does not match edit plan")
    shots = plan.get("shots")
    if not isinstance(shots, list) or not shots:
        raise RenderError("edit plan contains no shots")
    fps = float(plan.get("output", {}).get("fps", 0))
    if fps <= 0:
        raise RenderError("edit plan output fps must be positive")
    validated = []
    last_order = -1
    for index, shot in enumerate(shots):
        if shot.get("review_status") != "APPROVED":
            raise RenderError(f"{shot.get('shot_id', index)} is not individually approved")
        order = int(shot.get("order", index))
        if order <= last_order:
            raise RenderError("shot order must be strictly increasing")
        last_order = order
        src = shot.get("source", {})
        start, end = float(src.get("start_seconds", -1)), float(src.get("end_seconds", -1))
        start_frame = int(src.get("start_frame_no", -1))
        end_frame = int(src.get("end_frame_no_exclusive", -1))
        if start < 0 or end <= start or start_frame < 0 or end_frame <= start_frame:
            raise RenderError(f"{shot.get('shot_id', index)} has invalid source interval")
        if shot.get("transition", {}).get("type") != "cut" or int(shot.get("transition", {}).get("duration_frames", 0)) != 0:
            raise RenderError("MVP renderer supports approved hard cuts only")
        if shot.get("reframe", {}).get("crop") is not None or shot.get("reframe", {}).get("mode") != "contain":
            raise RenderError("MVP renderer refuses unimplemented crop/reframe instructions")
        if shot.get("subtitles", {}).get("enabled") is True:
            raise RenderError("MVP renderer does not burn subtitles; disable until a subtitle renderer is implemented")
        if abs((end - start) * fps - (int(shot.get("target", {}).get("end_frame_no_exclusive", 0)) - int(shot.get("target", {}).get("start_frame_no", 0)))) > 1.1:
            raise RenderError(f"{shot.get('shot_id', index)} target frames conflict with source duration")
        validated.append(shot)
    return validated


def render_approved_edit_plan(source: Path, output: Path, plan: dict[str, Any]) -> dict[str, Any]:
    """Cut matching source intervals from video/audio and concatenate them in plan order."""
    shots = validate_approved_edit_plan(source, plan)
    source_probe = probe_media(source)
    streams = source_probe.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise RenderError("source has no video stream")
    audio_exists = any(s.get("codec_type") == "audio" for s in streams)
    source_duration = float(source_probe.get("format", {}).get("duration", 0))
    fps = float(plan["output"]["fps"])
    width, height = int(plan["output"]["width"]), int(plan["output"]["height"])
    if width <= 0 or height <= 0 or width % 2 or height % 2:
        raise RenderError("output dimensions must be positive even numbers")
    if abs((width / height) - (int(video["width"]) / int(video["height"]))) > 0.002:
        raise RenderError("MVP renderer refuses aspect-ratio conversion without an approved background/reframe implementation")
    filters = []
    concat_labels = []
    duration_total = 0.0
    include_audio = audio_exists and plan["output"].get("audio_codec", "aac") != "none"
    for i, shot in enumerate(shots):
        start, end = float(shot["source"]["start_seconds"]), float(shot["source"]["end_seconds"])
        if end > source_duration + 0.05:
            raise RenderError(f"{shot['shot_id']} source interval exceeds media duration")
        duration_total += end - start
        video_label = f"v{i}"
        filters.append(
            f"[0:v:0]trim=start={start:.6f}:end={end:.6f},setpts=PTS-STARTPTS,"
            f"fps={fps:g},scale={width}:{height}:flags=lanczos,"
            f"setsar=1,format=yuv420p[{video_label}]"
        )
        concat_labels.append(f"[{video_label}]")
        if include_audio:
            audio_label = f"a{i}"
            filters.append(
                f"[0:a:0]atrim=start={start:.6f}:end={end:.6f},"
                f"asetpts=PTS-STARTPTS,aresample=48000[{audio_label}]"
            )
            concat_labels.append(f"[{audio_label}]")
    if include_audio:
        filters.append("".join(concat_labels) + f"concat=n={len(shots)}:v=1:a=1[vout][aout]")
    else:
        filters.append("".join(concat_labels) + f"concat=n={len(shots)}:v=1:a=0[vout]")
    out = plan["output"]
    codec = {"h264": "libx264", "hevc": "libx265"}.get(out.get("video_codec", "h264"))
    if not codec:
        raise RenderError("unsupported video codec in edit plan")
    command = ["ffmpeg", "-hide_banner", "-y", "-v", "error", "-i", str(source),
               "-filter_complex", ";".join(filters), "-map", "[vout]"]
    if include_audio:
        command += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    else:
        command += ["-an"]
    command += ["-c:v", codec, "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18",
                "-r", f"{fps:g}", "-movflags", "+faststart", "-t", f"{duration_total:.6f}", str(output)]
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode:
        raise RenderError(f"ffmpeg edit-plan render failed ({result.returncode}): {result.stderr[-3000:]}")
    output_probe = probe_media(output)
    if not any(s.get("codec_type") == "video" for s in output_probe.get("streams", [])):
        raise RenderError("render produced no video stream")
    return {
        "schema_version": "aimontage.edit_plan_render_report.v1",
        "render_mode": "approved_shot_assembly_hard_cuts",
        "creative_reconstruction_claimed": False,
        "source": {"path": source.as_posix(), "sha256": sha256_file(source),
                   "duration_seconds": source_duration, "probe": source_probe},
        "edit_plan": {"schema_version": plan["schema_version"], "sha256": hashlib.sha256(
            json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
            "reviewer": plan["acceptance"]["reviewer"]},
        "output": {"path": output.as_posix(), "sha256": sha256_file(output), "duration_seconds": duration_total,
                   "probe": output_probe},
        "shots": [{"shot_id": s.get("shot_id"), "order": s.get("order"),
                   "source_start_seconds": s["source"]["start_seconds"],
                   "source_end_seconds": s["source"]["end_seconds"]} for s in shots],
        "audio_policy": ("source_audio_cut_and_concatenated_per_shot" if include_audio else "audio_disabled_by_plan" if audio_exists else "no_source_audio"),
        "command": command,
        "manual_review_required": True,
    }

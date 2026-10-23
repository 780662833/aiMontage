"""FFmpeg-based content anomaly candidates; detections require human review."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

_NUMBER = r"(-?\d+(?:\.\d+)?)"


def parse_detection_log(stderr: str) -> dict[str, list[dict[str, float]]]:
    """Parse blackdetect, freezedetect and silencedetect events from FFmpeg stderr."""
    events: dict[str, list[dict[str, float]]] = {
        "black": [], "freeze": [], "silence": []
    }
    patterns = {
        "black_start": re.compile(r"black_start:" + _NUMBER),
        "black_end": re.compile(r"black_end:" + _NUMBER),
        "freeze_start": re.compile(r"freeze_start:" + _NUMBER),
        "freeze_end": re.compile(r"freeze_end:" + _NUMBER),
        "freeze_duration": re.compile(r"freeze_duration:" + _NUMBER),
        "silence_start": re.compile(r"silence_start:" + _NUMBER),
        "silence_end": re.compile(r"silence_end:" + _NUMBER),
        "silence_duration": re.compile(r"silence_duration:" + _NUMBER),
    }
    open_start: dict[str, float | None] = {"black": None, "freeze": None, "silence": None}
    for line in stderr.splitlines():
        for name, pattern in patterns.items():
            match = pattern.search(line)
            if not match:
                continue
            value = float(match.group(1))
            if name.endswith("_start"):
                kind = name.removesuffix("_start")
                open_start[kind] = value
                continue
            if name in ("black_end", "freeze_end", "silence_end"):
                kind = name.removesuffix("_end")
                start = open_start[kind]
                if start is not None:
                    events[kind].append({"start": start, "end": value, "duration": max(0.0, value - start)})
                    open_start[kind] = None
                continue
            if name in ("freeze_duration", "silence_duration"):
                kind = name.removesuffix("_duration")
                start = open_start[kind]
                if start is not None:
                    events[kind].append({"start": start, "end": start + value, "duration": value})
                    open_start[kind] = None
                break
    # An interval extending to EOF may have a start but no closing event.
    for kind, start in open_start.items():
        if start is not None:
            events[kind].append({"start": start, "end": start, "duration": 0.0, "open_ended": 1.0})
    return events


def analyze_content_anomalies(
    video: str | Path,
    *,
    ffmpeg: str = "ffmpeg",
    black_min_duration: float = 0.10,
    freeze_min_duration: float = 0.50,
    silence_min_duration: float = 0.50,
) -> dict[str, Any]:
    """Run content filters and report detections as review candidates, never automatic failures."""
    path = Path(video)
    if not path.is_file():
        raise FileNotFoundError(f"video does not exist: {path}")
    vf = (
        f"blackdetect=d={black_min_duration}:pix_th=0.10,"
        f"freezedetect=n=-60dB:d={freeze_min_duration}"
    )
    af = f"silencedetect=n=-50dB:d={silence_min_duration}"
    command = [
        ffmpeg, "-hide_banner", "-nostats", "-i", str(path),
        "-vf", vf, "-af", af, "-f", "null", "-"
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg content QA failed with exit code {result.returncode}: "
            f"{result.stderr[-2000:]}"
        )
    detections = parse_detection_log(result.stderr)
    return {
        "schema_version": "aimontage.content_qa.v1",
        "status": "REVIEW_REQUIRED",
        "source_video": path.name,
        "filters": {
            "blackdetect": {"minimum_duration_seconds": black_min_duration, "pixel_threshold": 0.10},
            "freezedetect": {"minimum_duration_seconds": freeze_min_duration, "noise_db": -60},
            "silencedetect": {"minimum_duration_seconds": silence_min_duration, "noise_db": -50},
        },
        "detections": detections,
        "detection_counts": {key: len(value) for key, value in detections.items()},
        "interpretation": (
            "Detections are candidates for human review, not automatic defects. "
            "Intentional fades, dark scenes, still shots, and quiet musical passages may trigger filters."
        ),
        "manual_review_required": True,
        "command": command,
    }

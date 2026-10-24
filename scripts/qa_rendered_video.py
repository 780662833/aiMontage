"""Technical QA for a rendered short; content approval remains a separate human gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}\n{result.stderr[-3000:]}")
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _last_json(text: str) -> dict[str, Any]:
    matches = list(re.finditer(r"\{[^{}]*\}", text, flags=re.DOTALL))
    for match in reversed(matches):
        try:
            value = json.loads(match.group(0))
            if isinstance(value, dict) and "input_i" in value:
                return value
        except json.JSONDecodeError:
            continue
    raise ValueError("Could not parse FFmpeg loudnorm measurement JSON")


def run_qa(
    video: Path,
    expected_duration: float,
    *,
    ffprobe: str = "ffprobe",
    ffmpeg: str = "ffmpeg",
    duration_tolerance: float = 0.25,
    expected_width: int = 1080,
    expected_height: int = 1920,
    expect_subtitle_stream: bool = False,
) -> dict[str, Any]:
    video = video.resolve()
    if not video.is_file():
        raise FileNotFoundError(f"Rendered video not found: {video}")
    probe = _run([
        ffprobe, "-v", "error", "-show_entries",
        "format=duration,format_name:stream=index,codec_type,codec_name,width,height,sample_rate,channels",
        "-of", "json", str(video),
    ])
    media = json.loads(probe.stdout)
    streams = media.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
    duration = float(media.get("format", {}).get("duration", 0.0) or 0.0)
    v = video_streams[0] if video_streams else {}
    loudness_result = _run([
        ffmpeg, "-hide_banner", "-i", str(video), "-vn",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-",
    ])
    loud = _last_json(loudness_result.stderr)
    volume_result = _run([
        ffmpeg, "-hide_banner", "-i", str(video), "-vn",
        "-af", "volumedetect", "-f", "null", "-",
    ])
    max_match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", volume_result.stderr)
    max_volume = float(max_match.group(1)) if max_match else None
    input_i = float(loud["input_i"])
    input_tp = float(loud["input_tp"])
    checks = {
        "video_stream_present": bool(video_streams),
        "resolution": bool(v) and v.get("width") == expected_width and v.get("height") == expected_height,
        "duration": abs(duration - expected_duration) <= duration_tolerance,
        "h264_codec": bool(v) and v.get("codec_name") == "h264",
        "audio_stream_present": bool(audio_streams),
        "audio_integrated_loudness": -18.0 <= input_i <= -14.0,
        "audio_true_peak": input_tp <= -1.5,
        "audio_sample_peak_headroom": max_volume is not None and max_volume < -0.1,
        "subtitle_stream_policy": bool(subtitle_streams) == expect_subtitle_stream,
    }
    technical_pass = all(checks.values())
    return {
        "schema_version": "aimontage.render_qa.v1",
        "video": str(video),
        "video_sha256": _sha256(video),
        "media": {
            "duration_seconds": duration,
            "format_name": media.get("format", {}).get("format_name"),
            "video": v,
            "audio": audio_streams,
            "subtitle_stream_count": len(subtitle_streams),
        },
        "audio_measurements": {
            "integrated_loudness_lufs": input_i,
            "true_peak_dbtp": input_tp,
            "max_sample_volume_dbfs": max_volume,
            "loudnorm_measurement": loud,
        },
        "checks": checks,
        "technical_pass": technical_pass,
        "manual_review": {
            "shot_continuity_passed": False,
            "story_fidelity_passed": False,
            "subtitle_script_consistency_passed": False,
            "human_review_required": True,
        },
        "ready_for_delivery": False,
        "blocking_gates": [
            key for key, passed in checks.items() if not passed
        ] + [
            "Human must review shot continuity and story fidelity",
            "Human must confirm subtitle/script policy; this source was reviewed as music-only",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--expected-duration", required=True, type=float)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--duration-tolerance", type=float, default=0.25)
    parser.add_argument("--expect-subtitle-stream", action="store_true")
    args = parser.parse_args()
    report = run_qa(
        args.video, args.expected_duration, ffprobe=args.ffprobe, ffmpeg=args.ffmpeg,
        duration_tolerance=args.duration_tolerance,
        expect_subtitle_stream=args.expect_subtitle_stream,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema_version": report["schema_version"],
        "technical_pass": report["technical_pass"],
        "ready_for_delivery": report["ready_for_delivery"],
        "blocking_gates": report["blocking_gates"],
        "out": str(args.out),
    }, ensure_ascii=False, indent=2))
    return 0 if report["technical_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

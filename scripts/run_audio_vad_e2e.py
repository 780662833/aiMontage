"""Independent WebRTC VAD pass over a video file's audio stream.

This is an activity detector, not a transcript or proof that detected activity is speech.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import webrtcvad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, default=Path("a.mp4"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/real_video_e2e/audio_vad"))
    parser.add_argument("--mode", type=int, choices=[0, 1, 2, 3], default=2)
    parser.add_argument("--frame-ms", type=int, choices=[10, 20, 30], default=20)
    args = parser.parse_args()

    video = args.video.resolve()
    if not video.is_file():
        raise FileNotFoundError(f"Video not found: {video}")
    args.out.mkdir(parents=True, exist_ok=True)

    extracted = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
         "-f", "s16le", "pipe:1"],
        check=True, capture_output=True, timeout=120,
    ).stdout
    sample_rate = 16000
    frame_bytes = int(sample_rate * args.frame_ms / 1000) * 2
    complete_bytes = len(extracted) - (len(extracted) % frame_bytes)
    frames = [extracted[i:i + frame_bytes] for i in range(0, complete_bytes, frame_bytes)]
    detector = webrtcvad.Vad(args.mode)
    flags = [detector.is_speech(frame, sample_rate) for frame in frames]

    intervals = []
    start = None
    for index, is_speech in enumerate(flags + [False]):
        if is_speech and start is None:
            start = index
        elif not is_speech and start is not None:
            intervals.append({
                "start_seconds": round(start * args.frame_ms / 1000, 3),
                "end_seconds": round(index * args.frame_ms / 1000, 3),
                "duration_seconds": round((index - start) * args.frame_ms / 1000, 3),
            })
            start = None

    total_seconds = len(frames) * args.frame_ms / 1000
    speech_seconds = sum(item["duration_seconds"] for item in intervals)
    result = {
        "schema_version": "aimontage.audio_vad_e2e.v1",
        "video": video.name,
        "detector": "WebRTC VAD",
        "mode": args.mode,
        "frame_ms": args.frame_ms,
        "sample_rate_hz": sample_rate,
        "analyzed_duration_seconds": round(total_seconds, 3),
        "speech_activity_detected": bool(intervals),
        "speech_activity_seconds": round(speech_seconds, 3),
        "speech_activity_ratio": round(speech_seconds / total_seconds, 4) if total_seconds else 0.0,
        "activity_intervals": intervals,
        "interpretation_note": "VAD detects speech-like acoustic activity; it does not identify words or prove intelligible speech.",
    }
    out_path = args.out / "audio_vad_evidence.json"
    out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "result": result, "evidence_bundle": out_path.as_posix()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

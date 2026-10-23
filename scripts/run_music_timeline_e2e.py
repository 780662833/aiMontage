"""Extract deterministic RMS/silence/energy-onset evidence from a video's audio stream."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from aimontage.music_timeline import analyze_pcm_s16le


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, default=Path("a.mp4"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/real_video_e2e/music_timeline"))
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--window-ms", type=int, default=100)
    parser.add_argument("--silence-threshold-dbfs", type=float, default=-45.0)
    parser.add_argument("--onset-threshold-db", type=float, default=8.0)
    parser.add_argument("--onset-refractory-ms", type=int, default=180)
    args = parser.parse_args()

    video = args.video.resolve()
    if not video.is_file():
        raise FileNotFoundError(f"Video not found: {video}")
    if args.sample_rate not in {8000, 16000, 22050, 44100, 48000}:
        raise ValueError("sample-rate must be one of 8000, 16000, 22050, 44100, 48000")
    args.out.mkdir(parents=True, exist_ok=True)

    probe = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=index,codec_name,sample_rate,channels,duration",
        "-of", "json", str(video),
    ], check=True, capture_output=True, text=True, timeout=60)
    streams = json.loads(probe.stdout).get("streams", [])
    if not streams:
        raise RuntimeError("Video has no audio stream; music timeline cannot be generated")

    extracted = subprocess.run([
        "ffmpeg", "-v", "error", "-i", str(video), "-map", "0:a:0",
        "-vn", "-ac", "1", "-ar", str(args.sample_rate), "-f", "s16le", "pipe:1",
    ], check=True, capture_output=True, timeout=120).stdout
    result = analyze_pcm_s16le(
        extracted, sample_rate_hz=args.sample_rate, channels=1, window_ms=args.window_ms,
        silence_threshold_dbfs=args.silence_threshold_dbfs,
        onset_threshold_db=args.onset_threshold_db,
        onset_refractory_ms=args.onset_refractory_ms,
    )
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    bundle = {
        **result,
        "source": {
            "file_name": video.name,
            "sha256": digest,
            "audio_stream": streams[0],
            "decoded_pcm_sha256": hashlib.sha256(extracted).hexdigest(),
        },
    }
    output_path = args.out / "music_timeline_evidence.json"
    output_path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "passed",
        "source_sha256": digest,
        "duration_seconds": result["measurement"]["duration_seconds"],
        "window_count": result["summary"]["window_count"],
        "silence_interval_count": len(result["silence_intervals"]),
        "candidate_energy_onset_count": len(result["candidate_onsets"]),
        "evidence_bundle": output_path.as_posix(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

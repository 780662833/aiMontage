"""Create a deterministic dense frame-evidence bundle at a configurable interval.

This sampler increases temporal coverage; it does not infer motion or prove that every
action transition has been captured. Samples are linked back to decoded source PTS.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from aimontage.evidence import sha256_file, write_json_atomic
from aimontage.upstream import run_upstream_tool
from run_real_video_e2e import (
    UPSTREAM_REVISION,
    TOOL_VERSION,
    build_normalized_sampled_frames,
    ffprobe_video_frames,
    require_success,
)
from aimontage.timestamp_audit import audit_frame_rows


def run(video: Path, out: Path, repo_root: Path, interval_seconds: float = 0.25) -> dict[str, Any]:
    video, out, repo_root = video.resolve(), out.resolve(), repo_root.resolve()
    if not video.is_file():
        raise FileNotFoundError(f"Video not found: {video}")
    if interval_seconds <= 0 or interval_seconds > 2:
        raise ValueError("interval_seconds must be > 0 and <= 2")
    out.mkdir(parents=True, exist_ok=True)

    sha = sha256_file(video)
    frame_rows = ffprobe_video_frames(video)
    if not frame_rows or any(row["source_pts_time"] is None for row in frame_rows):
        raise RuntimeError("source frame PTS are missing; dense evidence cannot be linked safely")
    audited = audit_frame_rows(frame_rows)
    bad = [row for row in audited if row["audit"]["status"] != "aligned"]
    if bad:
        raise RuntimeError(f"source PTS audit failed for {len(bad)} decoded frames")
    pts = [float(row["source_pts_time"]) for row in audited]

    frames_dir = out / "frames"
    raw = require_success("frame_sampler", run_upstream_tool(
        "frame_sampler",
        {"input_path": str(video), "strategy": "interval", "interval_seconds": interval_seconds,
         "output_dir": str(frames_dir), "format": "jpg", "quality": 2},
        repo_root=repo_root,
    ))
    samples = build_normalized_sampled_frames(raw, pts, sha, out)
    if not samples:
        raise RuntimeError("dense sampler produced no frame samples")

    payload = {
        "schema_version": "aimontage.dense_frame_evidence.v1",
        "source": {"path": video.as_posix(), "sha256": sha, "decoded_frame_count": len(pts)},
        "sampling": {
            "strategy": "uniform_interval",
            "interval_seconds": interval_seconds,
            "purpose": "increase temporal coverage for human/action review",
            "motion_inference": False,
            "limitation": "uniform dense samples can still miss brief actions between samples",
        },
        "upstream": {"repository": "https://github.com/calesthio/OpenMontage",
                     "revision": UPSTREAM_REVISION, "tool_version": TOOL_VERSION,
                     "raw_result": raw},
        "sample_count": len(samples),
        "samples": samples,
    }
    write_json_atomic(out / "dense_frame_evidence.json", payload)
    return {"schema_version": payload["schema_version"], "source_sha256": sha,
            "sample_count": len(samples), "interval_seconds": interval_seconds,
            "output": (out / "dense_frame_evidence.json").as_posix()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--interval-seconds", type=float, default=0.25)
    parser.add_argument("--repo-root", type=Path, default=Path("vendor/OpenMontage"))
    args = parser.parse_args()
    print(json.dumps(run(args.video, args.out, args.repo_root, args.interval_seconds),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

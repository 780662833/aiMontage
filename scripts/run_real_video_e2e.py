"""Run deterministic OpenMontage analysis tools on the checked-in a.mp4 fixture.

This intentionally excludes YouTube caption fetching (requires a URL/network) and
Whisper transcription (model download/compute); those have separate opt-in checks.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from aimontage.evidence import make_evidence_record, sha256_file, write_json_atomic
from aimontage.timestamp_audit import audit_frame_rows
from aimontage.upstream import run_upstream_tool


UPSTREAM_REVISION = "c8066452325cb57c8fc1ba8c2a71b6e8842e6b65"
TOOL_VERSION = "0.1.0+openmontage.c8066452"


def ffprobe_video_frames(video: Path) -> list[dict[str, Any]]:
    command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp_time,pkt_pts_time",
        "-of", "json", str(video),
    ]
    proc = subprocess.run(command, check=True, capture_output=True, text=True, timeout=120)
    payload = json.loads(proc.stdout)
    rows = []
    for index, frame in enumerate(payload.get("frames", [])):
        raw_pts = frame.get("best_effort_timestamp_time")
        if raw_pts is None:
            raw_pts = frame.get("pkt_pts_time")
        pts = float(raw_pts) if raw_pts is not None else None
        decoder_raw = frame.get("pkt_pts_time")
        rows.append({
            "frame_no": index,
            "source_pts_time": pts,
            "decoder_pts_time": float(decoder_raw) if decoder_raw is not None else None,
        })
    return rows


def require_success(name: str, result: dict[str, Any]) -> dict[str, Any]:
    if result.get("success") is not True:
        raise RuntimeError(f"{name} reported failure: {result.get('error') or result}")
    return result


def run(video: Path, output_dir: Path, repo_root: Path) -> dict[str, Any]:
    video = video.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not video.is_file():
        raise FileNotFoundError(f"Real-video fixture not found: {video}")

    media_sha256 = sha256_file(video)
    frames = ffprobe_video_frames(video)
    if not frames:
        raise RuntimeError("ffprobe returned no video frames")
    if any(row["source_pts_time"] is None for row in frames):
        raise RuntimeError("At least one decoded source frame has no usable timestamp")

    audited_frames = audit_frame_rows(frames)
    status_counts = Counter(row["audit"]["status"] for row in audited_frames)
    if status_counts.get("reorder", 0):
        raise RuntimeError(f"Source PTS decreases in fixture: {status_counts}")
    if status_counts.get("ambiguous-neighbor", 0):
        raise RuntimeError(f"Ambiguous source-frame timestamps in fixture: {status_counts}")

    raw_results: dict[str, dict[str, Any]] = {}
    raw_results["audio_probe"] = require_success(
        "audio_probe",
        run_upstream_tool("audio_probe", {"input_path": str(video)}, repo_root=repo_root),
    )
    raw_results["scene_detect"] = require_success(
        "scene_detect",
        run_upstream_tool(
            "scene_detect",
            {
                "input_path": str(video),
                "method": "content",
                "min_scene_length_seconds": 0.3,
                "output_path": str(output_dir / "scenes.json"),
            },
            repo_root=repo_root,
        ),
    )
    raw_results["frame_sampler"] = require_success(
        "frame_sampler",
        run_upstream_tool(
            "frame_sampler",
            {
                "input_path": str(video),
                "strategy": "interval",
                "interval_seconds": 1.0,
                "output_dir": str(output_dir / "frames"),
                "format": "jpg",
                "quality": 2,
            },
            repo_root=repo_root,
        ),
    )

    evidence_records = []
    for tool_name, raw_result in raw_results.items():
        evidence_records.append(make_evidence_record(
            evidence_id=f"real-a-mp4:{tool_name}",
            source_path=video,
            tool_name=f"OpenMontage.{tool_name}",
            tool_version=TOOL_VERSION,
            raw_result=raw_result,
        ))

    frame_audit_record = make_evidence_record(
        evidence_id="real-a-mp4:source-frame-pts-audit",
        source_path=video,
        tool_name="aiMontage.timestamp_audit",
        tool_version="0.1.0",
        raw_result={
            "frame_count": len(audited_frames),
            "status_counts": dict(status_counts),
            "first_source_pts_time": audited_frames[0]["source_pts_time"],
            "last_source_pts_time": audited_frames[-1]["source_pts_time"],
            "frames": audited_frames,
        },
    )
    evidence_records.append(frame_audit_record)

    bundle = {
        "schema_version": "aimontage.real_video_e2e.v1",
        "fixture": {
            "path": video.name,
            "size_bytes": video.stat().st_size,
            "sha256": media_sha256,
            "upstream_revision": UPSTREAM_REVISION,
        },
        "checks": {
            "source_frame_count": len(frames),
            "timestamp_audit_status_counts": dict(status_counts),
            "audio_probe_success": raw_results["audio_probe"]["success"],
            "scene_detect_success": raw_results["scene_detect"]["success"],
            "frame_sampler_success": raw_results["frame_sampler"]["success"],
            "sampled_image_count": len(list((output_dir / "frames").glob("*.jpg"))),
            "source_pts_is_authoritative": True,
            "decoder_pts_is_diagnostic_only": True,
        },
        "evidence": evidence_records,
    }
    if bundle["checks"]["sampled_image_count"] < 1:
        raise RuntimeError("frame_sampler succeeded but produced no JPG files")
    write_json_atomic(output_dir / "evidence_bundle.json", bundle)
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, default=Path("a.mp4"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/real_video_e2e"))
    parser.add_argument("--repo-root", type=Path, default=Path("vendor/OpenMontage"))
    args = parser.parse_args()
    bundle = run(args.video, args.out, args.repo_root)
    print(json.dumps({
        "status": "passed",
        "fixture": bundle["fixture"],
        "checks": {k: v for k, v in bundle["checks"].items()},
        "evidence_bundle": str((args.out / "evidence_bundle.json").as_posix()),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

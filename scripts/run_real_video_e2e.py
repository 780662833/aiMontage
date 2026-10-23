"""Run real-video analysis and build normalized, timestamp-linked evidence for a.mp4."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from bisect import bisect_left
from collections import Counter
from pathlib import Path
from typing import Any

from aimontage.evidence import make_evidence_record, sha256_file, write_json_atomic
from aimontage.timestamp_audit import audit_frame_rows
from aimontage.upstream import run_upstream_tool

UPSTREAM_REVISION = "c8066452325cb57c8fc1ba8c2a71b6e8842e6b65"
TOOL_VERSION = "0.1.1+openmontage.c8066452"


def ffprobe_video_frames(video: Path) -> list[dict[str, Any]]:
    command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp_time,pts_time,pkt_pts_time",
        "-of", "json", str(video),
    ]
    proc = subprocess.run(command, check=True, capture_output=True, text=True, timeout=120)
    payload = json.loads(proc.stdout)
    rows = []
    for index, frame in enumerate(payload.get("frames", [])):
        raw_pts = frame.get("best_effort_timestamp_time")
        if raw_pts is None:
            raw_pts = frame.get("pts_time") or frame.get("pkt_pts_time")
        diagnostic_raw = frame.get("pts_time") or frame.get("pkt_pts_time")
        rows.append({
            "frame_no": index,
            "source_pts_time": float(raw_pts) if raw_pts is not None else None,
            "decoder_pts_time": float(diagnostic_raw) if diagnostic_raw is not None else None,
        })
    return rows


def require_success(name: str, result: dict[str, Any]) -> dict[str, Any]:
    if result.get("success") is not True:
        raise RuntimeError(f"{name} reported failure: {result.get('error') or result}")
    return result


def nearest_frame_no(pts_times: list[float], target: float) -> tuple[int, float]:
    """Return nearest source frame and absolute time delta; ties prefer earlier frame."""
    pos = bisect_left(pts_times, target)
    candidates = [i for i in (pos - 1, pos) if 0 <= i < len(pts_times)]
    if not candidates:
        raise ValueError("No source PTS rows available")
    index = min(candidates, key=lambda i: (abs(pts_times[i] - target), pts_times[i]))
    return index, abs(pts_times[index] - target)


def scene_end_frame_no(pts_times: list[float], end_seconds: float) -> int:
    """Convert a scene end timestamp to a half-open source frame index."""
    return min(bisect_left(pts_times, end_seconds), len(pts_times))


def file_sha256(path: Path) -> str:
    return sha256_file(path)


def build_normalized_scenes(scene_result: dict[str, Any], pts_times: list[float],
                            source_sha256: str) -> list[dict[str, Any]]:
    scenes = scene_result["data"].get("scenes", [])
    normalized = []
    for scene in scenes:
        start = float(scene["start_seconds"])
        end = float(scene["end_seconds"])
        if end <= start:
            raise RuntimeError(f"Invalid scene interval: {scene}")
        start_frame_no, start_delta = nearest_frame_no(pts_times, start)
        end_frame_no = scene_end_frame_no(pts_times, end)
        if end_frame_no <= start_frame_no:
            raise RuntimeError(f"Scene maps to empty source frame interval: {scene}")
        normalized.append({
            "scene_index": int(scene.get("index", len(normalized))),
            "start_seconds": start,
            "end_seconds": end,
            "duration_seconds": round(end - start, 6),
            "start_frame_no": start_frame_no,
            "end_frame_no": end_frame_no,
            "frame_interval_semantics": "[start_frame_no, end_frame_no)",
            "start_boundary_mapping_delta_seconds": round(start_delta, 6),
            "source_sha256": source_sha256,
            "boundary_support": "scene_detector_time_mapped_to_source_pts",
        })
    if normalized:
        if normalized[0]["start_frame_no"] != 0:
            raise RuntimeError("First detected scene does not begin at source frame 0")
        for left, right in zip(normalized, normalized[1:]):
            if left["end_frame_no"] != right["start_frame_no"]:
                raise RuntimeError(f"Scene frame intervals are not contiguous: {left} -> {right}")
    return normalized


def build_normalized_sampled_frames(frame_result: dict[str, Any], pts_times: list[float],
                                    source_sha256: str, output_dir: Path) -> list[dict[str, Any]]:
    frames = frame_result["data"].get("frames", [])
    normalized = []
    for item in frames:
        sample_time = float(item["timestamp_seconds"])
        frame_no, delta = nearest_frame_no(pts_times, sample_time)
        raw_path = Path(item["path"])
        if not raw_path.is_absolute():
            raw_path = (output_dir / raw_path).resolve()
        if not raw_path.is_file():
            raise RuntimeError(f"Sampled frame listed by upstream does not exist: {raw_path}")
        try:
            relative_path = raw_path.relative_to(output_dir).as_posix()
        except ValueError as exc:
            raise RuntimeError(f"Sampled frame path escapes output directory: {raw_path}") from exc
        normalized.append({
            "sample_index": int(item.get("index", len(normalized))),
            "sample_timestamp_seconds": sample_time,
            "frame_no": frame_no,
            "source_pts_time": pts_times[frame_no],
            "mapping_delta_seconds": round(delta, 6),
            "relative_path": relative_path,
            "image_sha256": file_sha256(raw_path),
            "source_sha256": source_sha256,
            "association_key": {"source_sha256": source_sha256, "frame_no": frame_no},
            "association_status": "aligned" if delta <= 0.5 / 30.0 + 1e-6 else "ambiguous-neighbor",
        })
    if any(item["association_status"] != "aligned" for item in normalized):
        raise RuntimeError("At least one sampled image could not be reliably associated to a source frame")
    return normalized


def run(video: Path, output_dir: Path, repo_root: Path) -> dict[str, Any]:
    video = video.resolve()
    output_dir = output_dir.resolve()
    repo_root = repo_root.resolve()
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
    if status_counts.get("reorder", 0) or status_counts.get("ambiguous-neighbor", 0):
        raise RuntimeError(f"Source timestamp audit did not pass: {status_counts}")
    pts_times = [float(row["source_pts_time"]) for row in audited_frames]

    raw_results: dict[str, dict[str, Any]] = {}
    raw_results["audio_probe"] = require_success(
        "audio_probe", run_upstream_tool("audio_probe", {"input_path": str(video)}, repo_root=repo_root),
    )
    raw_results["scene_detect"] = require_success(
        "scene_detect",
        run_upstream_tool("scene_detect", {
            "input_path": str(video), "method": "content", "min_scene_length_seconds": 0.3,
            "output_path": str(output_dir / "scenes.json"),
        }, repo_root=repo_root),
    )
    raw_results["frame_sampler"] = require_success(
        "frame_sampler",
        run_upstream_tool("frame_sampler", {
            "input_path": str(video), "strategy": "interval", "interval_seconds": 1.0,
            "output_dir": str(output_dir / "frames"), "format": "jpg", "quality": 2,
        }, repo_root=repo_root),
    )

    normalized_scenes = build_normalized_scenes(raw_results["scene_detect"], pts_times, media_sha256)
    normalized_samples = build_normalized_sampled_frames(
        raw_results["frame_sampler"], pts_times, media_sha256, output_dir,
    )
    if not normalized_samples:
        raise RuntimeError("frame_sampler succeeded but produced no sampled frames")

    evidence_records = []
    for tool_name, raw_result in raw_results.items():
        evidence_records.append(make_evidence_record(
            evidence_id=f"real-a-mp4:{tool_name}", source_path=video,
            tool_name=f"OpenMontage.{tool_name}", tool_version=TOOL_VERSION,
            raw_result=raw_result,
        ))
    evidence_records.append(make_evidence_record(
        evidence_id="real-a-mp4:source-frame-pts-audit", source_path=video,
        tool_name="aiMontage.timestamp_audit", tool_version="0.1.1",
        raw_result={
            "frame_count": len(audited_frames), "status_counts": dict(status_counts),
            "first_source_pts_time": audited_frames[0]["source_pts_time"],
            "last_source_pts_time": audited_frames[-1]["source_pts_time"],
            "frames": audited_frames,
        },
    ))

    bundle = {
        "schema_version": "aimontage.real_video_e2e.v2",
        "fixture": {
            "path": video.name, "size_bytes": video.stat().st_size,
            "sha256": media_sha256, "upstream_revision": UPSTREAM_REVISION,
        },
        "checks": {
            "source_frame_count": len(frames),
            "timestamp_audit_status_counts": dict(status_counts),
            "audio_probe_success": raw_results["audio_probe"]["success"],
            "scene_detect_success": raw_results["scene_detect"]["success"],
            "frame_sampler_success": raw_results["frame_sampler"]["success"],
            "scene_count": len(normalized_scenes),
            "sampled_image_count": len(normalized_samples),
            "all_sampled_images_link_to_source_pts": all(
                row["association_status"] == "aligned" for row in normalized_samples
            ),
            "scene_frame_intervals_contiguous": all(
                left["end_frame_no"] == right["start_frame_no"]
                for left, right in zip(normalized_scenes, normalized_scenes[1:])
            ),
            "source_pts_is_authoritative": True,
            "decoder_pts_is_diagnostic_only": True,
        },
        "normalized": {"scenes": normalized_scenes, "sampled_frames": normalized_samples},
        "evidence": evidence_records,
    }
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
        "status": "passed", "fixture": bundle["fixture"], "checks": bundle["checks"],
        "scenes": bundle["normalized"]["scenes"],
        "sampled_frames": bundle["normalized"]["sampled_frames"],
        "evidence_bundle": (args.out.resolve() / "evidence_bundle.json").as_posix(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Run OpenMontage's native video_analyzer and preserve its official brief unchanged.

This is a thin adapter: OpenMontage owns analysis; aiMontage only validates the
minimum official structure and writes a run manifest. It does not invent scene
descriptions or convert the brief into a Blueprint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from aimontage.upstream import run_upstream_tool

UPSTREAM_REVISION = "c8066452325cb57c8fc1ba8c2a71b6e8842e6b65"
SCHEMA_VERSION = "aimontage.openmontage_video_analyzer_run.v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_official_brief(brief: dict[str, Any]) -> list[str]:
    """Check the required shape without mutating the upstream artifact."""
    errors: list[str] = []
    for key in ("version", "source", "content_analysis", "structure_analysis"):
        if key not in brief:
            errors.append(f"missing top-level key: {key}")
    source = brief.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    elif not isinstance(source.get("duration_seconds"), (int, float)):
        errors.append("source.duration_seconds must be numeric")

    content = brief.get("content_analysis")
    if not isinstance(content, dict):
        errors.append("content_analysis must be an object")
    else:
        for key in ("summary", "topics", "target_audience"):
            if key not in content:
                errors.append(f"missing content_analysis.{key}")

    structure = brief.get("structure_analysis")
    if not isinstance(structure, dict):
        errors.append("structure_analysis must be an object")
    else:
        for key in ("total_scenes", "scenes", "pacing_profile"):
            if key not in structure:
                errors.append(f"missing structure_analysis.{key}")
        scenes = structure.get("scenes", [])
        if isinstance(scenes, list):
            for i, scene in enumerate(scenes):
                if not isinstance(scene, dict):
                    errors.append(f"scene[{i}] must be an object")
                    continue
                for key in ("scene_index", "start_time", "end_time", "description"):
                    if key not in scene:
                        errors.append(f"scene[{i}] missing {key}")
                start, end = scene.get("start_time"), scene.get("end_time")
                if isinstance(start, (int, float)) and isinstance(end, (int, float)) and end < start:
                    errors.append(f"scene[{i}] end_time precedes start_time")
    return errors


def run(video: Path, out_dir: Path, repo_root: Path, depth: str, max_keyframes: int) -> dict[str, Any]:
    video = video.resolve()
    out_dir = out_dir.resolve()
    repo_root = repo_root.resolve()
    if not video.is_file():
        raise FileNotFoundError(f"Video not found: {video}")
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = run_upstream_tool(
        "video_analyzer",
        {
            "source": str(video),
            "analysis_depth": depth,
            "max_keyframes": max_keyframes,
            "output_dir": str(out_dir),
        },
        repo_root=repo_root,
        timeout_seconds=1800,
    )
    if raw.get("success") is not True:
        raise RuntimeError(f"OpenMontage video_analyzer failed: {raw.get('error') or raw}")

    brief = raw.get("data")
    if not isinstance(brief, dict):
        raise RuntimeError("OpenMontage video_analyzer returned no brief object")
    errors = validate_official_brief(brief)
    brief_path = out_dir / "video_analysis_brief.json"
    # Preserve the official artifact's schema and fields; no aiMontage fields are injected.
    brief_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if not errors else "review_required",
        "source": {
            "path": video.as_posix(),
            "size_bytes": video.stat().st_size,
            "sha256": sha256_file(video),
        },
        "upstream": {
            "repository": "https://github.com/calesthio/OpenMontage",
            "revision": UPSTREAM_REVISION,
            "tool": "video_analyzer",
            "analysis_depth": depth,
            "success": True,
        },
        "validation": {"official_brief_shape_valid": not errors, "errors": errors},
        "summary": {
            "duration_seconds": brief.get("source", {}).get("duration_seconds"),
            "scene_count": brief.get("structure_analysis", {}).get("total_scenes"),
            "keyframe_count": len(brief.get("keyframes", [])) if isinstance(brief.get("keyframes"), list) else None,
            "steps_completed": brief.get("_analysis_meta", {}).get("steps_completed", []),
            "steps_failed": brief.get("_analysis_meta", {}).get("steps_failed", []),
        },
        "artifact": "video_analysis_brief.json",
        "note": "The brief is upstream analysis output, not a semantically reviewed Blueprint.",
    }
    (out_dir / "analysis_run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, default=Path("a.mp4"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/openmontage_video_analysis"))
    parser.add_argument("--repo-root", type=Path, default=Path("vendor/OpenMontage"))
    parser.add_argument("--depth", choices=("transcript_only", "standard", "deep"), default="standard")
    parser.add_argument("--max-keyframes", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.max_keyframes <= 50:
        parser.error("--max-keyframes must be between 1 and 50")
    manifest = run(args.video, args.out, args.repo_root, args.depth, args.max_keyframes)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())

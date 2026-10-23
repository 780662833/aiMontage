#!/usr/bin/env python3
"""Render a reviewed candidate to the target profile and write technical QA reports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aimontage.evidence import write_json_atomic
from aimontage.ffmpeg_renderer import render_source_preserving
from aimontage.render_qa import validate_render_report


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--render-spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="Rendered MP4 path")
    parser.add_argument("--report", type=Path, required=True, help="Render provenance JSON")
    parser.add_argument("--qa", type=Path, required=True, help="Post-render QA JSON")
    args = parser.parse_args()
    spec = read_json(args.render_spec)
    report = render_source_preserving(args.video, args.out, read_json(args.candidate), spec)
    qa = validate_render_report(report, spec)
    write_json_atomic(args.report, report)
    write_json_atomic(args.qa, qa)
    print(json.dumps({
        "render_mode": report["render_mode"],
        "output": args.out.resolve().as_posix(),
        "output_sha256": report["output"]["sha256"],
        "qa_status": qa["status"],
        "manual_review_required": qa["manual_review_required"],
        "errors": qa["errors"],
    }, ensure_ascii=False, indent=2))
    return 0 if qa["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

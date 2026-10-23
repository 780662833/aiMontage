#!/usr/bin/env python3
"""Render an explicitly editor-approved shot edit plan; drafts are rejected."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aimontage.evidence import write_json_atomic
from aimontage.edit_plan_renderer import render_approved_edit_plan
from aimontage.ffmpeg_content_qa import analyze_content_anomalies
from aimontage.render_qa import validate_render_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--qa", type=Path, required=True)
    parser.add_argument("--content-qa", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    report = render_approved_edit_plan(args.video, args.out, plan)
    expected = {"output": {"width": plan["output"]["width"], "height": plan["output"]["height"],
                           "fps": plan["output"]["fps"], "audio_codec": plan["output"].get("audio_codec", "aac")}}
    qa = validate_render_report({
        "source": {"duration_seconds": report["output"]["duration_seconds"],
                   "probe": report["source"]["probe"]},
        "output": {"probe": report["output"]["probe"]},
    }, expected)
    content_qa = analyze_content_anomalies(args.out)
    write_json_atomic(args.report, report)
    write_json_atomic(args.qa, qa)
    write_json_atomic(args.content_qa, content_qa)
    print(json.dumps({"render_mode": report["render_mode"], "output": args.out.resolve().as_posix(),
                      "output_sha256": report["output"]["sha256"], "qa_status": qa["status"],
                      "content_detection_counts": content_qa["detection_counts"],
                      "manual_review_required": True, "errors": qa["errors"]}, indent=2))
    return 0 if qa["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build a review-gated per-shot edit plan from a reconstruction candidate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aimontage.edit_plan import build_edit_plan
from aimontage.evidence import write_json_atomic


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    plan = build_edit_plan(candidate)
    write_json_atomic(args.out, plan)
    print(json.dumps({
        "schema_version": plan["schema_version"],
        "status": plan["status"],
        "shot_count": len(plan["shots"]),
        "planned_duration_seconds": plan["output"]["planned_duration_seconds"],
        "editor_approval_required": plan["acceptance"]["editor_approval_required"],
        "output": args.out.resolve().as_posix(),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

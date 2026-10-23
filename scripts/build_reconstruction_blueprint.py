#!/usr/bin/env python3
"""Promote a reviewed visual review into a non-production reconstruction candidate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aimontage.evidence import write_json_atomic
from aimontage.reconstruction_blueprint import build_reconstruction_candidate


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blueprint", type=Path, required=True)
    parser.add_argument("--visual-review", type=Path, required=True)
    parser.add_argument("--render-spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    candidate = build_reconstruction_candidate(
        read_json(args.blueprint), read_json(args.visual_review), read_json(args.render_spec),
    )
    write_json_atomic(args.out, candidate)
    print(json.dumps({
        "status": candidate["status"],
        "source_sha256": candidate["source"]["sha256"],
        "shot_count": len(candidate["shots"]),
        "visual_review_complete": candidate["acceptance"]["visual_review_complete"],
        "render_ready": candidate["acceptance"]["render_ready"],
        "production_ready": candidate["acceptance"]["production_ready"],
        "blockers": candidate["acceptance"]["blockers"],
        "output": args.out.resolve().as_posix(),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

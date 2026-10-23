#!/usr/bin/env python3
"""Build an evidence-linked visual annotation template from the review-ready draft."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aimontage.evidence import write_json_atomic
from aimontage.visual_review import build_visual_review_template


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visual", type=Path, required=True, help="Evidence bundle JSON")
    parser.add_argument("--blueprint", type=Path, required=True, help="Blueprint draft JSON")
    parser.add_argument("--out", type=Path, required=True, help="Review template output JSON")
    args = parser.parse_args()

    template = build_visual_review_template(read_json(args.visual), read_json(args.blueprint))
    write_json_atomic(args.out, template)
    print(json.dumps({
        "status": template["status"],
        "source_sha256": template["source"]["sha256"],
        "shot_count": template["validation"]["shot_count"],
        "sampled_frame_count": template["validation"]["sampled_frame_count"],
        "shots_without_sampled_frames": template["validation"]["shots_without_sampled_frames"],
        "review_complete": template["validation"]["review_complete"],
        "output": args.out.resolve().as_posix(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate visual review annotations and report whether every shot was reviewed."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aimontage.evidence import write_json_atomic
from aimontage.visual_review_validation import visual_review_completion


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True, help="Visual review template or annotated JSON")
    parser.add_argument("--out", type=Path, required=True, help="Validation report output")
    parser.add_argument("--require-complete", action="store_true",
                        help="Exit non-zero unless every shot has evidence-linked annotations")
    args = parser.parse_args()
    review = json.loads(args.review.read_text(encoding="utf-8"))
    completion = visual_review_completion(review)
    report = {
        "schema_version": "aimontage.visual_review_validation.v1",
        "source_sha256": review.get("source", {}).get("sha256"),
        **completion,
        "review_path": args.review.as_posix(),
    }
    write_json_atomic(args.out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not completion["valid"]:
        return 2
    if args.require_complete and not completion["review_complete"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

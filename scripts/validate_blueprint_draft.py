#!/usr/bin/env python3
"""Validate a generated Blueprint draft and write a machine-readable report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aimontage.blueprint_validation import validate_blueprint_draft


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blueprint", required=True, help="Blueprint draft JSON")
    parser.add_argument("--out", required=True, help="Validation report JSON path")
    args = parser.parse_args()

    blueprint = json.loads(Path(args.blueprint).read_text(encoding="utf-8"))
    errors = validate_blueprint_draft(blueprint)
    report = {
        "schema_version": "aimontage.blueprint_validation.v1",
        "blueprint_path": args.blueprint,
        "valid": not errors,
        "errors": errors,
        "creative_blueprint_ready": False,
        "note": "Structural validity does not imply semantic review or production readiness.",
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())

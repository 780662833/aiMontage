#!/usr/bin/env python3
"""Apply reviewed shot annotations to a frame-linked visual review template."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aimontage.evidence import write_json_atomic
from aimontage.visual_review_validation import visual_review_completion


_FIELDS = (
    "visual_description", "subject", "action", "camera_motion",
    "composition", "lighting_and_color", "edit_intent", "confidence",
    "evidence_frame_nos", "review_status", "annotator_note",
)


def apply_annotations(template: dict, annotations: dict) -> dict:
    source_sha = template.get("source", {}).get("sha256")
    if not source_sha or source_sha != annotations.get("source_sha256"):
        raise ValueError("Annotation source_sha256 does not match review template")
    if annotations.get("schema_version") != "aimontage.visual_annotations.v1":
        raise ValueError("Unsupported visual annotations schema_version")
    incoming = annotations.get("shots")
    if not isinstance(incoming, list):
        raise ValueError("annotations.shots must be a list")
    by_id = {}
    for annotation in incoming:
        if not isinstance(annotation, dict) or not annotation.get("shot_id"):
            raise ValueError("Each annotation requires shot_id")
        sid = annotation["shot_id"]
        if sid in by_id:
            raise ValueError(f"Duplicate annotation shot_id: {sid}")
        by_id[sid] = annotation

    result = json.loads(json.dumps(template))
    template_ids = {shot["shot_id"] for shot in result.get("shots", [])}
    if set(by_id) != template_ids:
        missing = sorted(template_ids - set(by_id))
        extra = sorted(set(by_id) - template_ids)
        raise ValueError(f"Annotation shot IDs must match template; missing={missing}, extra={extra}")

    for shot in result["shots"]:
        annotation = by_id[shot["shot_id"]]
        linked_frames = {int(frame["frame_no"]) for frame in shot.get("evidence_frames", [])}
        for field in _FIELDS:
            if field not in annotation:
                raise ValueError(f"{shot['shot_id']} annotation missing {field}")
        cited = annotation["evidence_frame_nos"]
        if not isinstance(cited, list) or not cited:
            raise ValueError(f"{shot['shot_id']} must cite evidence_frame_nos")
        if any(int(frame_no) not in linked_frames for frame_no in cited):
            raise ValueError(f"{shot['shot_id']} cites evidence frames not linked to this shot")
        shot["annotation"] = {field: annotation[field] for field in _FIELDS}
    result["status"] = "annotated_pending_validation"
    completion = visual_review_completion(result)
    result["validation"] = {
        **result.get("validation", {}),
        "review_complete": completion["review_complete"],
        "annotation_validation_errors": completion["errors"],
        "reviewed_shot_count": completion["reviewed_shot_count"],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    template = json.loads(args.template.read_text(encoding="utf-8"))
    annotations = json.loads(args.annotations.read_text(encoding="utf-8"))
    result = apply_annotations(template, annotations)
    write_json_atomic(args.out, result)
    completion = visual_review_completion(result)
    print(json.dumps({
        "status": result["status"],
        "source_sha256": result["source"]["sha256"],
        "reviewed_shot_count": completion["reviewed_shot_count"],
        "shot_count": completion["shot_count"],
        "review_complete": completion["review_complete"],
        "errors": completion["errors"],
        "output": args.out.resolve().as_posix(),
    }, ensure_ascii=False, indent=2))
    return 0 if completion["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

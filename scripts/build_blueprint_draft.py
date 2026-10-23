"""Create an evidence-aligned Blueprint draft from validated analysis artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aimontage.blueprint import build_blueprint_draft
from aimontage.evidence import write_json_atomic


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visual", type=Path, default=Path("artifacts/real_video_e2e/evidence_bundle.json"))
    parser.add_argument("--timeline", type=Path, default=Path("artifacts/real_video_e2e/cross_modal_timeline.json"))
    parser.add_argument("--audio-review", type=Path, default=Path("artifacts/real_video_e2e/audio_content_review.json"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/real_video_e2e/blueprint_draft.json"))
    args = parser.parse_args()

    blueprint = build_blueprint_draft(
        read_json(args.visual), read_json(args.timeline), read_json(args.audio_review),
    )
    write_json_atomic(args.out, blueprint)
    print(json.dumps({
        "status": "passed" if blueprint["status"] == "evidence_aligned_draft" else "review_required",
        "source_sha256": blueprint["source"]["sha256"],
        "shot_count": len(blueprint["shots"]),
        "creative_blueprint_ready": blueprint["acceptance"]["creative_blueprint_ready"],
        "blockers": blueprint["acceptance"]["blockers"],
        "output": args.out.resolve().as_posix(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

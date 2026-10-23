"""Fuse visual and audio evidence JSON into a shared, validated event timeline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aimontage.cross_modal_timeline import build_cross_modal_timeline
from aimontage.evidence import write_json_atomic


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visual", type=Path, default=Path("artifacts/real_video_e2e/evidence_bundle.json"))
    parser.add_argument("--music", type=Path, default=Path("artifacts/real_video_e2e/music_timeline/music_timeline_evidence.json"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/real_video_e2e/cross_modal_timeline.json"))
    parser.add_argument("--duration-tolerance", type=float, default=0.15)
    args = parser.parse_args()

    visual = read_json(args.visual)
    music = read_json(args.music)
    timeline = build_cross_modal_timeline(
        visual, music, duration_tolerance_seconds=args.duration_tolerance,
    )
    write_json_atomic(args.out, timeline)
    print(json.dumps({
        "status": "passed",
        "source_sha256": timeline["source"]["sha256"],
        "source_duration_seconds": timeline["source"]["duration_seconds"],
        "event_count": len(timeline["events"]),
        "validation": timeline["validation"],
        "output": args.out.resolve().as_posix(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

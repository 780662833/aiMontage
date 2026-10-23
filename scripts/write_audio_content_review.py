"""Write an explicit audio-content review record for Blueprint gating."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from aimontage.audio_review import build_audio_content_review

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classification", required=True, choices=["music_only", "speech_only", "music_and_speech", "unknown"])
    parser.add_argument("--reviewer-note", required=True)
    parser.add_argument("--transcription-bundle", type=Path)
    parser.add_argument("--out", type=Path, default=Path("artifacts/real_video_e2e/audio_content_review.json"))
    args = parser.parse_args()
    transcription = None
    if args.transcription_bundle and args.transcription_bundle.is_file():
        transcription = json.loads(args.transcription_bundle.read_text(encoding="utf-8"))
    elif args.transcription_bundle:
        print(f"Warning: transcription bundle unavailable; recording review without ASR evidence: {args.transcription_bundle}")
    review = build_audio_content_review(classification=args.classification, reviewer_note=args.reviewer_note, transcription_bundle=transcription)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "review": review, "evidence_bundle": args.out.as_posix()}, indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

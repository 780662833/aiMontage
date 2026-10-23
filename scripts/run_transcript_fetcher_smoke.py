"""Optional network integration test for OpenMontage's YouTube caption fetcher."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
from aimontage.evidence import write_json_atomic
from aimontage.upstream import run_upstream_tool

def normalize_captions(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("success") is not True:
        raise RuntimeError(f"transcript_fetcher reported failure: {raw.get('error') or raw}")
    data = raw.get("data") or {}
    transcript = data.get("transcript")
    if not isinstance(transcript, list): raise RuntimeError("transcript_fetcher result must include a transcript array")
    normalized = []
    for segment in transcript:
        start, duration = float(segment["start"]), float(segment["duration"])
        if start < 0 or duration < 0: raise RuntimeError(f"Invalid caption timing: {segment}")
        normalized.append({"start_seconds": start, "end_seconds": start + duration, "text": str(segment.get("text", "")), "source": "youtube_captions"})
    if any(a["start_seconds"] > b["start_seconds"] for a, b in zip(normalized, normalized[1:])):
        raise RuntimeError("Caption segments are not in timestamp order")
    return {"video_id": data.get("video_id"), "language": data.get("language"),
            "is_auto_generated": data.get("is_auto_generated"), "source": data.get("source", "youtube_captions"),
            "segment_count": len(normalized), "segments": normalized, "full_text": data.get("full_text", "")}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="YouTube URL or video ID with accessible captions")
    parser.add_argument("--out", type=Path, default=Path("artifacts/caption_fetch_e2e"))
    parser.add_argument("--repo-root", type=Path, default=Path("vendor/OpenMontage"))
    parser.add_argument("--language", action="append", default=None)
    args = parser.parse_args()
    output_dir = args.out.resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    raw = run_upstream_tool("transcript_fetcher", {"url_or_video_id": args.url, "languages": args.language or ["en"], "include_auto_generated": True},
                            repo_root=args.repo_root.resolve(), timeout_seconds=120)
    normalized = normalize_captions(raw)
    bundle = {"schema_version": "aimontage.caption_fetch_e2e.v1", "source": {"url_or_video_id": args.url},
              "checks": {"fetcher_success": True, "timestamp_order_valid": True, "segment_count": normalized["segment_count"],
                         "language": normalized["language"], "is_auto_generated": normalized["is_auto_generated"]},
              "normalized": normalized, "raw_result": raw}
    write_json_atomic(output_dir / "caption_fetch_evidence.json", bundle)
    print(json.dumps({"status": "passed", "checks": bundle["checks"], "evidence_bundle": (output_dir / "caption_fetch_evidence.json").as_posix()}, indent=2))
    return 0
if __name__ == "__main__": raise SystemExit(main())

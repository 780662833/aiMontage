"""Run a controlled local transcription check against the repository's a.mp4."""
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path
from typing import Any
from aimontage.evidence import make_evidence_record, sha256_file, write_json_atomic
from aimontage.upstream import run_upstream_tool
from aimontage.transcript_qa import assess_transcript_quality
UPSTREAM_REVISION = "c8066452325cb57c8fc1ba8c2a71b6e8842e6b65"

def normalize_transcript(raw: dict[str, Any], media_duration: float) -> dict[str, Any]:
    if raw.get("success") is not True:
        raise RuntimeError(f"transcriber reported failure: {raw.get('error') or raw}")
    data = raw.get("data") or {}
    segments, words = data.get("segments"), data.get("word_timestamps")
    if not isinstance(segments, list) or not isinstance(words, list):
        raise RuntimeError("transcriber result must include segments and word_timestamps arrays")
    def validate(item, kind):
        start, end = float(item["start"]), float(item["end"])
        if start < 0 or end < start or end > media_duration + 0.5:
            raise RuntimeError(f"Transcript {kind} timestamp out of media bounds: {item}")
        return start, end
    normalized_segments = []
    for seg in segments:
        start, end = validate(seg, "segment")
        normalized_segments.append({"start_seconds": start, "end_seconds": end, "text": str(seg.get("text", "")), "source": "local_asr"})
    normalized_words = []
    for word in words:
        start, end = validate(word, "word")
        normalized_words.append({"start_seconds": start, "end_seconds": end, "text": str(word.get("word", "")), "probability": word.get("probability"), "source": "local_asr"})
    return {"language": data.get("language"), "model_size": data.get("model_size"), "device": data.get("device"),
            "duration_seconds": float(data.get("duration_seconds", media_duration)), "media_duration_seconds": media_duration,
            "speech_detected": bool(normalized_segments and any(s["text"].strip() for s in normalized_segments)),
            "segments": normalized_segments, "word_timestamps": normalized_words}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, default=Path("a.mp4"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/real_video_e2e/transcription"))
    parser.add_argument("--repo-root", type=Path, default=Path("vendor/OpenMontage"))
    parser.add_argument("--model-size", choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"], default="tiny")
    parser.add_argument("--language", default="en")
    args = parser.parse_args()
    video, output_dir, repo_root = args.video.resolve(), args.out.resolve(), args.repo_root.resolve()
    if not video.is_file(): raise FileNotFoundError(f"Video not found: {video}")
    output_dir.mkdir(parents=True, exist_ok=True)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video)], check=True, capture_output=True, text=True, timeout=30)
    duration = float(json.loads(probe.stdout)["format"]["duration"])
    raw = run_upstream_tool("transcriber", {"input_path": str(video), "model_size": args.model_size, "language": args.language, "diarize": False, "output_dir": str(output_dir)}, repo_root=repo_root, timeout_seconds=900)
    normalized = normalize_transcript(raw, duration)
    transcript_qa = assess_transcript_quality(normalized)
    evidence = make_evidence_record(evidence_id="real-a-mp4:local-asr", source_path=video, tool_name="OpenMontage.transcriber",
        tool_version=f"0.1.0+openmontage.{UPSTREAM_REVISION[:8]}", raw_result=raw)
    bundle = {"schema_version": "aimontage.transcription_e2e.v1",
        "fixture": {"path": video.name, "sha256": sha256_file(video), "upstream_revision": UPSTREAM_REVISION},
        "checks": {"transcriber_success": True, "segments_timestamp_valid": True, "words_timestamp_valid": True,
                   "speech_detected": normalized["speech_detected"], "segment_count": len(normalized["segments"]),
                   "word_count": len(normalized["word_timestamps"]), "model_size": args.model_size, "language": args.language,
                   "transcript_quality_status": transcript_qa["status"], "blueprint_ready": transcript_qa["blueprint_ready"]},
        "normalized": normalized, "transcript_qa": transcript_qa, "evidence": evidence}
    write_json_atomic(output_dir / "transcription_evidence.json", bundle)
    print(json.dumps({"status": "passed", "checks": bundle["checks"], "evidence_bundle": (output_dir / "transcription_evidence.json").as_posix()}, indent=2))
    return 0
if __name__ == "__main__": raise SystemExit(main())

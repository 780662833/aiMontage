"""Lightweight, deterministic QA gates for ASR evidence before Blueprint use."""
from __future__ import annotations
from typing import Any


def assess_transcript_quality(
    normalized: dict[str, Any],
    *,
    low_confidence_threshold: float = 0.2,
    max_interword_gap_seconds: float = 1.5,
) -> dict[str, Any]:
    words = normalized.get("word_timestamps", [])
    low_confidence = []
    large_gaps = []
    for i, word in enumerate(words):
        probability = word.get("probability")
        if isinstance(probability, (int, float)) and probability < low_confidence_threshold:
            low_confidence.append({
                "index": i, "text": word.get("text", ""),
                "probability": probability,
            })
        if i:
            previous = words[i - 1]
            gap = float(word["start_seconds"]) - float(previous["end_seconds"])
            if gap > max_interword_gap_seconds:
                large_gaps.append({
                    "previous_word_index": i - 1,
                    "word_index": i,
                    "gap_seconds": round(gap, 3),
                })
    if not normalized.get("speech_detected"):
        status = "NO_SPEECH"
    elif low_confidence or large_gaps:
        status = "REVIEW"
    else:
        status = "PASS"
    return {
        "status": status,
        "blueprint_ready": status == "PASS",
        "low_confidence_threshold": low_confidence_threshold,
        "max_interword_gap_seconds": max_interword_gap_seconds,
        "low_confidence_word_count": len(low_confidence),
        "low_confidence_words": low_confidence,
        "large_interword_gap_count": len(large_gaps),
        "large_interword_gaps": large_gaps,
        "reason": (
            "No speech segments detected; verify source audio before treating transcript as empty."
            if status == "NO_SPEECH" else
            "ASR has low-confidence words or large timestamp gaps; review against source audio."
            if status == "REVIEW" else
            "Basic confidence and word-timing checks passed; content accuracy still requires spot review."
        ),
    }

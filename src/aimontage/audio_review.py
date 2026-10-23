"""Human-reviewed audio content classification and transcript exclusion policy."""
from __future__ import annotations

from typing import Any

SUPPORTED_CLASSIFICATIONS = {"music_only", "speech_only", "music_and_speech", "unknown"}


def build_audio_content_review(
    *,
    classification: str,
    reviewer_note: str,
    transcription_bundle: dict[str, Any] | None = None,
    source: str = "human_review",
) -> dict[str, Any]:
    """Create an explicit review record without confusing ASR output with truth."""
    if classification not in SUPPORTED_CLASSIFICATIONS:
        raise ValueError(f"Unsupported audio classification: {classification}")
    if not reviewer_note.strip():
        raise ValueError("reviewer_note must explain the basis for the classification")

    qa = (transcription_bundle or {}).get("transcript_qa", {})
    normalized = (transcription_bundle or {}).get("normalized", {})
    transcript_included = classification in {"speech_only", "music_and_speech"} and qa.get("blueprint_ready") is True

    if classification == "music_only":
        transcript_status = "NOT_APPLICABLE"
        reason = "Human review confirmed music-only audio; exclude ASR text from Blueprint."
    elif classification == "unknown":
        transcript_status = "REVIEW_REQUIRED"
        reason = "Audio content type is not confirmed; do not accept transcript automatically."
    elif qa.get("blueprint_ready") is True:
        transcript_status = "QA_PASS_REQUIRES_CONTENT_SPOT_CHECK"
        reason = "Automated timing/confidence checks passed; semantic correctness still needs review."
    else:
        transcript_status = "REVIEW_REQUIRED"
        reason = "Transcript did not pass QA; exclude it from Blueprint until reviewed."

    return {
        "schema_version": "aimontage.audio_content_review.v1",
        "classification": classification,
        "classification_source": source,
        "reviewer_note": reviewer_note.strip(),
        "transcript_status": transcript_status,
        "transcript_included_in_blueprint": transcript_included,
        "asr_output_retained_for_traceability": bool(transcription_bundle),
        "asr_reported_speech_detected": normalized.get("speech_detected"),
        "transcript_qa_status": qa.get("status"),
        "blueprint_audio_policy": (
            "music_timeline_only_no_spoken_transcript"
            if classification == "music_only" else
            "spoken_transcript_candidate_requires_review"
            if classification in {"speech_only", "music_and_speech"} else
            "hold_audio_dependent_blueprint_fields"
        ),
        "reason": reason,
    }

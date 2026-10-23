import pytest

from aimontage.audio_review import build_audio_content_review


def test_music_only_review_excludes_asr_hallucination_and_keeps_traceability():
    review = build_audio_content_review(
        classification="music_only",
        reviewer_note="Reviewed source video: background music only; no spoken narration.",
        transcription_bundle={
            "normalized": {"speech_detected": True},
            "transcript_qa": {"status": "REVIEW", "blueprint_ready": False},
        },
    )
    assert review["classification"] == "music_only"
    assert review["transcript_status"] == "NOT_APPLICABLE"
    assert review["transcript_included_in_blueprint"] is False
    assert review["asr_output_retained_for_traceability"] is True
    assert review["blueprint_audio_policy"] == "music_timeline_only_no_spoken_transcript"


def test_unknown_audio_classification_holds_audio_dependent_fields():
    review = build_audio_content_review(
        classification="unknown",
        reviewer_note="Audio not reviewed yet.",
    )
    assert review["transcript_status"] == "REVIEW_REQUIRED"
    assert review["transcript_included_in_blueprint"] is False


def test_review_requires_note_and_valid_classification():
    with pytest.raises(ValueError):
        build_audio_content_review(classification="music_only", reviewer_note=" ")
    with pytest.raises(ValueError):
        build_audio_content_review(classification="not_a_type", reviewer_note="reviewed")

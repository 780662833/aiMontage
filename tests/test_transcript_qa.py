from aimontage.transcript_qa import assess_transcript_quality


def test_low_confidence_and_large_gap_require_review():
    result = assess_transcript_quality({
        "speech_detected": True,
        "word_timestamps": [
            {"text": "Thanks", "start_seconds": 0.0, "end_seconds": 1.58, "probability": 0.01},
            {"text": "for", "start_seconds": 4.46, "end_seconds": 5.0, "probability": 0.908},
        ],
    })
    assert result["status"] == "REVIEW"
    assert result["blueprint_ready"] is False
    assert result["low_confidence_word_count"] == 1
    assert result["large_interword_gap_count"] == 1


def test_high_confidence_contiguous_words_pass_basic_qa():
    result = assess_transcript_quality({
        "speech_detected": True,
        "word_timestamps": [
            {"text": "hello", "start_seconds": 0.0, "end_seconds": 0.3, "probability": 0.9},
            {"text": "there", "start_seconds": 0.31, "end_seconds": 0.7, "probability": 0.95},
        ],
    })
    assert result["status"] == "PASS"
    assert result["blueprint_ready"] is True


def test_no_speech_is_explicit_not_silent_success():
    result = assess_transcript_quality({"speech_detected": False, "word_timestamps": []})
    assert result["status"] == "NO_SPEECH"
    assert result["blueprint_ready"] is False

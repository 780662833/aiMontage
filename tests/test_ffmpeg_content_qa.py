from aimontage.ffmpeg_content_qa import parse_detection_log


def test_parse_black_freeze_and_silence_intervals():
    stderr = """
[blackdetect @ 0x1] black_start:1.000 black_end:1.250 black_duration:0.250
[freezedetect @ 0x2] lavfi.freezedetect.freeze_start:2.000
[freezedetect @ 0x2] lavfi.freezedetect.freeze_duration:0.750
[silencedetect @ 0x3] silence_start:4.000
[silencedetect @ 0x3] silence_end:5.000 | silence_duration:1.000
"""
    result = parse_detection_log(stderr)
    assert result["black"] == [{"start": 1.0, "end": 1.25, "duration": 0.25}]
    assert result["freeze"] == [{"start": 2.0, "end": 2.75, "duration": 0.75}]
    assert result["silence"] == [{"start": 4.0, "end": 5.0, "duration": 1.0}]


def test_unclosed_detection_is_preserved_as_open_ended_candidate():
    result = parse_detection_log("[silencedetect] silence_start:7.5")
    assert result["silence"] == [
        {"start": 7.5, "end": 7.5, "duration": 0.0, "open_ended": 1.0}
    ]


def test_empty_log_produces_empty_review_candidates():
    result = parse_detection_log("")
    assert result == {"black": [], "freeze": [], "silence": []}

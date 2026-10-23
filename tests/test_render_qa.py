from aimontage.render_qa import validate_render_report


def _report(width=1080, height=1920, fps="30/1", duration="12.367", audio=True):
    streams = [{"codec_type": "video", "width": width, "height": height, "avg_frame_rate": fps}]
    source_streams = [{"codec_type": "video"}]
    if audio:
        streams.append({"codec_type": "audio"})
        source_streams.append({"codec_type": "audio"})
    return {
        "source": {"duration_seconds": 12.367, "probe": {"streams": source_streams}},
        "output": {"probe": {"streams": streams, "format": {"duration": duration}}},
    }


def _spec():
    return {"output": {"width": 1080, "height": 1920, "fps": 30, "audio_codec": "aac"}}


def test_render_qa_passes_target_profile():
    result = validate_render_report(_report(), _spec())
    assert result["status"] == "PASS"
    assert result["manual_review_required"] is True


def test_render_qa_fails_wrong_dimensions_and_missing_audio():
    report = _report(width=720, audio=False)\n    report["source"]["probe"]["streams"].append({"codec_type": "audio"})\n    result = validate_render_report(report, _spec())
    assert result["status"] == "FAIL"
    assert any("width" in error for error in result["errors"])
    assert any("audio" in error for error in result["errors"])


def test_render_qa_fails_duration_drift():
    result = validate_render_report(_report(duration="11.0"), _spec())
    assert result["status"] == "FAIL"
    assert any("duration drift" in error for error in result["errors"])

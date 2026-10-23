import pytest

from aimontage.cross_modal_timeline import build_cross_modal_timeline


def visual(sha="abc"):
    return {
        "fixture": {"sha256": sha},
        "normalized": {"scenes": [
            {"scene_index": 0, "start_seconds": 0.0, "end_seconds": 1.0,
             "start_frame_no": 0, "end_frame_no": 30},
            {"scene_index": 1, "start_seconds": 1.0, "end_seconds": 2.0,
             "start_frame_no": 30, "end_frame_no": 60},
        ]},
    }


def music(sha="abc", duration=2.0):
    return {
        "source": {"sha256": sha},
        "measurement": {"duration_seconds": duration},
        "candidate_onsets": [{"time_seconds": 0.5, "energy_rise_db": 9.0}],
        "silence_intervals": [{"start_seconds": 0.0, "end_seconds": 0.2}],
    }


def test_fuses_events_on_shared_timeline_and_preserves_provenance():
    result = build_cross_modal_timeline(visual(), music())
    assert result["schema_version"] == "aimontage.cross_modal_timeline.v1"
    assert result["validation"]["source_hashes_match"] is True
    assert result["validation"]["visual_scene_count"] == 2
    assert result["validation"]["audio_onset_candidate_count"] == 1
    assert result["events"][0]["event_type"] == "threshold_silence"
    scene = next(x for x in result["events"] if x["event_type"] == "scene")
    assert scene["frame_interval"]["semantics"] == "[start_frame_no, end_frame_no)"
    onset = next(x for x in result["events"] if x["event_type"] == "candidate_energy_onset")
    assert onset["confidence_status"] == "unverified_transient_not_a_beat"


def test_rejects_different_source_hashes():
    with pytest.raises(ValueError, match="different source"):
        build_cross_modal_timeline(visual("one"), music("two"))


def test_rejects_duration_mismatch_and_empty_scenes():
    with pytest.raises(ValueError, match="duration mismatch"):
        build_cross_modal_timeline(visual(), music(duration=3.0))
    with pytest.raises(ValueError, match="no normalized scenes"):
        build_cross_modal_timeline(
            {"fixture": {"sha256": "abc"}, "normalized": {"scenes": []}}, music()
        )


def test_rejects_missing_source_identity():
    with pytest.raises(ValueError, match="SHA-256"):
        build_cross_modal_timeline(visual(), music(sha=""))

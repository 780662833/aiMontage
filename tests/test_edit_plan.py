import pytest

from aimontage.edit_plan import build_edit_plan


def _candidate():
    return {
        "schema_version": "aimontage.reconstruction_blueprint_candidate.v1",
        "source": {"sha256": "abc123"},
        "audio": {"classification": "music_only"},
        "render_spec": {
            "output": {"width": 1080, "height": 1920, "fps": 30, "container": "mp4", "video_codec": "h264", "audio_codec": "aac"},
            "fit_policy": {"background_fill": "blurred_duplicate"},
            "subtitles": {"burn_in": False, "source": "none_until_verified"},
            "audio": {"preserve_source_music": True},
        },
        "acceptance": {"visual_review_complete": True},
        "shots": [
            {
                "shot_id": "SHOT-001",
                "start_seconds": 0.0,
                "end_seconds": 2.0,
                "source_frame_interval": {"start_frame_no": 0, "end_frame_no": 60},
                "annotation_evidence_frame_nos": [0, 30],
                "visual_description": "A person holds a cup",
                "subject": "person",
                "action": "holds cup",
                "camera_motion": "unknown",
                "composition": "medium shot",
                "edit_intent": "introduce subject",
            }
        ],
    }


def test_build_edit_plan_preserves_source_interval_and_explicit_defaults():
    plan = build_edit_plan(_candidate())
    shot = plan["shots"][0]
    assert plan["schema_version"] == "aimontage.shot_edit_plan.v1"
    assert shot["source"]["start_frame_no"] == 0
    assert shot["source"]["end_frame_no_exclusive"] == 60
    assert shot["target"]["end_frame_no_exclusive"] == 60
    assert shot["reframe"]["crop"] is None
    assert shot["transition"]["type"] == "cut"
    assert shot["subtitles"]["enabled"] is False
    assert shot["audio"]["music_edit"] == "continuous_source_audio_no_beat_sync_claim"
    assert plan["acceptance"]["editor_approval_required"] is True


def test_build_edit_plan_rejects_unreviewed_candidate():
    candidate = _candidate()
    candidate["acceptance"]["visual_review_complete"] = False
    with pytest.raises(ValueError, match="complete visual review"):
        build_edit_plan(candidate)


def test_build_edit_plan_rejects_invalid_half_open_interval():
    candidate = _candidate()
    candidate["shots"][0]["source_frame_interval"]["end_frame_no"] = 0
    with pytest.raises(ValueError, match="invalid half-open"):
        build_edit_plan(candidate)

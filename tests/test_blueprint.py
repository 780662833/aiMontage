import pytest

from aimontage.blueprint import build_blueprint_draft


def fixture():
    visual = {
        "fixture": {"path": "a.mp4", "sha256": "abc"},
        "normalized": {"scenes": [
            {"scene_index": 0, "start_seconds": 0.0, "end_seconds": 1.0,
             "start_frame_no": 0, "end_frame_no": 30},
            {"scene_index": 1, "start_seconds": 1.0, "end_seconds": 2.0,
             "start_frame_no": 30, "end_frame_no": 60},
        ]},
    }
    timeline = {"source": {"sha256": "abc", "duration_seconds": 2.0}}
    audio = {
        "classification": "music_only",
        "blueprint_audio_policy": "music_timeline_only_no_spoken_transcript",
        "transcript_included_in_blueprint": False,
        "transcript_status": "NOT_APPLICABLE",
    }
    return visual, timeline, audio


def test_builds_evidence_aligned_draft_without_inventing_visual_semantics():
    result = build_blueprint_draft(*fixture())
    assert result["schema_version"] == "aimontage.blueprint_draft.v1"
    assert result["status"] == "evidence_aligned_draft"
    assert len(result["shots"]) == 2
    assert result["shots"][0]["visual_description"] is None
    assert result["shots"][0]["source_frame_interval"]["semantics"] == "[start_frame_no, end_frame_no)"
    assert result["audio"]["spoken_transcript"] is None
    assert result["acceptance"]["music_only_transcript_excluded"] is True
    assert result["acceptance"]["creative_blueprint_ready"] is False


def test_rejects_hash_mismatch_and_music_only_transcript_leak():
    visual, timeline, audio = fixture()
    timeline["source"]["sha256"] = "different"
    with pytest.raises(ValueError, match="same source"):
        build_blueprint_draft(visual, timeline, audio)
    visual, timeline, audio = fixture()
    audio["transcript_included_in_blueprint"] = True
    with pytest.raises(ValueError, match="cannot include"):
        build_blueprint_draft(visual, timeline, audio)


def test_rejects_non_contiguous_scene_intervals():
    visual, timeline, audio = fixture()
    visual["normalized"]["scenes"][1]["start_seconds"] = 1.1
    with pytest.raises(ValueError, match="contiguous"):
        build_blueprint_draft(visual, timeline, audio)

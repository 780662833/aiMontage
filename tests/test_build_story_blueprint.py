from __future__ import annotations

import pytest

from scripts.build_story_blueprint import build_story_blueprint


def event_draft():
    return {
        "schema_version": "aimontage.l2_event_timeline.v2",
        "source": {"path": "a.mp4", "sha256": "abc123", "duration_seconds": 4.0},
        "keyframe_evidence": [
            {"evidence_id": "kf-0", "timestamp_seconds": 0.5, "image_path": "frames/0.jpg"},
            {"evidence_id": "kf-1", "timestamp_seconds": 2.5, "image_path": "frames/1.jpg"},
            {"evidence_id": "kf-2", "timestamp_seconds": 3.5, "image_path": "frames/2.jpg"},
        ],
        "events": [
            {
                "event_id": "OM-SCENE-001",
                "summary": "Person enters",
                "candidate_intervals": [{"start_seconds": 0.0, "end_seconds": 2.0}],
            },
            {
                "event_id": "OM-SCENE-002",
                "summary": None,
                "candidate_intervals": [{"start_seconds": 2.0, "end_seconds": 4.0}],
            },
        ],
    }


def test_maps_scene_time_candidates_and_keyframe_evidence_without_inventing_semantics():
    result = build_story_blueprint(event_draft())

    assert result["schema_version"] == "aimontage.story_blueprint.v1"
    assert result["source"]["sha256"] == "abc123"
    assert result["validation"]["event_count"] == 2
    assert result["validation"]["events_with_time_candidates"] == 2
    assert result["validation"]["events_semantically_verified"] == 0
    assert result["validation"]["ready_for_remake_plan"] is False
    assert result["events"][0]["time_candidate"]["start_seconds"] == 0.0
    assert result["events"][0]["evidence_ids"] == ["kf-0"]
    assert result["events"][1]["evidence_ids"] == ["kf-1", "kf-2"]
    assert result["events"][0]["action"] is None
    assert result["events"][0]["actor_id"] is None
    assert result["events"][0]["reaction_to"] == []


def test_rejects_unknown_schema():
    data = event_draft()
    data["schema_version"] = "other"
    with pytest.raises(ValueError, match="Unsupported event draft schema"):
        build_story_blueprint(data)


def test_rejects_missing_source_hash():
    data = event_draft()
    data["source"]["sha256"] = ""
    with pytest.raises(ValueError, match="source.sha256"):
        build_story_blueprint(data)


def test_invalid_interval_does_not_become_verified_timing():
    data = event_draft()
    data["events"][0]["candidate_intervals"] = [{"start_seconds": 2.0, "end_seconds": 1.0}]
    result = build_story_blueprint(data)
    assert result["events"][0]["time_candidate"]["status"] == "missing"
    assert result["events"][0]["evidence_ids"] == []

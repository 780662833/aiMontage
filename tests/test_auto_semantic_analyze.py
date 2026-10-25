from __future__ import annotations

import pytest

from scripts.auto_semantic_analyze import build_auto_review


def packet():
    return {
        "schema_version": "aimontage.story_evidence_packet.v1",
        "source": {"sha256": "abc123", "path": "a.mp4", "duration_seconds": 2.0},
        "events": [{
            "event_id": "OM-SCENE-001",
            "linked_dense_samples": [
                {"sample_index": 0, "timestamp_seconds": 0.0, "frame_no": 0,
                 "relative_path": "frames/0.jpg", "image_sha256": "img0", "association_status": "aligned"},
                {"sample_index": 1, "timestamp_seconds": 1.0, "frame_no": 30,
                 "relative_path": "frames/1.jpg", "image_sha256": "img1", "association_status": "aligned"},
            ],
        }],
    }


def model_result():
    return {"model_name": "test-vision", "events": [{
        "start_seconds": 0.0,
        "end_seconds": 1.5,
        "visible_entities": ["woman", "banana"],
        "observable_actions": ["holds banana"],
        "before_state": "banana in hand",
        "after_state": "banana remains in hand",
        "cause_and_reaction": None,
        "story_function": "setup",
        "must_preserve": ["show the banana"],
        "uncertain_or_unobservable": [],
        "confidence": 0.82,
        "evidence_sample_indices": [0, 1],
        "summary": "A woman holds a banana.",
    }]}


def test_builds_traceable_unapproved_auto_draft():
    result = build_auto_review(packet(), model_result())
    event = result["events"][0]
    assert result["schema_version"] == "aimontage.semantic_review_template.v1"
    assert event["review"]["status"] == "needs_review"
    assert event["review"]["automation_status"] == "draft_not_approved"
    assert event["review"]["evidence_sample_indices"] == [0, 1]
    assert result["validation"]["ready_for_edit_plan"] is False


def test_rejects_unavailable_evidence_indices():
    value = model_result()
    value["events"][0]["evidence_sample_indices"] = [99]
    with pytest.raises(ValueError, match="missing or invalid sample indices"):
        build_auto_review(packet(), value)


def test_rejects_event_beyond_source_duration():
    value = model_result()
    value["events"][0]["end_seconds"] = 3.0
    with pytest.raises(ValueError, match="beyond source duration"):
        build_auto_review(packet(), value)


def test_rejects_empty_events():
    value = model_result()
    value["events"] = []
    with pytest.raises(ValueError, match="no semantic events"):
        build_auto_review(packet(), value)

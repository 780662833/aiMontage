from __future__ import annotations

import pytest

from scripts.build_shot_edit_plan import build_shot_edit_plan


def reviewed_doc():
    return {
        "schema_version": "aimontage.semantic_review_template.v1",
        "source": {"sha256": "abc123", "path": "a.mp4", "duration_seconds": 2.0},
        "events": [{
            "event_id": "EV-1",
            "candidate_interval": {"start_seconds": 0.0, "end_seconds": 1.0},
            "evidence": [{"sample_index": 0}, {"sample_index": 1}],
            "review": {
                "status": "reviewed",
                "visible_entities": ["woman", "banana"],
                "observable_actions": ["offers banana"],
                "before_state": "banana held in hand",
                "after_state": "banana accepted",
                "cause_and_reaction": "offer prompts acceptance",
                "story_function": "setup",
                "must_preserve": ["offer is visible"],
                "uncertain_or_unobservable": [],
                "confidence": 0.9,
                "evidence_sample_indices": [0, 1],
            },
        }],
    }


def test_builds_ordered_9_16_shot_plan_from_reviewed_evidence():
    result = build_shot_edit_plan(reviewed_doc())
    assert result["schema_version"] == "aimontage.shot_edit_plan.v1"
    assert result["output_spec"]["aspect_ratio"] == "9:16"
    assert result["shots"][0]["source_range"]["duration_seconds"] == 1.0
    assert result["shots"][0]["story"]["evidence_sample_indices"] == [0, 1]
    assert result["validation"]["ready_for_render"] is False


def test_blocks_unreviewed_semantics():
    value = reviewed_doc()
    value["events"][0]["review"]["status"] = "needs_review"
    with pytest.raises(ValueError, match="review.status must be 'reviewed'"):
        build_shot_edit_plan(value)


def test_blocks_evidence_indices_not_linked_to_event():
    value = reviewed_doc()
    value["events"][0]["review"]["evidence_sample_indices"] = [99]
    with pytest.raises(ValueError, match="must exist in this event's evidence"):
        build_shot_edit_plan(value)


def test_blocks_missing_preservation_criteria():
    value = reviewed_doc()
    value["events"][0]["review"]["must_preserve"] = []
    with pytest.raises(ValueError, match="must_preserve"):
        build_shot_edit_plan(value)


def test_rejects_wrong_schema():
    value = reviewed_doc()
    value["schema_version"] = "other"
    with pytest.raises(ValueError, match="semantic review schema"):
        build_shot_edit_plan(value)

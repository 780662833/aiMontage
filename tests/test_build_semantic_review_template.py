from __future__ import annotations

import pytest

from scripts.build_semantic_review_template import build_review_template


def packet():
    return {
        "schema_version": "aimontage.story_evidence_packet.v1",
        "source": {"sha256": "abc123", "path": "a.mp4", "duration_seconds": 2.0},
        "events": [{
            "event_id": "OM-SCENE-001",
            "candidate_interval": {"start_seconds": 0.0, "end_seconds": 1.0, "status": "candidate_only"},
            "upstream_summary": None,
            "scene_signals": {"motion_type": "motion_clip"},
            "linked_dense_samples": [{
                "sample_index": 0, "timestamp_seconds": 0.0, "frame_no": 0,
                "relative_path": "frames/0.jpg", "image_sha256": "img0",
                "association_status": "aligned",
            }],
        }],
    }


def test_builds_review_template_with_traceable_evidence_and_blank_semantics():
    result = build_review_template(packet())
    event = result["events"][0]
    assert result["schema_version"] == "aimontage.semantic_review_template.v1"
    assert event["evidence"][0]["sample_index"] == 0
    assert event["review"]["status"] == "needs_review"
    assert event["review"]["observable_actions"] == []
    assert event["review"]["confidence"] is None
    assert result["validation"]["ready_for_edit_plan"] is False


def test_rejects_wrong_packet_schema():
    value = packet()
    value["schema_version"] = "other"
    with pytest.raises(ValueError, match="evidence packet schema"):
        build_review_template(value)


def test_rejects_missing_source_hash():
    value = packet()
    value["source"]["sha256"] = ""
    with pytest.raises(ValueError, match="source.sha256"):
        build_review_template(value)

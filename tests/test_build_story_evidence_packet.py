from __future__ import annotations

import pytest

from scripts.build_story_evidence_packet import build_packet


def fixtures():
    event_draft = {
        "schema_version": "aimontage.l2_event_timeline.v2",
        "source": {"sha256": "abc123", "path": "a.mp4", "duration_seconds": 2.0},
        "events": [
            {
                "event_id": "OM-SCENE-001",
                "summary": "Scene one",
                "scene_signals": {"motion_type": "walking"},
                "candidate_intervals": [{"start_seconds": 0.0, "end_seconds": 1.0, "source": "OpenMontage"}],
            },
            {
                "event_id": "OM-SCENE-002",
                "summary": None,
                "scene_signals": {},
                "candidate_intervals": [{"start_seconds": 1.0, "end_seconds": 2.0}],
            },
        ],
    }
    dense = {
        "schema_version": "aimontage.dense_frame_evidence.v1",
        "source": {"sha256": "abc123", "path": "a.mp4"},
        "samples": [
            {"sample_index": 2, "source_pts_time": 1.5, "frame_no": 45, "relative_path": "frames/2.jpg",
             "image_sha256": "img2", "source_sha256": "abc123", "association_status": "aligned"},
            {"sample_index": 0, "source_pts_time": 0.0, "frame_no": 0, "relative_path": "frames/0.jpg",
             "image_sha256": "img0", "source_sha256": "abc123", "association_status": "aligned"},
            {"sample_index": 1, "source_pts_time": 0.5, "frame_no": 15, "relative_path": "frames/1.jpg",
             "image_sha256": "img1", "source_sha256": "abc123", "association_status": "aligned"},
        ],
    }
    motion = {
        "source_sha256": "abc123",
        "intervals": [
            {"start_seconds": 0.5, "end_seconds": 1.0, "motion_candidate": True},
            {"start_seconds": 1.0, "end_seconds": 1.5, "motion_candidate": False},
        ],
    }
    return event_draft, dense, motion


def test_links_samples_by_source_timestamp_and_sorts_chronologically():
    event_draft, dense, motion = fixtures()
    result = build_packet(event_draft, dense, motion)

    assert result["schema_version"] == "aimontage.story_evidence_packet.v1"
    assert result["sampling"]["chronological"] is True
    assert [x["sample_index"] for x in result["events"][0]["linked_dense_samples"]] == [0, 1]
    assert [x["sample_index"] for x in result["events"][1]["linked_dense_samples"]] == [2]
    assert result["events"][0]["semantic_review"]["action"] is None
    assert result["validation"]["semantic_event_count"] == 0
    assert len(result["motion_candidates"]) == 1


def test_rejects_source_hash_mismatch():
    event_draft, dense, _ = fixtures()
    dense["source"]["sha256"] = "different"
    with pytest.raises(ValueError, match="Source SHA-256 mismatch"):
        build_packet(event_draft, dense)


def test_rejects_sample_hash_mismatch():
    event_draft, dense, _ = fixtures()
    dense["samples"][0]["source_sha256"] = "different"
    with pytest.raises(ValueError, match="sample 2 source SHA-256"):
        build_packet(event_draft, dense)


def test_rejects_duplicate_sample_indices():
    event_draft, dense, _ = fixtures()
    dense["samples"][1]["sample_index"] = 2
    with pytest.raises(ValueError, match="unique integer"):
        build_packet(event_draft, dense)


def test_rejects_motion_report_from_different_source():
    event_draft, dense, motion = fixtures()
    motion["source_sha256"] = "different"
    with pytest.raises(ValueError, match="motion report"):
        build_packet(event_draft, dense, motion)


def test_rejects_unsupported_schemas():
    event_draft, dense, _ = fixtures()
    dense["schema_version"] = "other"
    with pytest.raises(ValueError, match="dense evidence schema"):
        build_packet(event_draft, dense)

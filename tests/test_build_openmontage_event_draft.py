from __future__ import annotations

import pytest

from scripts.build_openmontage_event_draft import build_event_draft


def fixtures():
    brief = {
        "source": {"duration_seconds": 4.0},
        "content_analysis": {
            "summary": "A person enters, then turns.",
            "topics": ["movement"],
            "target_audience": "general",
        },
        "structure_analysis": {
            "pacing_profile": "moderate",
            "scenes": [
                {
                    "scene_index": 0, "start_time": 0.0, "end_time": 2.0,
                    "description": "A person enters.", "visual_type": "human",
                    "energy_level": "low", "motion_type": "walking", "flow_variance": 0.2,
                },
                {
                    "scene_index": 1, "start_time": 2.0, "end_time": 4.0,
                    "description": "The person turns.", "visual_type": "human",
                    "energy_level": "medium", "motion_type": "turning", "flow_variance": 1.4,
                },
            ],
        },
        "keyframes": [
            {"timestamp": 0.5, "image_path": "keyframes/0001.jpg", "description": "Person at doorway"},
            {"timestamp": 2.5, "image_path": "keyframes/0002.jpg"},
        ],
    }
    manifest = {
        "status": "passed",
        "source": {"path": "input.mp4", "sha256": "abc123"},
        "validation": {"official_brief_shape_valid": True},
        "upstream": {
            "repository": "https://github.com/calesthio/OpenMontage",
            "tool": "video_analyzer",
            "revision": "deadbeef",
        },
    }
    return brief, manifest


def test_preserves_upstream_context_scene_metadata_and_keyframes():
    brief, manifest = fixtures()
    result = build_event_draft(brief, manifest)

    assert result["schema_version"] == "aimontage.l2_event_timeline.v2"
    assert result["source"]["sha256"] == "abc123"
    assert result["validation"]["event_count"] == 2
    assert result["validation"]["verified_event_count"] == 0
    assert result["validation"]["ready_for_blueprint"] is False
    assert result["upstream_context"]["summary"] == "A person enters, then turns."
    assert result["upstream_context"]["topics"] == ["movement"]
    assert result["events"][0]["summary"] == "A person enters."
    assert result["events"][0]["user_asserted_summary"] is None
    assert result["events"][0]["scene_signals"]["motion_type"] == "walking"
    assert result["events"][0]["upstream_scene"] == brief["structure_analysis"]["scenes"][0]
    assert result["events"][0]["start_seconds"] is None
    assert result["events"][0]["candidate_intervals"][0]["start_seconds"] == 0.0
    assert result["events"][0]["evidence"][0]["json_pointer"] == "/structure_analysis/scenes/0"
    assert result["validation"]["keyframe_evidence_count"] == 2
    assert result["keyframe_evidence"][0]["timestamp_seconds"] == 0.5
    assert result["keyframe_evidence"][0]["json_pointer"] == "/keyframes/0"


def test_empty_upstream_scene_description_is_not_invented():
    brief, manifest = fixtures()
    brief["structure_analysis"]["scenes"][0]["description"] = "   "

    result = build_event_draft(brief, manifest)

    assert result["events"][0]["summary"] is None
    assert result["events"][0]["summary_source"] is None
    assert result["validation"]["has_scene_descriptions"] == 1
    assert result["upstream_context"]["summary"] == "A person enters, then turns."


def test_rejects_invalid_scene_interval():
    brief, manifest = fixtures()
    brief["structure_analysis"]["scenes"][0]["end_time"] = 0.0
    with pytest.raises(ValueError, match="invalid interval"):
        build_event_draft(brief, manifest)


def test_rejects_invalid_source_manifest():
    brief, manifest = fixtures()
    manifest["source"]["sha256"] = ""
    with pytest.raises(ValueError, match="source.sha256"):
        build_event_draft(brief, manifest)


def test_preserves_valid_scene_interval_when_brief_duration_disagrees():
    brief, manifest = fixtures()
    brief["structure_analysis"]["scenes"][1]["end_time"] = 4.5

    result = build_event_draft(brief, manifest)

    assert result["events"][1]["candidate_intervals"][0]["end_seconds"] == 4.5
    assert result["events"][1]["end_seconds"] is None
    assert result["validation"]["ready_for_blueprint"] is False
    assert any("scene[1] end_time (4.5)" in warning for warning in result["validation"]["warnings"])


def test_microsecond_duration_mismatch_is_reported_as_precision_tolerance():
    brief, manifest = fixtures()
    brief["source"]["duration_seconds"] = 4.0
    brief["structure_analysis"]["scenes"][1]["end_time"] = 4.00005

    result = build_event_draft(brief, manifest)

    assert result["events"][1]["candidate_intervals"][0]["end_seconds"] == 4.00005
    assert any("precision tolerance" in warning for warning in result["validation"]["warnings"])


def test_rejects_non_finite_timestamps():
    brief, manifest = fixtures()
    brief["structure_analysis"]["scenes"][0]["start_time"] = float("nan")

    with pytest.raises(ValueError, match="finite numeric"):
        build_event_draft(brief, manifest)

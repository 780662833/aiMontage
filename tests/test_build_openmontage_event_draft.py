from __future__ import annotations

import pytest

from scripts.build_openmontage_event_draft import build_event_draft


def fixtures():
    brief = {
        "source": {"duration_seconds": 4.0},
        "structure_analysis": {
            "scenes": [
                {"scene_index": 0, "start_time": 0.0, "end_time": 2.0, "description": "A person enters."},
                {"scene_index": 1, "start_time": 2.0, "end_time": 4.0, "description": "The person turns."},
            ]
        },
    }
    manifest = {
        "status": "passed",
        "source": {"path": "input.mp4", "sha256": "abc123"},
        "validation": {"official_brief_shape_valid": True},
        "upstream": {"tool": "video_analyzer", "revision": "deadbeef"},
    }
    return brief, manifest


def test_scene_candidates_preserve_upstream_descriptions_but_do_not_verify_timing():
    brief, manifest = fixtures()
    result = build_event_draft(brief, manifest)

    assert result["schema_version"] == "aimontage.l2_event_timeline.v1"
    assert result["source"]["sha256"] == "abc123"
    assert result["validation"]["event_count"] == 2
    assert result["validation"]["verified_event_count"] == 0
    assert result["validation"]["ready_for_blueprint"] is False
    assert result["events"][0]["user_asserted_summary"] == "A person enters."
    assert result["events"][0]["start_seconds"] is None
    assert result["events"][0]["candidate_intervals"][0]["start_seconds"] == 0.0
    assert result["events"][0]["evidence"][0]["json_pointer"] == "/structure_analysis/scenes/0"


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

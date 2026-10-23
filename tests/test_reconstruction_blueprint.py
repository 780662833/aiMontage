import copy

import pytest

from aimontage.reconstruction_blueprint import build_reconstruction_candidate
from aimontage.render_spec import validate_render_spec
from aimontage.visual_review import build_visual_review_template


def inputs():
    sha = "abc"
    visual = {
        "fixture": {"path": "a.mp4", "sha256": sha},
        "normalized": {
            "scenes": [{"scene_index": 0, "start_seconds": 0.0, "end_seconds": 1.0,
                        "start_frame_no": 0, "end_frame_no": 30}],
            "sampled_frames": [
                {"frame_no": 0, "sample_timestamp_seconds": 0.0, "source_pts_time": 0.0,
                 "mapping_delta_seconds": 0.0, "relative_path": "frames/f0.jpg",
                 "image_sha256": "img0", "source_sha256": sha,
                 "association_key": {"source_sha256": sha, "frame_no": 0},
                 "association_status": "aligned"},
            ],
        },
    }
    blueprint = {
        "schema_version": "aimontage.blueprint_draft.v1",
        "status": "evidence_aligned_draft",
        "source": {"path": "a.mp4", "sha256": sha, "duration_seconds": 1.0},
        "audio": {"classification": "music_only", "spoken_transcript": None},
        "shots": [{
            "shot_id": "SHOT-001", "start_seconds": 0.0, "end_seconds": 1.0,
            "duration_seconds": 1.0,
            "source_frame_interval": {"start_frame_no": 0, "end_frame_no": 30,
                                      "semantics": "[start_frame_no, end_frame_no)"},
            "visual_description": None, "camera_motion": None, "edit_intent": None,
            "evidence_refs": ["scene_detect"], "semantic_status": "not_yet_annotated",
        }],
    }
    review = build_visual_review_template(visual, blueprint)
    a = review["shots"][0]["annotation"]
    a.update({
        "visual_description": "An animated adult stands behind a counter.",
        "subject": "One animated adult",
        "action": "Standing behind a counter.",
        "camera_motion": "No clear camera movement is observable in the sampled frame.",
        "composition": "Medium shot.",
        "lighting_and_color": "Soft indoor light.",
        "edit_intent": "Establish the scene.",
        "confidence": 0.85,
        "evidence_frame_nos": [0],
        "review_status": "reviewed",
        "annotator_note": "One sample; intermediate motion unknown.",
    })
    spec = {
        "schema_version": "aimontage.render_spec.v1",
        "output": {"width": 1080, "height": 1920, "aspect_ratio": "9:16",
                   "fps": 30, "container": "mp4", "video_codec": "h264",
                   "audio_codec": "aac", "duration_policy": "preserve_source"},
        "safe_area": {"top_pct": 8, "right_pct": 7, "bottom_pct": 14, "left_pct": 7},
        "subtitles": {"burn_in": False},
    }
    return blueprint, review, spec


def test_render_spec_rejects_bad_aspect_ratio_and_missing_audio_policy():
    _, _, spec = inputs()
    assert validate_render_spec(spec) == []
    bad = copy.deepcopy(spec)
    bad["output"]["width"] = 720
    assert any("dimensions do not match" in e for e in validate_render_spec(bad))


def test_builds_candidate_but_does_not_claim_render_readiness():
    blueprint, review, spec = inputs()
    result = build_reconstruction_candidate(blueprint, review, spec)
    assert result["schema_version"] == "aimontage.reconstruction_blueprint_candidate.v1"
    assert result["shots"][0]["semantic_status"] == "reviewed"
    assert result["shots"][0]["sampled_frame_evidence"][0]["frame_no"] == 0
    assert result["acceptance"]["visual_review_complete"] is True
    assert result["acceptance"]["render_ready"] is False
    assert result["acceptance"]["production_ready"] is False


def test_rejects_incomplete_review_or_source_mismatch():
    blueprint, review, spec = inputs()
    review["shots"][0]["annotation"]["review_status"] = "not_reviewed"
    with pytest.raises(ValueError, match="must be complete"):
        build_reconstruction_candidate(blueprint, review, spec)
    blueprint, review, spec = inputs()
    review["source"]["sha256"] = "different"
    with pytest.raises(ValueError, match="same source"):
        build_reconstruction_candidate(blueprint, review, spec)

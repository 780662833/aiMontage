import json
from pathlib import Path

import pytest

from scripts.apply_visual_annotations import apply_annotations
from aimontage.visual_review import build_visual_review_template
from aimontage.visual_review_validation import visual_review_completion


def template_and_annotations():
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
        "source": {"sha256": sha},
        "shots": [{"shot_id": "SHOT-001", "start_seconds": 0.0, "end_seconds": 1.0,
                   "source_frame_interval": {"start_frame_no": 0, "end_frame_no": 30,
                                             "semantics": "[start_frame_no, end_frame_no)"}}],
    }
    annotations = {
        "schema_version": "aimontage.visual_annotations.v1",
        "source_sha256": sha,
        "shots": [{
            "shot_id": "SHOT-001",
            "evidence_frame_nos": [0],
            "visual_description": "A person stands behind a counter.",
            "subject": "One animated adult",
            "action": "Standing behind a counter.",
            "camera_motion": "No clear motion is visible in the sampled frame.",
            "composition": "Medium shot.",
            "lighting_and_color": "Soft indoor lighting.",
            "edit_intent": "Establish the scene.",
            "confidence": 0.8,
            "review_status": "reviewed",
            "annotator_note": "Single sampled frame; temporal action remains uncertain.",
        }],
    }
    return build_visual_review_template(visual, blueprint), annotations


def test_apply_annotations_yields_review_complete_valid_output():
    template, annotations = template_and_annotations()
    result = apply_annotations(template, annotations)
    completion = visual_review_completion(result)
    assert completion["valid"] is True
    assert completion["review_complete"] is True
    assert result["shots"][0]["annotation"]["evidence_frame_nos"] == [0]


def test_rejects_source_mismatch_or_unknown_shot_id():
    template, annotations = template_and_annotations()
    annotations["source_sha256"] = "other"
    with pytest.raises(ValueError, match="does not match"):
        apply_annotations(template, annotations)
    template, annotations = template_and_annotations()
    annotations["shots"][0]["shot_id"] = "SHOT-404"
    with pytest.raises(ValueError, match="shot IDs must match"):
        apply_annotations(template, annotations)

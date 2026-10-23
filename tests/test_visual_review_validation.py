import copy

from aimontage.visual_review import build_visual_review_template
from aimontage.visual_review_validation import validate_visual_review, visual_review_completion


def make_review():
    sha = "abc"
    visual = {
        "fixture": {"path": "a.mp4", "sha256": sha},
        "normalized": {
            "scenes": [
                {"scene_index": 0, "start_seconds": 0.0, "end_seconds": 1.0,
                 "start_frame_no": 0, "end_frame_no": 30},
            ],
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
        "shots": [{
            "shot_id": "SHOT-001", "start_seconds": 0.0, "end_seconds": 1.0,
            "source_frame_interval": {"start_frame_no": 0, "end_frame_no": 30,
                                      "semantics": "[start_frame_no, end_frame_no)"},
        }],
    }
    return build_visual_review_template(visual, blueprint)


def test_template_is_valid_but_not_review_complete():
    review = make_review()
    assert validate_visual_review(review) == []
    completion = visual_review_completion(review)
    assert completion["valid"] is True
    assert completion["review_complete"] is False
    assert completion["production_ready"] is False


def test_reviewed_annotation_requires_fields_confidence_and_linked_frames():
    review = make_review()
    annotation = review["shots"][0]["annotation"]
    annotation.update({
        "visual_description": "A person stands behind a counter.",
        "subject": "Two animated adults",
        "action": "One adult holds a banana while the other reacts.",
        "camera_motion": "No clear camera movement is observable in the sampled frames.",
        "composition": "Medium two-shot with both characters centered above a foreground counter.",
        "lighting_and_color": "Soft even indoor lighting with muted green background and blue clothing.",
        "edit_intent": "Establish the interaction before a later reaction close-up.",
        "confidence": 0.86,
        "evidence_frame_nos": [0],
        "review_status": "reviewed",
    })
    assert validate_visual_review(review) == []
    assert visual_review_completion(review)["review_complete"] is True


def test_rejects_evidence_outside_shot_or_unlinked_annotation_frame():
    review = make_review()
    review["shots"][0]["evidence_frames"][0]["frame_no"] = 40
    errors = validate_visual_review(review)
    assert any("outside its shot interval" in e for e in errors)
    review = make_review()
    review["shots"][0]["annotation"].update({
        "visual_description": "Visible scene.",
        "subject": "Person",
        "action": "Standing.",
        "camera_motion": "Static",
        "composition": "Medium shot.",
        "lighting_and_color": "Soft light.",
        "edit_intent": "Establish scene.",
        "confidence": 0.8,
        "evidence_frame_nos": [99],
        "review_status": "reviewed",
    })
    assert any("unlinked evidence frame 99" in e for e in validate_visual_review(review))

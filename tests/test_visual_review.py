import pytest

from aimontage.blueprint import build_blueprint_draft
from aimontage.visual_review import build_visual_review_template


def fixtures():
    sha = "abc"
    visual = {
        "fixture": {"path": "a.mp4", "sha256": sha},
        "normalized": {
            "scenes": [
                {"scene_index": 0, "start_seconds": 0.0, "end_seconds": 1.0,
                 "start_frame_no": 0, "end_frame_no": 30},
                {"scene_index": 1, "start_seconds": 1.0, "end_seconds": 2.0,
                 "start_frame_no": 30, "end_frame_no": 60},
            ],
            "sampled_frames": [
                {"frame_no": 0, "sample_timestamp_seconds": 0.0, "source_pts_time": 0.0,
                 "mapping_delta_seconds": 0.0, "relative_path": "frames/frame_0001.jpg",
                 "image_sha256": "img0", "source_sha256": sha,
                 "association_key": {"source_sha256": sha, "frame_no": 0},
                 "association_status": "aligned"},
                {"frame_no": 30, "sample_timestamp_seconds": 1.0, "source_pts_time": 1.0,
                 "mapping_delta_seconds": 0.0, "relative_path": "frames/frame_0002.jpg",
                 "image_sha256": "img1", "source_sha256": sha,
                 "association_key": {"source_sha256": sha, "frame_no": 30},
                 "association_status": "aligned"},
            ],
        },
    }
    timeline = {"source": {"sha256": sha, "duration_seconds": 2.0}}
    audio = {
        "classification": "music_only",
        "blueprint_audio_policy": "music_timeline_only_no_spoken_transcript",
        "transcript_included_in_blueprint": False,
        "transcript_status": "NOT_APPLICABLE",
    }
    return visual, build_blueprint_draft(visual, timeline, audio)


def test_maps_frames_to_half_open_shot_intervals_and_leaves_semantics_blank():
    visual, blueprint = fixtures()
    result = build_visual_review_template(visual, blueprint)
    assert result["schema_version"] == "aimontage.visual_review_template.v1"
    assert [len(s["evidence_frames"]) for s in result["shots"]] == [1, 1]
    assert result["shots"][1]["evidence_frames"][0]["frame_no"] == 30
    assert result["shots"][0]["annotation"]["visual_description"] is None
    assert result["validation"]["review_complete"] is False


def test_rejects_different_source_and_unaligned_frames():
    visual, blueprint = fixtures()
    blueprint["source"]["sha256"] = "other"
    with pytest.raises(ValueError, match="same source"):
        build_visual_review_template(visual, blueprint)
    visual, blueprint = fixtures()
    visual["normalized"]["sampled_frames"][0]["association_status"] = "ambiguous-neighbor"
    with pytest.raises(ValueError, match="not aligned"):
        build_visual_review_template(visual, blueprint)

import copy

from aimontage.blueprint import build_blueprint_draft
from aimontage.blueprint_validation import require_valid_blueprint_draft, validate_blueprint_draft


def make_draft():
    visual = {
        "fixture": {"path": "a.mp4", "sha256": "abc"},
        "normalized": {"scenes": [
            {"scene_index": 0, "start_seconds": 0.0, "end_seconds": 1.0,
             "start_frame_no": 0, "end_frame_no": 30},
            {"scene_index": 1, "start_seconds": 1.0, "end_seconds": 2.0,
             "start_frame_no": 30, "end_frame_no": 60},
        ]},
    }
    timeline = {"source": {"sha256": "abc", "duration_seconds": 2.0}}
    audio = {
        "classification": "music_only",
        "blueprint_audio_policy": "music_timeline_only_no_spoken_transcript",
        "transcript_included_in_blueprint": False,
        "transcript_status": "NOT_APPLICABLE",
    }
    return build_blueprint_draft(visual, timeline, audio)


def test_validates_generated_evidence_aligned_draft():
    draft = make_draft()
    assert validate_blueprint_draft(draft) == []
    require_valid_blueprint_draft(draft)


def test_rejects_music_only_transcript_leak():
    draft = make_draft()
    draft["audio"]["spoken_transcript"] = "hallucinated words"
    assert any("must not contain a spoken transcript" in error
               for error in validate_blueprint_draft(draft))


def test_rejects_noncontiguous_timing_duplicate_ids_and_missing_evidence():
    draft = copy.deepcopy(make_draft())
    draft["shots"][1]["start_seconds"] = 1.25
    draft["shots"][1]["shot_id"] = draft["shots"][0]["shot_id"]
    draft["shots"][1]["evidence_refs"] = []
    errors = validate_blueprint_draft(draft)
    assert any("contiguous" in error for error in errors)
    assert any("duplicate shot_id" in error for error in errors)
    assert any("requires evidence_refs" in error for error in errors)


def test_rejects_semantics_filled_without_annotation_status():
    draft = make_draft()
    draft["shots"][0]["visual_description"] = "A person runs."
    assert any("unreviewed visual_description" in error
               for error in validate_blueprint_draft(draft))

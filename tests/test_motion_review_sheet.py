import json

from scripts.build_motion_review_sheet import build


def test_motion_review_sheet_embeds_candidate_frames(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"fake-jpeg")
    (tmp_path / "b.jpg").write_bytes(b"fake-jpeg-2")
    evidence = {
        "source": {"sha256": "same"},
        "samples": [
            {"sample_index": 0, "source_pts_time": 0.0, "frame_no": 0, "relative_path": "a.jpg"},
            {"sample_index": 1, "source_pts_time": 0.25, "frame_no": 8, "relative_path": "b.jpg"},
        ],
    }
    motion = {
        "source_sha256": "same", "interval_count": 1,
        "intervals": [{
            "start_sample_index": 0, "end_sample_index": 1,
            "start_seconds": 0.0, "end_seconds": 0.25,
            "mean_flow_magnitude_px": 2.0, "p90_flow_magnitude_px": 4.0,
            "motion_candidate": True,
        }],
    }
    ep, mp, out = tmp_path / "dense_frame_evidence.json", tmp_path / "motion.json", tmp_path / "review.html"
    ep.write_text(json.dumps(evidence), encoding="utf-8")
    mp.write_text(json.dumps(motion), encoding="utf-8")
    result = build(ep, mp, out)
    content = out.read_text(encoding="utf-8")
    assert result["candidate_count"] == 1
    assert "data:image/jpeg;base64," in content
    assert "action motion" in content
    assert "Source SHA-256: same" in content


def test_motion_review_sheet_rejects_source_mismatch(tmp_path):
    ep, mp = tmp_path / "evidence.json", tmp_path / "motion.json"
    ep.write_text(json.dumps({"source": {"sha256": "a"}, "samples": []}), encoding="utf-8")
    mp.write_text(json.dumps({"source_sha256": "b", "interval_count": 0, "intervals": []}), encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="SHA-256"):
        build(ep, mp, tmp_path / "review.html")

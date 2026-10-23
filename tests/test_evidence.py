import json
from aimontage.evidence import make_evidence_record, write_json_atomic

def test_evidence_has_hash_raw_result_and_pts(tmp_path):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"fixture-media")
    raw = {"success": True, "data": {"duration_seconds": 1.0}}
    record = make_evidence_record(evidence_id="E0001", source_path=source,
        tool_name="audio_probe", tool_version="0.1.0", raw_result=raw,
        frame_no=12, source_pts_time=.4, relative_path="frames/frame_0012.jpg")
    assert len(record["source"]["sha256"]) == 64
    assert record["frame"]["source_pts_time"] == .4
    assert record["frame"]["path"] == "frames/frame_0012.jpg"
    assert record["raw_result"] == raw
    target = tmp_path / "evidence.json"
    write_json_atomic(target, record)
    assert json.loads(target.read_text())["evidence_id"] == "E0001"

from aimontage.timestamp_audit import audit_frame_rows

def test_aligned_rows():
    rows = [{"frame_no": i, "source_pts_time": i * .1, "decoder_pts_time": i * .1} for i in range(3)]
    result = audit_frame_rows(rows)
    assert [r["audit"]["status"] for r in result] == ["aligned"] * 3
    assert all(r["audit"]["source_pts_time_authoritative"] for r in result)

def test_reordered_rows_are_not_sorted():
    rows = [{"frame_no": n, "source_pts_time": t} for n, t in [(0, 0.0), (1, .1), (2, .2), (9, .9), (4, .4)]]
    result = audit_frame_rows(rows)
    assert [r["frame_no"] for r in result] == [0, 1, 2, 9, 4]
    assert [r["audit"]["status"] for r in result] == ["aligned", "aligned", "aligned", "aligned", "reorder"]

def test_missing_pts_is_ambiguous():
    assert audit_frame_rows([{"frame_no": 0, "source_pts_time": None}])[0]["audit"]["status"] == "ambiguous-neighbor"

def test_duplicate_frame_no_is_ambiguous():
    rows = [{"frame_no": 3, "source_pts_time": 0.0}, {"frame_no": 3, "source_pts_time": .1}]
    assert all(r["audit"]["status"] == "ambiguous-neighbor" for r in audit_frame_rows(rows))

def test_duplicate_pts_is_ambiguous_neighbor():
    rows = [{"frame_no": 0, "source_pts_time": 0.0}, {"frame_no": 1, "source_pts_time": 0.0}]
    assert audit_frame_rows(rows)[1]["audit"]["status"] == "ambiguous-neighbor"

from aimontage.real_video import build_normalized_sampled_frames, build_normalized_scenes


def test_sampled_frame_has_source_hash_pts_relative_path_and_image_hash(tmp_path):
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    image = frames_dir / "frame_0001.jpg"
    image.write_bytes(b"fake-jpeg")
    result = {"data": {"frames": [{
        "index": 0, "timestamp_seconds": 0.0, "path": str(image),
    }]}}
    rows = build_normalized_sampled_frames(result, [0.0, 1 / 30, 2 / 30], "a" * 64, tmp_path)
    assert rows[0]["frame_no"] == 0
    assert rows[0]["source_pts_time"] == 0.0
    assert rows[0]["relative_path"] == "frames/frame_0001.jpg"
    assert rows[0]["source_sha256"] == "a" * 64
    assert len(rows[0]["image_sha256"]) == 64
    assert rows[0]["association_status"] == "aligned"


def test_sampled_frame_rejects_ambiguous_mapping(tmp_path):
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    image = frames_dir / "frame_0001.jpg"
    image.write_bytes(b"fake-jpeg")
    result = {"data": {"frames": [{
        "index": 0, "timestamp_seconds": 0.5, "path": str(image),
    }]}}
    import pytest
    with pytest.raises(RuntimeError, match="reliably associated"):
        build_normalized_sampled_frames(result, [0.0, 1.0], "a" * 64, tmp_path)


def test_scenes_use_half_open_contiguous_frame_intervals():
    result = {"data": {"scenes": [
        {"index": 0, "start_seconds": 0.0, "end_seconds": 1.0},
        {"index": 1, "start_seconds": 1.0, "end_seconds": 2.0},
    ]}}
    scenes = build_normalized_scenes(result, [0.0, 0.5, 1.0, 1.5], "b" * 64)
    assert (scenes[0]["start_frame_no"], scenes[0]["end_frame_no"]) == (0, 2)
    assert (scenes[1]["start_frame_no"], scenes[1]["end_frame_no"]) == (2, 4)
    assert scenes[0]["frame_interval_semantics"] == "[start_frame_no, end_frame_no)"

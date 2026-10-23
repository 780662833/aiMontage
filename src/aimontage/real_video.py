"""aiMontage real-video normalization helpers."""

def nearest_frame_no(pts_times: list[float], target: float) -> tuple[int, float]:
    """Return nearest source frame and absolute time delta; ties prefer earlier frame."""
    pos = bisect_left(pts_times, target)
    candidates = [i for i in (pos - 1, pos) if 0 <= i < len(pts_times)]
    if not candidates:
        raise ValueError("No source PTS rows available")
    index = min(candidates, key=lambda i: (abs(pts_times[i] - target), pts_times[i]))
    return index, abs(pts_times[index] - target)


def scene_end_frame_no(pts_times: list[float], end_seconds: float) -> int:
    """Convert a scene end timestamp to a half-open source frame index."""
    return min(bisect_left(pts_times, end_seconds), len(pts_times))


def file_sha256(path: Path) -> str:
    return sha256_file(path)


def build_normalized_scenes(scene_result: dict[str, Any], pts_times: list[float],
                            source_sha256: str) -> list[dict[str, Any]]:
    scenes = scene_result["data"].get("scenes", [])
    normalized = []
    for scene in scenes:
        start = float(scene["start_seconds"])
        end = float(scene["end_seconds"])
        if end <= start:
            raise RuntimeError(f"Invalid scene interval: {scene}")
        start_frame_no, start_delta = nearest_frame_no(pts_times, start)
        end_frame_no = scene_end_frame_no(pts_times, end)
        if end_frame_no <= start_frame_no:
            raise RuntimeError(f"Scene maps to empty source frame interval: {scene}")
        normalized.append({
            "scene_index": int(scene.get("index", len(normalized))),
            "start_seconds": start,
            "end_seconds": end,
            "duration_seconds": round(end - start, 6),
            "start_frame_no": start_frame_no,
            "end_frame_no": end_frame_no,
            "frame_interval_semantics": "[start_frame_no, end_frame_no)",
            "start_boundary_mapping_delta_seconds": round(start_delta, 6),
            "source_sha256": source_sha256,
            "boundary_support": "scene_detector_time_mapped_to_source_pts",
        })
    if normalized:
        if normalized[0]["start_frame_no"] != 0:
            raise RuntimeError("First detected scene does not begin at source frame 0")
        for left, right in zip(normalized, normalized[1:]):
            if left["end_frame_no"] != right["start_frame_no"]:
                raise RuntimeError(f"Scene frame intervals are not contiguous: {left} -> {right}")
    return normalized


def build_normalized_sampled_frames(frame_result: dict[str, Any], pts_times: list[float],
                                    source_sha256: str, output_dir: Path) -> list[dict[str, Any]]:
    frames = frame_result["data"].get("frames", [])
    normalized = []
    for item in frames:
        sample_time = float(item["timestamp_seconds"])
        frame_no, delta = nearest_frame_no(pts_times, sample_time)
        raw_path = Path(item["path"])
        if not raw_path.is_absolute():
            raw_path = (output_dir / raw_path).resolve()
        if not raw_path.is_file():
            raise RuntimeError(f"Sampled frame listed by upstream does not exist: {raw_path}")
        try:
            relative_path = raw_path.relative_to(output_dir).as_posix()
        except ValueError as exc:
            raise RuntimeError(f"Sampled frame path escapes output directory: {raw_path}") from exc
        normalized.append({
            "sample_index": int(item.get("index", len(normalized))),
            "sample_timestamp_seconds": sample_time,
            "frame_no": frame_no,
            "source_pts_time": pts_times[frame_no],
            "mapping_delta_seconds": round(delta, 6),
            "relative_path": relative_path,
            "image_sha256": file_sha256(raw_path),
            "source_sha256": source_sha256,
            "association_key": {"source_sha256": source_sha256, "frame_no": frame_no},
            "association_status": "aligned" if delta <= 0.5 / 30.0 + 1e-6 else "ambiguous-neighbor",
        })
    if any(item["association_status"] != "aligned" for item in normalized):
        raise RuntimeError("At least one sampled image could not be reliably associated to a source frame")
    return normalized



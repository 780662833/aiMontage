"""Join visual scene evidence and music measurements on a shared source timeline."""
from __future__ import annotations

from typing import Any


def build_cross_modal_timeline(
    visual_bundle: dict[str, Any],
    music_bundle: dict[str, Any],
    *,
    duration_tolerance_seconds: float = 0.15,
) -> dict[str, Any]:
    """Normalize scene and audio events while retaining explicit evidence provenance."""
    if duration_tolerance_seconds < 0:
        raise ValueError("duration_tolerance_seconds must be non-negative")
    visual_fixture = visual_bundle.get("fixture", {})
    music_source = music_bundle.get("source", {})
    visual_sha = visual_fixture.get("sha256")
    music_sha = music_source.get("sha256")
    if not visual_sha or not music_sha:
        raise ValueError("Both evidence bundles must identify the source video by SHA-256")
    if visual_sha != music_sha:
        raise ValueError("Visual and audio evidence refer to different source files")

    scenes = visual_bundle.get("normalized", {}).get("scenes", [])
    if not scenes:
        raise ValueError("Visual evidence bundle contains no normalized scenes")
    measurement = music_bundle.get("measurement", {})
    music_duration = measurement.get("duration_seconds")
    if not isinstance(music_duration, (int, float)) or music_duration <= 0:
        raise ValueError("Music timeline must contain a positive measured duration")
    last_scene_end = max(float(scene["end_seconds"]) for scene in scenes)
    delta = abs(last_scene_end - float(music_duration))
    if delta > duration_tolerance_seconds:
        raise ValueError(
            f"Visual/audio duration mismatch ({last_scene_end:.4f}s vs "
            f"{float(music_duration):.4f}s; delta={delta:.4f}s)"
        )

    events: list[dict[str, Any]] = []
    for scene in scenes:
        start = float(scene["start_seconds"])
        end = float(scene["end_seconds"])
        if end <= start:
            raise ValueError(f"Invalid visual scene interval: {scene}")
        events.append({
            "event_id": f"visual-scene-{int(scene['scene_index']):04d}",
            "modality": "visual",
            "event_type": "scene",
            "start_seconds": round(start, 6),
            "end_seconds": round(end, 6),
            "frame_interval": {
                "start_frame_no": int(scene["start_frame_no"]),
                "end_frame_no": int(scene["end_frame_no"]),
                "semantics": "[start_frame_no, end_frame_no)",
            },
            "evidence_refs": [f"real-a-mp4:scene_detect", f"real-a-mp4:source-frame-pts-audit"],
            "confidence_status": "detector_candidate",
        })

    for index, onset in enumerate(music_bundle.get("candidate_onsets", [])):
        time_s = float(onset["time_seconds"])
        events.append({
            "event_id": f"audio-onset-{index:04d}",
            "modality": "audio",
            "event_type": "candidate_energy_onset",
            "start_seconds": round(time_s, 6),
            "end_seconds": round(time_s, 6),
            "energy_rise_db": onset.get("energy_rise_db"),
            "evidence_refs": ["music_timeline_evidence"],
            "confidence_status": "unverified_transient_not_a_beat",
        })

    for index, silence in enumerate(music_bundle.get("silence_intervals", [])):
        start, end = float(silence["start_seconds"]), float(silence["end_seconds"])
        events.append({
            "event_id": f"audio-silence-{index:04d}",
            "modality": "audio",
            "event_type": "threshold_silence",
            "start_seconds": round(start, 6),
            "end_seconds": round(end, 6),
            "evidence_refs": ["music_timeline_evidence"],
            "confidence_status": "threshold_based",
        })

    events.sort(key=lambda item: (item["start_seconds"], item["end_seconds"], item["event_id"]))
    return {
        "schema_version": "aimontage.cross_modal_timeline.v1",
        "source": {
            "sha256": visual_sha,
            "duration_seconds": round(last_scene_end, 6),
            "duration_difference_seconds": round(delta, 6),
        },
        "timebase": {
            "seconds": "source media timeline",
            "video_pts_authoritative": True,
            "frame_interval_semantics": "[start_frame_no, end_frame_no)",
        },
        "events": events,
        "validation": {
            "source_hashes_match": True,
            "duration_within_tolerance": True,
            "visual_scene_count": len(scenes),
            "audio_onset_candidate_count": len(music_bundle.get("candidate_onsets", [])),
            "audio_silence_interval_count": len(music_bundle.get("silence_intervals", [])),
        },
        "limitations": [
            "Audio energy transients are not verified musical beats.",
            "Scene boundaries are detector candidates, not semantic story boundaries.",
            "This timeline is evidence for Blueprint generation, not a finished creative Blueprint.",
        ],
    }

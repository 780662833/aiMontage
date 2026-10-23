"""Deterministic audio energy timeline for evidence-first video analysis.

This module measures decoded PCM energy. It does not classify music genres, infer mood,
or claim that energy peaks are musical beats.
"""
from __future__ import annotations

import math
import struct
from typing import Any


def analyze_pcm_s16le(
    pcm: bytes,
    *,
    sample_rate_hz: int = 16000,
    channels: int = 1,
    window_ms: int = 100,
    silence_threshold_dbfs: float = -45.0,
    onset_threshold_db: float = 8.0,
    onset_refractory_ms: int = 180,
) -> dict[str, Any]:
    """Build RMS, silence, and candidate energy-onset evidence from signed 16-bit PCM."""
    if sample_rate_hz <= 0 or channels <= 0 or window_ms <= 0:
        raise ValueError("sample_rate_hz, channels, and window_ms must be positive")
    if not math.isfinite(silence_threshold_dbfs) or not math.isfinite(onset_threshold_db):
        raise ValueError("thresholds must be finite")
    frame_bytes = channels * 2
    usable = len(pcm) - len(pcm) % frame_bytes
    sample_count = usable // 2
    if sample_count == 0:
        raise ValueError("PCM input contains no complete samples")
    values = struct.unpack("<" + "h" * sample_count, pcm[:usable])
    mono = []
    for i in range(0, len(values), channels):
        mono.append(sum(values[i:i + channels]) / channels)

    samples_per_window = max(1, round(sample_rate_hz * window_ms / 1000))
    energies: list[dict[str, float]] = []
    for start in range(0, len(mono), samples_per_window):
        chunk = mono[start:start + samples_per_window]
        if not chunk:
            continue
        rms = math.sqrt(sum(value * value for value in chunk) / len(chunk))
        dbfs = 20 * math.log10(max(rms / 32768.0, 1e-8))
        start_s = start / sample_rate_hz
        end_s = min((start + len(chunk)) / sample_rate_hz, len(mono) / sample_rate_hz)
        energies.append({
            "start_seconds": round(start_s, 4),
            "end_seconds": round(end_s, 4),
            "rms_dbfs": round(dbfs, 3),
        })

    duration = len(mono) / sample_rate_hz
    silent_flags = [item["rms_dbfs"] <= silence_threshold_dbfs for item in energies]
    silence_intervals = _merge_flags(silent_flags, energies, window_ms)

    candidate_onsets = []
    refractory_windows = max(1, round(onset_refractory_ms / window_ms))
    last_onset = -refractory_windows
    for i in range(1, len(energies) - 1):
        previous = energies[i - 1]["rms_dbfs"]
        current = energies[i]["rms_dbfs"]
        following = energies[i + 1]["rms_dbfs"]
        rise = current - previous
        if rise >= onset_threshold_db and current >= following and i - last_onset >= refractory_windows:
            candidate_onsets.append({
                "time_seconds": energies[i]["start_seconds"],
                "energy_rise_db": round(rise, 3),
                "kind": "candidate_energy_onset",
                "interpretation": "energy transient candidate; not a verified musical beat",
            })
            last_onset = i

    return {
        "schema_version": "aimontage.music_timeline.v1",
        "measurement": {
            "method": "RMS energy on decoded signed 16-bit PCM",
            "sample_rate_hz": sample_rate_hz,
            "channels": channels,
            "window_ms": window_ms,
            "duration_seconds": round(duration, 4),
            "silence_threshold_dbfs": silence_threshold_dbfs,
            "onset_threshold_db": onset_threshold_db,
            "onset_refractory_ms": onset_refractory_ms,
        },
        "summary": {
            "window_count": len(energies),
            "mean_rms_dbfs": round(sum(x["rms_dbfs"] for x in energies) / len(energies), 3),
            "min_rms_dbfs": min(x["rms_dbfs"] for x in energies),
            "max_rms_dbfs": max(x["rms_dbfs"] for x in energies),
            "silence_duration_seconds": round(sum(x["end_seconds"] - x["start_seconds"] for x, flag in zip(energies, silent_flags) if flag), 4),
            "candidate_energy_onset_count": len(candidate_onsets),
        },
        "energy_envelope": energies,
        "silence_intervals": silence_intervals,
        "candidate_onsets": candidate_onsets,
        "limitations": [
            "Energy thresholds are configurable and are not a music/speech classifier.",
            "Candidate onsets are energy transients, not verified beats or tempo.",
            "Silence is defined only by the configured RMS dBFS threshold.",
        ],
    }


def _merge_flags(flags: list[bool], rows: list[dict[str, float]], window_ms: int) -> list[dict[str, float]]:
    intervals = []
    start = None
    for i, flag in enumerate(flags + [False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            intervals.append({
                "start_seconds": rows[start]["start_seconds"],
                "end_seconds": rows[i - 1]["end_seconds"],
                "duration_seconds": round(rows[i - 1]["end_seconds"] - rows[start]["start_seconds"], 4),
                "threshold_based": True,
            })
            start = None
    return intervals

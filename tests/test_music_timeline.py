import math
import struct

import pytest

from aimontage.music_timeline import analyze_pcm_s16le


def pcm(values):
    return struct.pack("<" + "h" * len(values), *values)


def test_energy_envelope_silence_and_candidate_onsets_are_deterministic():
    # 0.4s silence, 0.4s low tone, then a sharp higher-energy burst and sustain.
    values = [0] * 6400 + [500] * 6400 + [12000] * 3200 + [10000] * 3200
    result = analyze_pcm_s16le(
        pcm(values), sample_rate_hz=16000, window_ms=100,
        silence_threshold_dbfs=-40, onset_threshold_db=8,
    )
    assert result["schema_version"] == "aimontage.music_timeline.v1"
    assert result["measurement"]["duration_seconds"] == 1.2
    assert result["summary"]["window_count"] == 12
    assert result["silence_intervals"][0]["start_seconds"] == 0.0
    assert result["silence_intervals"][0]["end_seconds"] == 0.4
    assert result["candidate_onsets"]
    assert all(item["kind"] == "candidate_energy_onset" for item in result["candidate_onsets"])
    assert "not a verified musical beat" in result["candidate_onsets"][0]["interpretation"]


def test_empty_pcm_rejected_and_partial_sample_bytes_ignored():
    with pytest.raises(ValueError):
        analyze_pcm_s16le(b"")
    result = analyze_pcm_s16le(pcm([1000, 1000]) + b"\x00", sample_rate_hz=1000, window_ms=1)
    assert result["measurement"]["duration_seconds"] == 0.002


def test_invalid_parameters_rejected():
    with pytest.raises(ValueError):
        analyze_pcm_s16le(pcm([1]), sample_rate_hz=0)
    with pytest.raises(ValueError):
        analyze_pcm_s16le(pcm([1]), onset_threshold_db=float("nan"))


def test_stereo_input_duration_and_energy_are_valid():
    interleaved = struct.pack("<hhhh", 1000, 1000, 1000, 1000)
    result = analyze_pcm_s16le(interleaved, sample_rate_hz=1000, channels=2, window_ms=1)
    assert result["measurement"]["duration_seconds"] == 0.002
    assert result["summary"]["max_rms_dbfs"] == pytest.approx(20 * math.log10(1000 / 32768), abs=0.01)

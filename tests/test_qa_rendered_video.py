from __future__ import annotations

import json
import subprocess
from pathlib import Path

import scripts.qa_rendered_video as qa


def test_qa_measures_media_and_never_auto_approves_delivery(tmp_path: Path, monkeypatch):
    video = tmp_path / "render.mp4"
    video.write_bytes(b"video fixture")
    probe = {
        "format": {"duration": "12.374", "format_name": "mov,mp4"},
        "streams": [
            {"index": 0, "codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920},
            {"index": 1, "codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2},
        ],
    }
    loudnorm = (
        '[Parsed_loudnorm_0 @ 0x0]\n{\n'
        '"input_i" : "-16.2",\n"input_tp" : "-2.0",\n'
        '"input_lra" : "3.0",\n"input_thresh" : "-26.0",\n'
        '"output_i" : "-16.0",\n"output_tp" : "-1.8",\n'
        '"output_lra" : "3.0",\n"output_thresh" : "-25.8",\n'
        '"normalization_type" : "dynamic",\n"target_offset" : "0.2"\n}\n'
    )
    outputs = [
        subprocess.CompletedProcess([], 0, json.dumps(probe), ""),
        subprocess.CompletedProcess([], 0, "", loudnorm),
        subprocess.CompletedProcess([], 0, "", "max_volume: -2.0 dB\n"),
    ]

    def fake_run(command):
        return outputs.pop(0)

    monkeypatch.setattr(qa, "_run", fake_run)
    result = qa.run_qa(video, 12.374)
    assert result["technical_pass"] is True
    assert result["checks"]["audio_true_peak"] is True
    assert result["ready_for_delivery"] is False
    assert result["manual_review"]["story_fidelity_passed"] is False

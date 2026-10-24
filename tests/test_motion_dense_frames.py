import cv2
import numpy as np

from scripts.analyze_motion_dense_frames import analyze


def test_motion_review_scores_timestamp_linked_sample_pairs(tmp_path):
    first = np.zeros((64, 64), dtype=np.uint8)
    second = first.copy()
    third = first.copy()
    cv2.rectangle(first, (5, 20), (20, 35), 255, -1)
    cv2.rectangle(second, (20, 20), (35, 35), 255, -1)
    cv2.rectangle(third, (21, 20), (36, 35), 255, -1)
    cv2.imwrite(str(tmp_path / "f0.jpg"), first)
    cv2.imwrite(str(tmp_path / "f1.jpg"), second)
    cv2.imwrite(str(tmp_path / "f2.jpg"), third)
    evidence = {
        "source": {"sha256": "source-hash"},
        "sampling": {"interval_seconds": 0.25},
        "samples": [
            {"sample_index": i, "source_sha256": "source-hash",
             "source_pts_time": i * 0.25, "relative_path": f"f{i}.jpg"}
            for i in range(3)
        ],
    }
    report = analyze(evidence, tmp_path / "dense_frame_evidence.json")
    assert report["schema_version"] == "aimontage.motion_dense_review.v1"
    assert report["interval_count"] == 2
    assert report["source_sha256"] == "source-hash"
    assert all("mean_flow_magnitude_px" in interval for interval in report["intervals"])
    assert "production readiness" in " ".join(report["limitations"])

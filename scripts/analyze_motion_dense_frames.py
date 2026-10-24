"""Score adjacent dense samples for motion-heavy intervals; candidates still need review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from aimontage.evidence import write_json_atomic


def analyze(evidence: dict[str, Any], evidence_path: Path) -> dict[str, Any]:
    samples = evidence.get("samples", [])
    if len(samples) < 2:
        raise ValueError("At least two timestamp-linked samples are required")
    scored = []
    for left, right in zip(samples, samples[1:]):
        if left.get("source_sha256") != right.get("source_sha256"):
            raise ValueError("Adjacent samples must belong to the same source")
        base = evidence_path.parent
        lp, rp = (base / left["relative_path"]).resolve(), (base / right["relative_path"]).resolve()
        if not lp.is_file() or not rp.is_file():
            raise FileNotFoundError(f"Missing sampled image pair: {lp}, {rp}")
        a, b = cv2.imread(str(lp), cv2.IMREAD_GRAYSCALE), cv2.imread(str(rp), cv2.IMREAD_GRAYSCALE)
        if a is None or b is None:
            raise ValueError(f"Unable to decode sampled image pair: {lp}, {rp}")
        if a.shape != b.shape:
            b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_AREA)
        flow = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        magnitude = cv2.magnitude(flow[..., 0], flow[..., 1])
        scored.append({
            "start_sample_index": left["sample_index"],
            "end_sample_index": right["sample_index"],
            "start_seconds": left["source_pts_time"],
            "end_seconds": right["source_pts_time"],
            "mean_flow_magnitude_px": float(np.mean(magnitude)),
            "p90_flow_magnitude_px": float(np.percentile(magnitude, 90)),
            "mean_abs_luma_difference": float(np.mean(cv2.absdiff(a, b))),
        })
    scores = np.asarray([x["mean_flow_magnitude_px"] for x in scored], dtype=float)
    median = float(np.median(scores))
    mad = float(np.median(np.abs(scores - median)))
    threshold = median + max(1.5 * mad, 0.25)
    # A top-decile floor makes the candidate list useful even when the clip is low-motion.
    top_decile = float(np.percentile(scores, 90))
    threshold = min(threshold, top_decile) if top_decile > 0 else threshold
    for item in scored:
        item["motion_candidate"] = item["mean_flow_magnitude_px"] >= threshold and item["mean_flow_magnitude_px"] > 0
        item["candidate_rule_threshold_px"] = threshold
    candidates = [x for x in scored if x["motion_candidate"]]
    return {
        "schema_version": "aimontage.motion_dense_review.v1",
        "source_sha256": evidence["source"]["sha256"],
        "sampling_interval_seconds": evidence["sampling"]["interval_seconds"],
        "method": "Farneback optical-flow magnitude between adjacent sampled frames",
        "threshold": {"mean_flow_magnitude_px": threshold, "robust_median_px": median, "mad_px": mad},
        "interval_count": len(scored),
        "candidate_interval_count": len(candidates),
        "intervals": scored,
        "limitations": [
            "Scores prioritize visible image motion, not semantic importance or action correctness.",
            "Camera motion, cuts, flashes, and compression artifacts can score highly.",
            "Uniform source sampling may miss brief actions between samples; inspect source context around every candidate.",
            "This report does not certify complete motion coverage or production readiness."
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    evidence_path = args.evidence.resolve()
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    report = analyze(payload, evidence_path)
    write_json_atomic(args.out, report)
    print(json.dumps({"schema_version": report["schema_version"],
                      "interval_count": report["interval_count"],
                      "candidate_interval_count": report["candidate_interval_count"],
                      "output": args.out.resolve().as_posix()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

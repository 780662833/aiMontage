"""Build a portable HTML contact sheet for human review of motion candidates."""
from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path
from typing import Any


def build(evidence_path: Path, motion_path: Path, out_path: Path) -> dict[str, Any]:
    evidence_path, motion_path, out_path = evidence_path.resolve(), motion_path.resolve(), out_path.resolve()
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    motion = json.loads(motion_path.read_text(encoding="utf-8"))
    if evidence.get("source", {}).get("sha256") != motion.get("source_sha256"):
        raise ValueError("Dense evidence and motion report source SHA-256 do not match")
    by_index = {int(s["sample_index"]): s for s in evidence.get("samples", [])}
    candidates = sorted(
        (x for x in motion.get("intervals", []) if x.get("motion_candidate")),
        key=lambda x: float(x.get("mean_flow_magnitude_px", 0)), reverse=True,
    )
    cards = []
    for item in candidates:
        left_i, right_i = int(item["start_sample_index"]), int(item["end_sample_index"])
        if left_i not in by_index or right_i not in by_index:
            raise ValueError(f"Motion interval references missing sample: {left_i}, {right_i}")
        image_html = []
        for label, sample in (("Start", by_index[left_i]), ("End", by_index[right_i])):
            image_path = (evidence_path.parent / sample["relative_path"]).resolve()
            if not image_path.is_file():
                raise FileNotFoundError(f"Sample image missing: {image_path}")
            if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                raise ValueError(f"Unsupported image type: {image_path.suffix}")
            mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[image_path.suffix.lower()]
            encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
            image_html.append(
                f'<figure><img alt="{label} sample at {float(sample["source_pts_time"]):.3f}s" '
                f'src="data:{mime};base64,{encoded}"><figcaption>{label}: '
                f'{float(sample["source_pts_time"]):.3f}s · frame {int(sample["frame_no"])}</figcaption></figure>'
            )
        start, end = float(item["start_seconds"]), float(item["end_seconds"])
        cards.append(f"""
<section class="card">
  <header><strong>{start:.3f}s – {end:.3f}s</strong><span>mean flow {float(item['mean_flow_magnitude_px']):.2f}px · p90 {float(item['p90_flow_magnitude_px']):.2f}px</span></header>
  <div class="images">{''.join(image_html)}</div>
  <p class="review">Reviewer classification: ☐ action motion ☐ camera motion ☐ cut/flash ☐ compression/noise ☐ unclear</p>
  <p class="review">Action completeness / notes: ______________________________________________</p>
</section>""")
    document = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Motion-dense review sheet</title>
<style>
body{{font:16px system-ui,sans-serif;margin:24px;max-width:1200px;color:#222}}h1{{font-size:1.5rem}}
.note{{padding:12px;border:1px solid #aaa;border-radius:8px;background:#f7f7f7}}
.card{{border:1px solid #bbb;border-radius:10px;padding:14px;margin:16px 0;break-inside:avoid}}
header{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}}.images{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
figure{{margin:12px 0}}img{{width:100%;height:auto;object-fit:contain;background:#eee}}figcaption{{font-size:.9rem;color:#555}}
.review{{margin:8px 0}}@media print{{body{{margin:10mm}}.card{{break-inside:avoid}}}}
</style>
<body><h1>Motion-dense candidate review</h1>
<div class="note">Source SHA-256: {html.escape(str(evidence['source']['sha256']))}<br>
Candidates: {len(candidates)} / intervals analyzed: {int(motion.get('interval_count', 0))}<br>
This sheet prioritizes image motion, not semantic action. Cuts, camera movement, flashes, and compression may score highly. Inspect source context and do not treat this sheet as production approval.</div>
{''.join(cards) if cards else '<p>No motion candidates exceeded the scoring threshold.</p>'}
</body></html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(document, encoding="utf-8")
    return {"output": out_path.as_posix(), "candidate_count": len(candidates),
            "source_sha256": evidence["source"]["sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--motion-report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.evidence, args.motion_report, args.out), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

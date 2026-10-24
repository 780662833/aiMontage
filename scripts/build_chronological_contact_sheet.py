"""Build a chronological, self-contained HTML contact sheet from dense frame evidence."""
from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path
from typing import Any


def build(evidence_path: Path, out_path: Path, columns: int = 4) -> dict[str, Any]:
    evidence_path, out_path = evidence_path.resolve(), out_path.resolve()
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    source = evidence.get("source", {})
    source_sha = source.get("sha256")
    samples = evidence.get("samples", [])
    if not samples:
        raise ValueError("Evidence contains no samples")
    if columns < 1 or columns > 8:
        raise ValueError("--columns must be between 1 and 8")

    ordered = sorted(
        samples,
        key=lambda s: (
            float(s.get("source_pts_time", s.get("sample_timestamp_seconds", 0))),
            int(s.get("sample_index", 0)),
        ),
    )
    cards = []
    seen_indices: set[int] = set()
    for sample in ordered:
        index = int(sample["sample_index"])
        if index in seen_indices:
            raise ValueError(f"Duplicate sample_index: {index}")
        seen_indices.add(index)
        rel = Path(sample["relative_path"])
        image_path = (evidence_path.parent / rel).resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"Missing frame image for sample {index}: {image_path}")
        suffix = image_path.suffix.lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(suffix)
        if not mime:
            raise ValueError(f"Unsupported image extension: {suffix}")
        timestamp = float(sample.get("source_pts_time", sample.get("sample_timestamp_seconds", 0)))
        frame_no = sample.get("frame_no")
        if frame_no is None:
            frame_no = sample.get("source_frame_no", "unknown")
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        cards.append(
            f'<article class="frame" data-time="{timestamp:.6f}">'
            f'<div class="image-wrap"><a href="data:{mime};base64,{encoded}" target="_blank" '
            f'rel="noopener" title="Open full image in a new tab">'
            f'<img loading="lazy" src="data:{mime};base64,{encoded}" '
            f'alt="Frame at {timestamp:.3f} seconds"></a></div>'
            f'<div class="meta"><strong>#{index:04d} · {timestamp:.3f}s</strong>'
            f'<span>source frame: {html.escape(str(frame_no))}</span></div>'
            f'</article>'
        )

    duration = max(float(s.get("source_pts_time", s.get("sample_timestamp_seconds", 0))) for s in ordered)
    document = f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chronological Dense Frame Contact Sheet</title>
<style>
:root{{color-scheme:light dark}}
body{{font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;margin:20px;max-width:1800px}}
h1{{font-size:1.5rem;margin-bottom:.3rem}}.summary{{padding:12px;border:1px solid #8888;border-radius:8px;margin:12px 0 18px;overflow-wrap:anywhere}}
.grid{{display:grid;grid-template-columns:repeat({columns},minmax(0,1fr));gap:12px}}
.frame{{border:1px solid #8887;border-radius:8px;overflow:hidden;break-inside:avoid;min-width:0}}
.image-wrap{{background:#7772;display:flex;align-items:center;justify-content:center;min-height:120px}}
img{{display:block;width:100%;height:auto;object-fit:contain;cursor:zoom-in}}
.meta{{padding:8px;display:flex;flex-direction:column;gap:2px;overflow-wrap:anywhere}}.meta span{{font-size:.86rem;opacity:.8}}
@media(max-width:1000px){{.grid{{grid-template-columns:repeat(3,minmax(0,1fr))}}}}
@media(max-width:680px){{.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media print{{body{{margin:8mm}}.grid{{grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}}.frame{{break-inside:avoid}}}}
</style></head><body>
<h1>全视频密集帧时间线</h1>
<div class="summary">源 SHA-256：{html.escape(str(source_sha))}<br>
样本数：{len(ordered)}　首帧：{float(ordered[0].get("source_pts_time", ordered[0].get("sample_timestamp_seconds", 0))):.3f}s
　末帧：{duration:.3f}s<br>
按源时间戳升序排列。点击图片可在新标签页查看原始嵌入图像。联系表用于剧情全貌浏览；关键动作请回看原视频并按需补帧。</div>
<div class="grid">{''.join(cards)}</div></body></html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(document, encoding="utf-8")
    return {
        "output": out_path.as_posix(),
        "sample_count": len(ordered),
        "source_sha256": source_sha,
        "first_timestamp_seconds": float(ordered[0].get("source_pts_time", ordered[0].get("sample_timestamp_seconds", 0))),
        "last_timestamp_seconds": duration,
        "chronological": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(build(args.evidence, args.out, args.columns), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

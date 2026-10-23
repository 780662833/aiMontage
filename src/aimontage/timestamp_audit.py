from __future__ import annotations
from typing import Any, Iterable

def audit_frame_rows(rows: Iterable[dict[str, Any]], *, tolerance_seconds: float = 0.05) -> list[dict[str, Any]]:
    """Audit in input order; source_pts_time is authoritative, decoder PTS diagnostic."""
    if tolerance_seconds < 0:
        raise ValueError("tolerance_seconds must be >= 0")
    items = list(rows)
    nums = [r.get("frame_no") for r in items]
    seen: set[int] = set()
    duplicates = set()
    for n in nums:
        if n is not None:
            if n in seen:
                duplicates.add(n)
            seen.add(n)
    pts = [r.get("source_pts_time") for r in items]
    valid_pts = [p for p in pts if isinstance(p, (int, float))]
    reordered = any(b < a for a, b in zip(valid_pts, valid_pts[1:]))
    output = []
    for i, row in enumerate(items):
        status, reasons = "aligned", []
        n, p = row.get("frame_no"), row.get("source_pts_time")
        if n is None or not isinstance(p, (int, float)):
            status = "ambiguous-neighbor"
            reasons.append("missing-frame-number-or-source-pts")
        elif n in duplicates:
            status = "ambiguous-neighbor"
            reasons.append("duplicate-frame-number")
        elif reordered:
            status = "reorder"
            reasons.append("source-pts-not-monotonic-in-input-order")
        if i:
            prev = pts[i - 1]
            if isinstance(p, (int, float)) and isinstance(prev, (int, float)) and abs(p - prev) <= tolerance_seconds:
                if status == "aligned":
                    status = "ambiguous-neighbor"
                reasons.append("neighbor-pts-within-tolerance")
        output.append({**row, "audit": {
            "status": status, "reasons": reasons,
            "source_pts_time_authoritative": True,
            "decoder_pts_time_role": "diagnostic-only",
        }})
    return output

from __future__ import annotations
from typing import Any, Iterable

def audit_frame_rows(rows: Iterable[dict[str, Any]], *, tolerance_seconds: float = 1e-6) -> list[dict[str, Any]]:
    """Audit rows in original order; source PTS is authoritative, decoder PTS diagnostic."""
    if tolerance_seconds < 0:
        raise ValueError("tolerance_seconds must be >= 0")
    items = list(rows)
    seen: set[int] = set()
    duplicates: set[int] = set()
    for row in items:
        number = row.get("frame_no")
        if number is not None:
            if number in seen:
                duplicates.add(number)
            seen.add(number)

    output = []
    previous_pts = None
    for row in items:
        status, reasons = "aligned", []
        number = row.get("frame_no")
        pts = row.get("source_pts_time")
        if number is None or not isinstance(pts, (int, float)):
            status = "ambiguous-neighbor"
            reasons.append("missing-frame-number-or-source-pts")
        elif number in duplicates:
            status = "ambiguous-neighbor"
            reasons.append("duplicate-frame-number")
        elif isinstance(previous_pts, (int, float)) and pts < previous_pts:
            status = "reorder"
            reasons.append("source-pts-decreased-relative-to-previous-row")
        elif isinstance(previous_pts, (int, float)) and abs(pts - previous_pts) <= tolerance_seconds:
            status = "ambiguous-neighbor"
            reasons.append("neighbor-pts-within-tolerance")
        output.append({**row, "audit": {
            "status": status,
            "reasons": reasons,
            "source_pts_time_authoritative": True,
            "decoder_pts_time_role": "diagnostic-only",
        }})
        if isinstance(pts, (int, float)):
            previous_pts = pts
    return output

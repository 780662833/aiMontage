from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def make_evidence_record(*, evidence_id: str, source_path: str | Path,
                         tool_name: str, tool_version: str,
                         raw_result: dict[str, Any],
                         source_pts_time: float | None = None,
                         frame_no: int | None = None,
                         relative_path: str | None = None) -> dict[str, Any]:
    source = Path(source_path)
    record = {
        "schema_version": "aimontage.evidence_record.v1",
        "evidence_id": evidence_id,
        "source": {"path": source.as_posix(), "sha256": sha256_file(source)},
        "producer": {"tool": tool_name, "version": tool_version},
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "raw_result": raw_result,
    }
    if frame_no is not None or source_pts_time is not None or relative_path is not None:
        record["frame"] = {
            "frame_no": frame_no,
            "source_pts_time": source_pts_time,
            "path": relative_path.replace("\\", "/") if relative_path else None,
        }
    return record

def write_json_atomic(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(target)

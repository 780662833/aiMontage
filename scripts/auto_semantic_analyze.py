"""Generate an evidence-grounded semantic analysis draft with a vision-capable API.

This is the automatic replacement for manually filling the semantic worksheet. It
analyzes chronological dense frames, asks the model to propose event intervals and
observable actions, and binds each claim to supplied sample indices. Output remains a
draft: it never marks itself approved or render-ready.

Configuration (OpenAI-compatible Chat Completions API):
  AIMONTAGE_VISION_API_KEY   required
  AIMONTAGE_VISION_BASE_URL  optional, defaults to https://api.openai.com/v1
  AIMONTAGE_VISION_MODEL     required, vision-capable model name

Example:
  python scripts/auto_semantic_analyze.py `
    --evidence-packet artifacts/openmontage_video_analysis/story_evidence_packet.json `
    --out artifacts/openmontage_video_analysis/semantic_review.auto_draft.json
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SCHEMA = "aimontage.semantic_review_template.v1"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
SYSTEM_PROMPT = """You are a careful video analyst. Infer only what is visible in the supplied chronological frames. Frames may be sparse; do not invent actions between frames. Distinguish observable action from inferred intent. Return only a JSON object with key 'events', an array. Each event must have: start_seconds, end_seconds, visible_entities (array of short strings), observable_actions (array of short strings), before_state (string or null), after_state (string or null), cause_and_reaction (string or null), story_function (string), must_preserve (array of short strings), uncertain_or_unobservable (array of short strings), confidence (number 0..1), evidence_sample_indices (array of integer sample indices), and summary (string). Cover the main narrative beats in chronological order. Use only sample indices provided with the images. Use source timestamps shown with each image for intervals; intervals must be within the source duration. If a beat cannot be established, express uncertainty rather than guessing. Do not invent dialogue or audio content."""


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _image_data_url(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"Evidence image does not exist: {path}")
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _resolve_image(packet_path: Path, relative_path: str, evidence_root: Path | None) -> Path:
    if evidence_root is not None:
        candidate = evidence_root / relative_path
        if candidate.is_file():
            return candidate
    candidate = packet_path.parent / relative_path
    if candidate.is_file():
        return candidate
    # Common evidence layouts store paths relative to the repository root.
    if evidence_root is not None:
        candidate = evidence_root.parent / relative_path
        if candidate.is_file():
            return candidate
    raise ValueError(
        f"Cannot resolve evidence image {relative_path!r}; pass --evidence-root or fix the packet's relative_path"
    )


def build_messages(packet: dict[str, Any], packet_path: Path, evidence_root: Path | None = None) -> list[dict[str, Any]]:
    if packet.get("schema_version") != "aimontage.story_evidence_packet.v1":
        raise ValueError("Unsupported evidence packet schema; expected aimontage.story_evidence_packet.v1")
    source = packet.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("sha256"), str) or not source["sha256"]:
        raise ValueError("Evidence packet is missing source.sha256")
    samples: dict[int, dict[str, Any]] = {}
    for event in packet.get("events", []):
        if not isinstance(event, dict):
            continue
        for sample in event.get("linked_dense_samples", []):
            if isinstance(sample, dict) and isinstance(sample.get("sample_index"), int):
                samples[sample["sample_index"]] = sample
    # Include motion-candidate samples if the event windows are sparse, but de-duplicate by index.
    if not samples:
        raise ValueError("Evidence packet contains no linked dense-frame samples")
    duration = source.get("duration_seconds")
    content: list[dict[str, Any]] = [{
        "type": "text",
        "text": (
            f"Analyze this reference video from chronological evidence frames. Source SHA-256: {source['sha256']}. "
            f"Duration seconds: {duration}. The supplied timestamps are authoritative source PTS. "
            "Return event intervals and cite the sample indices that visibly support each event. "
            "Do not assume scene candidates are story-event boundaries."
        ),
    }]
    for index, sample in sorted(samples.items(), key=lambda pair: (float(pair[1].get("timestamp_seconds", 0)), pair[0])):
        rel = sample.get("relative_path")
        if not isinstance(rel, str) or not rel:
            continue
        image_path = _resolve_image(packet_path, rel, evidence_root)
        ts = sample.get("timestamp_seconds")
        frame_no = sample.get("frame_no")
        content.append({"type": "text", "text": f"Evidence sample_index={index}; source_timestamp_seconds={ts}; frame_no={frame_no}."})
        content.append({"type": "image_url", "image_url": {"url": _image_data_url(image_path), "detail": "low"}})
    if len(content) <= 1:
        raise ValueError("No resolvable images found in evidence packet")
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def _call_vision_api(messages: list[dict[str, Any]], model: str, api_key: str, base_url: str) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1500]
        raise RuntimeError(f"Vision API returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach vision API: {exc.reason}") from exc
    try:
        body = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Vision API response has no choices[0].message.content") from exc
    if isinstance(body, list):
        body = "".join(part.get("text", "") for part in body if isinstance(part, dict))
    if not isinstance(body, str):
        raise RuntimeError("Vision API message content is not text")
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Vision API returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("events"), list):
        raise RuntimeError("Vision API JSON must contain an 'events' array")
    return parsed


def build_auto_review(packet: dict[str, Any], model_result: dict[str, Any]) -> dict[str, Any]:
    if packet.get("schema_version") != "aimontage.story_evidence_packet.v1":
        raise ValueError("Unsupported evidence packet schema")
    source = packet.get("source", {})
    available: dict[int, dict[str, Any]] = {}
    for event in packet.get("events", []):
        if not isinstance(event, dict):
            continue
        for sample in event.get("linked_dense_samples", []):
            if isinstance(sample, dict) and isinstance(sample.get("sample_index"), int):
                available[sample["sample_index"]] = sample
    events = []
    raw_events = model_result.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        raise ValueError("Model returned no semantic events")
    duration = source.get("duration_seconds")
    for idx, raw in enumerate(raw_events):
        if not isinstance(raw, dict):
            continue
        start, end = raw.get("start_seconds"), raw.get("end_seconds")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or not 0 <= start < end:
            raise ValueError(f"Model event {idx} has invalid start/end timestamps")
        if isinstance(duration, (int, float)) and end > duration + 0.05:
            raise ValueError(f"Model event {idx} ends beyond source duration")
        cited = raw.get("evidence_sample_indices")
        if not isinstance(cited, list) or not cited or any(not isinstance(i, int) or i not in available for i in cited):
            raise ValueError(f"Model event {idx} cites missing or invalid sample indices")
        confidence = raw.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ValueError(f"Model event {idx} confidence must be between 0 and 1")
        evidence = []
        for sample_index in sorted(set(cited)):
            sample = available[sample_index]
            evidence.append({key: sample.get(key) for key in (
                "sample_index", "timestamp_seconds", "frame_no", "relative_path", "image_sha256", "association_status"
            )})
        events.append({
            "event_id": f"AUTO-EVENT-{idx + 1:03d}",
            "candidate_interval": {
                "start_seconds": float(start), "end_seconds": float(end),
                "status": "model_candidate_requires_validation",
            },
            "upstream_summary": raw.get("summary"),
            "scene_signals": {"origin": "multimodal_model", "model_confidence": float(confidence)},
            "evidence": evidence,
            "review": {
                "status": "needs_review",
                "visible_entities": raw.get("visible_entities") if isinstance(raw.get("visible_entities"), list) else [],
                "observable_actions": raw.get("observable_actions") if isinstance(raw.get("observable_actions"), list) else [],
                "before_state": raw.get("before_state"),
                "after_state": raw.get("after_state"),
                "cause_and_reaction": raw.get("cause_and_reaction"),
                "story_function": raw.get("story_function"),
                "must_preserve": raw.get("must_preserve") if isinstance(raw.get("must_preserve"), list) else [],
                "uncertain_or_unobservable": raw.get("uncertain_or_unobservable") if isinstance(raw.get("uncertain_or_unobservable"), list) else [],
                "reviewer_notes": "Automatically generated; verify low-confidence claims and event boundaries before approval.",
                "confidence": float(confidence),
                "evidence_sample_indices": sorted(set(cited)),
                "automation_status": "draft_not_approved",
            },
        })
    events.sort(key=lambda event: event["candidate_interval"]["start_seconds"])
    return {
        "schema_version": SCHEMA,
        "source": {"sha256": source.get("sha256"), "path": source.get("path"), "duration_seconds": duration},
        "analysis": {
            "mode": "automatic_multimodal_draft",
            "model": model_result.get("model_name"),
            "human_review_policy": "exception_only_after_confidence_and_evidence_gates_are_calibrated",
            "approval_state": "not_approved",
        },
        "review_policy": {
            "only_observable_claims": True,
            "cite_sample_indices": True,
            "uncertainty_is_allowed": True,
            "do_not_infer_offscreen_audio_or_intent": True,
            "candidate_scene_boundaries_are_not_verified_story_boundaries": True,
        },
        "events": events,
        "validation": {
            "event_count": len(events),
            "events_needing_review": len(events),
            "semantically_reviewed_count": 0,
            "evidence_cited_count": sum(bool(e["review"]["evidence_sample_indices"]) for e in events),
            "ready_for_edit_plan": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-packet", required=True, type=Path)
    parser.add_argument("--evidence-root", type=Path, help="Root directory used to resolve packet relative_path images")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--base-url", default=os.environ.get("AIMONTAGE_VISION_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.environ.get("AIMONTAGE_VISION_MODEL"))
    args = parser.parse_args()
    api_key = os.environ.get("AIMONTAGE_VISION_API_KEY")
    if not api_key:
        raise SystemExit("Set AIMONTAGE_VISION_API_KEY in the environment; do not place API keys in files or command history.")
    if not args.model:
        raise SystemExit("Set AIMONTAGE_VISION_MODEL to a vision-capable model name.")
    packet = read_json(args.evidence_packet)
    messages = build_messages(packet, args.evidence_packet, args.evidence_root)
    result = _call_vision_api(messages, args.model, api_key, args.base_url)
    result["model_name"] = args.model
    review = build_auto_review(packet, result)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": SCHEMA, "out": str(args.out), **review["validation"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

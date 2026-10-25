# Automatic semantic analysis MVP

## Purpose

`scripts/auto_semantic_analyze.py` replaces hand-writing the first semantic review draft. It sends the chronological dense-frame images and their source timestamps to a configured vision-capable OpenAI-compatible Chat Completions endpoint, asks for story events/actions/relationships, and validates that every event cites sample indices present in the evidence packet.

It is an **automatic draft generator**, not yet a calibrated autonomous approval gate. It deliberately writes `review.status = needs_review`, records `automation_status = draft_not_approved`, and leaves `ready_for_edit_plan = false`. Do not change those flags merely to bypass downstream validation.

## Setup (PowerShell)

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location).Path "src")
$env:AIMONTAGE_VISION_API_KEY = "<your API key>"
$env:AIMONTAGE_VISION_MODEL = "<vision-capable model name>"
# Optional for an OpenAI-compatible provider:
# $env:AIMONTAGE_VISION_BASE_URL = "https://provider.example/v1"
```

Do not commit credentials or place them in source files. `AIMONTAGE_VISION_MODEL` must name a model that accepts image input and JSON-object responses at the configured endpoint.

## Run

```powershell
python scripts/auto_semantic_analyze.py `
  --evidence-packet artifacts/openmontage_video_analysis/story_evidence_packet.json `
  --out artifacts/openmontage_video_analysis/semantic_review.auto_draft.json
```

If packet `relative_path` entries are not resolvable from the packet directory, pass the directory containing the referenced evidence images:

```powershell
python scripts/auto_semantic_analyze.py `
  --evidence-packet artifacts/openmontage_video_analysis/story_evidence_packet.json `
  --evidence-root artifacts/real_video_e2e `
  --out artifacts/openmontage_video_analysis/semantic_review.auto_draft.json
```

The script does not upload the source video itself; it sends the linked evidence images and timestamps. If the packet only links a sparse or incomplete subset of frames, the model cannot reliably infer actions that are not visible in those frames. Dense event-window sampling and targeted short-clip review are follow-up improvements before this can be treated as a robust general-purpose pipeline.

## Output guarantees and limits

- Source SHA-256 is preserved.
- Model-proposed intervals are checked against the source duration.
- Every event must cite real sample indices present in the packet.
- The output stays unapproved and blocked from rendering.
- Model confidence is recorded but is not assumed to be calibrated.
- Inferred intent must be separated from observable action; ambiguous events belong in `uncertain_or_unobservable`.

## Tests

```powershell
python -m pytest tests/test_auto_semantic_analyze.py tests/test_build_semantic_review_template.py tests/test_build_shot_edit_plan.py -q
```

## Next engineering gates

1. Run against the local `a.mp4` evidence packet and inspect request size, provider compatibility, and actual output.
2. Compare predicted events against the current user-confirmed story notes and a second, unrelated video.
3. Measure event coverage, boundary error, evidence-citation validity, and unsupported-claim rate.
4. Add adaptive frame/clip retrieval around ambiguous action boundaries.
5. Only after calibration on multiple videos, allow high-confidence events to pass automatically; retain exception-only human review for low confidence, missing evidence, or conflicting predictions.

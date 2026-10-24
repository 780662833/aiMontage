# Story Blueprint: first implementation slice

The first implementation is intentionally deterministic: it transforms the existing
OpenMontage L2 event draft into a story Blueprint skeleton while preserving source
hashes, scene interval candidates, and keyframe evidence references.

It does **not** claim that OpenMontage scene boundaries are semantic story events and
does not invent actions, actors, object interactions, or causal links. Those fields
must be populated by an evidence-grounded multimodal review step.

## Run locally (Windows PowerShell)

```powershell
Set-Location "F:\python\aiMontage"
git pull origin aimontage/phase-1-analysis-tools
$env:PYTHONPATH = (Join-Path (Get-Location).Path "src")
python -m pytest tests/test_build_openmontage_event_draft.py tests/test_build_story_blueprint.py -q

python scripts/build_story_blueprint.py `
  --event-draft artifacts/openmontage_video_analysis/l2_event_draft.json `
  --out artifacts/openmontage_video_analysis/story_blueprint.draft.json
```

If your L2 draft lives elsewhere, change only the `--event-draft` path. The output
is a draft, not an approved remake plan.

## Current schema

- `schema_version`: `aimontage.story_blueprint.v1`
- Source identity: SHA-256 and source path/duration when available.
- Per event: time candidate and its provenance, action/actor/target/state fields,
  causal references, preservation constraints, confidence, evidence IDs, review status.
- Keyframe evidence: carried forward without changing upstream evidence.
- Readiness: remains false until semantic verification is implemented and passed.

## Next implementation slice

1. Join the 49-frame dense-sampling evidence to the keyframe evidence using source
   timestamps (never file ordering alone).
2. Add a multimodal event-review step that emits action, actor, target, before/after
   states, causal links, and confidence with explicit frame evidence.
3. Validate event ordering and time bounds against source duration.
4. Only then generate a `remake_plan.json` with replacement-character references,
   per-shot prompts, shot duration, and required actions.
5. Render a 2–3 second interaction test before attempting the complete short.

The original media and upstream OpenMontage brief remain unchanged.

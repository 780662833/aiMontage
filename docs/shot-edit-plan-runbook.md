# Shot-by-shot edit plan runbook

This stage reuses the existing OpenMontage L2 candidates, dense-frame evidence packet,
and semantic review worksheet. It does not run scene detection, frame sampling, motion
analysis, transcription, or any other media analysis.

## 1. Review semantics

Generate the worksheet using `scripts/build_semantic_review_template.py`. Inspect the
linked frame paths and source playback. For each event, set `review.status` to
`reviewed` only after review, then populate:
- `visible_entities`, `observable_actions`, and `must_preserve` with observable facts;
- `story_function`, `before_state`, `after_state`, and `cause_and_reaction` where supported;
- `evidence_sample_indices` with indices actually present in that event's evidence;
- `confidence` from 0 to 1 and `uncertain_or_unobservable` for unresolved claims.

Keep the generated draft as a separate artifact; save the reviewed copy as
`semantic_review.reviewed.json`.

## 2. Build the shot plan

```powershell
python scripts/build_shot_edit_plan.py `
  --semantic-review artifacts/openmontage_video_analysis/semantic_review.reviewed.json `
  --out artifacts/openmontage_video_analysis/shot_edit_plan.draft.json
```

The builder fails closed if any event is unreviewed, required fields are missing, or
evidence indices do not exist in the event. Output ranges are a sequential assembly
scaffold, not a final timing decision. Source ranges remain candidates until confirmed
by playback. Each shot requires a production-method decision and content/audio QA.

## 3. Tests

```powershell
python -m pytest tests/test_build_shot_edit_plan.py -q
```

## 4. Render handoff

Do not render directly from the draft. After a human confirms source ranges, 9:16 crop,
production method, transitions, soundtrack/voiceover/subtitles, and QA requirements,
a subsequent renderer adapter can consume an approved plan. Keep render readiness false
until those checks are explicitly recorded.

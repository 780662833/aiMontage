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


## 5. Render handoff through the pinned OpenMontage composer

The renderer adapter delegates to the pinned submodule's
`tools.video.video_compose.VideoCompose` via `run_upstream_tool`; it does not copy
OpenMontage code or rebuild media analysis. It requires all of the following:
- the plan's `validation.ready_for_render` is explicitly true;
- every shot's source timing is marked `playback_confirmed` or `confirmed`;
- every shot has `timing_confirmed`, `story_function_preserved`,
  `visual_continuity_passed`, and `audio_checked` set true;
- the source file SHA-256 matches the plan;
- every shot has an explicit production method.

**Do not flip these fields just to make the renderer run.** Confirm the bite timing near
4.0–4.8s and the apparent arm-to-face contact near 11.7s by playing the original source.
Then record the confirmed in/out points and the human QA decision in a reviewed copy of
the plan. The currently committed draft is deliberately blocked.

Once the plan has been genuinely approved, render with:

```powershell
python scripts/render_approved_shot_plan.py `
  --approved-plan artifacts/openmontage_video_analysis/shot_edit_plan.approved.json `
  --video .\\a.mp4 `
  --out artifacts/openmontage_video_analysis/rendered_short.mp4 `
  --repo-root .\\vendor\\OpenMontage
```

The composer is configured for 1080x1920, H.264, and center-cover fit. The source fixture
is already 9:16, so the crop should not remove content if source metadata is correct.
The handoff result is `rendered_pending_qa`, never delivery approval.

## 6. Technical output QA

```powershell
python scripts/qa_rendered_video.py `
  --video artifacts/openmontage_video_analysis/rendered_short.mp4 `
  --expected-duration 12.374 `
  --out artifacts/openmontage_video_analysis/render_qa.json
```

This checks the video stream, 1080x1920 resolution, H.264, duration tolerance, audio
presence, integrated loudness (target window -18 to -14 LUFS), true peak (at or below
-1.5 dBTP), sample-peak headroom, and subtitle-stream policy. It writes measurements
and blockers even when QA fails. A technical pass is not sufficient for delivery:
the human reviewer must still confirm shot continuity, story fidelity, and subtitle/script
policy. The current source is reviewed as music-only; do not invent spoken dialogue.

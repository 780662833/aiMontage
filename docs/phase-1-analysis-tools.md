# Phase 1 — Analysis tool integration

## Pinned external source
- Repository: `https://github.com/calesthio/OpenMontage.git`
- Revision: `c8066452325cb57c8fc1ba8c2a71b6e8842e6b65`
- Integration method: Git submodule at `vendor/OpenMontage`; do not vendor/copy individual tool scripts.
- Upstream license: AGPL-3.0. Review obligations before distributing or offering a network service using modified/combined code.

## aiMontage-owned invariants
- Source video SHA-256 identifies the immutable input.
- `source_pts_time` is authoritative for source timeline alignment. Decoder-reported timestamps are diagnostic only.
- Associate sampled evidence using stable `(source_sha256, frame_no)`, not filenames alone.
- Use POSIX-style relative paths in normalized manifests; preserve raw upstream output separately for traceability.
- Use half-open frame intervals: `[start_frame_no, end_frame_no)`.
- Timestamp/frame association audit must report `aligned`, `ambiguous-neighbor`, or `reorder`; suspicious ordering must not be silently corrected.
- Keep raw tool output alongside normalized aiMontage records.

## Real-video analysis
The root `a.mp4` fixture is processed by `scripts/run_real_video_e2e.py`. It runs pinned upstream `audio_probe`, `scene_detect`, and `frame_sampler`, audits decoded source-frame PTS, maps scene boundaries to contiguous half-open source-frame intervals, and maps each sampled image to its source frame. Each normalized sample includes source SHA-256, source frame number, authoritative source PTS, relative POSIX path, image SHA-256, and mapping delta. Raw upstream output is preserved in parallel.

The inspected run had 371 decoded source frames, three scene intervals, and 12 sampled images. All source frame rows passed timestamp audit; all sampled images visually covered the source from 0 through 11 seconds. Normalized association is separately unit-tested.

## Local transcription
`scripts/run_transcriber_e2e.py` invokes the upstream local ASR tool with explicit model/language, validates segment and word timestamps against media duration, and records model settings plus raw output. CI uses the `base` model by default on push; a manual workflow dispatch can select `tiny`, `base`, or `small`. An empty transcript is not a tool failure; it is recorded as `speech_detected: false` and should be reviewed against source audio. The CLI reports `review_required` when the transcript QA gate blocks Blueprint readiness; successful tool execution is not the same as accepted transcript content.

```powershell
python scripts/run_transcriber_e2e.py --video a.mp4 --out artifacts/real_video_e2e/transcription --model-size tiny --language en
```

### Real-video ASR finding (2026-10-23)
The `tiny` model emitted “Thanks for watching!” on `a.mp4`, but the user confirmed that phrase is not present in the source audio. The first word had probability `0.01`, and there was a `2.88s` inter-word gap. This is a confirmed false positive: retain the raw ASR output for traceability, keep transcript QA at `REVIEW`, and do not pass this evidence bundle into Blueprint. A regression test locks this sample behind the gate. The fixture is now explicitly reviewed as `music_only`, so normal Phase 1 CI skips ASR for this fixture. Manual dispatch can select `speech_only`, `music_and_speech`, or `unknown` to exercise the transcript workflow. VAD indicates speech-like acoustic activity only; it does not identify words or prove intelligible speech.


## Human-reviewed audio content classification
The current `a.mp4` fixture has been reviewed by the user as background music only, with no spoken narration. The workflow writes `audio_content_review.json` through `scripts/write_audio_content_review.py` using the explicit `music_only` classification. This record is distinct from machine-inferred VAD or ASR results.

For `music_only`, the policy is `NOT_APPLICABLE` for spoken transcript and ASR text is excluded from Blueprint even if an ASR model reports words. Raw ASR output remains available for audit. Music timing and acoustic features can still be analyzed independently; VAD activity must not be treated as proof of speech or as a music classifier.

The deterministic policy and regression tests live in `src/aimontage/audio_review.py` and `tests/test_audio_review.py`. This reviewed label is specific to the current fixture; other videos should use their own reviewed classification rather than inherit it. The workflow also runs `scripts/run_music_timeline_e2e.py`, which extracts mono signed 16-bit PCM through FFmpeg and writes `music_timeline_evidence.json`. `src/aimontage/music_timeline.py` computes a configurable RMS energy envelope, threshold-based silence intervals, and candidate energy transients. Candidate transients are not asserted to be musical beats, and the module does not classify music versus speech or infer tempo.
## YouTube caption fetch
The upstream caption fetcher requires a YouTube URL/ID and network access; a local MP4 alone cannot exercise it. The workflow has an optional `workflow_dispatch` input `caption_video_url`. Leave it blank to skip the network test, or provide a known URL with accessible captions to run:

```powershell
python scripts/run_transcript_fetcher_smoke.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --out artifacts/caption_fetch_e2e
```

The fetch test preserves raw provider output and normalizes caption start/duration timestamps without confusing captions with ASR output.

## Verification checklist
- [x] Pinned upstream submodule initializes in clean CI.
- [x] FFmpeg/ffprobe checked before media jobs.
- [x] Timestamp audit unit tests cover missing PTS, duplicate/nearby timestamps, and deliberate row reorder.
- [x] Real `a.mp4` analysis passed: media probe, scene detection, frame sampling.
- [x] Source-frame PTS audit: 371/371 aligned in inspected fixture run.
- [x] Scene candidates mapped to contiguous half-open source frame intervals.
- [x] All 12 sampled images visually inspected and linked to frame number, source PTS, source hash, relative path, and image hash.
- [x] Unit tests added for normalized frame association and scene mapping.
- [x] Controlled real-video ASR executed and timestamp checks passed; content QA correctly blocked a user-confirmed hallucination (`REVIEW`, not Blueprint-ready).
- [x] Added configurable `tiny`/`base`/`small` ASR model selection; push CI defaults to `base`.
- [x] Added independent WebRTC VAD activity evidence (`scripts/run_audio_vad_e2e.py`); interpretation is limited to speech-like activity.
- [x] Added deterministic RMS/silence/energy-transient music timeline with unit tests.
- [ ] Review threshold choices and inspect generated `music_timeline_evidence.json` for the real fixture.
- [ ] Live caption fetch passes with an explicit YouTube URL with accessible captions.
- [x] Define and test `aimontage.cross_modal_timeline.v1`, joining visual scene intervals with candidate music-energy events and silence intervals; source SHA and duration alignment are enforced.
- [x] Generate `aimontage.blueprint_draft.v1` with source-aligned half-open shot intervals, provenance references, and null semantic fields rather than guessed content.
- [x] Validate Blueprint draft structure and enforce the music-only transcript exclusion gate in CI.
- [x] Generate a visual review template that links each shot to sampled source frames and preserves source SHA, frame number, source PTS, image SHA, and relative path.
- [x] Add evidence-backed visual annotation validation: annotations must cite frames linked to that shot, match the source SHA, include confidence, and pass contiguous time/frame checks.
- [x] Manually review sampled frames for the fixed `a.mp4` fixture and add `examples/real_video_a_mp4_visual_annotations.json`. Uncertain intent and unobserved motion are explicitly qualified rather than asserted as facts.
- [x] CI applies the fixture-specific annotation sidecar, writes `visual_review_annotated.json`, and requires every shot to pass the review gate.
- [x] Added `config/render_spec_social_9x16.json` and validation for a 1080×1920, 30 fps MP4 target, safe-area margins, audio policy, and crop review.
- [x] Assemble a `reviewable_candidate` reconstruction Blueprint that merges the evidence-backed visual annotations and render spec while preserving frame provenance.
- [ ] Motion-dense event sampling has not yet been validated; do not treat sparse 1-second samples as a complete action timeline.
- [x] Add deterministic FFmpeg profile-conformance render (`scripts/render_reconstruction_candidate.py`) with source-SHA lock, no-implicit-crop guard, target scaling/codec settings, provenance report, and technical output QA; CI renders the reviewed fixture. This is a source-preserving transcode smoke test, not a creative reconstruction.
- [ ] Review threshold choices and inspect candidate music-energy transients against the source audio before treating any as beats.
- [ ] Add dense motion/event sampling for actions that sparse 1-second samples may miss.
- [ ] Define the target 9:16 output spec and add a separate creative edit-intent / render-plan acceptance gate.
- [x] Extend render QA with FFmpeg black-frame, freeze-frame, and silence detection candidates; detections remain review-only because intentional fades, static shots, and quiet music can trigger them.
- [ ] Add audio glitch/pop detection beyond silence candidates and human-reviewed visual/content acceptance after semantic review and output-spec gates pass.


## First deterministic render boundary

The current render adapter is intentionally conservative. It checks that the input SHA-256 matches the reviewed candidate, probes the source with ffprobe, refuses aspect-ratio changes that would require an unreviewed crop/pad, then scales to the declared output profile and writes an MP4 plus provenance and QA JSON. The source fixture is already 9:16, so this validates the render path without inventing a reframing decision.

The output is explicitly labelled `source_preserving_vertical_transcode`; it does **not** claim to recreate the storyboard or edit intent. Technical QA checks dimensions, frame rate, duration drift, and expected audio presence. Human review remains required for visual integrity, black frames/freezes, audio quality, pacing, and creative correctness. A later renderer must consume explicit per-shot edit instructions before it can be treated as reconstruction.


## Content anomaly review candidates

After the profile-conformance render, `scripts/render_reconstruction_candidate.py` now runs `src/aimontage/ffmpeg_content_qa.py` and writes `content_qa.json`. The FFmpeg filters identify candidate intervals for black frames (`blackdetect`), visually frozen frames (`freezedetect`), and quiet audio (`silencedetect`). The report records thresholds, intervals, counts, and the exact command. These findings do not automatically fail the technical render gate: black frames may be intentional transitions, frozen frames may be deliberate holds, and silence can occur in valid audio. Human review remains mandatory. This is not yet a detector for clicks, clipping, or other audio artifacts.

## Human acceptance procedure (required before creative reconstruction)

CI success means that deterministic tests and the configured integration path ran successfully. It does not mean the creative result is approved. Perform this review on the uploaded `aimontage-real-video-e2e` artifact or on the same local run's output. Keep the source file immutable and record its SHA-256 with the review.

### Gate A — source evidence integrity
- Open the source video and sampled frames side by side. Check the first, middle, and last samples, then every sample used as evidence for a shot.
- Verify each sample's `source_sha256`, `frame_no`, `source_pts_time`, relative image path, and image SHA refer to the expected source frame. A filename or visually similar frame alone is not proof of alignment.
- Inspect every proposed shot boundary in context (at least 0.5 seconds before and after when available). Confirm that the boundary does not cut off an action or place a frame in the wrong shot.
- If timing, ordering, or visual mapping is ambiguous, mark the gate as REVIEW/FAIL and fix the evidence mapping; do not compensate by editing the Blueprint.

### Gate B — semantic and audio-content review
- Review each shot against the source and confirm only visible/aurally supported facts: subject, action, object identity, composition, camera motion, and action outcome. Record unknowns as unknown.
- Review the audio-content classification. For music-only media, do not accept ASR-generated words as subtitles. For speech, listen to the relevant segment and verify every accepted word and timestamp against the source.
- Check `music_timeline_evidence.json` against the audio by listening around candidate transients and silence intervals. Energy transients are not automatically beats; VAD activity is not proof of speech.
- Complete the visual review sidecar and rerun its validator. Do not proceed if any shot is unreviewed or the source hash differs.

### Gate C — per-shot edit plan review
Open `shot_edit_plan.json` and check every shot:
- `source.start_frame_no` and `source.end_frame_no_exclusive` use the half-open interval convention; compare them with the source and evidence frames.
- `source.start_seconds` / `source.end_seconds`, target duration, frame count, and order agree with the intended edit. Investigate rounding discrepancies rather than silently accepting them.
- The subject remains fully visible. Keep `crop: null` unless a reviewed bounding box or explicit manual crop approval exists; confirm the declared contain/background-fill policy is visually acceptable.
- Confirm hard cuts are acceptable at every boundary. Any transition, retiming, or reordered shot needs an explicit editorial decision and updated plan.
- Confirm subtitles are disabled unless text and timing have been verified. Confirm the music policy, gain, fades, and whether the source track should remain continuous.
- The generated plan is a draft: `acceptance.render_approved` must remain false until an authorized human approves the exact plan and source hash. Never change this flag merely to make a render command run.

Record each shot as PASS, FAIL, or REVIEW with a short reason. Any FAIL blocks approval; REVIEW means the missing evidence or decision must be resolved before rendering.

### Gate D — render and post-render content QA
- First confirm the output file opens, has the declared dimensions and frame rate, has expected audio, and its duration is within the declared tolerance. Check `render_report.json` and `render_qa.json`.
- Play the entire output once at normal speed with audio. Then inspect each detected black/freeze/silence interval with a few seconds of surrounding context. Intentional fades, still shots, and quiet passages may be valid; detections are review candidates, not automatic failures.
- Listen with headphones to the beginning, end, every edit boundary, and any flagged interval. A peak near 0 dBFS is a clipping-risk warning, not proof of clipped samples; listen for clicks/pops/distortion and inspect the waveform or true-peak measurement when needed.
- Check for subject cropping/deformation, unexpected blank bars/backgrounds, flashes, duplicated/frozen frames, abrupt audio cuts, lost key actions, subtitle errors, and pacing problems.
- Keep automated technical QA and human content QA as separate results. Mark PASS only when both pass; document intentional exceptions with timestamps and reviewer notes.

### Review record template
Create a review record next to the artifacts with:
- source SHA-256 and candidate/plan SHA-256;
- reviewer and review date;
- Gate A/B/C/D status (PASS / FAIL / REVIEW);
- per-shot status and notes, including source and output timestamps for each issue;
- accepted exceptions (for example, an intentional freeze or silent pause);
- final decision: `APPROVED`, `REJECTED`, or `NEEDS_REVISION`.

The current CI fixture contains sparse one-second image samples. Passing these gates does not establish complete motion coverage or prove AI-generated new actions/viewpoints. Motion-dense sampling and an editor-approved shot-assembly renderer remain separate work items.

## Editor-approved shot assembly renderer (MVP)

`scripts/render_edit_plan.py` now assembles actual source intervals in plan order and concatenates them with hard cuts. It preserves the source audio as a continuous track trimmed to the assembled video duration. This is genuine shot-level editing (trim + order + concatenate), but it does not generate new actions, synthesize camera viewpoints, implement crop/reframing, or burn subtitles. The renderer refuses aspect-ratio conversion, non-cut transitions, crop instructions, and enabled subtitles rather than silently ignoring them.

The renderer is deliberately **not added as an automatically approved production step in CI**. The generated `shot_edit_plan.json` remains a draft. After a human has reviewed the exact source and every shot, make an explicit reviewed copy of the plan and set:
- top-level `acceptance.editor_approved: true`;
- top-level `acceptance.render_approved: true`;
- top-level `acceptance.reviewer: "<reviewer identifier>"`;
- every shot's `review_status: "APPROVED"`.

These fields record an explicit decision; they are not proof that the review happened. Do not set them just to bypass the guard. The renderer also locks to the source SHA-256, validates half-open frame intervals and time intervals, and writes a provenance report with source/output hashes and the edit-plan hash.

Example after manual approval:
```powershell
python scripts/render_edit_plan.py `
  --video a.mp4 `
  --plan artifacts/real_video_e2e/shot_edit_plan.approved.json `
  --out artifacts/real_video_e2e/rendered/a_assembled.mp4 `
  --report artifacts/real_video_e2e/edit_plan_render_report.json `
  --qa artifacts/real_video_e2e/edit_plan_render_qa.json `
  --content-qa artifacts/real_video_e2e/edit_plan_content_qa.json
```

Review the output in a media player and inspect all three JSON reports. The automated QA is technical; content QA remains a review-candidate list. The report's `creative_reconstruction_claimed` remains false because this renderer assembles existing source shots and does not recreate missing actions.


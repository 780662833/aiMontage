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

The deterministic policy and regression tests live in `src/aimontage/audio_review.py` and `tests/test_audio_review.py`. This reviewed label is specific to the current fixture; other videos should use their own reviewed classification rather than inherit it. The workflow also runs `scripts/run_music_timeline_e2e.py`, which extracts mono signed 16-bit PCM through FFmpeg and writes `music_timeline_evidence.json`. `src/aimontage/music_timeline.py` computes a configurable RMS energy envelope, threshold-based silence intervals, and candidate energy transients. Candidate transients are not asserted to be musical beats, and the module does not classify music versus speech or infer tempo. The next workflow stage runs `scripts/build_cross_modal_timeline.py`, requiring the visual and audio artifacts to have the same source SHA-256 and durations within a configurable tolerance. It emits `cross_modal_timeline.json` with source-time events, visual half-open frame intervals, and explicit candidate confidence statuses. `scripts/build_blueprint_draft.py` then writes `blueprint_draft.json`: scene timing and evidence references are populated, while semantic descriptions and creative edit intent remain null until annotated. This artifact is deliberately `evidence_aligned_draft`, not production-ready Blueprint.
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
- [x] Define and test a cross-modal event schema joining music events with visual scene intervals, with source-hash and duration checks.
- [x] Build an evidence-aligned Blueprint draft with a transcript exclusion gate for music-only sources.
- [ ] Annotate visual semantics/camera motion from sampled-frame evidence and define target-output requirements before promoting the draft to production-ready Blueprint.

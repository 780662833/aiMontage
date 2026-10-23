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
`scripts/run_transcriber_e2e.py` invokes the upstream local ASR tool with explicit model/language, validates segment and word timestamps against media duration, and records model settings plus raw output. CI uses `tiny` to bound runtime. An empty transcript is not a tool failure; it is recorded as `speech_detected: false` and should be reviewed against source audio.

```powershell
python scripts/run_transcriber_e2e.py --video a.mp4 --out artifacts/real_video_e2e/transcription --model-size tiny --language en
```

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
- [ ] Controlled real-video Whisper transcription passes and audio presence is reviewed.
- [ ] Live caption fetch passes with an explicit YouTube URL with accessible captions.
- [ ] Evidence bundle accepted as Blueprint input after transcript and timestamp checks.

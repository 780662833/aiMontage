# Phase 1 — Analysis tool integration

## Pinned external source

- Repository: `https://github.com/calesthio/OpenMontage.git`
- Revision: `c8066452325cb57c8fc1ba8c2a71b6e8842e6b65`
- Integration method: Git submodule at `vendor/OpenMontage`; do not vendor/copy individual tool scripts.
- Upstream license: AGPL-3.0. Review obligations before distributing or offering a network service using modified/combined code.

## Tool map

| Capability | Upstream path | Contract in aiMontage |
|---|---|---|
| Audio/media probe | `tools/analysis/audio_probe.py` | Preserve source path/hash and store probe result as evidence. |
| Scene detection | `tools/analysis/scene_detect.py` | Preserve raw candidates and map scene boundaries to source PTS/frame intervals. |
| Frame sampling | `tools/analysis/frame_sampler.py` | Preserve raw results and add source frame number, source PTS, relative path, image SHA-256, and source SHA-256. |
| Caption retrieval | `tools/analysis/transcript_fetcher.py` | Record source/provider and original caption timestamps; requires a YouTube URL and network. |
| Speech transcription | `tools/analysis/transcriber.py` | Record model/configuration and word/segment timestamps; distinguish generated transcript from fetched captions. |

## aiMontage-owned invariants

- Source video SHA-256 identifies the immutable input.
- `source_pts_time` is authoritative for source timeline alignment. Decoder-reported timestamps are diagnostic only.
- Associate sampled evidence using stable `(source_sha256, frame_no)`, not filenames alone.
- Use POSIX-style relative paths in normalized manifests; preserve raw upstream output separately for forensic traceability.
- Use half-open frame intervals: `[start_frame_no, end_frame_no)`.
- Timestamp/frame association audit must report `aligned`, `ambiguous-neighbor`, or `reorder`; suspicious ordering must not be silently corrected.
- Keep raw tool output alongside normalized aiMontage records.

## Real-video end-to-end check

The root `a.mp4` fixture is processed by `scripts/run_real_video_e2e.py`. The check:

1. Calculates source SHA-256 and reads per-frame source timestamps with ffprobe.
2. Audits frame order and timestamp completeness without sorting or silently repairing rows.
3. Executes pinned upstream `audio_probe`, `scene_detect`, and `frame_sampler`.
4. Normalizes detected scenes to contiguous half-open source-frame intervals.
5. Associates every sampled image with its nearest source frame PTS, relative POSIX path, image SHA-256, and source SHA-256. Association fails if the sample timestamp is farther than half a 30-fps frame from the mapped source PTS.
6. Stores normalized data and the unmodified raw tool results in `artifacts/real_video_e2e/evidence_bundle.json`.
7. Uploads the evidence bundle, scene JSON, and extracted frames as a 14-day GitHub Actions artifact.

Caption retrieval remains a separate network-dependent test because it requires a YouTube URL; a local MP4 is not a valid caption-fetcher input. Whisper transcription uses a model download and should be run as a separately controlled integration check with an explicit model and cache policy.

Run locally from the repository root:

```powershell
python -m pip install -e ".[test]"
python -m pip install -r requirements-phase1.txt
python scripts/check_environment.py
python scripts/run_real_video_e2e.py --video a.mp4 --out artifacts/real_video_e2e
python -m pytest -q
```

## Verification status

- [x] Submodule resolves to the pinned revision in CI.
- [x] FFmpeg/ffprobe availability is checked before media jobs.
- [x] Thin invocation adapters exist for five upstream tools.
- [x] Timestamp audit unit tests cover missing PTS, duplicate/nearby timestamps, and deliberate frame-row reorder.
- [x] Real `a.mp4` run passed: 371 source frames audited, 3 scene intervals, 12 sampled images, and all three deterministic upstream tools succeeded.
- [x] Sampled images visually inspected as a contact sheet; images cover the source from 0 through 11 seconds and show the expected shot/scale change.
- [x] Normalized source-frame associations and image hashes are now asserted in tests and generated in the evidence bundle.
- [ ] Controlled real-video Whisper transcription run and review of whether any speech is present.
- [ ] Live caption-fetch test against an explicit YouTube URL.

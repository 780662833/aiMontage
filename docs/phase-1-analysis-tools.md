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
| Scene detection | `tools/analysis/scene_detect.py` | Store raw candidates and detector/version metadata; do not treat candidates as authoritative source-frame indices. |
| Frame sampling | `tools/analysis/frame_sampler.py` | Record sampled frame number, source PTS time, relative image path, and source SHA-256. |
| Caption retrieval | `tools/analysis/transcript_fetcher.py` | Record source/provider and original caption timestamps. |
| Speech transcription | `tools/analysis/transcriber.py` | Record model/configuration and word/segment timestamps; distinguish generated transcript from fetched captions. |

## aiMontage-owned invariants

- Source video SHA-256 identifies the immutable input.
- `source_pts_time` is authoritative for source timeline alignment. Decoder-reported timestamps are diagnostic only.
- Associate sampled evidence using stable `frame_no` plus source SHA-256, not filenames alone.
- Use POSIX-style relative paths in manifests.
- Use half-open frame intervals: `[start_frame_no, end_frame_no)`.
- Timestamp/frame association audit must report `aligned`, `ambiguous-neighbor`, or `reorder`; suspicious ordering must not be silently corrected.
- Keep raw tool output alongside normalized aiMontage records for traceability.

## Real-video end-to-end check

The committed `a.mp4` fixture is processed in CI by `scripts/run_real_video_e2e.py`. The check:

1. Calculates the source SHA-256 and reads per-frame source timestamps using ffprobe.
2. Audits frame order and timestamp completeness without sorting or silently repairing rows.
3. Executes the pinned upstream `audio_probe`, `scene_detect`, and `frame_sampler` on the actual video.
4. Saves each raw tool result in `artifacts/real_video_e2e/evidence_bundle.json`, together with source hash, pinned upstream revision, and timestamp audit.
5. Fails if a tool reports failure, PTS is missing/reordered/ambiguous, or no sampled image is produced. CI uploads the evidence bundle and extracted frames as an artifact.

Caption retrieval is intentionally not part of this local-file test because the upstream tool requires a YouTube URL and network access. Whisper transcription is not run by default because it may download a model and has a materially higher runtime; it should be tested separately with an explicitly selected model and cache policy.

Run locally from the repository root:

```powershell
python -m pip install -e ".[test]"
python -m pip install -r requirements-phase1.txt
python scripts/check_environment.py
python scripts/run_real_video_e2e.py --video a.mp4 --out artifacts/real_video_e2e
python -m pytest -q
```

## Initial verification checklist

- [x] Submodule resolves to the pinned revision in CI.
- [x] FFmpeg/ffprobe availability is checked before media jobs.
- [x] Thin invocation adapters exist for the five upstream tools.
- [x] Caption fetching and local transcription are separate fallback paths.
- [x] Timestamp audit tests cover missing PTS, duplicate/nearby timestamps, and deliberate frame-row reorder.
- [x] Real-video CI job runs media probe, scene detection, frame sampling, and source PTS audit on `a.mp4`.
- [ ] Real-video run passes in CI and its evidence artifact is inspected.

## Status

Unit tests, environment checks, and upstream import checks passed in a clean GitHub Actions runner before the real-video test was added. The new end-to-end step is the first actual execution of the three deterministic upstream analysis tools against the repository's `a.mp4` fixture; its status must be confirmed from the new CI run before claiming Phase 1 end-to-end validation.

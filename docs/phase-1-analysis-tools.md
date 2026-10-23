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

## Initial verification checklist

- [ ] Submodule resolves to the pinned revision.
- [ ] FFmpeg/ffprobe availability is checked before media jobs.
- [ ] Each tool has a thin invocation adapter and a documented input/output contract.
- [ ] Caption fetching and local transcription are separate fallback paths.
- [ ] Timestamp audit tests cover missing PTS, duplicate/nearby timestamps, and deliberate frame-row reorder.
- [ ] Sample outputs can be traced to source video SHA-256 and source PTS.

## Status

The pinned dependency and integration contract are being established first. Runtime adapters and end-to-end fixture tests are the next Phase 1 implementation items; no media job is claimed complete by this documentation commit.

# aiMontage

Independent evidence-first workflow for reference-video analysis and short-form video production.

## Design rules

- aiMontage is a standalone repository, not an OpenMontage fork.
- OpenMontage is referenced as a pinned Git submodule at commit `c8066452325cb57c8fc1ba8c2a71b6e8842e6b65`.
- Do not copy individual upstream tool files into aiMontage; call them through adapters.
- Keep aiMontage-owned media facts, source-timestamp audit, evidence bundle, Blueprint, render orchestration, and QA gates independent.
- Preserve the upstream official `video_analysis_brief` schema unchanged.

## Architecture and local runbook

See [`docs/l0-l1-runbook.md`](docs/l0-l1-runbook.md) for the L0/L1 layer boundaries, PowerShell commands, outputs, and current acceptance notes.

## Phase 1: analysis tools

Integrate `audio_probe`, `scene_detect`, `frame_sampler`, and `transcript_fetcher` / `transcriber`. See [`docs/phase-1-analysis-tools.md`](docs/phase-1-analysis-tools.md).

## Planned stages

1. Analysis tools and timestamp-audited evidence.
2. `video_analyzer` output validated against the official schema, plus an aiMontage-owned Blueprint.
3. Real 9:16 render using `subtitle_gen`, `video_trimmer`, `video_stitch`, and FFmpeg.
4. Technical and content quality gates.

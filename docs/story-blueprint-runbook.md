# Story Blueprint and evidence packet runbook

This workflow reuses OpenMontage's official analysis and aiMontage's existing dense-frame
evidence. It deliberately keeps semantic story claims unverified until a multimodal
review step can cite the actual frames.

## Windows PowerShell

```powershell
Set-Location "F:\python\aiMontage"
git pull origin aimontage/phase-1-analysis-tools
$env:PYTHONPATH = (Join-Path (Get-Location).Path "src")

python -m pytest `
  tests/test_build_openmontage_event_draft.py `
  tests/test_build_story_blueprint.py `
  tests/test_build_story_evidence_packet.py -q
```

### 1. Build L2 event candidates from the OpenMontage brief

```powershell
python scripts/build_openmontage_event_draft.py `
  --brief artifacts/openmontage_video_analysis/video_analysis_brief.json `
  --manifest artifacts/openmontage_video_analysis/analysis_run_manifest.json `
  --out artifacts/openmontage_video_analysis/l2_event_draft.json
```

If these upstream artifacts live in a different directory, adjust only the input paths.

### 2. Join scene candidates to the 0.25-second dense samples

```powershell
python scripts/build_story_evidence_packet.py `
  --event-draft artifacts/openmontage_video_analysis/l2_event_draft.json `
  --dense-evidence artifacts/real_video_e2e/dense_frames/dense_frame_evidence.json `
  --motion-report artifacts/real_video_e2e/motion_dense_review.json `
  --out artifacts/openmontage_video_analysis/story_evidence_packet.json
```

The packet joins samples by source PTS time and requires source SHA-256 agreement.
It includes source frame number, sample index, image hash, relative image path, upstream
scene signals, and optical-flow candidate intervals. It does not treat flow as action
recognition. If the source hashes differ, stop and investigate; do not bypass the guard.

### 3. Build the Blueprint skeleton

```powershell
python scripts/build_story_blueprint.py `
  --event-draft artifacts/openmontage_video_analysis/l2_event_draft.json `
  --out artifacts/openmontage_video_analysis/story_blueprint.draft.json
```

The skeleton preserves timing candidates and keyframe references. It intentionally
leaves action, actor, target, before/after state, causal links, and confidence empty.
The Blueprint is not ready for remake planning until these fields are grounded in
visual/audio evidence.

## Current implementation limits

- The joiner links dense samples that fall within each upstream scene candidate interval;
  overlapping intervals may share samples.
- Scene boundaries are navigation hints, not guaranteed story-event boundaries.
- The joiner does not yet associate samples to the nearest upstream keyframe image path;
  dense sample paths and keyframe references remain separately traceable.
- Semantic review is still the next implementation step. Do not use null fields as
  evidence that an action did not occur.
- The original video and OpenMontage official brief are never mutated.

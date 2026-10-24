# Semantic review template runbook

This stage turns the evidence packet into a structured review worksheet. It does not
infer story semantics. A reviewer must inspect the referenced images and fill in
observable entities/actions, before/after state, cause/reaction, story function, must-
preserve details, uncertainty, confidence, and the evidence sample indices supporting
each claim.

## Build the worksheet

```powershell
python scripts/build_semantic_review_template.py `
  --evidence-packet artifacts/openmontage_video_analysis/story_evidence_packet.json `
  --out artifacts/openmontage_video_analysis/semantic_review.draft.json
```

Open the JSON in an editor. For each event, inspect `evidence[].relative_path` images
and enter only what is supported by those frames/source playback. Preserve uncertainty;
do not treat scene boundaries or optical-flow candidates as verified actions. Cite the
`sample_index` values in `review.evidence_sample_indices`.

The generated template intentionally reports `ready_for_edit_plan=false`. The next
stage should consume a reviewed copy and reject missing semantic fields or unsupported
evidence references; never edit the generated packet to fake a review pass.

## Tests

```powershell
python -m pytest tests/test_build_semantic_review_template.py -q
```

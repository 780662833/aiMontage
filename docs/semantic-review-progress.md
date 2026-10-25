# Semantic review progress — a.mp4

Branch: `aimontage/phase-1-analysis-tools`

Source identity recorded in the existing dense-frame evidence:
- SHA-256: `c47cb72f6673402dbceec272530e7af8566db88c4f3905bb0d96046c4f297235`
- Duration: approximately 12.374 s
- Evidence inventory: 49 dense samples at 0.25 s intervals; source PTS remains authoritative.

This file is a progress note, **not** the machine-consumable `semantic_review.reviewed.json`. Approximate intervals below must not be treated as frame-accurate edit points.

## Event review

| Event | Approximate source interval | Current observation | Status |
|---|---:|---|---|
| E01 | 0.0–3.0 s | The man taps the woman's shoulder to signal her to follow him / do the same action. | User-confirmed semantic description; exact in/out still requires playback confirmation. |
| E02 | around 3.0–5.0 s; broader evidence window 3.0–7.5 s | Prior contact-sheet review noted a banana handoff/bite in this section. | Candidate only; exact action sequence and boundaries need confirmation. |
| E03 | around 5.2–7.2 s | Prior review noted a reaction close-up. | Candidate only; describe only visible expression/action after reviewing the frames. |
| E04 | around 7.5–12.0 s | Prior review noted escalating gestures. Possible arm-to-face contact around 11.7 s was flagged for verification. | Candidate only; confirm whether contact occurs and record the visible reaction. |

## Next actions

1. Review the 49-frame chronological contact sheet alongside the original video.
2. Confirm E01's exact in/out and the shoulder tap / response sequence.
3. Split E02/E03 only where the visible action or narrative beat supports a split; avoid overlapping shots unless intentional.
4. Confirm E04's gestures and whether the apparent arm-to-face contact is real.
5. Populate the event-level evidence sample indices from the actual evidence packet. Do not infer indices solely from approximate timestamps.
6. Only after every event has evidence-backed semantics, generate `semantic_review.reviewed.json` and run `scripts/build_shot_edit_plan.py`.

## Production constraints

- No voiceover was identified; source audio is background music only.
- Do not invent dialogue or subtitles.
- Keep the renderer blocked until shot timing, 9:16 composition, story fidelity, and audio QA are genuinely reviewed.

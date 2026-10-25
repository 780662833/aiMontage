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
| E02 | around 3.0–5.0 s; broader evidence window 3.0–7.5 s | The man asks the woman to imitate his movements while she holds a banana. During the second action, the banana comes close to the man, who takes the opportunity to bite it. | User-confirmed action sequence; exact boundaries and evidence indices still require frame-level confirmation. |
| E03 | around 5.2–7.2 s | The man chews the banana and appears to act innocent. The woman may be momentarily stunned, then puts down the remaining banana still partly wrapped in its peel; the story seems to turn toward her planning revenge. | User-described, with uncertainty explicitly retained for the woman's reaction and intent; exact visible actions and boundaries need playback confirmation. |
| E04 | around 7.5–12.0 s | Prior review noted escalating gestures. Possible arm-to-face contact around 11.7 s was flagged for verification. | Candidate only; confirm gestures, any contact, and the visible reaction. |

## Editorial invariants

- Preserve E01's shoulder-tap imitation cue.
- Preserve E02's causal chain: imitation cue → second action brings banana close → man bites opportunistically.
- For E03, distinguish visible action (chewing, putting down the banana) from interpretation (acting innocent, planning revenge); do not state inferred intent as an objectively verified facial expression.
- Do not invent dialogue or subtitles. The source was previously identified as background music only, with no voiceover.

## Next actions

1. Review the 49-frame chronological contact sheet alongside the original video.
2. Confirm exact in/out points and the sample indices supporting E01–E03.
3. Confirm E04's gestures and whether the apparent arm-to-face contact is real.
4. Populate event-level evidence sample indices from the actual evidence packet. Do not infer indices solely from approximate timestamps.
5. Only after every event has evidence-backed semantics, generate `semantic_review.reviewed.json` and run `scripts/build_shot_edit_plan.py`.

## Production constraints

Keep the renderer blocked until shot timing, 9:16 composition, story fidelity, and audio QA are genuinely reviewed. This note is not an approved semantic review artifact.
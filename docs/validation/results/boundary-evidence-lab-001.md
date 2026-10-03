# Boundary Evidence Lab - Run 001 (ED-0126 Phase A separability)

## Status and authority boundary

**COMPLETED. ONE FAMILY CLEARLY LEADS: VOICE CONTINUITY. THE LANGUAGE-MODEL REFEREE FAILS AS BUILT.**

- **Voice continuity** separates talk edges from ordinary moments on both corpora:
  - **held out:** 0.78–0.88 for ends and 0.72–0.86 for starts;
  - **cross-corpus:** it keeps the same direction on both, at 0.73–0.88.

  No other family exceeds 0.65 cross-corpus.
- **Usable secondary signals** keep the same direction in both corpora:
  - music-cue correlation for ends, 0.58–0.64;
  - Whisper average log probability for starts, 0.57–0.61;
  - Whisper compression ratio for ends, 0.56–0.60.
- **Venue-dependent signals** reverse direction between corpora: audio loudness and flux for ends, title-card
  similarity and scene change for starts. They are unusable without per-venue calibration.
- **The language-model referee does not add information.** Its median error is 141–199 s, about chance in its
  360 s window. In 32 of 45 real-edge windows on corpus A, it chose the last sentence of the window.
- **Whisper no-speech probability is constant at 0.0.** This holds on every segment and on synthetic silence and
  tone (finding F1).

This is the Phase A result of the [boundary-evidence plan](../../plans/boundary-evidence-sequence-model.md), using
the ED-0126 tooling: offline separability on owner archive recordings. It ran on the development machine. No
detector was trained or calibrated, and these numbers are not product accuracy. Only sanitized values are
committed: no media, names, titles, schedules, transcripts, prompts or times.

## Setup

- **Code:**
  - `main` at `0dcb579`: ED-0126 plus #199, #200 and #201, with the referee version parser.
  - Ground truth used the endpoint-anchor method later merged as #202.
- **Script:** `scripts/validation/boundary_evidence_lab.py`, run with all six families:
  - `audio_stats`, `picture`, `music_cue`, `whisper`, `voice_continuity`;
  - `llm_referee`.
- **Corpora:** owner archive recordings, kept local. Rights for internal use were confirmed on 2026-10-01.

  | Corpus | Content | Recorder blocks | Labelled edges |
  | --- | --- | --- | --- |
  | **A** | a three-day single-stage event | 112 ten-minute vMix blocks | 27 talks |
  | **B** | an earlier edition of the same event, three days | 106 blocks | 29 sessions |

  Each corpus has its own title-card set and music cue as references.
- **Ground truth:** export-to-block audio cross-correlation (`derive_ground_truth.py`).
  - **Corpus A:** from the edit project's decoded in/out points, cross-checked by audio.
  - **Corpus B:** derived entirely from the edited exports.
    - Window alignment covered 15 of 34 exports.
    - Endpoint anchors covered the rest. On aligned exports they agree with window alignment to within 1 s, with
      one 5.6 s case.
    - Three exports were edits of one session and were collapsed into one. That session's end is uncertain by
      about 50 s.
    - All exports from one day were padded with up to 1,370 s of trailing digital silence, which the tooling now
      trims.
- **Referee:**
  - **Model:** Qwen2.5-7B-Instruct Q4_K_M (Apache-2.0), SHA-256
    `1875fb29e8c91c86615c00e92d8b4114e56bc24359adb5a8db8b36452fae4a49`.
  - **Runtime:** llama.cpp build 11342 (`f1cee9941`, MIT), CUDA 12.4.
  - **Decoding:** grammar-constrained, temperature 0, seed 42.
- **Machine:** RTX 3080 Ti Laptop GPU (16 GiB) and a 12th-generation Core i7-12800H. Whisper used large-v3-turbo in
  `float16` on the ED-0122 engine.
- **Runs:** both exited 0.

  | Corpus | Wall time | Conditions | Status counts |
  | --- | --- | --- | --- |
  | A | 8.1 h | shared the CPU with ground-truth jobs | all families `ok` on all blocks, except 1 `music_cue` `skipped` (block shorter than the reference) and 1 referee point `failed` |
  | B | 5.1 h | sole job | 2 `music_cue` `skipped` |

## Results: separability

Each value is `max(AUC, 1 − AUC)` against truth edges:
- **positives:** seconds within ±15 s of an edge;
- **negatives:** seconds more than 120 s from any edge.

0.5 is chance. **Held out** is the mean over stage-days, with direction chosen from the other stage-days.
**Cross-corpus** applies one corpus's pooled direction to the other corpus, in both directions; the table shows the
lower and the higher of the two.

### Ends

| Family / feature | Held out A | Held out B | Cross-corpus | Same direction |
| --- | --- | --- | --- | --- |
| Voice continuity (cosine distance, higher) | 0.884 | 0.780 | 0.783–0.884 | yes |
| Music-cue correlation (higher) | 0.575 | 0.632 | 0.583–0.640 | yes |
| Whisper compression ratio (lower) | 0.605 | 0.560 | 0.563–0.597 | yes |
| Picture scene score (lower) | 0.438 | 0.601 | 0.510–0.610 | yes, weak in A |
| Audio flux / momentary loudness / RMS | 0.61–0.64 | 0.52–0.53 | 0.36–0.48 | **no** |
| Spectral centroid / rolloff (higher) | 0.57 | 0.50–0.53 | 0.51–0.57 | yes, weak |
| Black frames, music-cue detection, no-speech probability | ≤ 0.53 | ≤ 0.50 | ≈ 0.50 | — |

### Starts

| Family / feature | Held out A | Held out B | Cross-corpus | Same direction |
| --- | --- | --- | --- | --- |
| Voice continuity (cosine distance, higher) | 0.858 | 0.724 | 0.732–0.854 | yes |
| Whisper average log probability (lower) | 0.614 | 0.593 | 0.574–0.609 | yes |
| Whisper compression ratio (lower) | 0.554 | 0.557 | 0.550–0.557 | yes |
| Audio flux / momentary loudness (lower) | 0.42–0.43 | 0.55–0.56 | 0.51–0.55 | yes, weak |
| Picture scene score | 0.618 | 0.647 | 0.36–0.39 | **no** |
| Title-card similarity | 0.444 | 0.686 | 0.33–0.47 | **no** |
| Black frames, music cue, no-speech probability | ≈ 0.50 | ≈ 0.50 | ≈ 0.50 | — |

### Peak timing

The peak search uses ±120 s and reports pooled hit rates.

- **Voice continuity:**
  - **ends:** hits within 30 s on 0.67 (A) and 0.48 (B), with a median lag of +19 s and +28 s;
  - **starts:** hits within 30 s on 0.44 and 0.28, with the peak leading the logged start by 37–42 s.

  It fires at the speaker change, which for starts is usually the host's handoff before the talk.
- **Title-card similarity on corpus A** has low AUC, but its peak lands within 10 s of 44% of starts (67% on one
  day). It behaves as a sparse, occasional anchor rather than a continuous score. On corpus B its direction flips.

## Results: language-model referee

| Corpus | Role | Median absolute error | p90 | Edges answered | Negative agreement |
| --- | --- | --- | --- | --- | --- |
| A | start | 199 s | 245 s | 27 / 27 | 0.19 |
| A | end | 156 s | 248 s | 18 / 27 | 0.26 |
| B | start | 199 s | 249 s | 29 / 29 | 0.03 |
| B | end | 141 s | 248 s | 27 / 29 | 0.03 |

- **Positional bias.** We recomputed each window's deterministic placement. In 32 of 45 answered corpus-A truth
  windows, the chosen index was the window's last sentence.
- **Over-calling.** It also claims an edge in almost every negative window. Agreement is 0.03 on corpus B.
- **Cost.** 8–25 s per evaluated point.
- **Plan test.** The plan's test is "ships only if it adds accuracy on ends beyond the cheaper families". As built
  (prompt, 7B model, index choice), the referee does not meet it.
- **Possible redesigns.** Each would need its own lab measurement:
  - derive edges from the section-label transitions that the referee already returns;
  - score each sentence yes or no instead of choosing an index;
  - try a 14B model from the licence allowlist.

## Cost per ten-minute block

| Family | A | B |
| --- | --- | --- |
| Picture (scene, black, title cards) | 99.8 s | 73.1 s |
| Whisper inspection (shared with continuity) | 19.3 s | 17.8 s |
| Music cue | 6.9 s | 4.9 s |
| Audio statistics | 4.2 s | 3.3 s |

Picture extraction dominates. It runs at 1 fps with a scaled graphic match; corpus A also had CPU contention.

## Findings

- **F1: Whisper no-speech probability is always 0.0.**
  - **Scope:** all 14,638 corpus-A segments. Reproduced on synthetic digital silence, low noise and a tone, with and
    without suppressing `<|nospeech|>`.
  - **Configuration:** CTranslate2 4.8.1, large-v3-turbo, `float16`. The vocabulary and tokenizer do resolve
    `<|nospeech|>`.
  - **Production effect:** the engine's no-speech skip (`no_speech_prob > 0.6`) never fires.
  - **Not a regression:** this matches the qualified parity baseline, which used the same runtime path.
  - **Next step:** needs its own investigation before any evidence or production use.
- **F2: a missing CUDA library hangs the lab.** When the isolated CUDA library directory is not on `PATH`, Whisper
  inspection hangs instead of failing. The Demo launcher already preflights this. The lab should fail fast in the
  same way.
- **F3: the referee version format.** The referee now accepts the current llama.cpp version format (#201).

## Conclusions for Phase B (ED-0127)

- **Primary end evidence:** voice continuity, as the plan anticipated. Pair it with the changeover grammar, since it
  also fires at in-talk speaker changes such as Q&A and panels.
- **Secondary end evidence:** music-cue correlation and Whisper compression ratio, both stable across corpora.
  Calibrate them per family and never use them alone.
- **Excluded unless calibrated per venue:** audio loudness, flux and RMS for ends, and picture scene and title-card
  similarity for starts. Their direction is venue-dependent.
- **Starts:** voice continuity leads the logged start by about 40 s, so the v6 grammar should model a host-handoff
  segment.
- **Referee:** not included in v6 unless a redesigned referee passes a new lab run.

## Limitations

- **Small sample:** 56 labelled edges per role over six stage-days, from two editions of one event series.
- **Truth precision:** corpus-B truth has endpoint-anchor precision (about 1 s), and one session's end is uncertain
  by about 50 s.
- **Voice-continuity sampling:** it is sampled at 10 s window boundaries, so its observation count is about
  one-tenth of the per-second families.
- **Descriptive only:** hit rates and AUC are descriptive. No family was fitted, and the held-out direction is the
  only cross-validation.

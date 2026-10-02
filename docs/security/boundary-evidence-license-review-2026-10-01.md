# Boundary evidence: licence and risk review (2026-10-01)

## Purpose and status

This review covers the candidate evidence sources and runtimes for the proposed probabilistic
boundary model ([ADR-0038](../adr/ADR-0038-probabilistic-boundary-model.md)). For each one it
records its licence, its data-provenance and privacy exposure, and any operational catches.
It is research evidence, not legal clearance. A row marked "OK" means no blocking issue was
found under StageFlow's rules:
- no copyleft component in what StageFlow ships;
- NVIDIA runtime libraries allowed (the [ED-0122 D2 amendment](../plans/gpl-free-transcription-engine.md));
- offline operation;
- owner-operated appliance ([ADR-0037](../adr/ADR-0037-owner-operated-gpu-appliance-baseline.md)).

Sources were checked on 2026-10-01 and are listed under [Sources](#sources).

## Summary

- **The cleanest and fastest evidence is the evidence StageFlow already pays for:**
  - extra statistics from FFmpeg filters in the operator's existing LGPL build, added to the
    decode pass that already runs;
  - by-products of the Whisper engine already accepted under ADR-0036.

  These add no new licence class.
- **Third-party audio-event and speaker models are licence-clean as code and weights.** But
  they are trained on YouTube-derived datasets (AudioSet and VoxCeleb), whose audio terms are
  non-commercial research. Some publishers therefore treat the trained models as
  non-commercial. **Recommendation:** keep them as optional comparisons, not shipped
  defaults. Train StageFlow's own small detectors on the owner's archive instead, after
  confirming the owner may use that footage for training.
- **Speaker *identification* (an enrolled voiceprint) is special-category biometric data**
  under GDPR Article 9, and needs explicit consent. **Recommendation:** use only unsupervised,
  same-session *voice continuity* (is this the same voice as a moment ago?), never stored and
  never linked to a person.
- **Production signals need no SDK.** Read the recording software (vMix TCP API, OBS
  WebSocket v5) over its documented local protocol. Avoid the GPL-3.0 OBS Python client.
  Hardware consoles and Companion are optional extras.
- **Patents:** the closest prior art found is expired. This is not a freedom-to-operate
  opinion.

## Findings

| Component | Licence (code / weights) | Verdict | Catches and mitigations |
| --- | --- | --- | --- |
| FFmpeg filters `aspectralstats`, `astats`, `ebur128`, `scdet`, `blackdetect`, `freezedetect`, `silencedetect` | In the operator's LGPL build. That build is configured with `--enable-version3`, which makes it LGPL-3.0. It runs as a separate process. | **OK** | Verified present in the build in use. LGPL-3.0 asks for "installation information" only for *User Products* (consumer or household products). A professional appliance is very likely outside that. Revisit if appliances are ever sold or leased to consumers. |
| Whisper by-products (no-speech probability, average log-probability, non-speech tokens, pooled encoder states) | Already accepted. The weights are MIT, trained on 680,000 h of web audio. | **OK** (an accepted risk class) | The model card warns of hallucination. Treat non-speech tokens as weak evidence only. Its stated intended use excludes transcribing people without consent, which is an event-operations matter covered by the client agreement. |
| StageFlow's own small detectors (logistic or tiny models over FFmpeg and Whisper features) trained on the owner's archive | StageFlow-owned | **OK, conditional** | Confirm that production contracts let the owner use client event footage to train internal models. Keep training data and labels off the repository. Ship only weights and calibration. |
| YAMNet (AudioSet, 521 classes, 16 kHz) | Code Apache-2.0 (TF Models); the TF Hub page code is Apache-2.0 | **Optional comparison only** | Trained on AudioSet. AudioSet labels are CC-BY 4.0 and its ontology CC-BY-SA 4.0, but the audio is YouTube content under non-commercial research terms. Whether that carries over to trained weights is unsettled. TensorFlow runtime is heavy. |
| PANNs CNN14 (frame-level sound event detection) | Code MIT; weights CC-BY-4.0 (Zenodo) | **Optional comparison only** | Same AudioSet caveat. |
| EfficientAT (MobileNet, distilled) | MIT | **Optional comparison only** | Clip-level tagging only, with no frame-level events. Same AudioSet caveat. |
| Speaker embeddings: SpeechBrain ECAPA (Apache-2.0), WeSpeaker (Apache-2.0 code) | Apache-2.0 | **Avoid as a shipped default** | Trained on VoxCeleb (CC-BY 4.0 data from YouTube). Some projects treat models trained on it as CC-BY-NC-SA. If used to *identify* someone, the output is biometric data under GDPR Article 9. |
| pyannote speaker-diarization 3.1 | MIT; the model is gated (a contact-information form) | **Avoid** | Account gating, a heavy PyTorch stack, and a commercial upsell. Not needed for voice continuity. |
| RapidOCR (ONNX) with PP-OCR-derived models | Apache-2.0 | **OK** (Phase E) | Offline on ONNX Runtime (MIT). Windows supported. |
| SigLIP image-text embeddings | Apache-2.0 weights | **OK** (Phase E) | Training data (WebLI) is web-scraped; same caveat class as Whisper. |
| Local LLM: Qwen2.5 0.5B, 1.5B, 7B, 14B or 32B; Phi-3.5-mini | Apache-2.0; MIT | **OK** (Phase E) | **Qwen2.5-3B is non-commercial (the Qwen Research licence). Do not use it.** 72B has a usage cap. Avoid the custom Llama and Gemma licences. Runtime llama.cpp is MIT; ONNX Runtime is MIT. |
| vMix TCP API (port 8099; `SUBSCRIBE TALLY` and `SUBSCRIBE ACTS`; XML state) | Documented protocol, available in all editions since v22 | **OK** | Read-only use. No vendor SDK to bundle. |
| OBS WebSocket v5 (built into OBS 28 and later; password authentication; scene, scene-item, mute, media-playback and record-file events) | The server plugin is GPL-2.0, but StageFlow only speaks its protocol | **OK** | Talking to a GPL server over a network protocol does not make the client GPL. **Do not use `obsws-python` (GPL-3.0).** `simpleobsws` is MIT, or implement the small client over a permissive WebSocket library (for example `websockets`, BSD-3, which would be a new dependency). |
| Blackmagic ATEM protocol | `atem-connection` is MIT (Node) | **OK through Companion** | Prefer Companion's relay to bundling a Node library. |
| Audio consoles: Behringer/Midas X32 OSC (`/subscribe`, mute and fader), Allen & Heath dLive MIDI over TCP (51325/51327), Yamaha RCP over TCP (49280) | Public or unofficial protocols | **OK, read-only** | Unofficial protocols can change with firmware. Isolate each behind its own adapter, and treat it as optional evidence. |
| Bitfocus Companion (an operator-run bridge with 700+ device modules) | MIT | **OK** | A separate operator tool, not bundled. StageFlow exposes one generic production-signal ingest (HTTP or OSC) that Companion buttons and feedbacks call. |
| Chromaprint `fpcalc` (music fingerprinting) | Licence depends on its FFT backend (FFTW makes it GPL) | **Not needed** | Stinger and bumper detection can reuse StageFlow's own cross-correlation, already proven on the archive. |
| ONNX Runtime | MIT | **OK** | Its GPU execution provider uses CUDA and cuDNN, allowed under the D2 amendment. |

## Privacy and regulation

- **GDPR Article 9:** a voiceprint used to uniquely identify a person is special-category
  biometric data, and needs explicit consent. Voice continuity that compares adjacent windows
  within one session, never stores embeddings and never names a person, avoids
  identification. Still, document it in the event privacy notice.
- **EU AI Act:** the biometric categories of concern are remote identification and
  categorisation. StageFlow performs neither under this design. Transcription itself is
  already part of ADR-0036.
- **Event footage rights:** footage and transcripts belong to, or are licensed by, the event
  client. The owner confirmed on 2026-10-01 that supplied archives may be used for this
  internal purpose.

## Patents (prior art, not a freedom-to-operate opinion)

| Patent | Subject | Status |
| --- | --- | --- |
| US6072542 | Video segmentation using hidden Markov models | Expired (priority 1997) |
| US7046914 | Multimedia table of contents with boundary detection | Expired (fee-related) |
| US9741345 | Speaker-model-based segmentation of video and audio into clips | Expired (fee-related) |

Explicit-duration (semi-Markov) segmentation is long-established academic technique. No live
blocking patent was found in this pass.

## Open items for the owner

1. **Training rights:** confirmed by the owner on 2026-10-01 for internal use.
2. Accept the "voice continuity, no identification" rule.
3. **Production signals:** focus on vMix and OBS (owner, 2026-10-01).

## Sources

- [OBS WebSocket v5 protocol](https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md); [simpleobsws (MIT)](https://pypi.org/project/simpleobsws/); [obsws-python (GPL-3.0)](https://libraries.io/pypi/obsws-python)
- [vMix TCP API](https://www.vmix.com/help28/TCPAPI.html); vMix API in all editions since v22 ([Wikipedia: vMix](https://en.wikipedia.org/wiki/VMix))
- [Bitfocus Companion licence (MIT)](https://github.com/bitfocus/companion/blob/main/LICENSE.md); [atem-connection (MIT)](https://www.npmjs.com/package/atem-connection)
- [YAMNet (TF Models)](https://github.com/tensorflow/models/tree/master/research/audioset/yamnet); [TF Hub YAMNet tutorial](https://www.tensorflow.org/hub/tutorials/yamnet)
- [AudioSet ontology](https://github.com/audioset/ontology); [AudioSet audio terms](https://huggingface.co/datasets/Muno459/audioset)
- [PANNs checkpoint (Zenodo)](https://zenodo.org/records/7939403); [EfficientAT (MIT)](https://github.com/fschmid56/EfficientAT)
- [SpeechBrain ECAPA](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb); [WeSpeaker](https://github.com/wenet-e2e/wespeaker); [VoxCeleb licence](https://www.robots.ox.ac.uk/~vgg/data/voxceleb/vox1.html); [VoxBlink2 note on models trained on YouTube data](https://voxblink2.github.io/)
- [pyannote speaker-diarization 3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
- [RapidOCR](https://github.com/RapidAI/RapidOCR); [SigLIP](https://huggingface.co/google/siglip-base-patch16-224); [ONNX Runtime licence](https://github.com/microsoft/onnxruntime/blob/main/LICENSE)
- [Qwen2.5 licences](https://qwenlm.github.io/blog/qwen2.5/); [Qwen2.5-3B (research licence)](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct); [Phi-3.5-mini (MIT)](https://huggingface.co/microsoft/Phi-3.5-mini-instruct); [llama.cpp](https://huggingface.co/docs/hub/gguf-llamacpp)
- [Whisper model card](https://github.com/openai/whisper/blob/main/model-card.md)
- [Chromaprint](https://github.com/acoustid/chromaprint)
- [X32 OSC protocol (unofficial)](https://tostibroeders.nl/wp-content/uploads/2020/02/X32-OSC.pdf); [dLive MIDI over TCP](https://www.allen-heath.com/content/uploads/2024/06/dLive-MIDI-Over-TCP-Protocol-V2.0.pdf); [Yamaha RCP (unofficial)](https://github.com/BrenekH/yamaha-rcp-docs)
- [FFmpeg filters](https://ffmpeg.org/ffmpeg-all.html)
- GDPR and voice biometrics: [EU AI Act biometric overview](https://www.euai-act.com/articles/biometric-ai-compliance), [GDPR voice data](https://fiund.com/rights/gdpr-and-voice-data)
- Patents: [US6072542](https://patents.google.com/patent/US6072542A/en), [US7046914](https://patents.google.com/patent/US7046914B2/en), [US9741345](https://patents.google.com/patent/US9741345B2/en)
- Explicit-duration models: [Murphy, HSMMs](https://www.cs.ubc.ca/~murphyk/papers/segment.pdf)

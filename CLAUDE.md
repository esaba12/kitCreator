# kitCreator: CLAUDE.md

The architecture bible for this project is:
`docs/architecture-report.md`
Read it before making any architectural suggestion. All design decisions flow from it.

---

## What This Project Is

A CLI tool that turns any song into a fully playable, multi-octave sampler kit (SFZ + DecentSampler format). Eventually a DAW plugin. Built solo by Ethan Saba, CS sophomore at U-Michigan.

**Pipeline:** song → source separation → polyphonic transcription → sample slicing + ADSR → CLAP-embedding clustering → pitch-shift fill → SFZ/DecentSampler export

**Phase 2 differentiator:** a DAC-token language model (~100M params) conditioned on pitch + velocity + CLAP timbre embedding that *generates* missing keyboard range instead of DSP-shifting.

---

## Project Layout

```
kitCreator/
├── CLAUDE.md
├── pyproject.toml
├── kitforge/
│   ├── __init__.py
│   ├── cli.py                   # Typer entry point
│   ├── config.py                # pydantic-settings + TOML
│   ├── pipeline.py              # high-level orchestrator
│   ├── cache.py                 # diskcache by content hash
│   ├── separation/
│   │   ├── demucs_runner.py
│   │   ├── roformer_runner.py
│   │   ├── larsnet_runner.py
│   │   └── query_separator.py   # Banquet-style w/ CLAP query
│   ├── transcribe/
│   │   ├── basic_pitch_runner.py
│   │   ├── mt3_runner.py
│   │   └── crepe_mono.py
│   ├── timbre/
│   │   ├── clap_embed.py
│   │   ├── mert_embed.py
│   │   └── classify.py
│   ├── extract/
│   │   ├── slicer.py
│   │   ├── adsr.py
│   │   ├── denoise.py
│   │   ├── cluster.py           # HDBSCAN over CLAP
│   │   └── loop_finder.py
│   ├── pitchshift/
│   │   └── rubberband_wrapper.py
│   ├── synth/                   # Phase 2 only
│   │   ├── dac_lm.py
│   │   ├── rave_runner.py
│   │   └── ddsp_runner.py
│   └── package/
│       ├── sfz_writer.py
│       ├── decentsampler_writer.py
│       └── ableton_writer.py
└── tests/
```

Do not create files outside this structure without discussing first.

---

## Canonical Tool Choices

These are locked in. Do not propose alternatives unless explicitly asked.

| Stage | Tool | Notes |
|---|---|---|
| Separation (default) | `htdemucs_ft` via `facebookresearch/demucs` | MIT, 9.20 dB SDR |
| Separation (quality mode) | BS-RoFormer via `python-audio-separator` | optional flag |
| Drum sub-stems | LarsNet (`polimi-ispl/larsnet`) | code MIT; weights CC-BY-NC 4.0 |
| Sub-instrument / query | Banquet (`kwatcharasupat/query-bandit`) | CLAP-conditioned |
| Transcription (polyphonic) | Basic Pitch (Spotify, Apache 2.0) | default for all pitched stems |
| Transcription (monophonic f0) | CREPE (`marl/crepe`) | bass, lead synth, melody |
| Transcription (multi-instrument) | MT3 / YourMT3+ | defer until needed |
| Timbre embeddings | LAION-CLAP (512-d) | universal currency for routing, clustering, conditioning |
| Music SSL features | MERT | supplement to CLAP |
| Pitch shifting | Rubber Band v3 R3 via `pyrubberband` | ±3 st acceptable, ±5 noticeable, ±7+ use neural fill |
| Denoising | DeepFilterNet (MIT) | post-separation residual cleanup |
| Clustering | HDBSCAN over CLAP embeddings | canonical sample + 2–4 round-robins |
| Caching | `diskcache` keyed by `(input_sha256, model_name, model_version, params_hash)` | every stage output cached |
| CLI framework | Typer | |
| Config | pydantic-settings + TOML | |
| MIDI | pretty_midi + mido | |
| Package manager | uv | Python 3.11 |
| Primary output | SFZ | emit simultaneously with DecentSampler |
| Secondary output | DecentSampler `.dspreset` | XML; SFZ import exists |

---

## Phase 2 Neural Stack (don't implement until Phase 1 is end-to-end on 5 test songs)

- **Audio tokenizer:** DAC (descriptinc/descript-audio-codec, 44.1 kHz, MIT)
- **Model:** decoder-only transformer (~50–200M params, LLaMA-style) over DAC tokens
- **Conditioning:** pitch + velocity + CLAP target timbre embedding + MIDI note context
- **Reference papers:** TokenSynth (arXiv:2502.08939), InstrumentGen (arXiv:2311.04339 / 2407.15641)
- **Training data:** NSynth (CC-BY) + Slakh2100 + MoisesDB + FreeSound CC — target 1–3M notes
- **Compute:** ~$500–$1000 per run on RunPod/Lambda; budget 2–4 runs

---

## Build Order (do not skip ahead)

1. **Phase 0 (Week 1):** environment + smoke test
2. **Phase 1.1 (Weeks 2–4):** minimum playable drum kit → SFZ acceptance test
3. **Phase 1.2 (Weeks 5–10):** pitched instruments (bass, vocals, other)
4. **Phase 1.3 (Weeks 11–13):** CLI polish, `--debug`, TOML config
5. **Phase 2 (Months 4–9):** DAC-LM training
6. **Phase 3 (Months 10–14):** Neutone plugin, then JUCE standalone

---

## Hard Rules

**Architecture**
- CLAP embeddings are the universal currency: separation routing, sample clustering, and neural-synth conditioning all flow through CLAP. One model, many uses.
- Every pipeline stage must write a content-addressed cache artifact before returning. No stage re-runs if the cache key matches.
- Emit SFZ and DecentSampler simultaneously. Never one without the other.
- Never target Kontakt `.nki` — it is closed/proprietary and not worth engineering against.

**Code style**
- Python 3.11. Type-annotate all function signatures.
- No comments unless the WHY is non-obvious. No docstrings beyond a single short line.
- No abstractions beyond what the current task requires. Three similar lines beats a premature helper.
- No error handling for scenarios that can't happen. Trust internal guarantees; validate only at system boundaries (CLI input, external model output).
- GPU memory: load each model on demand; call `torch.cuda.empty_cache()` between stages. Never hold two heavy models in VRAM simultaneously.

**ML models**
- Never load a model more than once per pipeline run. Pass handles, don't reload.
- All model weights must be MIT, Apache 2.0, or CC-BY licensed for distribution. CC-BY-NC weights (LarsNet, RAVE checkpoints) are fine for local use but must be flagged in code comments if they'd affect distribution.
- Do not retrain NSynth WaveNet AE — the official README states it takes ~10 days on 32 K40 GPUs.

**Testing**
- Acceptance test for every phase milestone: a real audio file in, a loadable SFZ/DecentSampler kit out, triggered from a MIDI keyboard.
- Unit tests live in `tests/`; integration tests require real audio (keep a small test fixture set, <10 MB total).

**Upgrades: gate criteria before switching tools**
- htdemucs_ft → BS-RoFormer: only when stem SDR is the measurable bottleneck (kit sounds "smeary" on eval set)
- DSP pitch shift → neural fill: only when users report formant artifacts beyond ±4 semitones
- CLI → plugin: only when ≥50 weekly active users or kit-export workflow is the clear friction point

---

## The Hardest Engineering Problem

Sub-stem separation: isolating guitar vs. piano vs. synth within the "other" stem. htdemucs_6s piano quality is explicitly poor (flagged in Meta's own README). Banquet (CLAP-query-conditioned) is the current frontier. Prototype `query_separator.py` early because it gates all downstream pitched-instrument work.

---

## Legal

- Distribute as a local CLI, not a hosted service.
- The CLI must display a consent banner on first run: user is responsible for clearing samples before commercial release.
- Phase 2 training data: NSynth CC-BY, Slakh2100 CC-BY, MoisesDB research license, FreeSound CC0/CC-BY, FMA CC only. Never train on copyrighted multitracks.
- Commercial plugin release requires music-copyright attorney review.

---

## CLI Interface (target)

```
kitforge build --song <path> --instrument "lead synth" --range C2-C7 --out kit.sfz
kitforge build --song <path> --instrument drums --out drums/
kitforge build --song <path> --instrument bass --quality high --out bass_kit.sfz
```

Flags: `--quality [fast|default|high]`, `--debug` (writes intermediate WAVs + CLAP t-SNE plots), `--config <toml>`.

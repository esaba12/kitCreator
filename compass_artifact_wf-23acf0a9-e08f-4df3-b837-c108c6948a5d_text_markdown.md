# From Song to Playable Kit: A Technical Architecture & Build Report

**Prepared for:** Ethan Saba — CS sophomore, U-Michigan
**Project:** Universal "sound-alike" instrument generator (CLI → DAW plugin)
**Date:** May 18, 2026

---

## TL;DR

- **No open-source tool currently does end-to-end song → playable, multi-octave instrument kit in one pipeline.** Every component (state-of-the-art stem separation, polyphonic transcription, pitch tracking, neural timbre synthesis, SFZ/DecentSampler packaging) exists individually; the *orchestration layer* that fuses them — plus the timbre-conditioned sample completion across the full keyboard — is the novel engineering work.
- **Build it in Python as a CLI in two layers.** Layer 1 ("good enough v1, ~6–10 weeks of focused work") = Demucs/BS-RoFormer separation → Basic Pitch/MT3 transcription → librosa/Rubber Band slicing + multi-sampling → SFZ/DecentSampler emit. Layer 2 ("the differentiator, +3–6 months") = neural timbre synthesis (RAVE/DDSP/TokenSynth-style DAC LM) to fill missing pitches/velocities and synthesize coherent round-robins. Phase 2 DAW plugin = JUCE + libtorch (Neutone-SDK route) or nih-plug + ONNX.
- **The single biggest research gap to engineer through is "sub-stem" extraction** (isolating guitar vs piano vs synth vs strings *within* the "other" stem). htdemucs_6s is bleeding-prone, MoisesDB-trained models like Banquet are the current frontier, and many target instruments will require zero-shot/query-based separation with CLAP/MERT embeddings — this is the area Ethan should prototype earliest because it gates everything downstream.

---

## Key Findings

1. **Separation SOTA (May 2026):** BS-RoFormer and Mel-RoFormer are the public SOTA on MUSDB18-HQ (BS-RoFormer with extra data: 11.99 dB avg SDR, SDX'23 winner). For permissive open-source production, **htdemucs_ft** (9.20 dB avg SDR, MIT-licensed) is the practical default. For 6-stem (adds piano + guitar) use htdemucs_6s, but quality on piano is notably poor per Meta's own README. For drum sub-component separation, **LarsNet** (StemGMD-trained, CC-BY-NC 4.0) splits a drum stem into kick/snare/toms/hi-hat/cymbals.
2. **Transcription:** Use **Spotify Basic Pitch** (Apache 2.0, lightweight, polyphonic, pitch-bend aware) as the baseline for most pitched stems; use **MT3 / YourMT3+** for true multi-instrument joint transcription; use **CREPE** for monophonic f0 (e.g., lead synth, bass) — >90% RPA at 10-cent threshold.
3. **Timbre embedding:** Use **LAION-CLAP** (HTSAT audio encoder) as the universal timbre fingerprint and similarity metric; supplement with **MERT** for music-domain SSL features. These drive (a) sub-stem queries, (b) duplicate-cluster detection across detected one-shots, and (c) conditioning for neural synthesis.
4. **Neural timbre synthesis** is the differentiator. The most relevant primitives:
   - **DDSP / DDSP-VST** (Magenta, archived October 2024): solid for monophonic harmonic instruments with as little as 10 min of training audio; deployment proven via JUCE + TF Lite.
   - **RAVE v2/v3** (IRCAM, CC-BY-NC 4.0 checkpoints): real-time VAE timbre transfer; trainable on consumer GPU; ships as TorchScript and runs in `nn~` (Max/PD) and the RAVE VST.
   - **InstrumentGen** (Nercessian & Imort, iZotope, arXiv:2311.04339, NeurIPS-W 2023) and its 2024 extension (arXiv:2407.15641): MusicGen-style transformer over **DAC tokens**, conditioned on instrument family + pitch + velocity, generates a *coherent multi-pitch sample set*. **Closest existing work to Ethan's actual vision — but paper-only, no public weights or repo.**
   - **TokenSynth** (Kim et al., arXiv:2502.08939, ICASSP 2025): decoder-only transformer over DAC, conditioned on MIDI tokens + CLAP embedding, supports instrument cloning and text-to-instrument with no fine-tuning. Also paper-only.
   - **VampNet / MAGNeT**: masked-token generation over EnCodec — useful for short audio "vamping" and inpainting, less so for clean isolated one-shots.
5. **Packaging:** Emit **SFZ** (open, text-based; broadly supported by Sforzando, sfizz, Aria; trivial programmatic generation) and **DecentSampler `.dspreset`** (XML; free runtime VST/AU/AAX on all OSes; SFZ-import exists). For Ableton-native, emit drum-rack-shaped folders and let the user drag-and-drop, or write `.adg` / `.adv` (gzipped XML — reverse-engineered, not officially documented).
6. **Phase-2 plugin:** Best PyTorch-friendly path is **JUCE + libtorch via Neutone SDK** (Apache-style SDK; ships TorchScript `.nm` files). For permissive, Rust-comfortable, ONNX-friendly: **nih-plug**. For non-commercial JUCE alternative: **iPlug2** (zlib license; works for VST3/AU/CLAP).

---

## Details

### 1. Source Separation

#### 1.1 Benchmark table (MUSDB18-HQ test set, per-stem SDR in dB)

| Model | Vocals | Drums | Bass | Other | Avg | Notes |
|---|---|---|---|---|---|---|
| Open-Unmix (UMX) | 6.3 | 5.7 | 5.2 | 4.0 | ~5.3 | sigsep, 2019; bi-LSTM mask-based |
| Spleeter 4-stems (MWF) | 6.86 | 6.71 | 5.51 | 4.55 | 5.91 | Deezer, 2019; U-Net |
| KUIELab-MDX-Net | 8.90 | 7.17 | 7.23 | 5.64 | 7.24 | MDX'21 LB-A 2nd place |
| Hybrid Demucs v3 (hdemucs_mmi) | 8.04 | 8.58 | 8.67 | 5.59 | 7.72 | MUSDB-HQ-only as reported by Lu et al. (arXiv:2310.01809) |
| HT-Demucs (htdemucs, +800 songs) | — | — | — | — | 9.00 | Rouard et al., arXiv:2211.08553 |
| HT-Demucs fine-tuned (htdemucs_ft, sparse + per-source FT) | — | — | — | — | 9.20 | SOTA in Demucs v4 paper |
| BS-RoFormer L=6 (MUSDB-HQ only) | 10.78 | 9.61 | 11.43 | 7.86 | 9.92 | Mel-RoFormer Table 1 |
| BS-RoFormer L=9 (MUSDB-HQ only) | 11.02 | 9.66 | 11.58 | 7.80 | 10.02 | same |
| Mel-RoFormer L=6 | 11.21 | 9.91 | 9.64 | 7.81 | 9.64 | Wang et al., arXiv:2310.01809 |
| BS-RoFormer (MUSDB-HQ + 500 extra) | — | — | — | — | **11.99** | SDX'23 winner |

Open-Unmix per-stem numbers approximate (SiSEC18 reporting). BS-RoFormer arxiv abstract quotes 9.80 dB for its smaller variant on MUSDB-HQ-only — minor discrepancy with the Mel-RoFormer follow-up table (config differences).

#### 1.2 Architectures
- **Open-Unmix:** bi-LSTM, magnitude-spectrogram masking — historical baseline.
- **Spleeter:** 2-D U-Net on STFT magnitude — fast, CPU-friendly, low quality by 2026 standards.
- **MDX-Net (KUIELab):** Time-Frequency Convolutions with TDF blocks; winner of MDX'21 Track A.
- **Demucs (htdemucs):** Hybrid bi-U-Net operating in waveform *and* spectrogram, with a cross-domain Transformer in the bottleneck.
- **BS-RoFormer / Mel-RoFormer:** band-split (62 non-overlapping subbands for BS; mel-band overlapping for Mel) → hierarchical Transformer with RoPE positional encoding → multi-band mask estimation.
- **LarsNet (StemGMD-trained, polimi-ispl/larsnet):** parallel bank of dedicated U-Nets, one per drum class (KD/SD/TT/HH/CY), spectro-temporal soft masks. Runs >60× real-time on GPU.
- **Banquet (query-based, kwatcharasupat/query-bandit):** 24.9 M-param query-conditioned model trained on MoisesDB; matches HT-Demucs-6s on VDBO stems and beats it on guitar/piano.

#### 1.3 Repos, licenses, hardware
| Project | Repo | License | Min VRAM (inference) |
|---|---|---|---|
| Demucs v4 | facebookresearch/demucs | MIT | ~3 GB (htdemucs); 6+ GB for `_ft` |
| Spleeter | deezer/spleeter | MIT | CPU-OK |
| Open-Unmix | sigsep/open-unmix-pytorch | MIT (umxl weights CC-BY-NC-SA 4.0) | CPU-OK |
| MDX-Net | kuielab/mdx-net | MIT | ~4 GB |
| BS-RoFormer (community) | lucidrains/BS-RoFormer | MIT | 8 GB recommended; community weights on HF |
| LarsNet | polimi-ispl/larsnet | code MIT; weights CC-BY-NC 4.0 | ~2 GB |
| python-audio-separator | nomadkaraoke/python-audio-separator | MIT | wraps Demucs/MDX/Roformer; recommended single dependency |

#### 1.4 Sub-instrument separation (the hardest gate)
- htdemucs_6s adds piano + guitar but "the piano source is not working great" per the official README.
- **Banquet** (Watcharasupat & Lerch, 2024) is the best public direction: it's query-conditioned, separating arbitrary instrument classes by example.
- **Practical near-term move:** for guitar/piano/synth/strings, run htdemucs_6s, then post-process with a CLAP-similarity classifier to confirm bleed and either gate or re-route. For brass/reeds/strings inside "other", train or fine-tune a Banquet-style model on **MoisesDB (240 tracks from 45 artists covering twelve musical genres, per Pereira et al., ISMIR 2023, arXiv:2307.15913: "It consists of 240 tracks from 45 artists, covering twelve musical genres")**, a 2-level hierarchical stem taxonomy.

### 2. Transcription & Onset Detection

- **Basic Pitch** (Spotify, github.com/spotify/basic-pitch; Apache 2.0). Lightweight CNN, joint prediction of frame-wise multipitch, onset, and note activations with pitch-bend output. *"Basic pitch is instrument-agnostic and supports polyphonic instruments… Basic pitch works best on one instrument at a time."* Pairs naturally with stem-separation output.
- **MT3 / YourMT3+** (magenta/mt3; arXiv:2111.03017 + 2407.04822). T5-based seq-to-seq over spectrograms, jointly transcribes multi-instrument MIDI. YourMT3+ adds hierarchical attention + MoE encoder; trained with cross-dataset stem augmentation. Use for "give me MIDI for the whole song with instrument tags."
- **Onsets & Frames** (Magenta) — piano-specific historical baseline; surpassed by Basic Pitch for most use cases.
- **CREPE** (marl/crepe; arXiv:1802.06182). Monophonic f0; >99% RPA at 50 cents and >90% at 10 cents on MDB-stem-synth. Use for monophonic stems (bass, lead synth, sung melody).
- **pYIN / SWIPE** (librosa.pyin) — DSP baseline.
- **Onset detection:** librosa `onset.onset_detect`, `madmom.features.onsets` (CNN-based), or the joint onset branch from Basic Pitch.
- **Drum transcription:** Vogl et al. CRNN (3-/8-/18-class), ADTOF package (5–7-class with MIDI-velocity estimation; ~114h crowdsourced corpus), or run **LarsNet → per-stem peak picking** for the cleanest one-shot extraction in our pipeline.

Output convention: emit `pretty_midi.PrettyMIDI` objects per stem, with note-on/note-off times, MIDI pitch, velocity (estimated from local RMS), and instrument label.

### 3. Timbre Analysis & Classification

- **Features:** mel-spectrograms (128 mel bins, 22.05 kHz, 1024 FFT) as the universal substrate; MFCCs (13–20 coeffs) for classical classifiers; spectral centroid/rolloff/bandwidth/flatness from librosa for ADSR-adjacent envelope features.
- **Embeddings (use these, not hand-crafted features, for similarity / clustering / conditioning):**
  - **LAION-CLAP** (laion-ai/CLAP; HTSAT audio + RoBERTa text encoders, 512-d shared L2-normalized space). **On Inst-Sim-ABX (Slakh2100), per Vohra et al., arXiv:2601.19109 (27 Jan 2026), "Interpretable and Perceptually-Aligned Music Similarity with Pretrained Embeddings": "zero-shot LAION-CLAP and MuQ-MuLan reach 71.9% and 72.4% agreement with human listeners (XAB; full mixes)."** Strongest open model for timbre descriptors.
  - **MERT** (m-a-p/MERT, 95M-330M params): SSL music transformer; better for pitch- and rhythm-aware tasks.
  - **PaSST** (kkoutini/PaSST): Patchout AST; AudioSet pretrained — use for instrument-tag classification on OpenMIC-2018.
  - **Wav2Vec2 / HuBERT music variants:** general SSL — viable but less music-specialized.
- **Sub-instrument classification:** train a small linear/MLP head on top of CLAP or PaSST embeddings against OpenMIC-2018 (20 instrument classes, ~20k clips) plus your own MoisesDB hierarchical labels.

### 4. Sample Extraction & Processing

Pipeline for each pitched stem after separation:
1. Run Basic Pitch → per-note `(start, end, pitch, velocity_estimate)`.
2. For each detected note, slice waveform `[onset - 10 ms, offset + tail_ms]` where `tail_ms` is chosen by detecting the −60 dB decay point (true ADSR Release).
3. Estimate ADSR: attack = peak-RMS time from onset; decay = time from peak to sustained level; sustain = mean RMS over middle 60% of note; release = post-offset −60 dB decay. Encode as SFZ `ampeg_*` opcodes.
4. De-bleed each slice: optional second pass through **DeepFilterNet** (Rikorose/DeepFilterNet, MIT, runs ~real-time on CPU) or RNNoise for residual hum/leakage. For musical denoising, prefer Demucs-residual subtraction over noise-suppressor for music.
5. Polyphonic-overlap handling: for chord/dyad regions where notes overlap, prefer notes that occur as one-shots; if none, accept the slice as a "chord sample" labeled separately and skip pitching from it.
6. Cluster slices per pitch with HDBSCAN on CLAP embeddings → pick a canonical per-pitch sample (medoid) + 2–4 round-robins (other cluster members within cosine-sim threshold).
7. Velocity layers: bucket detected velocities into 2–4 layers; if only one bucket is observed, synthesize others by amplitude- and spectral-tilt modeling (or generate via Phase-2 neural synth).
8. Loops vs one-shots: drum/perc → one-shot; sustained pitched → mark `loop_start`/`loop_end` with zero-crossing-aligned cross-fade points (autocorrelation-based loop-point search).

### 5. Pitch Shifting & Range Generation

Reality: pitch-shifting a single sample over a wide range introduces formant smearing and "Munchkin/Barry-White" artifacts. The classic threshold is ±3 semitones acceptable, ±5 noticeable, ±7+ unusable for natural instruments.

- **Algorithms:** PSOLA (good for monophonic with strong f0), phase vocoder (general-purpose, "smear"), **Rubber Band Library v3 R3 engine** (best open-source quality, supports formant-preservation; commercial via paid license, GPLv2 otherwise — careful about distribution), SoundTouch (fast but lower quality), Élastique (closed/commercial, used in Cubase).
- **Python:** `pyrubberband` (bmcfee, shells out to `rubberband` CLI), `librosa.effects.pitch_shift` (uses phase vocoder under the hood, fine for prototyping), `audiotsm`, `parselmouth` (Praat) for formant-preserving on vocals.
- **Strategy:** multi-sample every 3 semitones (i.e., capture C, D#, F#, A per octave) when raw material exists; pitch-shift to fill the in-betweens with Rubber Band R3 + formant-preserve flag. For Phase 2, use a neural synth (RAVE/DDSP/DAC-LM) to *render the missing pitch from latent conditioning* rather than DSP-shift.

### 6. Neural Timbre Synthesis — Deep Review

This is where Ethan's project differentiates itself. Each option below is rated for one-person feasibility in 2026.

| Model | What it does | Realistic for one-person use? | Notes |
|---|---|---|---|
| **NSynth WaveNet AE** (Engel et al., 2017; magenta/nsynth) | Encodes individual notes into 16-d temporal embedding, decodes with WaveNet | Use the pre-trained model & NSynth-300k dataset; *don't retrain* — per the official Magenta/NSynth README (github.com/magenta/magenta/models/nsynth): **"The WaveNet model takes around 10 days on 32 K40 gpus (synchronous) to converge at ~200k iterations"** | Slow inference; mostly historical |
| **GANSynth** (Engel et al., 2019) | Spherical-Gaussian-prior GAN over log-mag + IF spectrograms; trained on NSynth | Pretrained models usable; ~3–4 days to retrain on 1× V100 | 50,000× faster than WaveNet at inference; pitch & timbre disentangled |
| **DDSP** (Engel et al., ICLR 2020; magenta/ddsp) | Differentiable harmonic-plus-noise synthesizer; trained on a few minutes of monophonic instrument audio | **Yes** — train on a single Colab GPU in hours; **but** repo archived Oct 2024, monophonic-only, 16 kHz limit | DDSP-VST shipped (also archived). MAWF and Neural Analog continue the lineage |
| **RAVE v2/v3** (Caillon & Esling, IRCAM; acids-ircam/RAVE) | VAE w/ adversarial fine-tune, 48 kHz, 20× real-time on CPU | **Yes** — but plan for **multi-day training**: the IRCAM forum tutorial ("Training RAVE models on custom data", forum.ircam.fr) states "first training phase last for about three or four days, and second phase may take from four days to three weeks"; a community RTX 4090 run (acids-ircam/RAVE Discussion #300) completed in "a little less than 3 days" | Best for timbre transfer of *continuous* audio, not strictly one-shots; export TorchScript to use in nn~ or RAVE VST. Many pretrained checkpoints under CC-BY-NC 4.0 |
| **EnCodec / DAC** (Meta / Descript) | Neural audio codecs producing discrete tokens (RVQ); not generative themselves but the tokenizer for everything below | Use pretrained DAC at 44.1 kHz (MIT weights) | **DAC outperforms EnCodec across all comparable bitrates in MUSHRA-style listening tests, per Kumar et al., arXiv:2306.06546 ("High-Fidelity Audio Compression with Improved RVQGAN"): "listeners consistently rating the proposed codec significantly higher than EnCodec across all comparable bitrates," with ViSQOL 4.18 vs. EnCodec's 3.13 at 8 kbps vs. 12 kbps** |
| **MusicGen / AudioGen / MAGNeT** (Meta AudioCraft) | Text-to-music transformer over EnCodec; MAGNeT is non-AR, 7× faster | Inference yes; training from scratch no (16k hours of music) | Useful for *audio-prompt* style transfer, not directly for clean instrument one-shots |
| **VampNet** (Flores García et al., ISMIR 2023; hugofloresgarcia/vampnet) | Masked acoustic-token model over DAC; supports prompts, inpainting, vamping | Yes — fine-tune on your own corpus; checkpoints provided | Best for short loops; can be coerced into note infilling |
| **InstrumentGen** (Nercessian & Imort, iZotope; arXiv:2311.04339 / 2407.15641) | DAC-token transformer conditioned on instrument family + pitch + velocity + text/audio prompt → coherent full-keyboard sample set | **Paper-only, no public weights — but this is exactly the architecture Ethan should re-implement for Layer 2** | Quote: *"text-to-instrument must generate several samples corresponding to the text prompt that are timbrally consistent to one another"* |
| **TokenSynth** (Kim et al., arXiv:2502.08939, ICASSP 2025) | Decoder-only transformer over DAC tokens, conditioned on MIDI tokens + CLAP embedding; instrument cloning + text-to-instrument with no fine-tuning | Paper-only; promising prior art | The cleanest published recipe for Ethan's vision |
| **Spectrogram Diffusion** (Hawthorne et al., 2022) | Diffusion in log-mel space, MIDI-conditioned | Inference doable; harder to fine-tune than token LMs | |
| **SING / SampleRNN / DiffWave** | Mostly historical; DiffWave still useful as a vocoder backbone | | |

**Recommended Phase-2 synthesis stack:**
1. **DAC encoder + decoder** (Descript, 44.1 kHz, MIT) as the audio tokenizer.
2. **Decoder-only transformer** (LLaMA-style, ~50–200M params) over DAC tokens, conditioned on `(pitch, velocity, CLAP_target_timbre_embedding, MIDI-style note context)` — i.e., re-implement the TokenSynth / InstrumentGen recipe.
3. **Training data:** start with NSynth (305,979 notes, 1006 instruments, CC-BY 4.0), augment with Slakh2100, MoisesDB-mined one-shots, and FreeSound CC-licensed instrument packs. Total: aim for 1–3M notes.
4. **Compute:** training a 100M-param DAC-LM to convergence ≈ 200–400 A100-hours. On Lambda or RunPod at ~$1.50/A100-hr, that is **$300–600 per training run.** Plan for 2–4 runs = $1k–$2.4k. Inference is cheap (<1 s per note on a single GPU).
5. **Inference-time conditioning:** the user-uploaded song stem produces an averaged CLAP embedding; the model conditions on this + each desired pitch + velocity layer and emits DAC tokens → DAC decoder → 44.1 kHz audio → write to SFZ.

If $1k+ in cloud compute is unacceptable, **RAVE v2 is the realistic fallback**: fine-tune a v2 checkpoint on the extracted stem (1+ hours of audio recommended; expect 3–7 days of training), then "play" the latent at different pitches by combining with a separate f0/pitch-conditioning signal — but this gives less crisp one-shots than a DAC-LM.

### 7. Packaging & DAW Integration

**SFZ** is the right primary target. Open spec at sfzformat.com, supported by Sforzando (free), sfizz (open-source SFZ engine, MIT), Aria, HISE, Plogue, Kontakt (partial), Bitwig Sampler, Falcon. Programmatic emission is trivial — concatenate text:

```
<global> ampeg_release=0.5
<group> lokey=48 hikey=59 pitch_keycenter=53
<region> sample=samples/Eb3_v1.wav lovel=1   hivel=63
<region> sample=samples/Eb3_v2.wav lovel=64  hivel=100
<region> sample=samples/Eb3_v3.wav lovel=101 hivel=127 seq_position=1 seq_length=2
<region> sample=samples/Eb3_v3_rr2.wav lovel=101 hivel=127 seq_position=2 seq_length=2
```

Key opcodes Ethan needs: `lokey/hikey/pitch_keycenter`, `lovel/hivel`, `seq_position/seq_length` (round-robins), `ampeg_attack/decay/sustain/release`, `loop_mode/loop_start/loop_end`, `trigger=release` for release samples, `group/off_by/off_mode` for hi-hat choke groups.

**DecentSampler** (`.dspreset`): free runtime VST3/AU/AAX cross-platform; XML-based; **has SFZ import**, so generating SFZ first and converting is the highest-leverage workflow. Native `.dspreset` adds a built-in UI engine, knobs, oscillators, FX — useful if you want a branded UI.

**Ableton Drum Rack / Sampler**: `.adg` is gzipped XML. Community libraries (`AbletonParsing` style) exist but format is unofficial. Easiest UX: write a folder of named WAVs (`C3 Kick.wav`, `D3 Snare.wav`…) and have the user drag the folder onto a Drum Rack — Ableton auto-maps by filename. For multisampled instruments use Sampler/Simpler and emit a Sampler `.adv`.

**Kontakt `.nki`** is closed/proprietary; need Native Instruments' "Kontakt Creator Tools" + KSP. Not worth pursuing as a generator target — distribute SFZ and let users convert if they want NI tooling.

**Phase 2 VST/AU plugin paths:**
- **JUCE** (juce-framework/JUCE) — dual-licensed AGPLv3 / commercial. The de-facto industry framework, VST3/AU/AAX/CLAP/AUv3/LV2/standalone. Commercial license required for closed-source distribution. Mature.
- **iPlug2** (iPlug2/iPlug2) — zlib-style permissive license, free for commercial. CLAP/VST2/VST3/AUv2/AUv3/AAX/WAM. Smaller community than JUCE.
- **nih-plug** (robbert-vdh/nih-plug) — Rust, ISC framework; VST3 binding inherits GPLv3 via Steinberg `vst3-sys`. Targets VST3 + CLAP. Good if Ethan wants to learn Rust.
- **DPF** (DISTRHO/DPF) — ISC, includes own ISC VST3 implementation; LV2/VST2/VST3/CLAP/AU/JACK.

**Deploying ML models in plugins:**
- **Neutone SDK** (Neutone/neutone_sdk; arXiv:2508.09126) — wraps a PyTorch model as TorchScript (`.nm`), runs inside the free Neutone FX/Gen plugin via libtorch. Lowest-friction path; ships an example with MusicGen-style generative models.
- **libtorch in JUCE directly** — as RAVE VST does; large binary footprint (~hundreds of MB) but full PyTorch op coverage.
- **TFLite + XNNPACK** — what DDSP-VST does; smaller, CPU-fast, TF-only.
- **ONNX Runtime** — cross-framework; supported by **Anira** (C++ inference engine designed for real-time plugin embedding).
- **RT-Neural** (Jatin Chowdhury) — hand-coded C++ for tiny recurrent/MLP nets; smallest footprint when model is simple.

### 8. Architecture & System Design (CLI, Phase 1)

Project layout (recommended):

```
kit-forge/
├── pyproject.toml          # Poetry or uv, Python 3.11
├── kitforge/
│   ├── __init__.py
│   ├── cli.py              # Typer-based CLI
│   ├── config.py           # pydantic-settings
│   ├── pipeline.py         # high-level orchestrator
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
│   │   ├── denoise.py            # DeepFilterNet wrapper
│   │   ├── cluster.py            # HDBSCAN over CLAP
│   │   └── loop_finder.py
│   ├── pitchshift/
│   │   └── rubberband_wrapper.py
│   ├── synth/                    # Phase 2
│   │   ├── dac_lm.py
│   │   ├── rave_runner.py
│   │   └── ddsp_runner.py
│   ├── package/
│   │   ├── sfz_writer.py
│   │   ├── decentsampler_writer.py
│   │   └── ableton_writer.py
│   └── cache.py                  # diskcache by content hash
└── tests/
```

**Caching:** every stage outputs a cacheable artifact keyed by `(input_sha256, model_name, model_version, params_hash)`. Use `diskcache` or simple parquet/npz files in `~/.cache/kitforge/`.

**GPU utilization:** load each model on demand; explicitly free with `torch.cuda.empty_cache()` between stages. For batch processing of many songs, queue songs and process model-by-model rather than song-by-song to avoid load/unload overhead.

**ONNX/TorchScript:** convert htdemucs to ONNX (Mixxx GSoC 2025 has published a working conversion script) for CPU users; keep PyTorch path for GPU.

**Reference for "how the pros approach this":**
- LANDR Samples / Output Arcade: hand-curated sample libraries with ML-driven tagging, no generative reconstruction.
- Moises Pro: Demucs-derivative + proprietary 7-stem; chord/lyric detection — closest commercial analog for "instrument-level" separation but doesn't emit playable kits.
- AudioShake: enterprise B2B separation API (used by LANDR Stems) — trained on licensed multitracks; quality leads on dialog/SFX separation.
- LALAL.AI (Phoenix/Orion engines): single-track vocal-instrument separation; recent multi-stem additions (drums, bass, guitar, piano, synth, strings, wind).
- Splice Create AI / Drumify: generative drum-pattern + sample-pack recommender, **not** sample synthesis.

### 9. What Exists vs. What Ethan Has to Build

**Available off-the-shelf (pip-installable or git+download):**
- Demucs, Spleeter, Open-Unmix, LarsNet, lucidrains BS-RoFormer, python-audio-separator
- Basic Pitch, MT3, CREPE, librosa, madmom, pretty_midi, mido
- CLAP (laion-clap, transformers), MERT, PaSST
- Rubber Band CLI / pyrubberband, librosa effects
- DAC (descriptinc/descript-audio-codec, MIT), EnCodec (Meta, MIT)
- RAVE (acids-ircam, GPLv3), DDSP (Magenta, Apache 2.0, archived)
- Neutone SDK, sfizz, DecentSampler runtime
- DeepFilterNet, RNNoise

**Research-only / paper-only (no production weights):**
- InstrumentGen (Nercessian & Imort, 2023/2024)
- TokenSynth (Kim et al., 2025)
- YourMT3+ partial release
- Banquet (kwatcharasupat/query-bandit has code but limited pretrained scope)

**What nobody has built (Ethan's novel work):**
1. The **orchestration layer** unifying separation → transcription → slicing → embedding-cluster → pitch-range fill → SFZ emit, with content-addressed caching and per-instrument plugin profiles.
2. The **velocity-bucket + round-robin auto-assignment** algorithm that selects which captured one-shots to promote to RRs vs. discard.
3. A **CLAP-query / Banquet-style sub-instrument router** that picks the best separation strategy given the user's target ("synth lead", "Rhodes piano", "808 sub bass") — including a fallback chain when no clean stem can be obtained.
4. **The conditioned DAC-token LM** that fills the missing keyboard range from a small set of captured exemplars + CLAP timbre target. This is the core IP and the only piece that requires real ML training rather than integration.
5. A **DAW-native exporter** for Ableton `.adg`/`.adv`, Logic EXS/Sampler, and Kontakt KSP (best-effort), beyond SFZ/DecentSampler.

### 10. Competitive Landscape

No tool reconstructs a *playable, multi-octave instrument kit* from an arbitrary song. The space is segmented:

- **Separation only:** LALAL.AI, Moises, AudioShake, MVSep, RipX DAW, SpectraLayers 11, Logic Pro Stem Splitter, iZotope RX 12 Music Rebalance, Ultimate Vocal Remover (free, UVR5).
- **Separation + transcription + practice tools:** Moises, fadr.com.
- **Stem editing at note level:** RipX DAW (post-separation note editing — closest competitor in the "extract one-shots" sense, but no kit generation).
- **Sample generation from text/audio:** Output Arcade (library only), Splice Create (recommender), Suno/Udio (full track generation), Stable Audio (Stability), MusicGen (Meta), MAGNeT — none emit playable multi-sampled instruments.
- **Generative-instrument plugins:** DDSP-VST (Magenta, archived), Neutone Gen, RAVE VST, MAWF — all timbre-transfer or single-patch, not full kit reconstruction.

**Conclusion: the kit-from-song niche is open.**

### 11. Practical Build Plan

#### Phase 0 — environment & smoke test (week 1)
- Python 3.11, `uv` or Poetry, PyTorch 2.4+ with CUDA 12.x, ffmpeg, libsndfile.
- Install `demucs`, `basic-pitch`, `crepe`, `librosa`, `pretty_midi`, `pyrubberband` (system `rubberband` via brew/apt), `laion-clap`, `pretty_midi`, `pyloudnorm`, `diskcache`, `typer`, `hdbscan`, `deepfilternet`.
- Smoke test: separate one song with `python -m demucs -n htdemucs_ft <song.wav>`; transcribe drum stem with `basic-pitch out_dir drums.wav`.

#### Phase 1.1 — minimum playable drum kit (weeks 2–4)
- Drum stem (htdemucs) → LarsNet → 5 sub-stems (KD/SD/HH/TT/CY).
- Per-stem onset detection (madmom CRNN); slice 100–600 ms one-shots with auto-tail.
- Per-class pick canonical sample + 3 round-robins via CLAP-similarity clustering.
- Emit SFZ drum kit and DecentSampler `.dspreset` with hi-hat choke group.
- Acceptance test: drop into Sforzando/DecentSampler, trigger from MIDI keyboard, drumkit plays back recognizably.

#### Phase 1.2 — pitched instruments via separation + multisampling (weeks 5–10)
- For "bass": htdemucs bass stem → CREPE f0 → note slicing → octave-up to E4 via Rubber Band (3-semitone steps, formant preserve off for bass) → SFZ across MIDI 24–84.
- For "vocals": htdemucs vocals → Basic Pitch with formant-preserve pitch shift → 2 octaves.
- For "other" pitched (guitar/piano/synth): user supplies an instrument hint → htdemucs_6s if guitar/piano, else Banquet with CLAP query computed from a 5-second user-highlighted region → Basic Pitch → ADSR + multisample.
- Velocity layers: bucket detected velocities into terciles; if <2 buckets are observed, synthesize a softer layer by spectral-tilt low-pass + gain reduction.

#### Phase 1.3 — UX & robustness (weeks 11–13)
- Typer CLI: `kitforge build --song path --instrument "lead synth" --range C2-C7 --out kit.sfz`.
- Per-stage diagnostics (`--debug` writes intermediate WAVs and CLAP-tSNE plots).
- Optional config file (TOML) for reproducible recipes.

#### Phase 2 — neural timbre synthesis fill (months 4–9)
- Implement a TokenSynth/InstrumentGen-style DAC-token transformer (~100M params) in PyTorch Lightning.
- Train on NSynth + Slakh2100 + MoisesDB-derived one-shots + FreeSound. Budget: ~300–600 A100-hours per run (~$500–1000 on RunPod/Lambda).
- Conditioning: pitch (one-hot or sinusoidal), velocity (continuous), target CLAP embedding (from user stem).
- At inference, decode 1–3 second clips per pitch × velocity bucket × round-robin, then run the standard packaging step.
- Distill / quantize (INT8) for CPU inference; export TorchScript for the future plugin.

#### Phase 3 — DAW plugin (months 10–14)
- Wrap the trained DAC-LM in **Neutone SDK** as a "Gen"-style model (TorchScript `.nm`), shipping inside free Neutone Gen plugin. This is the lowest-friction first plugin release.
- Standalone plugin: JUCE + libtorch. Controls: "load source song", "target instrument prompt", "render kit". Renders to a local SFZ that the host loads.

**GPU compute budget for Ethan (rough):**
- Phase 1 inference: free on a personal RTX 3060 / 4060 / 4070 / Macbook Pro M-series MPS.
- Phase 2 training: $500–$2,400 cloud GPU per run; budget 2–4 runs.
- Cheap alternative path: use **Modal** ($30/mo free credits) or Lambda Cloud spot instances.

**Realistic time estimate for a sophomore with Ethan's stack:**
- Phase 1 (CLI v1, drum kits + bass + monophonic instruments, SFZ + DecentSampler): **8–12 weeks of weekend/evening work**.
- Phase 1.2 (general pitched instruments via Banquet/CLAP routing): **+4 weeks**.
- Phase 2 (DAC-LM training + integration): **+3–6 months**, gated on cloud GPU access and willingness to debug training instabilities.
- Phase 3 (Neutone-packaged plugin): **+1–2 months**; standalone JUCE plugin: +2–4 months on top.

### 12. Legal & Ethical Notes

- **Generating samples from copyrighted songs is legally ambiguous.** Sample-based reproductions can constitute derivative works. In the U.S., Bridgeport Music v. Dimension Films set a strict no-de-minimis precedent for direct sampling, though that has been narrowed by later rulings (VMG Salsoul v. Ciccone). Synthesizing a "sound-alike" timbre is more defensible than reusing audio directly, but a kit that contains 100+ slices of a copyrighted recording is *not* a sound-alike — it is a derivative work.
- **Existing services' position:**
  - Moises explicitly states it *"only trains our models on licensed materials. We never train on any music without the owner's full approval."*
  - Splice samples are royalty-free with explicit license terms.
  - LALAL.AI / AudioShake disclaim copyright on user uploads and place the burden on the user.
- **Recommended posture for Ethan's tool:**
  1. Distribute as a **local CLI**, not a hosted service — this shifts liability to the user and avoids hosting/transmitting copyrighted content.
  2. Add a clear consent banner: "this tool may produce derivative works of copyrighted recordings; you are responsible for clearing samples before commercial release."
  3. For Phase 2 training data, use **only permissively licensed corpora** (NSynth CC-BY, Slakh2100 CC-BY, MoisesDB research license, FreeSound CC0/CC-BY, FMA CC). Never train on copyrighted multitracks even if you have copies.
  4. Personal/educational use is the lowest-risk distribution case; commercial release (e.g., a paid plugin) materially increases exposure and would benefit from a music-lawyer review.

---

## Recommendations

1. **Build the CLI before anything else.** Ship a working Phase-1 SFZ generator targeting drums + bass + 1 pitched instrument family by end of summer; do *not* start Phase-2 ML training until Phase-1 is working end-to-end on five test songs.
2. **Pick htdemucs_ft as the default separator** (MIT license, runs locally, 9.20 dB SOTA without extra training); add BS-RoFormer via `python-audio-separator` as an optional "quality mode."
3. **Use Basic Pitch as the default transcriber + CREPE for monophonic stems**; defer MT3/YourMT3+ until you actually need cross-instrument transcription on un-separated audio.
4. **Make CLAP embeddings the universal currency** — separation routing, sample clustering, neural-synth conditioning all flow through CLAP. One model, many uses.
5. **Emit SFZ + DecentSampler simultaneously.** SFZ is the open standard with the widest sampler support; DecentSampler gives a polished free runtime and ships with SFZ import.
6. **Re-implement TokenSynth (arXiv:2502.08939) as your Phase-2 generative core**, not InstrumentGen — TokenSynth's CLAP-conditioning matches your existing infrastructure exactly and its no-fine-tune cloning is what enables "any instrument from any song."
7. **Don't write a VST3 from scratch in Phase 2.** Ship inside Neutone Gen first; only build a standalone JUCE plugin if user demand justifies the engineering cost.
8. **Benchmarks to gate decisions:**
   - Move from htdemucs_ft → BS-RoFormer when stem SDR on your eval set is the bottleneck (i.e., reconstructed kit sounds "smeary").
   - Move from DSP pitch-shifting → neural fill when users complain about formant artifacts beyond ±4 semitones.
   - Move from CLI to plugin when ≥50 weekly active users exist or when sample-pack export workflow becomes the friction point.

---

## Caveats

- The BS-RoFormer SDR averages cited (9.80 dB vs 9.92/10.02 dB) come from primary paper and follow-up paper respectively and use slightly different model configs; both numbers are real, neither is "wrong."
- Demucs htdemucs_6s "experimental" status: piano source quality is explicitly flagged poor by Meta in the official README. Don't assume 6-stem htdemucs solves sub-instrument separation.
- DDSP / DDSP-VST were archived by Magenta in 2024 — the codebase still works but won't receive updates; Hanoi Hantrakul's MAWF (ByteDance) is the active spiritual successor.
- InstrumentGen and TokenSynth are **paper-only**; Ethan must reimplement, which carries non-trivial ML-engineering risk. Expect 1–2 months of just getting the training loop stable.
- The legal analysis here is a starting point, not legal advice; commercial release should be reviewed by an attorney experienced in music-copyright law.
- All forward-looking time estimates assume Ethan continues at his described skill level and has consistent weekend availability; full-time work compresses these by ~3×.
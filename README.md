# kitCreator

Turn any song into a playable multi-octave sampler kit. Give it an audio file, tell it what instrument you want, get back an SFZ + DecentSampler preset ready to load in any sampler.

![kitCreator demo](docs/media/kitcreator-demo.gif)

▶ [Watch with sound](https://ethansaba.com/videos/kitcreator.mp4) — "Any song becomes a playable kit."

Built by Ethan Saba.

---

## What works right now

**Drums, bass, guitar, piano, and synth are working end-to-end.**

```bash
# Drum kit
kitforge build --song mysong.wav --instrument drums --out ~/Desktop/my_kit

# Bass kit
kitforge build --song mysong.wav --instrument bass --range C1-G4 --out ~/Desktop/bass_kit

# Guitar / piano / synth
kitforge build --song mysong.wav --instrument guitar --out ~/Desktop/guitar_kit
kitforge build --song mysong.wav --instrument piano --range C2-C7 --out ~/Desktop/piano_kit
kitforge build --song mysong.wav --instrument "lead synth" --out ~/Desktop/synth_kit
```

### Drums pipeline

1. **Demucs htdemucs_ft** — separates the song into vocals / drums / bass / other stems
2. **[`--quality high`] DeepFilterNet3** — denoises the drum stem to remove residual bleed before slicing
3. **LarsNet** — splits the drum stem into 5 clean sub-stems: kick, snare, hi-hat, toms, cymbals
4. **Onset detection** — finds every hit in each sub-stem via librosa
5. **Velocity-layered slicing** — sorts hits by pre-normalization energy, bins into up to 4 velocity layers
6. **CLAP round-robin selection** — picks up to 4 timbrally-diverse round-robins per layer via farthest-point sampling on LAION-CLAP embeddings (falls back to energy-spread without internet/weights)
7. **SFZ + DecentSampler export** — hi-hat choke groups, velocity layers (`lovel/hivel`), round-robin sequencing

### Bass / Guitar / Piano / Synth pipeline

1. **BS-RoFormer vocal pre-removal** — `python-audio-separator` with the SOTA `model_bs_roformer_ep_317` checkpoint (17.0 dB instrumental SDR); strips vocals from the mix before htdemucs sees it, so the "other" stem doesn't inherit residual vocal bleed. Runs on Apple Silicon MPS + CoreML, ~3 min/song.
2. **Demucs** — guitar/piano use `htdemucs_6s` (6-stem, dedicated stems); synth uses `htdemucs_ft` "other" stem. Now fed the BS-RoFormer instrumental, not the raw mix.
3. **[`--quality high`] Banquet** — query-conditioned separation. Query is auto-picked as the highest-RMS 10 s window of the rough htdemucs stem (or user-specified via `--query MM:SS-MM:SS`). Banquet runs on the BS-RoFormer instrumental, not the raw mix.
4. **[`--quality high`] DeepFilterNet3** — denoises the (Banquet-refined) stem before transcription
5. **Basic Pitch / torchcrepe** — polyphonic transcription for guitar/piano/synth, monophonic f0 for bass
6. **CLAP canonical selection** — medoid across all occurrences of each MIDI pitch
7. **Voronoi zone fill** — Rubber Band R3 pre-shift for gaps > 6 semitones
8. **ADSR estimation + loop point detection** — RMS-envelope ADSR per zone, autocorrelation-based loop points on sustained samples
9. **SFZ + DecentSampler export** — `pitch_keycenter` per zone, per-region ADSR and loop opcodes

### Output structure

```
my_kit/
├── kit.sfz          # load in Sforzando, sfizz, Bitwig Sampler, etc.
├── kit.dspreset     # load in DecentSampler (free VST/AU/AAX)
└── samples/
    ├── kick_v0_1.wav … kick_v96_4.wav       # drums: vel layer × round-robin
    ├── snare_v0_1.wav … snare_v96_4.wav
    ├── hihat_v0_1.wav … hihat_v96_4.wav
    ├── toms_v0_1.wav  … toms_v96_4.wav
    ├── cymbals_v0_1.wav … cymbals_v96_4.wav
    ├── bass_C2_midi36.wav …                 # bass: one file per zone
    └── bass_E2_midi40.wav …                 # guitar/piano/synth: same scheme
```

Sample filename convention — drums: `{class}_v{vel_low}_{rr_index}.wav`, pitched: `bass_{note}_{midi}.wav`

### Drum SFZ MIDI layout (GM-adjacent)

| Class   | MIDI note |
|---------|-----------|
| kick    | C1 (36)   |
| snare   | D1 (38)   |
| hihat   | F#1 (42)  |
| toms    | B1 (47)   |
| cymbals | C2 (48)   |

---

## Setup

**Requirements:** Python 3.11, [uv](https://github.com/astral-sh/uv), ffmpeg, rubberband

```bash
# macOS
brew install ffmpeg rubberband

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone git@github.com:esaba12/kitCreator.git
cd kitCreator
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

**LarsNet weights** (562 MB, CC-BY-NC 4.0 — local use only):

```bash
gdown "1U8-5924B1ii1cjv9p0MTPzayb00P4qoL" -O ~/.cache/kitforge/larsnet/pretrained_larsnet_models.zip
unzip ~/.cache/kitforge/larsnet/pretrained_larsnet_models.zip -d ~/.cache/kitforge/larsnet/
```

The LarsNet repo is auto-cloned to `~/.cache/kitforge/larsnet/` on first run if weights are present. Without weights the pipeline falls back to a frequency-band energy split (coarser, still works).

---

## Usage

```bash
source .venv/bin/activate

# Drum kit
kitforge build --song song.wav --instrument drums --out ~/Desktop/kit

# Bass kit (default range C1–G4)
kitforge build --song song.wav --instrument bass --out ~/Desktop/bass_kit

# Bass kit with explicit range
kitforge build --song song.wav --instrument bass --range E1-C5 --out ~/Desktop/bass_kit

# Guitar / piano / synth
kitforge build --song song.wav --instrument guitar --out ~/Desktop/guitar_kit
kitforge build --song song.wav --instrument piano --range C2-C7 --out ~/Desktop/piano_kit
kitforge build --song song.wav --instrument "lead synth" --out ~/Desktop/synth_kit

# High-quality mode: Banquet separation + DeepFilterNet denoising + CLAP clustering
kitforge build --song song.wav --instrument piano --quality high --out ~/Desktop/piano_kit

# Pin Banquet's query to a specific 10s window of the song (--quality high only)
kitforge build --song song.wav --instrument synth --quality high --query 0:44-0:54 --out ~/Desktop/synth_kit

# Export the kit to a Roland MC-101 SD card (drums: per-pad WAVs + SETUP.txt; pitched: single root sample)
kitforge build --song song.wav --instrument drums --out ~/Desktop/kit --mc101 /Volumes/MC-101

# Flags
--quality fast|default|high    # fast = htdemucs; default = + BS-RoFormer cascade for pitched; high = + Banquet + DeepFilterNet
--query MM:SS-MM:SS            # (--quality high) override Banquet's auto query window with an exact timestamp
--mc101 <path>                 # also copy the kit to a Roland MC-101 SD card with a SETUP.txt
--debug                        # extra diagnostics and intermediate WAV locations
--config kitforge.toml         # load settings from a TOML file
```

Supported input formats: `.wav`, `.mp3`, `.flac`, `.aiff`, `.aif`, `.m4a`, `.ogg`

**Stem cache:** Demucs results are cached at `~/.cache/kitforge/stems/<songname>/` keyed by file SHA-256. Re-running the same file skips separation entirely.

**Stage cache:** Slicing and packaging results are cached in `~/.cache/kitforge/stage_cache/` keyed by `(file_hash, stage_version, params, output_dir)`. Second run on the same song+output is near-instant.

**Example output (drums, cached run):**
```
Stage 1/3: Stems cached — skipping separation
  separation: 0.0s
Stage 2/3: Extracting samples...
  extraction: 12.2s — 80 one-shots
Stage 3/3: Writing SFZ and DecentSampler preset...
  packaging: 0.0s

Done in 12.3s — 80 samples
  SFZ           ~/Desktop/kit/kit.sfz
  DecentSampler ~/Desktop/kit/kit.dspreset
  Samples dir   ~/Desktop/kit/samples
```

---

## Architecture

```
song.wav
  │
  ├─ (pitched only) ─▶
  │   roformer_runner.py   BS-RoFormer → vocals + instrumental
  │                        (instrumental fed to demucs instead of raw mix)
  │
  ▼
demucs_runner.py         htdemucs_ft → drums.wav, bass.wav, vocals.wav, other.wav
  │                      htdemucs_6s → + guitar.wav, piano.wav  (guitar/piano only)
  │
  ├─▶ (drums)
  │   denoise.py*          DeepFilterNet3 stem cleanup          [--quality high]
  │   larsnet_runner.py    LarsNet → kick / snare / hihat / toms / cymbals stems
  │   slicer.py            onset detect → velocity-layered one-shots → normalize
  │   clap_embed.py        LAION-CLAP embeddings per hit
  │   cluster.py           farthest-point sampling → diverse round-robins per layer
  │   sfz_writer.py        kit.sfz  (vel layers, round-robins, hihat choke)
  │   decentsampler_writer.py  kit.dspreset
  │
  ├─▶ (bass)
  │   denoise.py*          DeepFilterNet3 stem cleanup          [--quality high]
  │   crepe_mono.py        torchcrepe f0 → (times, f0_hz, periodicity)
  │   pitched_slicer.py    note segmentation → collect all occurrences per pitch
  │   clap_embed.py        LAION-CLAP embeddings per occurrence
  │   cluster.py           pick_medoid → canonical sample per MIDI note
  │   pitched_slicer.py    Voronoi zone fill → Rubber Band R3 pre-shift (gap > 6 st)
  │   adsr.py              RMS-envelope ADSR estimation per zone
  │   loop_finder.py       autocorrelation loop points (sustained samples only)
  │   sfz_writer.py        kit.sfz  (lokey/hikey/pitch_keycenter, ampeg_*, loop)
  │   decentsampler_writer.py  kit.dspreset
  │
  └─▶ (guitar / piano / synth)
      query_separator.py*  Banquet query separation             [--quality high]
                           (input = BS-RoFormer instrumental, not raw mix)
                           (query window = highest-RMS 10 s of rough stem, or --query)
      denoise.py*          DeepFilterNet3 stem cleanup          [--quality high]
      basic_pitch_runner.py  Basic Pitch polyphonic → note events
      pitched_slicer.py    collect occurrences → CLAP medoid → Voronoi fill
      adsr.py + loop_finder.py  envelope + loop points per zone
      sfz_writer.py        kit.sfz
      decentsampler_writer.py  kit.dspreset

(after the kit is built, --mc101 <path> copies it to a Roland MC-101 SD card
 via package/mc101_writer.py — drums become per-pad PCM_16 WAVs + SETUP.txt;
 pitched exports a single root sample for the MC-101 Tone track's chromatic transpose)

* only when --quality high
```

**Module map:**

| Module | Status | Does |
|--------|--------|------|
| `separation/demucs_runner.py` | ✅ Working | htdemucs_ft / htdemucs_6s separation, MPS-accelerated |
| `separation/larsnet_runner.py` | ✅ Working | LarsNet 5-class drum sub-stem separation |
| `separation/roformer_runner.py` | ✅ Working | BS-RoFormer vocal pre-removal cascade (pitched instruments, all qualities) |
| `separation/query_separator.py` | ✅ Working | Banquet query-based separation (optional, `--quality high`) |
| `transcribe/crepe_mono.py` | ✅ Working | torchcrepe monophonic f0 tracking for bass/lead |
| `transcribe/basic_pitch_runner.py` | ✅ Working | Basic Pitch polyphonic transcription for guitar/piano/synth |
| `transcribe/mt3_runner.py` | 🔲 Stub | Multi-instrument joint transcription (deferred) |
| `extract/slicer.py` | ✅ Working | Drum onset detection, velocity-layered one-shot slicing |
| `extract/pitched_slicer.py` | ✅ Working | Bass f0 / polyphonic note events → per-note samples + zone fill |
| `extract/adsr.py` | ✅ Working | ADSR envelope estimation (attack/decay/sustain/release from RMS envelope) |
| `extract/cluster.py` | ✅ Working | CLAP-based medoid + farthest-point RR selection |
| `extract/denoise.py` | ✅ Working | DeepFilterNet3 post-separation denoising (activated at --quality high) |
| `extract/loop_finder.py` | ✅ Working | Autocorrelation loop-point search with zero-crossing alignment |
| `pitchshift/rubberband_wrapper.py` | ✅ Working | Rubber Band R3 pitch shifting |
| `timbre/clap_embed.py` | ✅ Working | LAION-CLAP 512-d timbre embeddings (lazy singleton, 600 MB download on first use) |
| `package/sfz_writer.py` | ✅ Working | SFZ: drums (vel layers, RR, choke) + pitched (zones) |
| `package/decentsampler_writer.py` | ✅ Working | DecentSampler XML: same structure |
| `package/mc101_writer.py` | ✅ Working | Roland MC-101 SD card export (drums: per-pad PCM_16 + SETUP.txt; pitched: single root sample) |
| `package/ableton_writer.py` | 🔲 Stub | Ableton .adg drum rack export (Phase 2) |
| `cache.py` | ✅ Working | Content-addressed diskcache, wired into pipeline |
| `synth/dac_lm.py` | 🔲 Stub | DAC-token LM for neural pitch fill (Phase 2) |

---

## Roadmap

### `--quality high` stack

**Default quality** for pitched instruments now runs a BS-RoFormer → htdemucs cascade automatically (no flag). `--quality high` adds three more optional stages on top:

| Stage | What it does | Runtime (CPU) |
|-------|-------------|---------------|
| **Banquet** (pitched only) | Query-conditioned separation. Runs on the BS-RoFormer instrumental (not the raw mix), with the auto-picked highest-RMS 10 s window of the rough stem as query — or `--query MM:SS-MM:SS` for manual control | ~15–35 min/song |
| **DeepFilterNet3** (all instruments) | Neural noise suppression on the target stem before slicing | ~real-time |
| **CLAP round-robins** (drums) | Timbral farthest-point sampling instead of energy-spread; ~600 MB model download on first use | fast after download |

```bash
# One-time setup for Banquet (guitar/piano/synth):
kitforge setup-banquet    # ~30 MB repo + ~645 MB weights

# Run with all enhancements:
kitforge build --song song.wav --instrument piano --quality high --out ~/Desktop/piano_kit
```

`default` and `fast` are unchanged — the extra models are never loaded.

### Phase 2 — DAC-token language model

Neural pitch fill: train a ~100M param decoder-only transformer over DAC tokens,
conditioned on pitch + velocity + CLAP timbre embedding. Replaces DSP pitch shifting
for large intervals. See `synth/dac_lm.py`.

---

## Known issues / gotchas

- **LarsNet weights are CC-BY-NC 4.0** — fine for personal use, not for distribution
- **Bass on 808-heavy tracks** — 808 sub-bass is often one root note; expect 1–2 unique pitches. Use `--range C1-G4` or lower to match the tuning
- **torchcrepe capped at 90s** — f0 tracking runs on the first 90s of the bass stem to avoid OOM. Pitches that only appear late in the song are missed
- **torchaudio + torchcodec** — demucs stem writing uses soundfile directly to avoid MPS incompatibility with torchcodec's audio encoder
- **LarsNet tqdm output** — LarsNet prints its own progress bars to stdout; these come from inside the library and can't be suppressed without patching
- **CLAP model download (~600 MB)** — downloads from HuggingFace on the first kit build that needs CLAP clustering; subsequent runs use the cached weights
- **deepfilternet 0.5.6 + torchaudio 2.x** — the package uses removed APIs; `denoise.py` patches them at import time. If deepfilternet releases a fix, the patch is safe to remove
- **Banquet CPU runtime** — ~15–35 min/song on CPU; plan for an overnight run or use a CUDA GPU. Not needed for default quality
- **BS-RoFormer adds ~3 min** to pitched-instrument runs at any quality. Stems are cached by content hash, so it only runs once per song
- **Banquet timbral limits** — Banquet maps the user's instrument name to one of a fixed set of stems (`synth_lead`, `synth_pad`, `electric_piano`, etc.). Hybrid timbres (e.g. a synth + Rhodes layer) blend toward the closest prototype; absolute exact-timbre reconstruction will need Phase 2's neural fill
- **MC-101 SD card auto-unmount** — long Banquet runs sometimes outlive the SD card's USB connection. Replug after the kit finishes and re-run `kitforge build … --mc101 …` — the pipeline is fully cached, so the export takes <1 s

---

## Tech decisions log

| Decision | What was chosen | Why |
|----------|----------------|-----|
| Separator | htdemucs_ft (default), htdemucs_6s (6-stem) | MIT license, 9.20 dB SDR, runs on MPS |
| Drum sub-stems | LarsNet (w/ freq-band fallback) | Only open model with dedicated per-class U-Nets |
| Monophonic f0 | torchcrepe (not crepe PyPI) | crepe 0.0.16 build is broken on setuptools ≥ 71 |
| Pitch shifting | pyrubberband + Rubber Band R3 | ±6 st pre-shift threshold; sampler handles smaller intervals |
| Stem save format | soundfile PCM_24 (not torchaudio.save) | torchcodec doesn't support MPS encoding |
| Output formats | SFZ + DecentSampler simultaneously | SFZ is the open standard; DS gives a free polished runtime |
| Bass range default | C1–G4 (MIDI 24–67) | Real-song testing showed most bass sits at C#1–E1, below old E1 floor |
| f0 tracking window | 90s cap | Full-song torchcrepe OOM on 4-min stems at CPU; 90s captures all pitches |
| Velocity layers | Sort by pre-normalization peak | Post-normalization peaks are uniform; raw energy needed to sort |
| Cache key | (file_sha256, model, version, params, out_dir) | Out dir must be in key — absolute paths in cached OneShots break across runs |
| Package manager | uv | Fast, Python-version-aware, no conda |
| LarsNet config | abs-path config_abs.yaml written at runtime | config.yaml uses relative paths, breaks when cwd ≠ larsnet dir |
| Canonical sample selection | CLAP medoid (all occurrences) | "Pick longest" misses quieter but timbrally cleaner occurrences; CLAP centroid is more perceptually representative |
| Round-robin diversity | Farthest-point sampling on CLAP | HDBSCAN degenerates on small N (5–20 hits/bucket); farthest-point directly maximises pairwise cosine distance |
| Denoising compat | monkey-patch torchaudio.backend.common before df.* import | deepfilternet 0.5.6 uses APIs removed in torchaudio 2.x; patching avoids pinning torchaudio |
| ADSR source | 5 ms RMS hops on the normalized clip | Spectral-centroid approaches miss the envelope shape for non-harmonic sounds; RMS is instrument-agnostic |
| Loop points | Autocorrelation on middle-half + zero-crossing alignment | Period detection on the steady-state region avoids attack transient bias; zero-crossing prevents clicks |
| DS ADSR granularity | Median across zones on `<group>` | DecentSampler ADSR is per-group, not per-sample; SFZ gets full per-region ADSR |
| Pitched separation cascade | BS-RoFormer (vocal pre-removal) → htdemucs (everything else) | htdemucs's vocal isolation (~10.5 dB) leaks into "other"; pre-stripping with 17 dB BS-RoFormer makes "other" a true non-vocal residual |
| Banquet query selection | Highest-RMS 10 s window of the rough htdemucs stem (auto), overridable via `--query MM:SS-MM:SS` | First-10 s window misses sparse intros and can lock Banquet onto intro percussion — auto-RMS finds the moment the target instrument is actually present |
| Banquet input audio | The BS-RoFormer instrumental, not the raw mix | When Banquet sees vocals in the input, it can extract vocal-bleed content matching the query timbre; the cascade input keeps it on instrument-only |
| MC-101 drum format | Re-encode WAVs as PCM_16 on export | MC-101 firmware rejects float32 WAVs; slicer writes float32 by default so we re-encode at the export boundary |
| MC-101 SD card copy | `shutil.copyfile` (content only), not `copy2` | FAT32 returns `EINVAL` on `chflags`, breaking `copystat`; `copyfile` skips metadata |

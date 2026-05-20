# kitCreator

Turn any song into a playable multi-octave sampler kit. Give it an audio file, tell it what instrument you want, get back an SFZ + DecentSampler preset ready to load in any sampler.

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
2. **LarsNet** — splits the drum stem into 5 clean sub-stems: kick, snare, hi-hat, toms, cymbals
3. **Onset detection** — finds every hit in each sub-stem via librosa
4. **Velocity-layered slicing** — sorts hits by pre-normalization energy, bins into up to 4 velocity layers, picks round-robins within each layer
5. **SFZ + DecentSampler export** — hi-hat choke groups, velocity layers (`lovel/hivel`), round-robin sequencing

### Bass pipeline

1. **Demucs htdemucs_ft** — isolates the bass stem
2. **torchcrepe** — tracks f0 frame-by-frame on the first 90s of the stem
3. **Note segmentation** — groups voiced frames into note events by pitch stability (±60 cents) and confidence threshold
4. **Per-note slicing** — picks the longest occurrence of each detected MIDI pitch as the canonical sample
5. **Voronoi zone fill** — assigns `lokey/hikey` boundaries between adjacent real samples; gaps > 6 semitones get pre-shifted via Rubber Band R3
6. **SFZ + DecentSampler export** — `pitch_keycenter` per zone

### Guitar / Piano / Synth pipeline

1. **Demucs** — guitar/piano use `htdemucs_6s` (6-stem, dedicated stems); synth uses `htdemucs_ft` "other" stem
2. **Basic Pitch** — Spotify's polyphonic transcription model; converts the stem to MIDI note events
3. **Per-note slicing** — picks longest occurrence of each MIDI pitch as canonical sample
4. **Voronoi zone fill** — same as bass; Rubber Band R3 pre-shift for gaps > 6 semitones
5. **SFZ + DecentSampler export** — `pitch_keycenter` per zone

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

# Flags
--quality fast|default|high    # fast = htdemucs; default = htdemucs_ft; high = htdemucs_ft + Banquet (see below)
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
  ▼
demucs_runner.py       htdemucs_ft → drums.wav, bass.wav, vocals.wav, other.wav
  │
  ├─▶ (drums)
  │   larsnet_runner.py    LarsNet → kick / snare / hihat / toms / cymbals stems
  │   slicer.py            onset detect → velocity-layered one-shots → normalize
  │   sfz_writer.py        kit.sfz  (vel layers, round-robins, hihat choke)
  │   decentsampler_writer.py  kit.dspreset
  │
  ├─▶ (bass)
  │   crepe_mono.py        torchcrepe f0 → (times, f0_hz, periodicity)
  │   pitched_slicer.py    note segmentation → per-note slices → Voronoi zone fill
  │   rubberband_wrapper.py  Rubber Band R3 pre-shift for gaps > 6 semitones
  │   sfz_writer.py        kit.sfz  (lokey/hikey/pitch_keycenter per zone)
  │   decentsampler_writer.py  kit.dspreset
  │
  └─▶ (guitar / piano / synth)
      demucs_runner.py     htdemucs_6s (guitar/piano) or htdemucs_ft other stem (synth)
      basic_pitch_runner.py  Basic Pitch polyphonic transcription → note events
      pitched_slicer.py    per-note slices → Voronoi zone fill (same as bass)
      rubberband_wrapper.py  Rubber Band R3 pre-shift for gaps > 6 semitones
      sfz_writer.py        kit.sfz
      decentsampler_writer.py  kit.dspreset
```

**Module map:**

| Module | Status | Does |
|--------|--------|------|
| `separation/demucs_runner.py` | ✅ Working | htdemucs_ft / htdemucs_6s separation, MPS-accelerated |
| `separation/larsnet_runner.py` | ✅ Working | LarsNet 5-class drum sub-stem separation |
| `separation/roformer_runner.py` | 🔲 Stub | BS-RoFormer high-quality mode |
| `separation/query_separator.py` | ✅ Working | Banquet query-based separation (optional, `--quality high`) |
| `transcribe/crepe_mono.py` | ✅ Working | torchcrepe monophonic f0 tracking for bass/lead |
| `transcribe/basic_pitch_runner.py` | ✅ Working | Basic Pitch polyphonic transcription for guitar/piano/synth |
| `transcribe/mt3_runner.py` | 🔲 Stub | Multi-instrument joint transcription (deferred) |
| `extract/slicer.py` | ✅ Working | Drum onset detection, velocity-layered one-shot slicing |
| `extract/pitched_slicer.py` | ✅ Working | Bass f0 / polyphonic note events → per-note samples + zone fill |
| `extract/adsr.py` | 🔲 Stub | ADSR envelope estimation for pitched samples |
| `extract/cluster.py` | 🔲 Stub | HDBSCAN over CLAP embeddings for RR selection |
| `extract/denoise.py` | 🔲 Stub | DeepFilterNet post-separation cleanup |
| `extract/loop_finder.py` | 🔲 Stub | Autocorrelation loop-point search |
| `pitchshift/rubberband_wrapper.py` | ✅ Working | Rubber Band R3 pitch shifting |
| `timbre/clap_embed.py` | 🔲 Stub | LAION-CLAP 512-d timbre embeddings |
| `package/sfz_writer.py` | ✅ Working | SFZ: drums (vel layers, RR, choke) + pitched (zones) |
| `package/decentsampler_writer.py` | ✅ Working | DecentSampler XML: same structure |
| `package/ableton_writer.py` | 🔲 Stub | Ableton .adg drum rack export (Phase 2) |
| `cache.py` | ✅ Working | Content-addressed diskcache, wired into pipeline |
| `synth/dac_lm.py` | 🔲 Stub | DAC-token LM for neural pitch fill (Phase 2) |

---

## Roadmap

### Optional: Banquet high-quality separation

For better guitar/piano/synth isolation (htdemucs_6s piano quality is flagged as poor in Meta's own README), enable Banquet:

```bash
# One-time setup: ~30 MB repo clone + ~645 MB model weights
kitforge setup-banquet

# Then use --quality high to activate it
kitforge build --song song.wav --instrument piano --range C2-C7 --out ~/Desktop/piano_kit --quality high
```

**Runtime:** CPU ~35 min/song. CUDA GPU ~5 min. gated behind `--quality high` only; `default` and `fast` are unchanged.

Banquet is a query-based separator — it takes the rough htdemucs stem as a 10-second reference and uses it to extract that instrument directly from the full mix. On piano and guitar specifically, Banquet outperforms htdemucs_6s (per the original paper).

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

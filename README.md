# kitCreator

Turn any song into a playable multi-octave sampler kit. Give it an audio file, tell it what instrument you want, get back an SFZ + DecentSampler preset ready to load in any sampler.

Built by Ethan Saba.

---

## What it does right now

**Drums are working end-to-end.**

```
kitforge build --song mysong.wav --instrument drums --out ~/Desktop/my_kit
```

This runs:
1. **Demucs htdemucs_ft** — separates the song into vocals / drums / bass / other stems
2. **LarsNet** — splits the drum stem into 5 clean sub-stems: kick, snare, hi-hat, toms, cymbals (each through its own dedicated U-Net)
3. **Onset detection** — finds every hit in each sub-stem via librosa
4. **One-shot slicing** — cuts, tail-trims, and peak-normalizes up to 4 round-robins per class
5. **SFZ + DecentSampler export** — writes a loadable kit with hi-hat choke groups and round-robin sequencing

Output lands at `--out/`:
```
my_kit/
├── kit.sfz          # load in Sforzando, sfizz, Bitwig Sampler, etc.
├── kit.dspreset     # load in DecentSampler (free VST/AU/AAX)
└── samples/
    ├── kick_1.wav … kick_4.wav
    ├── snare_1.wav … snare_4.wav
    ├── hihat_1.wav … hihat_4.wav
    ├── toms_1.wav  … toms_4.wav
    └── cymbals_1.wav … cymbals_4.wav
```

SFZ MIDI layout (GM-adjacent):
| Class   | Note |
|---------|------|
| kick    | C1 (36) |
| snare   | D1 (38) |
| hihat   | F#1 (42) |
| toms    | B1 (47) |
| cymbals | C2 (48) |

---

## Setup

**Requirements:** Python 3.11, [uv](https://github.com/astral-sh/uv), ffmpeg, rubberband

```bash
# macOS
brew install ffmpeg rubberband

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone <repo>
cd kitCreator
uv venv --python 3.11 .venv
uv pip install -e ".[dev]"
```

**LarsNet weights** (562 MB, CC-BY-NC 4.0 — local use only):

```bash
# Download from Google Drive
gdown "1U8-5924B1ii1cjv9p0MTPzayb00P4qoL" -O ~/.cache/kitforge/larsnet/pretrained_larsnet_models.zip
unzip ~/.cache/kitforge/larsnet/pretrained_larsnet_models.zip -d ~/.cache/kitforge/larsnet/
```

The LarsNet repo itself is auto-cloned to `~/.cache/kitforge/larsnet/` on first run if weights are present. If weights aren't found, the pipeline falls back to a frequency-band energy split (coarser separation, still works).

---

## Usage

```bash
# Activate the venv
source .venv/bin/activate

# Build a drum kit
kitforge build --song song.wav --instrument drums --out ~/Desktop/kit

# Flags
--quality fast|default|high    # fast = htdemucs, default/high = htdemucs_ft
--debug                        # writes intermediate WAVs to inspect each stage
--config kitforge.toml         # load settings from a TOML file
```

Supported input formats: `.wav`, `.mp3`, `.flac`, `.aiff`, `.aif`, `.m4a`, `.ogg`

**Stem cache:** Demucs separation results are cached at `~/.cache/kitforge/stems/<songname>/`. Re-running the same file skips separation entirely — only the slicing and packaging stages re-run.

---

## Architecture

```
song.wav
  │
  ▼
demucs_runner.py          htdemucs_ft → drums.wav, bass.wav, vocals.wav, other.wav
  │
  ▼ (drums path)
larsnet_runner.py         LarsNet → kick.wav, snare.wav, hihat.wav, toms.wav, cymbals.wav
  │
  ▼
slicer.py                 onset detection → one-shot slices → peak normalize → tail trim
  │
  ▼
sfz_writer.py             emit kit.sfz  (round-robins, hihat choke, GM note map)
decentsampler_writer.py   emit kit.dspreset  (same structure, XML format)
```

**Module map:**

| Module | Status | Does |
|--------|--------|------|
| `separation/demucs_runner.py` | ✅ Working | htdemucs_ft / htdemucs_6s separation, MPS-accelerated |
| `separation/larsnet_runner.py` | ✅ Working | LarsNet 5-class drum sub-stem separation |
| `separation/roformer_runner.py` | 🔲 Stub | BS-RoFormer high-quality mode (Phase 1.2) |
| `separation/query_separator.py` | 🔲 Stub | Banquet CLAP-query sub-instrument router (Phase 1.2) |
| `transcribe/basic_pitch_runner.py` | 🔲 Stub | Polyphonic note transcription for pitched stems |
| `transcribe/crepe_mono.py` | 🔲 Stub | Monophonic f0 tracking (torchcrepe) for bass/lead |
| `transcribe/mt3_runner.py` | 🔲 Stub | Multi-instrument joint transcription (deferred) |
| `extract/slicer.py` | ✅ Working | Drum onset detection + one-shot slicing |
| `extract/adsr.py` | 🔲 Stub | ADSR envelope estimation for pitched samples |
| `extract/cluster.py` | 🔲 Stub | HDBSCAN over CLAP embeddings for RR selection |
| `extract/denoise.py` | 🔲 Stub | DeepFilterNet post-separation cleanup |
| `extract/loop_finder.py` | 🔲 Stub | Autocorrelation loop-point search for sustained notes |
| `pitchshift/rubberband_wrapper.py` | 🔲 Stub | Rubber Band R3 pitch shifting for keyboard range fill |
| `timbre/clap_embed.py` | 🔲 Stub | LAION-CLAP 512-d timbre embeddings |
| `package/sfz_writer.py` | ✅ Working | SFZ emit: round-robins, velocity layers, choke groups |
| `package/decentsampler_writer.py` | ✅ Working | DecentSampler XML preset emit |
| `package/ableton_writer.py` | 🔲 Stub | Ableton .adg drum rack export (Phase 2) |
| `synth/dac_lm.py` | 🔲 Stub | DAC-token LM for neural pitch fill (Phase 2) |
| `cache.py` | ✅ Written | Content-addressed diskcache (not yet wired into pipeline) |

---

## What's next (Phase 1 roadmap)

**Velocity layers** — currently picks up to 4 round-robins per class by onset order. Need to sort by hit energy and map to SFZ `lovel/hivel` so soft vs. hard hits play different samples.

**Content-addressed caching** — `cache.py` exists but isn't wired into the pipeline yet. Slicing and packaging stages should be skipped on re-run if nothing changed.

**Bass** — first pitched instrument: htdemucs bass stem → torchcrepe f0 → note slicing → Rubber Band pitch-shift to fill MIDI range → SFZ.

**General pitched instruments** (guitar, piano, synth) — requires Banquet query-based sub-stem separation from the "other" stem, then Basic Pitch transcription.

---

## Known issues / gotchas

- **LarsNet weights are CC-BY-NC 4.0** — fine for personal use, not for distribution in a commercial product
- **Stem cache is not content-addressed** — if you reprocess the same filename with different settings, delete `~/.cache/kitforge/stems/<songname>/` manually
- **torchaudio 2.12 + torchcodec** — demucs stem writing uses soundfile directly to avoid MPS incompatibility with torchcodec's audio encoder
- **pydantic toml_file warning** — cosmetic; TOML config loading isn't wired yet, settings come from env vars (`KITFORGE_*`) only

---

## Tech decisions log

| Decision | What was chosen | Why |
|----------|----------------|-----|
| Separator | htdemucs_ft (default), htdemucs_6s (6-stem) | MIT license, 9.20 dB SDR, runs on MPS |
| Drum sub-stems | LarsNet (w/ freq-band fallback) | Only open model with dedicated per-class U-Nets |
| Monophonic f0 | torchcrepe (not crepe PyPI) | crepe 0.0.16 build is broken on setuptools ≥ 71 |
| Stem save format | soundfile PCM_24 (not torchaudio.save) | torchcodec doesn't support MPS encoding |
| Output formats | SFZ + DecentSampler simultaneously | SFZ is the open standard; DS gives a free polished runtime |
| Package manager | uv | Fast, Python-version-aware, no conda |
| LarsNet install | cloned to ~/.cache/kitforge/larsnet | Not on PyPI; weights on Google Drive |
| LarsNet config | abs-path config_abs.yaml written at runtime | config.yaml uses relative paths, breaks when cwd != larsnet dir |

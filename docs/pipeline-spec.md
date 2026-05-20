# Pipeline Spec

Precise definitions of what each instrument pipeline produces. This is the contract tests and future contributors should verify against.

---

## Drums

**Trigger:** `--instrument drums` (also: `drum`, `kit`, `drum kit`)

### Input
- Any audio file supported by Demucs (`.wav .mp3 .flac .aiff .m4a .ogg`)

### Stage 1 — Source separation
- Model: `htdemucs_ft` (default/high) or `htdemucs` (fast)
- Outputs: `drums.wav`, `bass.wav`, `vocals.wav`, `other.wav` at model SR (44100 Hz), stereo PCM-24
- Cached by: SHA-256 of input file → `~/.cache/kitforge/stems/<name>/.song_hash`

### Stage 2 — Drum sub-stem separation
- Model: LarsNet (preferred) or frequency-band energy split (fallback)
- LarsNet outputs: `kick.wav`, `snare.wav`, `hihat.wav`, `toms.wav`, `cymbals.wav`
- Fallback band split outputs: `kick.wav`, `snare.wav`, `hihat.wav`, `perc.wav`
- Written to `<out>/_larsnet_stems/`

### Stage 3 — Onset detection + slicing
- Library: librosa `onset_detect` with `backtrack=True`, `hop_length=256`
- Min onset interval: 50 ms
- One-shot bounds: min 50 ms, max 800 ms (or next onset, whichever is shorter)
- Tail trim: RMS scan backwards in 256-sample hops until RMS > −55 dB threshold
- Normalization: peak normalize to −1 dBFS (0.891 linear) **after** recording raw peak for velocity sorting

### Stage 4 — Velocity bucketing
- Slices sorted by pre-normalization peak amplitude (raw energy)
- Up to `MAX_VELOCITY_BUCKETS = 4` layers; actual bucket count = `min(4, len(slices) // 2)`
- Velocity boundaries: evenly spaced across 0–127 (`vel_step = 128 // actual_buckets`)
- Last bucket always ends at 127
- Within each bucket: up to `MAX_ROUND_ROBINS = 4` samples, spread evenly across the bucket's energy range

### Output
- Sample files: `samples/{class}_v{vel_low}_{rr_index+1}.wav` (1-indexed)
- `kit.sfz` — see [SFZ Format](#sfz-format-drums)
- `kit.dspreset` — see [DecentSampler Format](#decentsampler-format)

---

## Bass

**Trigger:** `--instrument bass` (also: `bass guitar`, `synth bass`, `808`)

### Input
- Any supported audio file
- `--range LO-HI` (e.g. `C1-G4`); default `C1-G4` (MIDI 24–67)

### Stage 1 — Source separation
- Same as drums; uses `bass.wav` stem

### Stage 2 — f0 tracking
- Library: torchcrepe (`full` model, CPU only)
- Input: bass stem resampled to 16 kHz, capped to first 90 seconds
- `hop_length = 512`, `fmin = 35.0 Hz`, `fmax = 420.0 Hz`, `batch_size = 512`
- Returns: `(times_s, f0_hz, periodicity)` arrays of shape `(n_frames,)`
- Voiced frame threshold: `periodicity ≥ 0.55`

### Stage 3 — Note segmentation
- Voiced frames grouped into contiguous segments
- A frame breaks the current segment if its MIDI pitch differs from segment median by > 60 cents
- Segment discarded if duration < 60 ms

### Stage 4 — Per-note sample collection
- For each unique MIDI pitch: longest voiced segment chosen as canonical sample
- Sample capped at 4.0 s
- Peak normalized to −1 dBFS

### Stage 5 — Voronoi zone fill
- Anchors: real samples whose MIDI pitch falls within `[lo − 6, hi + 6]`
- Zone boundaries: midpoint between adjacent anchors, clipped to `[lo, hi]`
- Gap > `MAX_SHIFT_SEMITONES = 6`: audio pre-shifted with Rubber Band R3 (`pyrubberband.pitch_shift`)
- Gap ≤ 6 semitones: sampler handles pitch internally (standard zone-mapping)

### Output
- Sample files: `samples/bass_{note}_{midi}.wav` (e.g. `bass_Cs1_midi25.wav`)
- `kit.sfz` — see [SFZ Format (pitched)](#sfz-format-pitched)
- `kit.dspreset` — see [DecentSampler Format](#decentsampler-format)

---

## Guitar / Piano / Synth

**Trigger:**
- Guitar: `--instrument guitar` (also: `electric guitar`, `acoustic guitar`)
- Piano: `--instrument piano` (also: `keys`, `keyboard`, `electric piano`, `rhodes`)
- Synth: `--instrument synth` (also: `lead synth`, `lead`, `pad`, `organ`, `synth lead`)

### Input
- Any supported audio file
- `--range LO-HI` (e.g. `E2-E6`); defaults: guitar E2–E6 (40–88), piano C2–C7 (36–96), synth C3–C6 (48–84)

### Stage 1 — Source separation
- Guitar/piano: `htdemucs_6s` (6-stem) — provides dedicated `guitar.wav` and `piano.wav` stems
- Synth: `htdemucs_ft` (4-stem) — uses `other.wav`
- Cached same as drums

### Stage 2 — Polyphonic transcription
- Library: Spotify Basic Pitch (Apache 2.0), CoreML model on Mac
- Input: stem WAV at native SR
- Parameters: `onset_threshold=0.5`, `frame_threshold=0.3`, `minimum_note_length=60 ms`
- Returns: `list[(start_s, end_s, midi_note, amplitude)]`
- All stdout/stderr/logging suppressed during inference via `_silence()` context manager

### Stage 3 — Per-note sample collection
- For each unique MIDI note: longest occurrence chosen as canonical sample
- Sample capped at 4.0 s, peak normalized to −1 dBFS

### Stage 4 — Voronoi zone fill
- Same algorithm as bass: midpoint boundaries, Rubber Band R3 pre-shift when gap > 6 semitones

### Output
- Sample files: `samples/bass_{note}_midi{n}.wav` (reuses bass filename scheme)
- `kit.sfz` and `kit.dspreset` — same pitched format as bass

---

## SFZ Format — Drums

```sfz
// kitforge drum kit — SFZ format
<global>
ampeg_release=0.05

// kick
<group> lokey=36 hikey=36 pitch_keycenter=36
<region> sample=samples/kick_v0_1.wav    lovel=0   hivel=31
<region> sample=samples/kick_v0_2.wav    lovel=0   hivel=31  seq_position=2 seq_length=2
<region> sample=samples/kick_v32_1.wav   lovel=32  hivel=63
...

// hihat (choke group)
<group> lokey=42 hikey=42 pitch_keycenter=42 group=1 off_by=1 off_mode=fast
<region> sample=samples/hihat_v0_1.wav   lovel=0   hivel=31
...
```

**MIDI note map (GM-adjacent):**

| Class   | MIDI |
|---------|------|
| kick    | 36   |
| snare   | 38   |
| hihat   | 42   |
| toms    | 47   |
| cymbals | 48   |

**Hi-hat choke:** `group=1 off_by=1 off_mode=fast` on the hihat `<group>`. Any new hihat hit cuts the previous one.

**Round-robins:** `seq_position` and `seq_length` per region within each velocity layer. Counter is per-group so layers don't share sequence state.

---

## SFZ Format — Pitched

```sfz
// kitforge pitched kit — SFZ format
<global>
ampeg_release=0.3

<group>
<region> sample=samples/bass_Cs1_midi25.wav lokey=24 hikey=25 pitch_keycenter=25
<region> sample=samples/bass_D1_midi26.wav  lokey=26 hikey=67 pitch_keycenter=26
```

- One `<region>` per zone (real or pre-shifted)
- `pitch_keycenter` = MIDI note of the audio in the file (source note before any sampler pitch)
- Sampler transposes: plays at lokey → hikey by pitching relative to `pitch_keycenter`

---

## DecentSampler Format

```xml
<?xml version="1.0" encoding="UTF-8"?>
<DecentSampler minVersion="1.0.0">
  <ui .../>
  <groups>
    <!-- drums: one <group> per velocity layer per drum class -->
    <group seqMode="round_robin" [silencedByTags="hihat" tags="hihat"]>
      <sample path="samples/kick_v0_1.wav"
              loNote="36" hiNote="36" rootNote="36"
              loVel="0" hiVel="31" volume="1.0" seqPosition="1"/>
      ...
    </group>

    <!-- bass: one <group> covering all zones -->
    <group>
      <sample path="samples/bass_Cs1_midi25.wav"
              loNote="24" hiNote="25" rootNote="25"
              loVel="0" hiVel="127" volume="1.0"/>
      ...
    </group>
  </groups>
</DecentSampler>
```

---

## Caching Contract

Every pipeline stage is cached. Cache is never stale — keys change when inputs or logic change.

| Stage | Cache type | Key includes |
|-------|-----------|--------------|
| Demucs separation | SHA-256 sentinel file at `stems_dir/.song_hash` | Input file content hash |
| Drum slicing | diskcache (`stage_cache/`) | drum_wav hash, stage version, `round_robins`, `velocity_buckets`, `tail_db`, output dir |
| Bass pitching | diskcache (`stage_cache/`) | bass_wav hash, stage version, `lo_midi`, `hi_midi`, output dir |
| Guitar/piano/synth | diskcache (`stage_cache/`) | stem_wav hash, stage version, `lo_midi`, `hi_midi`, stem path, output dir |

**Version bumping:** increment `_SLICER_VERSION` or `_PITCHER_VERSION` in `pipeline.py` to invalidate cached results after logic changes.

**Cache location:** `~/.cache/kitforge/stage_cache/` (diskcache directory)

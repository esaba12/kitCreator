# Changelog

All notable changes to kitCreator. Entries are grouped by feature area, not by individual commit.

---

## [Unreleased]

### Planned
- `query_separator.py` — Banquet CLAP-query separation for guitar/piano/synth from "other" stem

---

## 2026-05-19 — General Pitched Instruments: Guitar, Piano, Synth (Phase 1.2)

### Added
- `--instrument guitar` / `acoustic guitar` / `electric guitar` — uses htdemucs_6s guitar stem
- `--instrument piano` / `keys` / `keyboard` / `electric piano` / `rhodes` — uses htdemucs_6s piano stem
- `--instrument synth` / `lead synth` / `lead` / `pad` / `organ` — uses htdemucs_ft "other" stem
- `transcribe/basic_pitch_runner.py` — Spotify Basic Pitch polyphonic transcription; returns `list[tuple[start_s, end_s, midi_note, amplitude]]`
- `extract/pitched_slicer.py` — `slice_pitched_stem()` for polyphonic note events from Basic Pitch
- Default MIDI ranges: guitar E2–E6 (40–88), piano C2–C7 (36–96), synth C3–C6 (48–84)
- htdemucs_6s (6-stem model) auto-selected when instrument is guitar or piano; htdemucs_ft used otherwise

### Fixed
- Basic Pitch stdout/stderr noise ("isfinite: True", "shape:", "Predicting MIDI for ...") fully suppressed via `sys.stdout`/`sys.stderr` redirect + `logging.disable(CRITICAL)` in `_silence()` context manager

### Notes
- Sparse results (few zones) on loop-based production tracks are expected — the pipeline finds what's actually in the stem
- htdemucs_6s downloads a ~52 MB model on first use

---

## 2026-05-19 — CLI Polish (Phase 1.3)

### Added
- Per-stage timing printed after each pipeline stage
- End-of-run summary: elapsed time, sample count, SFZ/DS/samples paths
- Consent banner now shown only on first run (sentinel at `~/.cache/kitforge/.consent_shown`)
- TOML config loading via Python 3.11 `tomllib` — `--config kitforge.toml` now works
- `--quality` and `--config` CLI flags wired into `KitForgeConfig`

### Fixed
- Cache key now includes output directory — cached `OneShot` paths no longer break when `--out` changes between runs
- `--quality` was validated but silently ignored; now propagates to `separator_quality`
- pydantic `toml_file` warning suppressed (removed from `model_config`, loaded manually instead)
- Suppressed non-actionable third-party warnings: resampy `pkg_resources`, torch STFT resize

---

## 2026-05-19 — Bass Instrument (Phase 1.2)

### Added
- `kitforge build --instrument bass` — full pipeline from song to playable SFZ/DS bass kit
- `extract/pitched_slicer.py` — f0 → note segmentation → per-note samples → Voronoi zone fill
- `pitchshift/rubberband_wrapper.py` — Rubber Band R3 pitch shifting via pyrubberband
- `package/sfz_writer.py` — `write_pitched_sfz`: `lokey/hikey/pitch_keycenter` per zone
- `package/decentsampler_writer.py` — `write_pitched_dspreset`: same structure
- `--range` flag for pitched instruments (e.g. `C1-G4`, `E1-C5`)
- Default bass range C1–G4 (MIDI 24–67); lowered from E1 after real-song testing revealed most bass sits at C#1–E1

### Fixed
- `transcribe/crepe_mono.py` — `torchcrepe.predict` returns `(f0, periodicity)` not 4 values; fixed unpacking
- Bass OOM on full-length songs: f0 tracking now loads at 16 kHz and caps to first 90s
- `batch_size` default lowered 2048 → 512 to reduce peak memory

### Notes
- 808-heavy tracks typically yield only 1–2 unique pitches (single root note); this is correct behavior
- torchcrepe runs on CPU only (MPS support inconsistent)

---

## 2026-05-19 — Content-Addressed Caching

### Added
- `cache.py` — `StageCache` wrapping `diskcache`, keyed by `(file_sha256, model, version, params, out_dir)`
- Demucs stems cached via SHA-256 sentinel file at `stems_dir/.song_hash`; re-run skips separation entirely
- Slicing/packaging results cached in `~/.cache/kitforge/stage_cache/`; second run on same song+output is near-instant

---

## 2026-05-19 — Velocity Layers

### Added
- Drum slices sorted by pre-normalization peak energy before bucketing
- Up to 4 velocity layers per drum class, each with up to 4 round-robins
- `OneShot` dataclass gains `vel_low` / `vel_high` fields
- SFZ `lovel/hivel` per region; DecentSampler `loVel/hiVel` per sample
- One DS `<group>` per velocity layer (DS `seqMode` is per-group)
- Sample filenames: `{class}_v{vel_low}_{rr_index}.wav`
- Fixed: post-normalization peaks are uniform — sorting must use raw pre-normalization energy
- Fixed: `toms` (47) and `cymbals` (48) added to `_DRUM_MIDI` maps in both writers

---

## 2026-05-19 — Initial Release (Phase 1.1)

### Added
- `kitforge build --instrument drums` — full drums pipeline end-to-end
- `separation/demucs_runner.py` — htdemucs_ft source separation, MPS-accelerated
- `separation/larsnet_runner.py` — LarsNet 5-class drum sub-stem separation (kick/snare/hihat/toms/cymbals)
- Frequency-band fallback when LarsNet weights aren't present
- `extract/slicer.py` — onset detection (librosa), one-shot slicing, tail trim at −55 dB, peak normalize to −1 dBFS
- `package/sfz_writer.py` — SFZ emit with round-robins (`seq_position/seq_length`) and hi-hat choke (`group/off_by/off_mode`)
- `package/decentsampler_writer.py` — DecentSampler XML emit
- `kitforge/cli.py` — Typer CLI with `build` subcommand
- `kitforge/config.py` — pydantic-settings config with `KITFORGE_*` env var support
- Stem cache at `~/.cache/kitforge/stems/<songname>/`
- Full project scaffold: all stub modules in place per architecture spec

### Notes
- Stems written with soundfile PCM_24 (not `torchaudio.save`) — torchcodec doesn't support MPS encoding
- LarsNet `config_abs.yaml` generated at runtime to fix relative-path resolution when cwd ≠ larsnet dir
- `torchcrepe` used instead of `crepe` PyPI package — crepe 0.0.16 build broken on setuptools ≥ 71

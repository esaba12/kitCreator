# Changelog

All notable changes to kitCreator. Entries are grouped by feature area, not by individual commit.

---

## [Unreleased]

---

## 2026-05-21 — Banquet Query Fixes: Clean Input + Smart Window + `--query`

### Fixed
- Banquet was running on the original song mix (vocals + everything) and using the first 10 s of the rough htdemucs stem as its query — for sparse intros this locked Banquet onto percussion/claps, producing short transient-only output that didn't sound like the target instrument
- Banquet now runs on the BS-RoFormer instrumental (vocals stripped) so it can't accidentally extract vocal content
- Query window now auto-picks the highest-RMS 10 s slice of the rough stem instead of the first 10 s, skipping sparse intros

### Added
- `--query MM:SS-MM:SS` CLI flag — extracts that window from the ORIGINAL song as Banquet's query when the user knows exactly where the target instrument peaks; overrides the auto-RMS heuristic
- `_best_query_window(data, sr)` helper in `pipeline.py` — 1 s stride, picks loudest 10 s by RMS
- `build_kit(..., query_window=None)` parameter

### Notes
- `_BANQUET_VERSION` bumped 1.0 → 1.1 — busts old refined-stem caches
- Cache key now distinguishes `banquet_<instr>_auto` vs `banquet_<instr>_user` so changing the query timestamp re-runs separation without wiping the auto cache

---

## 2026-05-20 — BS-RoFormer Cascade for Pitched Instruments

### Added
- `separation/roformer_runner.py` — `is_available()`, `separate_vocals(audio_path, out_dir)`; wraps `python-audio-separator` with `model_bs_roformer_ep_317_sdr_12.9755.ckpt` (vocals SDR 12.9, instrumental SDR 17.0); singleton model, MPS / CoreML accelerated on Apple Silicon
- `pipeline.py` — for bass, guitar, piano, synth: a Stage 1a vocal-pre-removal pass runs BS-RoFormer on the raw mix, then htdemucs sees the vocal-stripped instrumental. Drums skip the cascade.
- Stems cache sentinel now encodes `roformer=<bool>/6s=<bool>` so old single-stage caches bust automatically when the cascade is enabled

### Why
- htdemucs "other" stem is a catch-all and inherits residual vocals from htdemucs's ~10.5 dB vocal isolation; on vocal-heavy tracks Basic Pitch then transcribes vocal melodies as synth notes
- BS-RoFormer at 17 dB instrumental SDR removes ~99% of vocal content before htdemucs runs, so "other" is a true non-drums/bass/vocals residual

### Notes
- `_PITCHER_VERSION` and `_BASIC_PITCH_VERSION` bumped to 1.2 — old cached `PitchedShot` lists bust
- ~2–3 min added per song on M-series MPS; runs once and is cached
- On failure (network, OOM, etc.) silently falls back to plain htdemucs on the raw mix

---

## 2026-05-20 — Roland MC-101 Export (`--mc101`)

### Added
- `package/mc101_writer.py` — `export_drums(shots, kit_name, sd_root)` and `export_pitched(shots, instrument, kit_name, sd_root)`
  - Drums: copies all velocity-layer WAVs as PCM_16 (MC-101 requirement) to `ROLAND/GROOVEBOX/SAMPLE/<songname>_drums/`; generates `SETUP.txt` with pad assignments (kick=1, snare=2, hihat=3, toms=5, cymbals=9, perc=13) and step-by-step load instructions
  - Pitched: copies the single root-pitch sample (WAV closest to median MIDI note) to `ROLAND/GROOVEBOX/SAMPLE/<songname>_<instrument>/`; generates `SETUP.txt` with root key and transpose note; MC-101 handles chromatic transposition
- `cli.py` — `--mc101 <path>` flag on `build` command; exports immediately after kit is built; reconstructs shot list from WAV filenames (no pipeline state required)

### Notes
- Drum WAVs from `slicer.py` are float32; `_copy_wav_pcm16` clips to [-1,1] and re-encodes as PCM_16 on export
- Pitched WAVs are already PCM_24 — copied directly via `shutil.copy2`
- MC-101 Tone track supports only 1 sample; root-sample export + `rootNote` instruction is the simplest workflow that works

---

## 2026-05-20 — ADSR Envelope Estimation + Loop Point Detection

### Added
- `extract/adsr.py` — `estimate_adsr(audio, sr)` → `ADSRParams`; computes attack (time to peak RMS), decay (peak to sustain level), sustain (median RMS over central 60% of clip, as SFZ 0–100% scale), release (decay end to −40 dB below peak); 5 ms RMS hop
- `extract/loop_finder.py` — `find_loop(audio, sr)` → `(loop_start, loop_end) | None`; autocorrelation in the middle-half steady-state region; rejects fast-decaying signals (<15% sustain fraction); aligns both endpoints to nearest zero crossing; `None` for drums, guitar, plucked bass
- `PitchedShot` gains six optional fields: `ampeg_attack`, `ampeg_decay`, `ampeg_sustain`, `ampeg_release`, `loop_start`, `loop_end` (all default `None`)
- `extract/pitched_slicer._fill_range` now calls both estimators for every zone after writing the WAV
- `package/sfz_writer.write_pitched_sfz` emits `ampeg_*` and `loop_mode=loop_continuous loop_start loop_end` per region when set
- `package/decentsampler_writer.write_pitched_dspreset` emits median ADSR on `<group>` and per-sample `loopStart`/`loopEnd`/`loopCrossfade` when set

### Notes
- `_PITCHER_VERSION` and `_BASIC_PITCH_VERSION` bumped to 1.1 — old cached `PitchedShot` objects without ADSR fields are busted
- Loop detection intentionally skips drum/plucked samples; autocorrelation peak < 0.3 → no loop
- DecentSampler ADSR is per-group (not per-sample); median across all zones is used

---

## 2026-05-20 — DeepFilterNet Post-Separation Denoising

### Added
- `extract/denoise.py` — DeepFilterNet3 noise suppression; `denoise(audio, sr)` and `denoise_file(src, dst)` with automatic 48 kHz resampling; lazy singleton model (~5 MB download to `~/Library/Caches/DeepFilterNet/` on first call)
- `pipeline.py` — `_denoise_stem()` helper; denoising is applied to the target stem at `--quality high` before slicing, for all instrument types (drums, bass, guitar, piano, synth)
- `_DENOISE_VERSION = "1.0"` cache key; denoised stem written as `denoised_<stem>.wav` alongside the separation cache

### Notes
- deepfilternet 0.5.6 imports `torchaudio.backend.common.AudioMetaData` and `torchaudio.info`, both removed in torchaudio 2.x — `_patch_torchaudio()` injects compatible stubs before any `df.*` import
- DeepFilterNet runs on CPU, ~real-time speed; a 3-minute stem takes ~3 minutes; gated behind `--quality high`
- On failure (network issue, etc.) `_denoise_stem` falls back to the undenoised stem silently

---

## 2026-05-20 — CLAP-Embedding Clustering

### Added
- `timbre/clap_embed.py` — LAION-CLAP 512-d audio embeddings; lazy singleton (`630k-audioset-best.pt`, ~600 MB, downloaded from HuggingFace on first use); `embed(audio, sr)` and `embed_batch(clips)` with 48 kHz resampling + zero-pad to 10 s
- `extract/cluster.py` — `pick_medoid(clips, sr)` and `pick_diverse_rr(clips, sr, n)` using farthest-point sampling over CLAP embeddings; both fall back to energy/index selection if CLAP is unavailable or raises
- `extract/slicer.py` — drum round-robin selection now uses `pick_diverse_rr` within each velocity bucket instead of evenly-spread indexing; `_assign_velocity_buckets` gains `sr` parameter
- `extract/pitched_slicer.py` — `_collect_real_samples` now collects all occurrences per MIDI note and picks the canonical via `pick_medoid` (CLAP medoid); previously picked longest occurrence only

### Notes
- CLAP model (~600 MB) downloads once to the `laion_clap` package directory on first kit build
- Both cluster functions are exception-safe: any CLAP failure silently falls back to the prior energy/spread heuristics so the pipeline never breaks

---

## 2026-05-20 — Banquet Query Separation (--quality high)

### Added
- `separation/query_separator.py` — Banquet (kwatcharasupat/query-bandit) integration for higher-quality guitar/piano/synth isolation
- `kitforge setup-banquet` CLI command — clones repo, installs deps (pytorch-lightning, hear21passt, torchmetrics), downloads 645 MB weights from Zenodo
- `--quality high` now uses Banquet separation when available: runs on original mix with htdemucs stem as 10-second query, then passes refined stem to Basic Pitch
- Graceful fallback: if audio < 28s or Banquet not set up, falls back to htdemucs stem silently

### Notes
- CPU inference ~35 min/song (CUDA ~5 min); gated behind `--quality high` only — default/fast remain unchanged
- MPS not supported: PaSST position embeddings are float64, which MPS rejects
- `is_available()` validates weights file > 500 MB to reject truncated downloads

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

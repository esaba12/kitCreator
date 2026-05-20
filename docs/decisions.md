# Engineering Decisions

Running log of non-obvious decisions, bugs caught, and why things are the way they are.
Update this whenever something would confuse a future reader of the code.

---

## Source Separation

**Use soundfile instead of torchaudio.save for stem writing**
torchaudio 2.12 delegates audio saving to torchcodec. torchcodec doesn't implement the `encode_audio_to_file` op for MPS devices. Writing via `soundfile.write(source.cpu().numpy().T, ...)` bypasses this entirely.

**LarsNet requires an absolute-path config at runtime**
LarsNet's `config.yaml` stores weight paths as relative paths (e.g. `pretrained_larsnet_models/kick/...`). These resolve relative to cwd, which is the project root when running kitforge — not the larsnet directory. Fix: `larsnet_runner._write_abs_config()` generates `config_abs.yaml` with fully-qualified paths before instantiating LarsNet.

**Stems cached by file content hash, not filename**
Cached at `~/.cache/kitforge/stems/<name>/.song_hash` (SHA-256 of input file). Re-processing the same filename with different audio content re-separates; renaming the same file does not.

---

## Drums

**Sort velocity slices by pre-normalization peak, not post**
All slices are peak-normalized to −1 dBFS before being returned from `_slice_at_onsets`. If you sort after normalization, every slice has the same "energy" and bucketing is arbitrary. The fix: `_slice_at_onsets` returns `(raw_peak, normalized_audio)` tuples; `_assign_velocity_buckets` sorts by `raw_peak`.

**Hi-hat choke uses `off_by=1` not a tag name in SFZ**
SFZ choke groups use integer IDs, not string tags. DecentSampler uses `silencedByTags` / `tags` string attributes. Both are set to the same logical group (hihat) but via different mechanisms.

**`seq_length` must be per velocity layer, not global**
If you put `seq_length` at the `<group>` level spanning all velocity layers, the SFZ player counts round-robins across layers and plays the wrong sample. Each velocity bucket gets its own region list with `seq_length = len(that_bucket)`.

---

## Bass

**torchcrepe returns `(frequencies, periodicity)`, not 4 values**
The original `crepe_mono.py` tried to unpack 4 values. torchcrepe's `predict()` with `return_periodicity=True` returns exactly 2 tensors. `times` must be computed manually: `np.arange(n_frames) * hop_length / sample_rate`.

**torchcrepe runs on CPU, not MPS**
MPS support for torchcrepe is inconsistent across torch versions. CPU is safe and fast enough for bass stems (90s @ 16kHz ≈ 25s wall time).

**Load bass stem at 16 kHz for f0 tracking**
torchcrepe resamples input to 16 kHz internally regardless of input SR. Passing a 44.1 kHz tensor means torchcrepe holds both the full 44.1 kHz buffer and the resampled 16 kHz copy simultaneously. Loading at 16 kHz upfront halves the memory footprint. The native-SR load for sample slicing is kept separate.

**Cap f0 tracking at 90 seconds**
A 4-minute 44.1 kHz bass stem → ~3.5M samples at 16 kHz → torchcrepe allocates several GB for sliding windows. OOM killed processes on 16 GB RAM machines. 90 seconds captures the entire pitch vocabulary for typical loop-based production (bass lines repeat within 8–16 bars).

**Cache key must include output directory**
`OneShot` and `PitchedShot` objects store absolute `Path` references to sample WAVs. If the cache key doesn't include the output dir, a cached result from run A (`/tmp/kit_a/samples/kick.wav`) gets returned for run B (`~/Desktop/kit_b/`) and `relative_to()` raises `ValueError`. Fix: `"out": str(sample_dir)` in the params dict.

---

## Packaging

**Emit SFZ and DecentSampler simultaneously, always**
Architectural constraint from `CLAUDE.md`. Never emit one without the other. SFZ is the open standard; DecentSampler gives a free polished runtime.

**Bass default range C1–G4, not E1–G4**
Original default was E1 (MIDI 28). Real-song testing on four tracks showed the most common bass pitches are C#1 (MIDI 25) and D1 (MIDI 26) — below E1. Changed to C1 (MIDI 24) to avoid silently missing the root note.

---

## Banquet Query Separation

**Banquet runs CPU-only — not MPS**
`PasstFiLMConditionedBandit` contains float64 buffers (PaSST position embeddings) that MPS doesn't support. CUDA works fine. On CPU with batch_size=4, inference on a 3-minute song takes ~35 minutes; on a GPU it's ~5 minutes. This is why Banquet is gated behind `--quality high`, not enabled by default.

**Banquet is a research repo, not a PyPI package**
Cloned to `~/.cache/kitforge/banquet/repo/` at setup time. The repo directory is added to `sys.path` at runtime. `CONFIG_ROOT` env var must point to `repo/config/` for omegaconf to resolve `${oc.env:CONFIG_ROOT}` references in the YAML configs.

**Don't import from train.py**
`train.py` imports `pytorch_lightning.profilers.AdvancedProfiler` which was removed in pl 2.0. Our `_infer()` function imports only from `core.*`, bypassing `train.py` entirely.

**Audio must be ≥28 seconds for chunked_inference**
Chunk size=6s, hop=0.5s → overlap=5.5s. The F.pad call requires `2*overlap < n_samples`. Minimum safe input = 28s at 44.1kHz. `_infer` checks duration upfront via `librosa.get_duration()` and raises `ValueError` for short files; `_banquet_refine` catches this and falls back to the htdemucs stem.

**Weights are 645 MB from Zenodo — validate size in is_available()**
A truncated download (partial file) would fail silently at `load_from_checkpoint`. `is_available()` checks `st_size > 500 MB` to reject incomplete files.

---

## Infrastructure

**`torchcrepe` instead of `crepe` from PyPI**
`crepe==0.0.16` (the current PyPI release) uses `pkg_resources` in its build which is no longer available under setuptools ≥ 71. `torchcrepe` is a maintained PyTorch-native fork with a compatible API.

**pydantic-settings `toml_file` in `model_config` causes a warning**
`toml_file` is recognized as a config key but only takes effect if a `TomlConfigSettingsSource` is added to `settings_customise_sources`. Without that, pydantic-settings emits a warning on every import. Fix: removed `toml_file` from `model_config`; TOML loading is now done manually via `tomllib` in `config.load_config()`.

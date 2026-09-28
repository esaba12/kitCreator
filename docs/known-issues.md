# Known Issues & Gotchas

- **LarsNet weights are CC-BY-NC 4.0**: fine for personal use, not for distribution
- **Bass on 808-heavy tracks**: 808 sub-bass is often one root note; expect 1–2 unique pitches. Use `--range C1-G4` or lower to match the tuning
- **torchcrepe capped at 90s**: f0 tracking runs on the first 90s of the bass stem to avoid OOM. Pitches that only appear late in the song are missed
- **torchaudio + torchcodec**: demucs stem writing uses soundfile directly to avoid MPS incompatibility with torchcodec's audio encoder
- **LarsNet tqdm output**: LarsNet prints its own progress bars to stdout; these come from inside the library and can't be suppressed without patching
- **CLAP model download (~600 MB)**: downloads from HuggingFace on the first kit build that needs CLAP clustering; subsequent runs use the cached weights
- **CLAP load peaks at ~2.7 GB RSS**: measured in isolation, loading the model alone is fine on a machine with several GB free. On a real (multi-minute) song's drum build, `pick_diverse_rr` has enough onsets per velocity bucket to actually call CLAP (unlike short test clips, which fall under the `len(audios) <= n` fast path and skip it entirely) — combined with whatever else is running system-wide, this has triggered macOS's memory-pressure killer (SIGKILL/exit -9) even when a `vm_stat` check moments earlier showed multiple GB free. A free-page snapshot isn't a reliable predictor here; close other memory-heavy apps before a real-song drum build on a RAM-constrained machine
- **deepfilternet 0.5.6 + torchaudio 2.x**: the package uses removed APIs; `denoise.py` patches them at import time. If deepfilternet releases a fix, the patch is safe to remove
- **Banquet CPU runtime**: ~15–35 min/song on CPU; plan for an overnight run or use a CUDA GPU. Not needed for default quality
- **BS-RoFormer adds ~3 min** to pitched-instrument runs at any quality. Stems are cached by content hash, so it only runs once per song
- **Banquet timbral limits**: Banquet maps the user's instrument name to one of a fixed set of stems (`synth_lead`, `synth_pad`, `electric_piano`, etc.). Hybrid timbres (e.g. a synth + Rhodes layer) blend toward the closest prototype; absolute exact-timbre reconstruction will need Phase 2's neural fill
- **MC-101 SD card auto-unmount**: long Banquet runs sometimes outlive the SD card's USB connection. Replug after the kit finishes and re-run `kitforge build … --mc101 …`; the pipeline is fully cached, so the export takes <1 s

---

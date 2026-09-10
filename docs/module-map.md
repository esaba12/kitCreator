# Module Map

Every module in the `kitforge` package, what it does, and whether it's implemented.
The end-to-end data flow it implements is in [pipeline-spec.md](pipeline-spec.md).

## Pipeline data flow

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

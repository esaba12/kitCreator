# Acceptance checks

Headless "does this kit actually play" verification using the [sfizz](https://sfz.tools/sfizz/)
SFZ engine's render CLI. Not run by default under `pytest` (no `test_*.py` files
here) -- these are slow, need an external compiled binary, and build/verify a
real kit rather than testing pure logic.

## One-time setup: build `sfizz_render`

No Homebrew formula exists for it; build from source:

```
brew install cmake
git clone --recursive --depth 1 --shallow-submodules \
    https://github.com/sfztools/sfizz.git ~/.cache/kitforge-dev/sfizz/src
cmake -S ~/.cache/kitforge-dev/sfizz/src -B ~/.cache/kitforge-dev/sfizz/build \
    -DSFIZZ_TESTS=OFF -DSFIZZ_BENCHMARKS=OFF -DSFIZZ_DEMOS=OFF -DSFIZZ_DEVTOOLS=OFF \
    -DENABLE_LTO=OFF \
    -DCMAKE_CXX_FLAGS="-Wno-missing-template-arg-list-after-template-kw"
cmake --build ~/.cache/kitforge-dev/sfizz/build --target sfizz_render -j2
```

The `CMAKE_CXX_FLAGS` works around a strict Apple Clang 17 diagnostic
(`-Wmissing-template-arg-list-after-template-kw`) tripping on the vendored
`atomic_queue` submodule -- not a kitCreator issue. `-j2` keeps the build's
memory footprint low; bump it if you have RAM to spare.

The build lives entirely under `~/.cache/kitforge-dev/`, outside this repo --
nothing here ever needs committing or gitignoring for it.

Alternatively, set `KITFORGE_SFIZZ_RENDER` to point at any existing
`sfizz_render` binary.

## Running

```
python tests/acceptance/run_playback_check.py --kit-dir site/demo/assets/drums
python tests/acceptance/run_playback_check.py --kit-dir site/demo/assets/bass
python tests/acceptance/run_playback_check.py --song assets/test_audio/test_mix.wav \
    --instrument drums --out /tmp/kit_check
```

Exit code 0 = pass, 1 = fail. Prints a per-note report (which MIDI notes
actually produced audio, at what RMS, vs. the pre-render noise floor).

## What this does and doesn't verify

- Generates a MIDI file that hits every note actually present in the kit's own
  `kit.sfz` (parsed, not hardcoded against `sfz_writer.py`'s current note
  assignments), renders it through the real kit via `sfizz_render`, and checks
  real audio energy appears at each expected note-on.
- **Only verifies the `.sfz` half of the kit.** DecentSampler's `.dspreset`
  format has no known headless renderer, so it's not covered here -- that half
  still needs a real DecentSampler install for manual verification.

## Memory note

Building `sfizz_render` is a one-time C++ compile (~30s at `-j2`) and is
independent of kitforge's ML pipeline. Running `run_playback_check.py --song`
still invokes a full `kitforge build`, though, which loads the same
Demucs/LarsNet/etc. models as any other build -- run one instrument/song at a
time, not a scripted loop, and check memory headroom (`vm_stat`) beforehand if
you've just run a heavy build.

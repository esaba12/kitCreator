"""Locate the sfizz_render binary (built from source, never committed to this repo)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_CACHE_BUILD_DIR = Path.home() / ".cache" / "kitforge-dev" / "sfizz" / "build"

_BUILD_INSTRUCTIONS = """\
sfizz_render not found. Build it once:

  brew install cmake
  git clone --recursive --depth 1 --shallow-submodules \\
      https://github.com/sfztools/sfizz.git ~/.cache/kitforge-dev/sfizz/src
  cmake -S ~/.cache/kitforge-dev/sfizz/src -B ~/.cache/kitforge-dev/sfizz/build \\
      -DSFIZZ_TESTS=OFF -DSFIZZ_BENCHMARKS=OFF -DSFIZZ_DEMOS=OFF -DSFIZZ_DEVTOOLS=OFF \\
      -DENABLE_LTO=OFF \\
      -DCMAKE_CXX_FLAGS="-Wno-missing-template-arg-list-after-template-kw"
  cmake --build ~/.cache/kitforge-dev/sfizz/build --target sfizz_render -j2

(The CMAKE_CXX_FLAGS above works around a strict new Apple Clang 17 diagnostic
tripping on the vendored atomic_queue submodule; -j2 keeps the build's memory
footprint low on RAM-constrained machines.)

Or set KITFORGE_SFIZZ_RENDER to an existing sfizz_render binary path.
"""


def find_sfizz_render() -> Path:
    """Return the sfizz_render binary path, or exit with build instructions."""
    override = os.environ.get("KITFORGE_SFIZZ_RENDER")
    if override:
        p = Path(override)
        if p.is_file():
            return p
        print(f"KITFORGE_SFIZZ_RENDER={override} does not exist", file=sys.stderr)
        sys.exit(1)

    if _CACHE_BUILD_DIR.exists():
        matches = list(_CACHE_BUILD_DIR.rglob("sfizz_render"))
        matches = [m for m in matches if m.is_file() and os.access(m, os.X_OK)]
        if matches:
            return matches[0]

    print(_BUILD_INSTRUCTIONS, file=sys.stderr)
    sys.exit(1)

"""Minimal SFZ opcode parser: enough to read back what kitforge's own writers emit.

Not a general SFZ parser (no #define, no multi-file includes, no quoted values
with spaces) -- just <global>/<group>/<region> header + key=value opcode blocks,
which is exactly what kitforge.package.sfz_writer produces.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_HEADER_RE = re.compile(r"<(\w+)>")
_OPCODE_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(\S+)")


@dataclass
class Region:
    opcodes: dict[str, str] = field(default_factory=dict)

    def int(self, key: str, default: int | None = None) -> int | None:
        v = self.opcodes.get(key)
        return int(v) if v is not None else default

    def float(self, key: str, default: float | None = None) -> float | None:
        v = self.opcodes.get(key)
        return float(v) if v is not None else default


def parse_regions(sfz_path: Path) -> list[Region]:
    """Return one merged (global -> group -> region) opcode dict per <region>."""
    text = sfz_path.read_text()
    text = re.sub(r"//.*", "", text)  # strip line comments

    headers = list(_HEADER_RE.finditer(text))
    regions: list[Region] = []
    global_ops: dict[str, str] = {}
    group_ops: dict[str, str] = {}

    for i, m in enumerate(headers):
        tag = m.group(1).lower()
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[start:end]
        ops = dict(_OPCODE_RE.findall(body))

        if tag == "global":
            global_ops.update(ops)
        elif tag == "group":
            group_ops = ops  # a new group replaces, doesn't merge with, the previous one
        elif tag == "region":
            merged = {**global_ops, **group_ops, **ops}
            regions.append(Region(opcodes=merged))

    return regions

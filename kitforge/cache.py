from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import diskcache


def _content_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _params_hash(params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:16]


def cache_key(input_path: Path, model_name: str, model_version: str, params: dict[str, Any]) -> str:
    return f"{_content_hash(input_path)}:{model_name}:{model_version}:{_params_hash(params)}"


class StageCache:
    def __init__(self, cache_dir: Path) -> None:
        self._cache = diskcache.Cache(str(cache_dir))

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        self._cache.set(key, value)

    def has(self, key: str) -> bool:
        return key in self._cache

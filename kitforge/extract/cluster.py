"""Timbral diversity selection via CLAP embeddings for round-robin / canonical picking."""
from __future__ import annotations

import numpy as np


def pick_medoid(clips: list[tuple[float, np.ndarray]], sr: int) -> np.ndarray:
    """
    Return the clip whose CLAP embedding is closest to the cluster centroid.

    clips: list of (any_float, mono_audio) — only the audio is embedded.
    Falls back to the first clip if CLAP unavailable or N == 1.
    """
    if len(clips) <= 1:
        return clips[0][1] if clips else np.array([], dtype=np.float32)

    try:
        from kitforge.timbre.clap_embed import embed_batch
        audios = [a for _, a in clips]
        embs = embed_batch([(a, sr) for a in audios])          # (N, 512)
        norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8
        embs = embs / norms
        centroid = embs.mean(axis=0)
        centroid /= np.linalg.norm(centroid) + 1e-8
        return audios[int(np.argmax(embs @ centroid))]
    except Exception:
        return clips[0][1]


def pick_diverse_rr(
    clips: list[tuple[float, np.ndarray]],
    sr: int,
    n: int = 4,
) -> list[np.ndarray]:
    """
    Pick up to n timbrally-diverse clips via farthest-point sampling on CLAP embeddings.

    clips: list of (any_float, mono_audio) — only the audio is embedded.
    Falls back to evenly-spread selection if CLAP unavailable or N <= n.
    """
    audios = [a for _, a in clips]
    if len(audios) <= n:
        return audios

    try:
        from kitforge.timbre.clap_embed import embed_batch
        embs = embed_batch([(a, sr) for a in audios])          # (N, 512)
        norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8
        embs = embs / norms                                     # L2-normalise → cosine dist

        # Greedy farthest-point sampling: maximally covers the embedding space
        selected = [0]
        while len(selected) < n:
            min_sims = np.full(len(embs), np.inf)
            for idx in selected:
                cosine_dist = 1.0 - (embs @ embs[idx])
                min_sims = np.minimum(min_sims, cosine_dist)
            for idx in selected:
                min_sims[idx] = -np.inf
            selected.append(int(np.argmax(min_sims)))

        return [audios[i] for i in selected]

    except Exception:
        step = len(audios) / n
        return [audios[int(i * step)] for i in range(n)]

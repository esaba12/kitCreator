import numpy as np
import pytest

import kitforge.timbre.clap_embed as clap_embed
from kitforge.extract.cluster import pick_diverse_rr, pick_medoid

SR = 44100


def _clip(i: int) -> tuple[float, np.ndarray]:
    return (float(i), np.full(4, i, dtype=np.float32))


def test_pick_medoid_single_clip_returns_it_without_embedding(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("should not embed a single clip")

    monkeypatch.setattr(clap_embed, "embed_batch", _boom)
    clip = _clip(0)
    assert np.array_equal(pick_medoid([clip], SR), clip[1])


def test_pick_medoid_empty_returns_empty_array():
    assert pick_medoid([], SR).size == 0


def test_pick_medoid_returns_clip_closest_to_centroid(monkeypatch):
    # mean of [1,0], [-1,0], [0,1] normalizes to [0,1] -> exact match with clip C
    embeddings = np.array([[1.0, 0.0], [-1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    monkeypatch.setattr(clap_embed, "embed_batch", lambda clips: embeddings)

    clips = [_clip(0), _clip(1), _clip(2)]
    result = pick_medoid(clips, SR)
    assert np.array_equal(result, clips[2][1])


def test_pick_medoid_falls_back_on_clap_failure(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("no model weights")

    monkeypatch.setattr(clap_embed, "embed_batch", _boom)
    clips = [_clip(0), _clip(1)]
    assert np.array_equal(pick_medoid(clips, SR), clips[0][1])


def test_pick_diverse_rr_returns_all_when_fewer_than_n():
    clips = [_clip(0), _clip(1)]
    result = pick_diverse_rr(clips, SR, n=4)
    assert len(result) == 2


def test_pick_diverse_rr_farthest_point_sampling(monkeypatch):
    # Cardinal directions: antipode of clip 0 is clip 2.
    embeddings = np.array(
        [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0], [0.0, -1.0]], dtype=np.float32
    )
    monkeypatch.setattr(clap_embed, "embed_batch", lambda clips: embeddings)

    clips = [_clip(i) for i in range(4)]
    result = pick_diverse_rr(clips, SR, n=2)
    assert len(result) == 2
    assert np.array_equal(result[0], clips[0][1])
    assert np.array_equal(result[1], clips[2][1])


def test_pick_diverse_rr_falls_back_to_evenly_spread_on_failure(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("no model weights")

    monkeypatch.setattr(clap_embed, "embed_batch", _boom)
    clips = [_clip(i) for i in range(8)]
    result = pick_diverse_rr(clips, SR, n=4)
    assert len(result) == 4

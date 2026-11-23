import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TINY
from params import init_params, make_inputs
from float_model import run_sequence
from int_model import QModel


def cos(a, b):
    a, b = a.ravel(), b.ravel()
    return float(a @ b / np.linalg.norm(a) / np.linalg.norm(b))


def test_int_matches_float_over_sequence():
    P = init_params(TINY)
    frames, imus = make_inputs(TINY, 4)
    fo, rec = run_sequence(TINY, P, frames, imus)
    qo = QModel(TINY, P, rec.maxabs).run_sequence(frames, imus)
    for (fc, fs), (qc, qs) in zip(fo, qo):
        assert fc.shape == (TINY.grid_h, TINY.grid_w, TINY.n_corners, 3)
        assert qs.shape == (TINY.state_dim,)
        assert cos(fc, qc) > 0.99
        assert cos(fs, qs) > 0.98


def test_full_size_layer0_matches_float():
    """Full 640x480 config (1201 tokens, 301 keys): first frame, all layers."""
    from config import FULL
    P = init_params(FULL)
    frames, imus = make_inputs(FULL, 1)
    fo, rec = run_sequence(FULL, P, frames, imus)
    qo = QModel(FULL, P, rec.maxabs).run_sequence(frames, imus)
    assert cos(fo[0][0], qo[0][0]) > 0.98
    assert cos(fo[0][1], qo[0][1]) > 0.98


def test_temporal_memory_changes_output():
    P = init_params(TINY)
    frames, imus = make_inputs(TINY, 3)
    fo, _ = run_sequence(TINY, P, frames, imus)
    fo_single, _ = run_sequence(TINY, P, frames[-1:], imus[-1:])
    assert not np.allclose(fo[-1][0], fo_single[0][0])   # memory of previous frames is used


def test_integer_model_is_deterministic():
    P = init_params(TINY)
    frames, imus = make_inputs(TINY, 2)
    _, rec = run_sequence(TINY, P, frames, imus)
    a = QModel(TINY, P, rec.maxabs).run_sequence(frames, imus)
    b = QModel(TINY, P, rec.maxabs).run_sequence(frames, imus)
    assert all(np.array_equal(x[0], y[0]) for x, y in zip(a, b))

import math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from int_ops import (i_exp, i_softmax_weights, i_attn_normalise, i_gelu, i_layernorm, requant, dyadic,
                     quantize, scale_for, imatmul, S_SM, LN_FRAC, AV_FRAC)
from float_model import gelu, softmax

rng = np.random.default_rng(0)


def test_dyadic_precision():
    for m in [1e-6, 3.7e-3, 0.5, 1.0, 7.3, 1234.5]:
        M, sh = dyadic(m)
        assert 2 ** 14 <= M < 2 ** 15
        assert abs(M * 2.0 ** -sh / m - 1) < 2 ** -14


def test_i_exp():
    x = -np.linspace(0, 10, 2001)
    q = np.round(x / S_SM).astype(np.int64)
    e = i_exp(q) * (0.3585 * S_SM ** 2)
    # 2nd-order polynomial of I-BERT: about 0.6% worst-case relative error
    assert np.abs(e - np.exp(x)).max() < 5e-3
    assert (np.abs(e - np.exp(x)) / np.exp(x))[x > -3].max() < 0.01


def test_i_softmax_weights():
    for n in [16, 301, 1201]:
        x = rng.normal(0, 3, (64, n))
        s = 1e-3
        w, rowsum = i_softmax_weights(np.round(x / s).astype(np.int64), s)
        assert w.max() == 127 and w.min() >= 0
        p, ref = w / rowsum, softmax(x)
        # Per-entry error grows with the number of keys (many tiny weights round to 1/127),
        # but the distribution's direction, which is what the weighted sum of V depends on, holds.
        row_cos = (p * ref).sum(1) / np.linalg.norm(p, axis=1) / np.linalg.norm(ref, axis=1)
        assert row_cos.min() > 0.999


def test_attention_with_many_keys():
    """Regression: normalised int8 probabilities fail with ~300 keys; deferred
    normalisation must stay accurate."""
    for n in [301, 900]:
        q = rng.normal(0, 1, (200, 64)); k = rng.normal(0, 1, (n, 64)); v = rng.normal(0, 1, (n, 64))
        sq, sk, sv = (scale_for(np.abs(a).max()) for a in (q, k, v))
        qq, kq, vq = quantize(q, sq), quantize(k, sk), quantize(v, sv)
        ref = softmax((qq * sq) @ (kq * sk).T / 8) @ (vq * sv)
        w, rowsum = i_softmax_weights(imatmul(qq, kq.T), sq * sk / 8)
        out = i_attn_normalise(imatmul(w, vq), rowsum) * 2.0 ** -AV_FRAC * sv
        c = (out.ravel() @ ref.ravel()) / np.linalg.norm(out) / np.linalg.norm(ref)
        assert c > 0.99


def test_i_gelu():
    x = np.linspace(-10, 10, 4001)
    s = 1e-3
    q, so = i_gelu(np.round(x / s).astype(np.int64), s)
    assert np.abs(q * so - gelu(x)).max() < 0.02


def test_i_layernorm():
    d = 192
    x = rng.normal(0.3, 1.5, (100, d))
    sx = scale_for(np.abs(x).max())
    xq = quantize(x, sx)
    g, b = 1 + rng.normal(0, 0.1, d), rng.normal(0, 0.1, d)
    sg = scale_for(np.abs(g).max())
    out = i_layernorm(xq, quantize(g, sg), quantize(b, sg * 2 ** -LN_FRAC, bits=32)) * sg * 2 ** -LN_FRAC
    xd = xq * sx
    ref = (xd - xd.mean(-1, keepdims=True)) / xd.std(-1, keepdims=True) * g + b
    assert np.abs(out - ref).max() < 0.05

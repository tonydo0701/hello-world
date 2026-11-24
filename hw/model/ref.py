"""Bit-exact golden models for each hardware block (integer arithmetic only)."""
import numpy as np

# Number formats used by the hardware
X_BITS = 8    # activations: signed int8
W_BITS = 4    # weights: signed int4 in [-8, 7]
ACC_BITS = 32 # accumulators: signed int32


def random_weights(n, k, rng):
    return rng.integers(-(1 << (W_BITS - 1)), 1 << (W_BITS - 1), size=(n, k), dtype=np.int64)


def random_acts(k, rng, count=1):
    return rng.integers(-(1 << (X_BITS - 1)), 1 << (X_BITS - 1), size=(count, k), dtype=np.int64)


def matvec(w, x):
    """y[i] = sum_j w[i, j] * x[j], exact in int32 (no overflow for our sizes)."""
    y = w @ x
    assert np.all(np.abs(y) < (1 << (ACC_BITS - 1)))
    return y

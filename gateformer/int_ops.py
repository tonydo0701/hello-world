"""Integer-only kernels for GateFormer-T. Every function here uses only
integer add, multiply, shift, compare, one integer square root per row
(LayerNorm) and one integer reciprocal per row (Softmax, LayerNorm). This is
the bit-accurate golden model that RTL (Gemmini + vector/CGRA units) must match.

Non-linear approximations follow I-BERT (Kim et al., ICML 2021): second-order
polynomials for exp and erf, with fixed scales chosen here so that the
hardware needs only shifts and 32-bit intermediates.
"""
import math
import numpy as np

# ----------------------------------------------------------------- basics

def scale_for(maxabs, bits=8):
    return max(float(maxabs), 1e-6) / (2 ** (bits - 1) - 1)


def quantize(x, s, bits=8):
    qmax = 2 ** (bits - 1) - 1
    return np.clip(np.round(np.asarray(x) / s), -qmax - 1, qmax).astype(np.int64)


def dyadic(m, mbits=15):
    """Real multiplier m > 0  ->  (M, sh) with m ~= M * 2**-sh and M a 15-bit integer."""
    assert m > 0, m
    sh = mbits - 1 - math.floor(math.log2(m))
    M = int(round(m * 2 ** sh))
    if M >= 2 ** mbits:
        M //= 2
        sh -= 1
    return M, sh


def rshift_round(x, sh):
    return (x + (1 << (sh - 1))) >> sh if sh > 0 else x << (-sh)


def requant(acc, m, bits=8):
    """acc (int) at scale s_in  ->  int<bits> at scale s_out, where m = s_in / s_out."""
    M, sh = dyadic(m)
    out = rshift_round(np.asarray(acc, dtype=np.int64) * M, sh)
    qmax = 2 ** (bits - 1) - 1
    return np.clip(out, -qmax - 1, qmax)


def imatmul(a, b):
    """Exact integer matmul (int8 x int8 -> int32 accumulate). Done in float64,
    which is exact while |result| < 2**53 (checked)."""
    bound = float(np.abs(a).max()) * float(np.abs(b).max()) * a.shape[-1]
    assert bound < 2 ** 53
    return np.rint(a.astype(np.float64) @ b.astype(np.float64)).astype(np.int64)


def int_add(qa, sa, qb, sb, s_out, bits=8):
    """Residual add of two int tensors with different scales (16-bit fixed-point multipliers)."""
    ma = int(round(sa / s_out * 2 ** 16))
    mb = int(round(sb / s_out * 2 ** 16))
    out = rshift_round(qa.astype(np.int64) * ma + qb.astype(np.int64) * mb, 16)
    qmax = 2 ** (bits - 1) - 1
    return np.clip(out, -qmax - 1, qmax)


def pool2x2(grid):
    h, w, d = grid.shape
    g = grid[: h // 2 * 2, : w // 2 * 2].reshape(h // 2, 2, w // 2, 2, d).astype(np.int64)
    return ((g.sum(axis=(1, 3)) + 2) >> 2).reshape(-1, d)


def isqrt(n):
    flat = np.asarray(n, dtype=np.int64).reshape(-1)
    return np.array([math.isqrt(int(v)) for v in flat], dtype=np.int64).reshape(np.shape(n))

# ----------------------------------------------------------------- softmax
SM_FRAC = 8
S_SM = math.log(2) / 2 ** SM_FRAC      # fixed score scale: ln2 / 256  -> exp needs shifts only


def i_exp(q):
    """q <= 0, int at scale S_SM. Returns exp(q*S_SM) as int at scale A_EXP*S_SM**2."""
    z = np.minimum((-q) >> SM_FRAC, 31)          # how many factors of 1/2
    p = q + (z << SM_FRAC)                        # remainder in (-ln2, 0]
    qb = math.floor(1.353 / S_SM)
    qc = math.floor(0.344 / (0.3585 * S_SM ** 2))
    return ((p + qb) ** 2 + qc) >> z              # < 2**19


def i_softmax_weights(acc, s_acc):
    """Softmax with deferred normalisation (as in FlashAttention).
    acc: int32 attention scores at scale s_acc (rows = queries).
    Returns (w, rowsum): w = int8 in [0, 127], the exponentials relative to the
    row maximum (the max is always 127); rowsum = sum of w per row.
    softmax ~= w / rowsum. The caller multiplies w by V on the int8 array and
    divides the (much smaller) d_head-wide result by rowsum.

    Normalising first and storing probabilities in int8 fails when there are many
    keys: with ~300 keys most probabilities are below 1/128 and round to zero."""
    q = requant(acc, s_acc / S_SM, bits=16)
    q = q - q.max(axis=-1, keepdims=True)
    e = i_exp(q)
    emax = e.max(axis=-1, keepdims=True)          # = exp(0), same for every row
    w = (e * 127 + (emax >> 1)) // emax           # constant divisor -> a multiply in hardware
    return w, w.sum(axis=-1, keepdims=True)


AV_FRAC = 24


def i_attn_normalise(av_acc, rowsum):
    """av_acc = w @ v (int32). Returns int at scale s_v * 2**-AV_FRAC."""
    r = (1 << AV_FRAC) // rowsum                  # one reciprocal per query row
    return av_acc * r


# ----------------------------------------------------------------- GELU
S_G = 2.0 ** -11                       # GELU input as int16, range +-16


def i_gelu(acc, s_acc):
    """acc: int (FC1 accumulator) at scale s_acc. Returns (int, scale) of GELU(x)."""
    q = requant(acc, s_acc / S_G, bits=16)
    se = S_G / math.sqrt(2)
    a, b = -0.2888, -1.769
    sgn = np.sign(q)
    qa = np.minimum(np.abs(q), math.floor(-b / se))
    qb = math.floor(b / se)
    qc = math.floor(1 / (a * se * se))
    q_erf = -(sgn * ((qa + qb) ** 2 + qc))       # sign flipped so its scale is positive
    s_erf = -a * se * se
    q_one = math.floor(1 / s_erf)
    return q * (q_erf + q_one), S_G * s_erf / 2

# ----------------------------------------------------------------- LayerNorm
LN_FRAC = 7


def i_layernorm(q, g_q, b_q):
    """q: int8 (N, d). g_q: int8 gamma (scale s_g). b_q: int32 beta at scale s_g * 2**-7.
    Returns int32 at scale s_g * 2**-7."""
    d = q.shape[-1]
    c = d * q - q.sum(axis=-1, keepdims=True)                 # d * (x - mean) / s
    den = np.maximum(isqrt((c * c).sum(axis=-1, keepdims=True) // d), 1)   # d * std / s
    r = (1 << 30) // den
    y = (c * r) >> (30 - LN_FRAC)                             # normalised x, scale 2**-7
    return y * g_q + b_q

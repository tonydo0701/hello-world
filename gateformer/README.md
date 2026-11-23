# GateFormer-T: an encoder-only transformer for high-speed drone perception

A small, **integer-only** encoder transformer designed together with the edge AI SoC.
It runs drone gate perception on the M1 sampling chip (one 32×32 INT8 Gemmini array
plus the CGRA/vector units) **with all weights in on-chip SRAM**.

This folder contains:

| File | What it is |
|---|---|
| `config.py` | Model hyperparameters (`FULL` = 640×480, `TINY` for fast tests) |
| `params.py` | Deterministic random weights and synthetic input frames (placeholders until training) |
| `float_model.py` | Float reference forward pass; also records calibration ranges |
| `int_ops.py` | **Integer-only kernels**: requantisation, Softmax, GELU, LayerNorm, pooling |
| `int_model.py` | **Bit-accurate integer golden model** of the whole network (what the hardware must compute) |
| `cost.py` | Parameters, operations, memory and Gemmini 32×32 cycle estimate |
| `export_vectors.py` | Writes golden test vectors (`.hex` + `.npz` + manifest) for RTL testbenches |
| `tests/` | 10 tests: kernel accuracy, integer vs float model, temporal memory, determinism |

## 1. Task and interface

| | |
|---|---|
| **Input** | One grayscale frame, 640×480, uint8, at up to 120 Hz; IMU deltas since the last frame (gyro 3 + accel 3) |
| **Output 1: gate corners** | 40×30 grid (stride 16). Per cell and per corner (4): a detection logit and a sub-cell (dx, dy) offset → sub-pixel corner positions for PnP/EKF |
| **Output 2: state** | Gate relative pose (6), ego velocity (3), confidence (1), read from the IMU token |
| **Memory** | Pooled tokens of the last 3 frames, used by the last 2 layers (temporal cross-attention) |

## 2. Architecture

```text
 640x480 u8 ─► Conv stem (stride 16) ─► 40x30x192 + position emb ─┐
 IMU (6)   ─► Linear ─────────────────► 1 token ─────────────────┴─► 1201 tokens x 192
                                                                       │
   ┌───────────────────────── 6 encoder layers (pre-LayerNorm) ─────────┴───────┐
   │ LN ─► Q (1201 tokens)                                                       │
   │    └► 2x2 avg-pool ─► K,V (300 grid + 1 IMU = 301 keys)   spatial-reduction │
   │       multi-head attention, 3 heads x 64  ─► + residual                    │
   │ [layers 5,6] LN ─► cross-attention to 3 previous frames (900 keys) ─► +res │
   │ LN ─► FC 192→768 ─► GELU ─► FC 768→192 ─► + residual                      │
   └─────────────────────────────────────────────────────────────────────────────┘
                     │                                      │
        LN ─► corner head (per grid token)        LN ─► state head (IMU token)
```

| Part | Choice | Why |
|---|---|---|
| Stem | 3× conv 3×3 stride 2 (24, 48, 96 ch, ReLU) + conv 2×2 stride 2 → 192 | Cheap local features before tokenisation; better than a raw 16×16 patch for blurred, low-contrast images |
| Width | d = 192, 3 heads × 64, MLP 768 | Same as DeiT-Tiny, so layers can be initialised from pretrained DeiT-Tiny; all multiples of 32 for the array |
| Depth | 6 layers | ~2× fewer than DeiT-Tiny; keeps the model at 3.4 M parameters |
| Attention | **Global** over the whole frame, keys/values from 2×2-pooled tokens | Global context is the point of using a transformer here (gate parts far apart, motion blur); pooling keys 4× cuts attention cost 4× |
| Temporal | Cross-attention to 3 previous frames in the last 2 layers | Tracks gates across frames; K/V of a frame are computed once when it enters memory |
| IMU token | Extra token | Lets the model compensate for ego-motion and blur direction |
| Norm / activation | Pre-LayerNorm, GELU | Matches DeiT-Tiny for initialisation; both have accurate integer approximations |

## 3. Integer-only arithmetic (what the hardware implements)

All activations are INT8 with static per-tensor scales from calibration; weights INT8 per tensor;
biases INT32. Every rescale is a **dyadic multiply**: integer × 15-bit constant, then a rounding right-shift.
The only floating point is on the host: converting the IMU input and reading the two outputs.

| Operation | Integer method | Hardware unit |
|---|---|---|
| Linear / conv / QKᵀ / AV | INT8 × INT8 → INT32 accumulate | Gemmini 32×32 (conv via im2col) |
| Requantisation | `(acc × M + 2^(sh-1)) >> sh` | Gemmini accumulator scaling or vector unit |
| **Softmax** | Scores rescaled to a fixed scale ln2/256, so exp(x) = polynomial(low 8 bits) >> (high bits), using I-BERT's second-order polynomial. **Deferred normalisation:** INT8 weights relative to the row max, then (weights × V) on the array, then divide the 64-wide result by the row sum (one reciprocal per row) | Vector/CGRA: shifts, 1 square, 1 reciprocal per row |
| **GELU** | I-BERT integer erf polynomial on an INT16 input (scale 2⁻¹¹, range ±16) | Vector/CGRA: 2 multiplies per element |
| **LayerNorm** | Integer mean and variance, one integer square root and one reciprocal per row | Vector/CGRA |
| Residual add | Two 16-bit fixed-point multiplies + add + shift | Vector/CGRA |
| K/V pooling | `(a + b + c + d + 2) >> 2` | Vector/CGRA |

Every intermediate fits in 32 bits, except the products before a shift, which need at most 48 bits.

### Design finding: do not normalise Softmax before quantising

The first version stored normalised probabilities as INT8 (scale 1/128). That worked on the small test
config (13 keys) but failed at full size: with 301 keys most probabilities are ~1/300, below one INT8
step, so they rounded to zero. The attention output dropped to **cosine 0.83** against float.
Comparing options on the real layer-0 attention:

| Option | Matmuls for AV | Cosine vs float |
|---|---|---|
| Normalised probabilities, INT8 | 1 | 0.834 |
| **Deferred normalisation, INT8 weights (chosen)** | **1** | **0.997** |
| Normalised probabilities, 15-bit split into two INT8 halves | 2 | 1.000 |
| Deferred normalisation, 15-bit split | 2 | 1.000 |

Deferred normalisation (the FlashAttention trick) keeps one INT8 matmul and also needs fewer divides
(one per row, applied to 64 outputs instead of 301 probabilities). If trained-model accuracy needs it,
the 15-bit split is the fallback at the cost of doubling the AV matmuls (+16% total compute).
`tests/test_int_ops.py::test_attention_with_many_keys` guards against this regression.

## 4. Results

With random placeholder weights (deliberately strong attention so the test is meaningful), the
integer model against the float model at full size, 4-frame sequence:

| Frame | Corner output cosine | State output cosine |
|---|---|---|
| 0 (no memory) | 0.996 | 0.9995 |
| 1 | 0.996 | 0.994 |
| 2 | 0.992 | 0.992 |
| 3 | 0.995 | 0.998 |

Cost (`python3 cost.py`):

| Metric | Value |
|---|---|
| Parameters | **3.37 M → 3.2 MiB INT8**: fits in M1's 2–4 MB on-chip SRAM |
| Compute | **5.18 GMAC = 10.4 GOP per frame** (FC1+FC2 41%, attention 32%, projections 17%, stem 10%) |
| Non-linear work | 13 M exp, 5.5 M GELU, ~18 k LayerNorm rows per frame |
| Temporal memory | ~1 MiB (pooled tokens + their K/V for 2 layers × 3 frames); ~0.66 MiB if only K/V are kept |
| Largest activation | 0.9 MiB (FC1 output) |
| Gemmini 32×32 utilisation from tiling | 91% overall (the first 3×3 conv, 1 input channel, only 21%: run it on the CGRA) |
| Frame time, tiling-limited, 1 GHz | 5.6 ms |
| **With a further 50% loss (DMA, non-linear ops)** | **1 Gemmini: ~11 ms → ~90 fps. 2 Gemmini: ~5.6 ms → ~180 fps** |

The frame rates are estimates from a tiling model, not measurements. They assume weights stay on-chip
and the exp/GELU/LayerNorm work overlaps with the array (13 M exp per frame needs ≥ ~16 exp lanes at
1 GHz to stay under 1 ms). Measure on FireSim.

## 5. Mapping to the M1 / A1 chips

| Work | M1 (1 Gemmini) | A1 (2 Gemmini or attention engine) |
|---|---|---|
| All matmuls | Gemmini, weight-stationary, tiles of 32 | Split by head or by token rows across 2 arrays |
| Softmax / GELU / LayerNorm / residual | CGRA or RISC-V vector unit | Same, or the hardware normalisation unit |
| First stem conv (1 channel) | CGRA (21% array utilisation otherwise) | CGRA |
| Weights | On-chip SRAM, loaded once | On-chip SRAM |
| Temporal memory | L2/SRAM (~0.7–1 MiB) | L2/SRAM |
| Expected rate | ~60–90 fps | ~120–180 fps |

## 6. What still needs to be done

| Step | Notes |
|---|---|
| **Training** | PyTorch version of the same graph (not included: PyTorch could not be installed in this environment). Initialise the encoder from DeiT-Tiny layers; train on TII "Race Against the Machine" + synthetic frames with motion blur and rolling-shutter augmentation; loss = focal loss on corner logits + L1 on offsets + pose/velocity regression |
| **Quantisation-aware training** | Train with the integer kernels from `int_ops.py` simulated in the forward pass (fake-quant), so the trained weights match the golden model |
| **Calibration** | Replace the synthetic calibration frames with a few hundred real frames; consider per-channel weight scales if accuracy needs it |
| **Accuracy targets** | Corner reprojection ≤ 2 px, gate recall ≥ 99% within 15 m (from the Tier 3 due diligence) |
| **RTL verification** | `python3 export_vectors.py [--full]` writes every intermediate tensor; RTL must match bit-for-bit |
| **Performance** | Run on FireSim with the real Gemmini DMA; check whether exp/GELU throughput or DMA is the bottleneck |

## Running

```bash
python3 -m pytest -q tests        # 10 tests, ~2 s
python3 cost.py                   # parameters, compute, Gemmini estimate
python3 export_vectors.py         # golden vectors for the small config -> vectors/
python3 export_vectors.py --full  # golden vectors at 640x480
```

Requires Python 3 and NumPy only.

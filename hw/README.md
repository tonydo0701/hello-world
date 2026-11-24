# Hardwired-weight Qwen3-0.6B layer, built block by block

A learning project that builds the hardware for one Qwen3-0.6B transformer
layer using the Taalas idea: **the weights are constants in the circuit**, not
data loaded from memory. Weight values are random; the shapes and arithmetic
are real. Every block has a bit-exact NumPy golden model and a self-checking
Icarus Verilog simulation.

## Layout

| Path | What |
|---|---|
| `model/config.py` | Qwen3-0.6B shapes, plus a `TINY` config with the same ratios for fast sims |
| `model/ref.py` | Golden (integer-exact) models of each block |
| `rtl/` | Hand-written RTL |
| `gen/` | Generators that turn weight matrices into Verilog |
| `tb/` | Testbenches and test runners |

## Number formats

| Value | Format |
|---|---|
| Weights | signed int4, [-8, 7] |
| Activations | signed int8 |
| Accumulators | signed int32 |

## Blocks

| # | Block | Status |
|---|---|---|
| 1 | Hardwired matrix-vector unit (q, k, v, o, gate, up, down) | done |
| 2 | Requantize int32 to int8 | todo |
| 3 | RMSNorm (full vector, and per-head for QK-norm) | todo |
| 4 | RoPE | todo |
| 5 | KV cache + attention scores (q·Kᵀ) | todo |
| 6 | Softmax | todo |
| 7 | Attention × V | todo |
| 8 | SiLU and gating (SwiGLU) | todo |
| 9 | Residual adds | todo |
| 10 | Full layer integration | todo |

## Block 1: hardwired matrix-vector unit

`y = W·x` where `W` is N×K.

- `gen/gen_matvec.py` writes a `<name>_rom` module: a `case` statement whose
  entries are the weights. Synthesis turns it into fixed logic, not a RAM.
- `rtl/matvec_core.v` reads P columns per cycle from that ROM and does N·P
  multiply-accumulates per cycle, so one product takes K/P cycles.
  P trades area for speed: P = K makes it one cycle.

Run the tests:

```sh
python3 tb/test_matvec.py                    # all 7 projections, TINY size
python3 tb/test_matvec.py --config qwen3 --only k_proj --p 16 --vectors 2   # full 1024x1024, ~40 s
```

Requires `iverilog` (`apt-get install iverilog`) and NumPy.

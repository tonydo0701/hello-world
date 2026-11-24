# ASAP7 results: 64x64 hardwired k_proj block

OpenROAD-flow-scripts (Docker image `openroad/orfs:latest`), ASAP7 predictive
7 nm PDK, 1 GHz target, int4 weights / int8 activations / int32 accumulators,
random weights (seed 1). Reproduce with `asic/run_asap7.sh <P> 1000`.

ASAP7 is an academic PDK, not a manufacturable process: use these numbers to
compare designs, not as silicon predictions.

| | P=4 (ROM-selected weights) | P=64 (all weights constant) |
|---|---|---|
| Weights handled per cycle | 4 columns (256 MACs) | all 64 columns (4096 MACs) |
| Cells after synthesis | 98,302 | 363,415 |
| Synthesized area | 9,901 µm² | 34,396 µm² |
| Area after placement/CTS | 10,253 µm² (final) | 42,813 µm² (after CTS) |
| Area per MAC | ~40 µm² | ~8.4 µm² (synthesis) |
| Worst setup slack @ 1 GHz | -30 ps (fmax ≈ 970 MHz) | -343 ps (fmax ≈ 745 MHz, after CTS) |
| Cycles per matvec | 16 | 1 |
| Time per matvec | ≈ 16.5 ns | ≈ 1.34 ns |
| Power | 41 mW (final) | not yet reported |
| Route DRC | 0 | flow still running at time of writing |
| Flow runtime (4 cores) | ~35 min | > 2 h (detailed route pending) |

## What it shows

- **Constant weights make multipliers cheap.** With every weight fixed, each
  int4 × int8 product collapses into a few shifted adds (or nothing, for 0),
  and the weight-select mux disappears. Per MAC that is ~4.7x less area than
  the ROM-select design.
- **12x faster for 4.2x the area**, because P=64 does the whole product in one
  cycle. The cost is a deep adder tree (64 products per output), which limits
  the clock to ~745 MHz. Pipelining the tree, or using P=16/P=32, would close
  timing at 1 GHz.
- **Routing is the problem at scale.** Every activation fans out to all 64
  rows, and the P=64 block is much harder to route. A full Qwen3 layer is
  ~3,800x larger than this block, which is why real hardwired designs need a
  custom cell and floorplan rather than standard cells and auto place-and-route.

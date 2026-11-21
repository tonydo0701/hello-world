# 4×4 Systolic Array (INT8 → INT32)

A small, parameterized **output-stationary systolic array** that computes `C = A × B`.
It is the core building block of the matrix (GEMM) engine in a transformer accelerator.

```
        B[k][0]  B[k][1]  B[k][2]  B[k][3]      (skewed: column j delayed j cycles)
           │        │        │        │
A[0][k] ─▶ PE ───▶ PE ───▶ PE ───▶ PE
           │        │        │        │
A[1][k] ─▶ PE ───▶ PE ───▶ PE ───▶ PE          (skewed: row i delayed i cycles)
           │        │        │        │
A[2][k] ─▶ PE ───▶ PE ───▶ PE ───▶ PE
           │        │        │        │
A[3][k] ─▶ PE ───▶ PE ───▶ PE ───▶ PE
```

Each PE multiplies the A value arriving from the left by the B value arriving from above, adds the product to its own accumulator, and passes A right and B down one cycle later. PE(i,j) ends up holding `C[i][j]`.

| Parameter | Default | Meaning |
|---|---|---|
| `N` | 4 | Array size (N×N PEs) |
| `DW` | 8 | Signed input width |
| `AW` | 32 | Signed accumulator width |

## Interface

1. Pulse `clear` for one cycle.
2. For k = 0 … K−1, drive `a_col` = column k of A and `b_row` = row k of B. The array applies the input skew itself.
3. Drive zeros. `C[i][j]` is available on `c_flat[(i*N+j)*AW +: AW]` **2N−1 clock edges** after the last input.

## Files

| Path | Contents |
|---|---|
| `rtl/pe.v` | Processing element (MAC + pass-through registers) |
| `rtl/systolic_array.v` | N×N grid plus input skew registers |
| `tb/tb_systolic_array.sv` | Self-checking testbench: 50 random signed matrix products plus a −128 corner case |
| `syn/synth.ys` | Yosys script: generic gate-level synthesis (no PDK needed) |

## Running

Needs Verilator 5 and Yosys (or `pip install yowasp-yosys`).

```bash
make lint    # Verilator lint, -Wall clean
make sim     # RTL simulation
make synth   # synthesize to generic gates, print cell statistics
make gls     # re-run the testbench on the synthesized netlist
```

## Results (N=4, DW=8, AW=32)

| Check | Result |
|---|---|
| Lint (`verilator -Wall`) | Clean |
| RTL simulation | PASS, 50/50 random 4×4 products |
| Gate-level simulation | PASS, 50/50 on the synthesized netlist |
| Testbench sanity check | A deliberately broken PE produces 800 mismatches |

Synthesis with Yosys 0.71, generic gate library (`synth -flatten; abc -g AND,NAND,OR,NOR,XOR,XNOR,MUX`):

| Cell | Count |
|---|---|
| Flip-flops (`$_SDFF_PP0_`) | 800 |
| NAND | 3,453 |
| XOR | 2,164 |
| AND | 1,814 |
| XNOR | 877 |
| OR | 594 |
| NOT | 250 |
| NOR | 95 |
| MUX | 42 |
| **Total logic + FF cells** | **10,089** |

The flip-flop count matches the design: 16 PEs × (8 + 8 + 32) bits = 768, plus 96 skew-register bits, minus 64 edge-output bits that nothing reads and synthesis removes, giving 800.

This is a technology-independent synthesis. Area, timing and power figures need a real cell library, for example SkyWater 130 nm or another open PDK via OpenROAD/OpenLane.

#!/usr/bin/env bash
# Full verification flow for the re-created PACE PE.
#   needs: iverilog (>=12), verilator (>=5), cargo, python3
set -euo pipefail
cd "$(dirname "$0")/.."
N=${N:-1000}; NCYC=${NCYC:-500}
RTL="rtl/pace_pe_pkg.sv rtl/pace_fp8_lane.sv rtl/pace_alu.sv rtl/pace_router.sv rtl/pace_pe.sv"
mkdir -p build
quiet() { grep -v "sorry: constant selects" || true; }

echo "== 1. lint (verilator -Wall)"
verilator --lint-only -Wall -Wno-UNUSEDPARAM -Wno-UNUSEDSIGNAL --top-module pace_pe $RTL
verilator --lint-only -Wall -Wno-UNUSEDPARAM -Wno-UNUSEDSIGNAL --top-module pace_pe -GPACESIM_FWD="1'b0" -GMEM_PE="1'b1" $RTL
echo "   clean"

echo "== 2. golden model (pace-sim, pinned commit)"
(cd model/golden && cargo build --release -q)
GOLD=model/golden/target/release/pace-pe-golden

echo "== 3. FP8 exhaustive (65536 pairs x VADD/VMUL)"
$GOLD fp8 build/fp8_golden.txt
iverilog -g2012 -o build/tb_fp8.vvp rtl/pace_fp8_lane.sv tb/tb_fp8.sv 2>&1 | quiet
vvp -n build/tb_fp8.vvp | grep "FP8 exhaustive"

echo "== 4. directed tests"
python3 scripts/mk_directed.py >/dev/null
iverilog -g2012 -o build/tb_directed.vvp $RTL tb/tb_directed.sv 2>&1 | quiet
vvp -n build/tb_directed.vvp | grep DIRECTED

echo "== 5. random co-simulation vs pace-sim"
iverilog -g2012 -o build/tb_pe.vvp $RTL tb/tb_pe.sv 2>&1 | quiet
python3 scripts/regress.py "$N" "$NCYC" iverilog
verilator --binary --timing -Wno-fatal -Wno-lint -Wno-style -Wno-TIMESCALEMOD --top-module tb_pe -Mdir build/obj_tb_pe $RTL tb/tb_pe.sv >/dev/null 2>&1
python3 scripts/regress.py "$N" "$NCYC" verilator

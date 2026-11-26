#!/usr/bin/env bash
# Full verification flow: PE, 8x8 CGRA, RISC-V SoC.
#   needs: iverilog (>=12), verilator (>=5), cargo, python3, riscv64-unknown-elf-gcc
#   PACESIM_TESTS = path to a pace-sim checkout's tests/ (for the lab's 8x8 kernels)
set -euo pipefail
cd "$(dirname "$0")/.."
N=${N:-1000}; NCYC=${NCYC:-500}; NARR=${NARR:-50}
PE_RTL="rtl/pace_pe_pkg.sv rtl/pace_fp8_lane.sv rtl/pace_alu.sv rtl/pace_router.sv rtl/pace_pe.sv"
RTL="$PE_RTL rtl/pace_agu.sv rtl/pace_dmem.sv rtl/pace_cgra.sv"
VLFLAGS="-Wno-fatal -Wno-lint -Wno-style -Wno-TIMESCALEMOD -Wno-UNOPTFLAT -Wno-MULTIDRIVEN"
mkdir -p build/arr
quiet() { grep -v "sorry: constant selects" || true; }

echo "== 1. lint (verilator -Wall)"
verilator --lint-only -Wall -Wno-UNUSEDPARAM -Wno-UNUSEDSIGNAL --top-module pace_pe $PE_RTL
verilator --lint-only -Wall -Wno-UNUSEDPARAM -Wno-UNUSEDSIGNAL --top-module pace_pe -GPACESIM_FWD="1'b0" -GMEM_PE="1'b1" $PE_RTL
# array: mesh is structurally cyclic (UNOPTFLAT), DMEM model uses ordered blocking writes (BLKSEQ)
verilator --lint-only -Wall -Wno-UNUSEDPARAM -Wno-UNUSEDSIGNAL -Wno-PINCONNECTEMPTY -Wno-UNOPTFLAT -Wno-BLKSEQ --top-module pace_cgra $RTL
echo "   clean"

echo "== 2. golden model (pace-sim, pinned commit)"
(cd model/golden && cargo build --release -q)
GOLD=model/golden/target/release/pace-pe-golden

echo "== 3. PE: FP8 exhaustive"
$GOLD fp8 build/fp8_golden.txt
iverilog -g2012 -o build/tb_fp8.vvp rtl/pace_fp8_lane.sv tb/tb_fp8.sv 2>&1 | quiet
vvp -n build/tb_fp8.vvp | grep "FP8 exhaustive"

echo "== 4. PE: directed tests"
python3 scripts/mk_directed.py >/dev/null
iverilog -g2012 -o build/tb_directed.vvp $PE_RTL tb/tb_directed.sv 2>&1 | quiet
vvp -n build/tb_directed.vvp | grep DIRECTED

echo "== 5. PE: random co-simulation vs pace-sim PE"
iverilog -g2012 -o build/tb_pe.vvp $PE_RTL tb/tb_pe.sv 2>&1 | quiet
python3 scripts/regress.py "$N" "$NCYC" iverilog
verilator --binary --timing $VLFLAGS --top-module tb_pe -Mdir build/obj_tb_pe $PE_RTL tb/tb_pe.sv >/dev/null 2>&1
python3 scripts/regress.py "$N" "$NCYC" verilator

echo "== 6. CGRA 8x8: lab kernels vs pace-sim grid (per-cycle 64-PE trace + all DMs)"
iverilog -g2012 -o build/tb_cgra.vvp $RTL tb/tb_cgra.sv 2>&1 | quiet
verilator --binary --timing -j 8 -O2 $VLFLAGS --top-module tb_cgra -Mdir build/obj_tb_cgra $RTL tb/tb_cgra.sv >/dev/null 2>&1
if [ -n "${PACESIM_TESTS:-}" ]; then
  for k in gemm complex_scalar_8x8; do
    python3 scripts/cgra_image.py "$PACESIM_TESTS/$k" build/$k.writes >/dev/null
    $GOLD grid "$PACESIM_TESTS/$k" 100000 build/$k.gold.trace build/$k.gold.dm >/dev/null
    build/obj_tb_cgra/Vtb_cgra +IMG=build/$k.writes +TRACE=build/$k.rtl.trace +DMOUT=build/$k.rtl.dm >/dev/null
    ok=1; cmp -s build/$k.gold.trace build/$k.rtl.trace || ok=0
    for d in 0 1 2 3 4 5 6 7; do cmp -s build/$k.gold.dm$d build/$k.rtl.dm$d || ok=0; done
    echo "   $k: $(wc -l < build/$k.rtl.trace) cycles -> $([ $ok = 1 ] && echo PASS || echo FAIL)"
  done
else echo "   (set PACESIM_TESTS to run the lab kernels)"; fi

echo "== 7. CGRA 8x8: constrained-random kernels vs pace-sim grid"
python3 scripts/regress_array.py "$NARR" 200 verilator

echo "== 8. RISC-V SoC: firmware loads GEMM, runs CGRA, checks result"
if [ -n "${PACESIM_TESTS:-}" ]; then
  make -s -C soc/fw clean
  make -s -C soc/fw KERNEL="$PACESIM_TESTS/gemm" GOLD_DM=../../build/gemm.gold.dm >/dev/null
  verilator --binary --timing -j 8 -O2 $VLFLAGS --top-module tb_soc -Mdir build/obj_tb_soc \
    $RTL soc/third_party/picorv32.v soc/pace_soc.sv soc/tb_soc.sv >/dev/null 2>&1
  build/obj_tb_soc/Vtb_soc | grep -E "RESULT|exit code|finished"
fi

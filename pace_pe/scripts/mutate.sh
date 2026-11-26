#!/bin/bash
# Mutation test: apply one sed edit to a copy of rtl/, rerun the random 8x8
# regression on the mutant and print the first mismatch (empty = not detected).
# usage: N=<seeds> scripts/mutate.sh <name> <rtl file> <sed expression>
# $1 = name, $2 = file, $3 = sed expression
cd /home/user/hello-world/pace_pe
mkdir -p build/mut; rm -rf build/mut/rtl && cp -r rtl build/mut/rtl
sed -i "$3" build/mut/rtl/$2
if diff -q rtl/$2 build/mut/rtl/$2 >/dev/null; then echo "$1: sed did not apply"; exit; fi
M=build/mut/rtl; R="$M/pace_pe_pkg.sv $M/pace_fp8_lane.sv $M/pace_alu.sv $M/pace_router.sv $M/pace_pe.sv $M/pace_agu.sv $M/pace_dmem.sv $M/pace_cgra.sv"
iverilog -g2012 -o build/mut/tb.vvp $R tb/tb_cgra.sv 2>/dev/null
cp build/tb_cgra.vvp build/tb_cgra.vvp.good; cp build/mut/tb.vvp build/tb_cgra.vvp
echo "$1: $(python3 scripts/regress_array.py ${N:-3} 100 2>&1 | grep -E 'MISMATCH' | head -1)"
cp build/tb_cgra.vvp.good build/tb_cgra.vvp

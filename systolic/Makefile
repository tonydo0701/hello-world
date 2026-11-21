YOSYS ?= $(shell command -v yosys || command -v yowasp-yosys)

.PHONY: all sim synth gls lint clean
all: lint sim synth gls

lint:
	verilator --lint-only -Wall -Wno-DECLFILENAME rtl/pe.v rtl/systolic_array.v --top-module systolic_array

sim:
	mkdir -p build
	verilator --binary --timing -Wno-fatal -Wno-WIDTHTRUNC -Wno-WIDTHEXPAND \
		--top-module tb_systolic_array -Mdir build/obj \
		rtl/pe.v rtl/systolic_array.v tb/tb_systolic_array.sv
	./build/obj/Vtb_systolic_array

synth:
	mkdir -p syn/build
	cd syn && $(YOSYS) -q -s synth.ys
	@cat syn/build/stats.txt

clean:
	rm -rf build syn/build

# Re-run the testbench against the synthesized gate-level netlist.
gls: synth
	mkdir -p build
	verilator --binary --timing -Wno-fatal -Wno-lint -Wno-style \
		-DGLS --top-module tb_systolic_array -Mdir build/gls \
		syn/build/systolic_array_netlist.v tb/tb_systolic_array.sv
	./build/gls/Vtb_systolic_array

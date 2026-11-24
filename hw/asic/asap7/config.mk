# OpenROAD-flow-scripts config for a generated matvec block on ASAP7.
# Driven by run_asap7.sh, which sets VARIANT, SRC_DIR and CLOCK_PERIOD_PS.
export PLATFORM        = asap7
export DESIGN_NAME     = k_proj_top
export DESIGN_NICKNAME = $(VARIANT)

export VERILOG_FILES = /work/hw/rtl/matvec_core.v $(SRC_DIR)/k_proj.v
export SDC_FILE      = /work/hw/asic/asap7/constraint.sdc

export CORE_UTILIZATION = 50
export PLACE_DENSITY    = 0.60

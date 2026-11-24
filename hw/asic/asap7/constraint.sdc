# Single clock; period (ps) comes from the CLOCK_PERIOD_PS environment variable.
current_design k_proj_top
set clk_period $::env(CLOCK_PERIOD_PS)
create_clock -name core_clock -period $clk_period [get_ports clk]
set_input_delay  [expr $clk_period * 0.2] -clock core_clock [delete_from_list [all_inputs] [get_ports clk]]
set_output_delay [expr $clk_period * 0.2] -clock core_clock [all_outputs]

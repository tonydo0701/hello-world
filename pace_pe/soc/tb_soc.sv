`timescale 1ns/1ps
module tb_soc;
  logic clk = 0, rst_n = 0;
  logic [7:0] con_data; logic con_valid, exit_valid; logic [31:0] exit_code;
  always #5 clk = ~clk;
  pace_soc dut (.clk, .rst_n, .con_data, .con_valid, .exit_valid, .exit_code);
  integer cycles = 0;
  always @(posedge clk) begin
    cycles <= cycles + 1;
    if (con_valid) $write("%c", con_data);
    if (exit_valid) begin
      $display("\n[tb_soc] firmware exit code %0d after %0d CPU cycles", exit_code, cycles);
      $finish;
    end
    if (cycles > 20_000_000) begin $display("[tb_soc] TIMEOUT"); $finish; end
  end
  initial begin
    if ($test$plusargs("vcd")) begin $dumpfile("build/soc.vcd"); $dumpvars(1, dut); $dumpvars(0, dut.u_cgra.running); end
    repeat (5) @(posedge clk); rst_n = 1;
  end
endmodule

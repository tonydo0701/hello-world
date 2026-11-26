// Trace testbench: loads a 16-word program into the PE's configuration memory
// through the write port, then drives per-cycle neighbour inputs and dumps a
// trace in the same format as model/golden (pace-sim) for diffing.
`timescale 1ns/1ps
module tb_pe;
  import pace_pe_pkg::*;
  logic clk = 0, rst_n = 0, exec_en = 0;
  logic cm_we = 0; logic [3:0] cm_waddr = 0; logic [63:0] cm_wdata = 0;
  logic [63:0] in_n = 0, in_s = 0, in_w = 0, in_e = 0;
  logic [63:0] out_n, out_s, out_w, out_e, st_data;
  logic agu_trigger;
  logic [3:0]  dbg_pc;
  logic [63:0] dbg_alu_out, dbg_op1, dbg_op2, dbg_res, dbg_q_n, dbg_q_s, dbg_q_w, dbg_q_e;
  logic [4:0]  dbg_ls, dbg_le;
  logic dbg_illegal;

  pace_pe dut (
    .clk, .rst_n, .exec_en, .cm_we, .cm_waddr, .cm_wdata,
    .in_n, .in_s, .in_w, .in_e, .out_n, .out_s, .out_w, .out_e,
    .agu_trigger, .st_data, .ld_valid(1'b0), .ld_data(64'h0),
    .dbg_pc, .dbg_alu_out, .dbg_op1, .dbg_op2, .dbg_res,
    .dbg_q_n, .dbg_q_s, .dbg_q_w, .dbg_q_e,
    .dbg_loop_start(dbg_ls), .dbg_loop_end(dbg_le), .dbg_illegal);

  always #5 clk = ~clk;

  logic [63:0] prog [16];
  logic [63:0] inp  [];
  string fprog, finp, ftrace;
  integer ncyc, fd, fo, n, i;
  logic [63:0] w0, w1, w2, w3;
  logic [3:0]  s_pc; logic [63:0] s_alu, s_n, s_s, s_w, s_e;

  initial begin
    void'($value$plusargs("PROG=%s", fprog));
    void'($value$plusargs("INPUTS=%s", finp));
    void'($value$plusargs("TRACE=%s", ftrace));
    $readmemh(fprog, prog);
    // count + read inputs
    fd = $fopen(finp, "r"); ncyc = 0;
    inp = new[4*20000];
    while (!$feof(fd)) begin
      n = $fscanf(fd, "%h %h %h %h\n", w0, w1, w2, w3);
      if (n == 4) begin
        inp[4*ncyc] = w0; inp[4*ncyc+1] = w1; inp[4*ncyc+2] = w2; inp[4*ncyc+3] = w3;
        ncyc++;
      end
    end
    $fclose(fd);
    fo = $fopen(ftrace, "w");

    // reset, then program the configuration memory (exec held off)
    repeat (2) @(posedge clk);
    rst_n = 1;
    for (i = 0; i < 16; i++) begin
      @(negedge clk); cm_we = 1; cm_waddr = i[3:0]; cm_wdata = prog[i];
    end
    @(negedge clk); cm_we = 0; exec_en = 1;

    for (i = 0; i < ncyc; i++) begin
      in_n = inp[4*i]; in_s = inp[4*i+1]; in_w = inp[4*i+2]; in_e = inp[4*i+3];
      #4;   // settle combinational paths before the edge
      s_pc = dbg_pc; s_alu = dbg_alu_out; s_n = out_n; s_s = out_s; s_w = out_w; s_e = out_e;
      @(posedge clk); #1;
      $fdisplay(fo, "%0h %016h %016h %016h %016h %016h %016h %016h %016h %016h %016h %016h %016h %0h %0h",
                s_pc, s_alu, s_n, s_s, s_w, s_e, dbg_op1, dbg_op2, dbg_res,
                dbg_q_n, dbg_q_s, dbg_q_w, dbg_q_e, dbg_ls, dbg_le);
      @(negedge clk);
    end
    $fclose(fo);
    $finish;
  end
endmodule

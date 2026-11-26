// Directed, self-checking tests for the re-created PACE PE.
//  T1  1x3 row: PE0 -> PE1 (pass-through) -> PE2 in ONE cycle (multi-hop)
//  T2  FP8x8 SIMD accumulate (VADD with result forwarding)
//  T3  memory-PE side band (AGU trigger, store data, load return)
//  T4  router input ("parking") register: latch once, reuse later
`timescale 1ns/1ps
module tb_directed;
  logic clk = 0, rst_n = 0, exec_en = 0, cm_we = 0;
  logic [3:0] cm_waddr = 0; logic [63:0] cm_wdata = 0;
  always #5 clk = ~clk;
  integer errs = 0, i;

  `define CHECK(cond, msg) if (!(cond)) begin errs++; $display("  FAIL: %s", msg); end

  // ---------------- T1: three PEs in a row -------------------------------
  logic [63:0] e0, e1, e2, z;
  logic [2:0]  we3;
  assign z = 64'h0;
  logic [63:0] p0_res, p2_op1, p2_res;

  pace_pe pe0 (.clk, .rst_n, .exec_en, .cm_we(cm_we & we3[0]), .cm_waddr, .cm_wdata,
    .in_n(z), .in_s(z), .in_w(z), .in_e(z), .out_n(), .out_s(), .out_w(), .out_e(e0),
    .agu_trigger(), .st_data(), .ld_valid(1'b0), .ld_data(z), .dbg_pc(), .dbg_alu_out(),
    .dbg_op1(), .dbg_op2(), .dbg_res(p0_res), .dbg_q_n(), .dbg_q_s(), .dbg_q_w(), .dbg_q_e(),
    .dbg_loop_start(), .dbg_loop_end(), .dbg_illegal());
  pace_pe pe1 (.clk, .rst_n, .exec_en, .cm_we(cm_we & we3[1]), .cm_waddr, .cm_wdata,
    .in_n(z), .in_s(z), .in_w(e0), .in_e(z), .out_n(), .out_s(), .out_w(), .out_e(e1),
    .agu_trigger(), .st_data(), .ld_valid(1'b0), .ld_data(z), .dbg_pc(), .dbg_alu_out(),
    .dbg_op1(), .dbg_op2(), .dbg_res(), .dbg_q_n(), .dbg_q_s(), .dbg_q_w(), .dbg_q_e(),
    .dbg_loop_start(), .dbg_loop_end(), .dbg_illegal());
  pace_pe pe2 (.clk, .rst_n, .exec_en, .cm_we(cm_we & we3[2]), .cm_waddr, .cm_wdata,
    .in_n(z), .in_s(z), .in_w(e1), .in_e(z), .out_n(), .out_s(), .out_w(), .out_e(e2),
    .agu_trigger(), .st_data(), .ld_valid(1'b0), .ld_data(z), .dbg_pc(), .dbg_alu_out(),
    .dbg_op1(p2_op1), .dbg_op2(), .dbg_res(p2_res), .dbg_q_n(), .dbg_q_s(), .dbg_q_w(), .dbg_q_e(),
    .dbg_loop_start(), .dbg_loop_end(), .dbg_illegal());

  // ---------------- T2/T3/T4: single PEs ---------------------------------
  logic [63:0] t2_w, t2_res, t3_st, t3_ld, t3_op1, t4_n, t4_s, t4_res;
  logic t3_trig, t3_ldv;
  logic [2:0] we_s;   // which single PE is being programmed: 1=T2 2=T3 4=T4
  pace_pe pe_t2 (.clk, .rst_n, .exec_en, .cm_we(cm_we & we_s[0]), .cm_waddr, .cm_wdata,
    .in_n(z), .in_s(z), .in_w(t2_w), .in_e(z), .out_n(), .out_s(), .out_w(), .out_e(),
    .agu_trigger(), .st_data(), .ld_valid(1'b0), .ld_data(z), .dbg_pc(), .dbg_alu_out(),
    .dbg_op1(), .dbg_op2(), .dbg_res(t2_res), .dbg_q_n(), .dbg_q_s(), .dbg_q_w(), .dbg_q_e(),
    .dbg_loop_start(), .dbg_loop_end(), .dbg_illegal());
  pace_pe #(.MEM_PE(1'b1)) pe_t3 (.clk, .rst_n, .exec_en, .cm_we(cm_we & we_s[1]), .cm_waddr, .cm_wdata,
    .in_n(z), .in_s(z), .in_w(z), .in_e(z), .out_n(), .out_s(), .out_w(), .out_e(),
    .agu_trigger(t3_trig), .st_data(t3_st), .ld_valid(t3_ldv), .ld_data(t3_ld), .dbg_pc(),
    .dbg_alu_out(), .dbg_op1(t3_op1), .dbg_op2(), .dbg_res(), .dbg_q_n(), .dbg_q_s(), .dbg_q_w(),
    .dbg_q_e(), .dbg_loop_start(), .dbg_loop_end(), .dbg_illegal());
  pace_pe pe_t4 (.clk, .rst_n, .exec_en, .cm_we(cm_we & we_s[2]), .cm_waddr, .cm_wdata,
    .in_n(t4_n), .in_s(z), .in_w(z), .in_e(z), .out_n(), .out_s(t4_s), .out_w(), .out_e(),
    .agu_trigger(), .st_data(), .ld_valid(1'b0), .ld_data(z), .dbg_pc(), .dbg_alu_out(),
    .dbg_op1(), .dbg_op2(), .dbg_res(t4_res), .dbg_q_n(), .dbg_q_s(), .dbg_q_w(), .dbg_q_e(),
    .dbg_loop_start(), .dbg_loop_end(), .dbg_illegal());

  logic [63:0] pbuf [16];
  task automatic load(input string fn, input logic [2:0] sel3, input logic [2:0] sels);
    $readmemh(fn, pbuf);
    for (int k = 0; k < 16; k++) begin
      @(negedge clk); we3 = sel3; we_s = sels; cm_we = 1; cm_waddr = k[3:0]; cm_wdata = pbuf[k];
    end
    @(negedge clk); cm_we = 0;
  endtask

  logic [63:0] e0_hist [0:31];
  logic [7:0]  exp_acc [0:8];
  initial begin
    exp_acc[0]=8'h00; exp_acc[1]=8'h38; exp_acc[2]=8'h40; exp_acc[3]=8'h44; exp_acc[4]=8'h48;
    exp_acc[5]=8'h4A; exp_acc[6]=8'h4C; exp_acc[7]=8'h4E; exp_acc[8]=8'h50;  // 1.0 .. 8.0 in E4M3
    we3 = 0; we_s = 0; t2_w = 64'h3838383838383838; t3_ldv = 0; t3_ld = 0; t4_n = 64'h1234;
    repeat (2) @(posedge clk); rst_n = 1;
    load("build/t1_pe0.hex", 3'b001, 3'b000); load("build/t1_pe1.hex", 3'b010, 3'b000);
    load("build/t1_pe2.hex", 3'b100, 3'b000); load("build/t2_pe.hex",  3'b000, 3'b001);
    load("build/t3_pe.hex",  3'b000, 3'b010); load("build/t4_pe.hex",  3'b000, 3'b100);

    @(negedge clk); exec_en = 1;
    for (i = 0; i < 12; i++) begin
      #3;
      // multi-hop: the value leaving PE0 arrives at PE2's W input in the same cycle
      `CHECK(pe2.in_w === e0, "T1 PE0.E_out must reach PE2.W_in combinationally (2 hops)")
      e0_hist[i] = e0;
      if (i == 4) t4_n = 64'hDEAD;          // change the wire after it was parked
      // memory PE: return a load at cycle 5
      t3_ldv = (i == 5); t3_ld = 64'hCAFE_F00D;
      @(posedge clk); #1;
      if (i >= 1)
        `CHECK(p2_op1 === e0_hist[i], "T1 PE2.op1 latched PE0's value of this cycle")
      // sampled just after the edge: PE2's ALU now holds e0(i) + 100
      if (i >= 1)
        `CHECK(e2 === e0_hist[i] + 100, "T1 PE2 E_out (next cycle) = PE0 value + 100")
      // CM[0] is the JUMP, CM[1] starts at cycle 1, first useful add at cycle 2
      if (i >= 1 && i <= 9)
        `CHECK(t2_res === {8{exp_acc[i-1]}}, $sformatf("T2 FP8 acc after %0d adds = %h", i-1, t2_res))
      if (i == 5) `CHECK(t3_op1 === 64'hCAFE_F00D, "T3 load data wins op1 at the edge")
      if (i >= 2) `CHECK(t4_s === 64'h1234, "T4 parked N value still routed after wire changed")
      @(negedge clk);
      $display("cyc %0d | PE0.E=%0d PE1.E=%0d PE2.E=%0d | T2 acc=%h | T3 trig=%b st=%h | T4 S=%h",
               i, e0, e1, e2, t2_res[7:0], t3_trig, t3_st, t4_s);
    end
    // let the FP8 accumulator run to saturation-by-rounding: 16 + 1 -> 16 (RNE)
    repeat (20) @(posedge clk); #1;
    `CHECK(t2_res === {8{8'h58}}, "T2 FP8 accumulate saturates at 16.0 (0x58) by RNE")
    `CHECK(t3_trig === 1'b1, "T3 AGU trigger bit 59 visible on memory PE")
    $display("DIRECTED: %0d errors -> %s", errs, errs == 0 ? "PASS" : "FAIL");
    $finish;
  end
endmodule

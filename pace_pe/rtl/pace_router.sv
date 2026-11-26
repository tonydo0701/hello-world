// -----------------------------------------------------------------------------
// pace_router.sv
// HyCUBE-style single-cycle multi-hop router, 6 sources x 7 sinks.
//
//   sources : E_in, S_in, W_in, N_in   (wire, or the input register if bypass=1)
//             ALU_out (combinational, this cycle), ALU_res (result register)
//   sinks   : E_out, S_out, W_out, N_out  (combinational -> neighbour PE)
//             ALU op1, ALU op2, predicate (sampled into PE registers)
//
// Because the E/S/W/N outputs are combinational functions of the wire inputs,
// a value can cross several PEs in one clock (a "bypass" path); the 4 input
// registers let a value be parked in the router and reused in later cycles.
// -----------------------------------------------------------------------------
module pace_router
  import pace_pe_pkg::*;
#(
  // 1: operand capture follows pace-sim's update order (input-register and
  //    result-register writes are visible to op1/op2 in the same cycle,
  //    i.e. write-through forwarding). 0: plain flop semantics.
  parameter bit PACESIM_FWD = 1'b1
)(
  input  logic          clk,
  input  logic          rst_n,
  input  logic          en,            // execution enable (state update)

  input  logic [20:0]   sw_cfg,        // switch configuration
  input  logic [3:0]    reg_bypass,    // {N,S,W,E}: read input register, not wire
  input  logic [3:0]    reg_we,        // {N,S,W,E}: latch wire into input register

  input  logic [DW-1:0] in_e, in_s, in_w, in_n,   // from neighbours
  input  logic [DW-1:0] alu_out,
  input  logic [DW-1:0] alu_res,
  input  logic          res_we,        // result register is written this cycle

  output logic [DW-1:0] out_e, out_s, out_w, out_n,
  output logic [DW-1:0] op1_data,
  output logic          op1_load,      // 0 when op1 select is OPEN (hold)
  output logic [DW-1:0] op2_data,
  output logic          op2_load,

  // observability
  output logic [DW-1:0] q_e, q_s, q_w, q_n
);

  logic [DW-1:0] src_e, src_s, src_w, src_n;     // crossbar-output view
  logic [DW-1:0] opd_e, opd_s, opd_w, opd_n;     // operand-capture view
  logic [DW-1:0] opd_res;

  // effective direction sources: wire or parked register
  assign src_e = reg_bypass[D_E] ? q_e : in_e;
  assign src_s = reg_bypass[D_S] ? q_s : in_s;
  assign src_w = reg_bypass[D_W] ? q_w : in_w;
  assign src_n = reg_bypass[D_N] ? q_n : in_n;

  // operand capture (PACESIM_FWD=1): if a direction is bypassed AND written
  // this cycle, forward the incoming wire; ALU_res forwards the new result.
  assign opd_e = (reg_bypass[D_E] && !(PACESIM_FWD && reg_we[D_E])) ? q_e : in_e;
  assign opd_s = (reg_bypass[D_S] && !(PACESIM_FWD && reg_we[D_S])) ? q_s : in_s;
  assign opd_w = (reg_bypass[D_W] && !(PACESIM_FWD && reg_we[D_W])) ? q_w : in_w;
  assign opd_n = (reg_bypass[D_N] && !(PACESIM_FWD && reg_we[D_N])) ? q_n : in_n;
  assign opd_res = (PACESIM_FWD && res_we) ? alu_out : alu_res;

  function automatic logic [DW-1:0] pick(input logic [2:0] sel,
                                         input logic [DW-1:0] e, s, w, n, ao, ar);
    case (sel)
      SRC_E:      pick = e;
      SRC_S:      pick = s;
      SRC_W:      pick = w;
      SRC_N:      pick = n;
      SRC_ALUOUT: pick = ao;
      SRC_ALURES: pick = ar;
      default:    pick = '0;     // OPEN / reserved: output not driven
    endcase
  endfunction

  function automatic logic is_open(input logic [2:0] sel);
    is_open = (sel == SRC_OPEN) || (sel == SRC_RSVD);
  endfunction

  // 7 crossbar outputs (predicate [20:18] is decoded but unused, see README)
  assign out_e    = pick(sw_cfg[2:0],   src_e, src_s, src_w, src_n, alu_out, alu_res);
  assign out_s    = pick(sw_cfg[5:3],   src_e, src_s, src_w, src_n, alu_out, alu_res);
  assign out_w    = pick(sw_cfg[8:6],   src_e, src_s, src_w, src_n, alu_out, alu_res);
  assign out_n    = pick(sw_cfg[11:9],  src_e, src_s, src_w, src_n, alu_out, alu_res);
  assign op1_data = pick(sw_cfg[14:12], opd_e, opd_s, opd_w, opd_n, alu_out, opd_res);
  assign op2_data = pick(sw_cfg[17:15], opd_e, opd_s, opd_w, opd_n, alu_out, opd_res);
  assign op1_load = !is_open(sw_cfg[14:12]);
  assign op2_load = !is_open(sw_cfg[17:15]);

  // input (parking) registers: always latch the raw wire
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      q_e <= '0; q_s <= '0; q_w <= '0; q_n <= '0;
    end else if (en) begin
      if (reg_we[D_E]) q_e <= in_e;
      if (reg_we[D_S]) q_s <= in_s;
      if (reg_we[D_W]) q_w <= in_w;
      if (reg_we[D_N]) q_n <= in_n;
    end
  end

endmodule

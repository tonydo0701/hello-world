// -----------------------------------------------------------------------------
// pace_pe.sv
// Re-created PACE CGRA processing element: configuration memory + loop/PC
// controller + decoder + 16b/FP8x8 ALU + operand/result registers + router.
//
// Per cycle (one configuration word per cycle, no stall):
//   cfg      = CM[pc]                                (async read)
//   alu_out  = ALU(op, op1_q, op2_q | imm)           (combinational)
//   outputs  = router(cfg, wires, alu_out, res_q)    (combinational, multi-hop)
//   @posedge : res_q  <= alu_out          if update_res and not control op
//              op1_q  <= router op1 src   if not OPEN (mem PE: load data wins)
//              op2_q  <= router op2 src   if not OPEN
//              in-regs<= wires            per write-enable mask
//              loop regs <= JUMP fields   if JUMP
//              pc     <= next pc (JUMP / loop wrap / +1)
// -----------------------------------------------------------------------------
module pace_pe
  import pace_pe_pkg::*;
#(
  parameter bit MEM_PE      = 1'b0,    // edge PE attached to a data memory/AGU
  parameter bit PACESIM_FWD = 1'b1     // see pace_router
)(
  input  logic             clk,
  input  logic             rst_n,
  input  logic             exec_en,    // 1 = run, 0 = hold all execution state

  // configuration-memory write port (host / QSPI loader side)
  input  logic             cm_we,
  input  logic [CM_AW-1:0] cm_waddr,
  input  logic [CW-1:0]    cm_wdata,

  // mesh links
  input  logic [DW-1:0]    in_n, in_s, in_w, in_e,
  output logic [DW-1:0]    out_n, out_s, out_w, out_e,

  // memory-PE side band (ignored when MEM_PE = 0)
  output logic             agu_trigger,
  output logic [DW-1:0]    st_data,    // store data = op1 register
  input  logic             ld_valid,   // load data returning at this edge
  input  logic [DW-1:0]    ld_data,

  // observability
  output logic [CM_AW-1:0] dbg_pc,
  output logic [DW-1:0]    dbg_alu_out,
  output logic [DW-1:0]    dbg_op1, dbg_op2, dbg_res,
  output logic [DW-1:0]    dbg_q_n, dbg_q_s, dbg_q_w, dbg_q_e,
  output logic [4:0]       dbg_loop_start, dbg_loop_end,
  output logic             dbg_illegal
);

  // ---------------------------------------------------------------------------
  // Configuration memory: 16 x 64b
  // ---------------------------------------------------------------------------
  logic [CW-1:0] cm [CM_DEPTH];
  always_ff @(posedge clk) if (cm_we) cm[cm_waddr] <= cm_wdata;

  logic [CM_AW-1:0] pc_q;
  logic [CW-1:0]    cfg;
  assign cfg = cm[pc_q];

  // ---------------------------------------------------------------------------
  // Decode
  // ---------------------------------------------------------------------------
  logic [4:0]  opc;
  logic        is_jump, is_ctrl, imm_en, upd_res;
  logic [15:0] imm;
  logic [4:0]  j_dst, j_ls, j_le;

  assign opc     = cfg[34:30];
  assign is_jump = (opc == OP_JUMP);
  assign is_ctrl = is_jump || (opc == OP_BR) || (opc == OP_MOVC) || (opc == OP_MOVCL);
  assign imm_en  = cfg[B_IMMV] && !is_jump;
  assign imm     = cfg[50:35];
  assign upd_res = cfg[B_UPDRES] && !is_ctrl;
  assign j_dst   = cfg[49:45];
  assign j_le    = cfg[44:40];
  assign j_ls    = cfg[39:35];

  // ---------------------------------------------------------------------------
  // Datapath
  // ---------------------------------------------------------------------------
  logic [DW-1:0] op1_q, op2_q, res_q, alu_out;
  logic [DW-1:0] r_op1, r_op2;
  logic          r_op1_ld, r_op2_ld, illegal;

  pace_alu u_alu (
    .op(opc), .op1(op1_q), .op2(op2_q), .imm_en(imm_en), .imm(imm),
    .alu_out(alu_out), .illegal(illegal)
  );

  pace_router #(.PACESIM_FWD(PACESIM_FWD)) u_router (
    .clk(clk), .rst_n(rst_n), .en(exec_en),
    .sw_cfg(cfg[20:0]), .reg_bypass(cfg[24:21]), .reg_we(cfg[29:26]),
    .in_e(in_e), .in_s(in_s), .in_w(in_w), .in_n(in_n),
    .alu_out(alu_out), .alu_res(res_q), .res_we(upd_res),
    .out_e(out_e), .out_s(out_s), .out_w(out_w), .out_n(out_n),
    .op1_data(r_op1), .op1_load(r_op1_ld), .op2_data(r_op2), .op2_load(r_op2_ld),
    .q_e(dbg_q_e), .q_s(dbg_q_s), .q_w(dbg_q_w), .q_n(dbg_q_n)
  );

  // ---------------------------------------------------------------------------
  // Loop / PC controller
  // ---------------------------------------------------------------------------
  logic [4:0]       ls_q, le_q, ls_d, le_d;
  logic             prev_jump_q;
  logic [CM_AW-1:0] pc_d;

  always_comb begin
    ls_d = is_jump ? j_ls : ls_q;
    le_d = is_jump ? j_le : le_q;
    if (is_jump && !prev_jump_q)
      pc_d = j_dst[CM_AW-1:0];
    else if ({1'b0, pc_q} >= le_d || {1'b0, pc_q} < ls_d)
      pc_d = ls_d[CM_AW-1:0];
    else
      pc_d = pc_q + 1'b1;
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      pc_q        <= '0;
      ls_q        <= 5'd0;
      le_q        <= 5'd15;
      prev_jump_q <= 1'b0;
      op1_q       <= '0;
      op2_q       <= '0;
      res_q       <= '0;
    end else if (exec_en) begin
      pc_q        <= pc_d;
      ls_q        <= ls_d;
      le_q        <= le_d;
      prev_jump_q <= is_jump;
      if (upd_res) res_q <= alu_out;
      if (MEM_PE && ld_valid) op1_q <= ld_data;
      else if (r_op1_ld)      op1_q <= r_op1;
      if (r_op2_ld)           op2_q <= r_op2;
    end
  end

  // ---------------------------------------------------------------------------
  // Memory-PE side band and debug
  // ---------------------------------------------------------------------------
  assign agu_trigger = MEM_PE ? (cfg[B_AGU] && exec_en) : 1'b0;
  assign st_data     = MEM_PE ? op1_q : '0;

  assign dbg_pc         = pc_q;
  assign dbg_alu_out    = alu_out;
  assign dbg_op1        = op1_q;
  assign dbg_op2        = op2_q;
  assign dbg_res        = res_q;
  assign dbg_loop_start = ls_q;
  assign dbg_loop_end   = le_q;
  assign dbg_illegal    = illegal;

endmodule

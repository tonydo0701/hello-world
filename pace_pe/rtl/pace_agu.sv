// -----------------------------------------------------------------------------
// pace_agu.sv
// Address generation unit for one memory PE (pace-sim src/agu/agu.rs).
//   CM  : up to 16 one-byte instructions {stride[7:4], width[3:2], const[1], store[0]}
//         width: 0 = 8b, 1 = 16b, 2 = 64b
//   ARF : 16 x 13b byte addresses, one per instruction (live, post-incremented)
//   MAX : [23:0] iteration count, [31:24] index of the last CM entry
// On every PE-side trigger the AGU issues the access of CM[pc] at ARF[pc],
// post-increments ARF[pc] by stride*size if strided, then advances pc; after
// the last entry pc wraps and the iteration counter increments. A trigger that
// arrives once count == max signals END (the access is not performed).
// -----------------------------------------------------------------------------
module pace_agu (
  input  logic        clk,
  input  logic        rst_n,
  input  logic        clr,          // start of a new kernel: pc = count = 0
  // host configuration
  input  logic        cm_we,  input logic [3:0] cm_waddr,  input logic [7:0]  cm_wdata,
  input  logic        arf_we, input logic [3:0] arf_waddr, input logic [12:0] arf_wdata,
  input  logic        max_we, input logic [31:0] max_wdata,
  // execution
  input  logic        trigger,      // PE asks for a memory access this cycle
  input  logic        commit,       // the array commits this cycle (no global END)
  output logic        end_o,        // trigger while count >= max  -> end of kernel
  output logic        req,          // memory access this cycle
  output logic        is_store,
  output logic [1:0]  width,
  output logic [12:0] addr
);
  logic [7:0]  cm  [16];
  logic [12:0] arf [16];
  logic [23:0] max_cnt, count;
  logic [3:0]  last_pc, pc;
  logic [7:0]  inst;
  logic [12:0] step;

  assign inst     = cm[pc];
  assign is_store = inst[0];
  assign width    = inst[3:2];
  assign addr     = arf[pc];
  assign end_o    = trigger && (count >= max_cnt);
  assign req      = trigger && !end_o;
  always_comb begin
    case (inst[3:2])
      2'd0:    step = {9'd0, inst[7:4]};
      2'd1:    step = {8'd0, inst[7:4], 1'b0};
      default: step = {6'd0, inst[7:4], 3'b0};
    endcase
  end

  always_ff @(posedge clk) begin
    if (cm_we)  cm[cm_waddr]   <= cm_wdata;
    if (arf_we) arf[arf_waddr] <= arf_wdata;
    else if (req && commit && !inst[1]) arf[pc] <= arf[pc] + step;
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      pc <= '0; count <= '0; max_cnt <= '0; last_pc <= '0;
    end else begin
      if (max_we) begin max_cnt <= max_wdata[23:0]; last_pc <= max_wdata[27:24]; end
      if (clr) begin
        pc <= '0; count <= '0;
      end else if (req && commit) begin
        if (pc == last_pc) begin pc <= '0; count <= count + 24'd1; end
        else                     pc <= pc + 4'd1;
      end
    end
  end
endmodule

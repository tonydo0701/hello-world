// -----------------------------------------------------------------------------
// pace_dmem.sv
// 8 KB data memory shared by two vertically adjacent memory PEs (ports A/B),
// plus a 32-bit host port. Byte addressed, little endian, 8/16/64-bit accesses
// (pace-sim src/sim/dmem.rs). Reads are registered: data is valid the cycle
// after the request; the PE latches it into op1 at the end of that cycle, so
// a load issued in cycle T is usable by the ALU in cycle T+2.
// Behavioural model (byte array, port A then port B order, like pace-sim).
// A silicon version would use a dual-port SRAM macro with byte enables.
// -----------------------------------------------------------------------------
module pace_dmem #(parameter int BYTES = 8192) (
  input  logic        clk,
  // CGRA ports
  input  logic        a_req, a_we, input logic [1:0] a_w, input logic [12:0] a_addr,
  input  logic [63:0] a_wdata, output logic [63:0] a_rdata,
  input  logic        b_req, b_we, input logic [1:0] b_w, input logic [12:0] b_addr,
  input  logic [63:0] b_wdata, output logic [63:0] b_rdata,
  // host port (32-bit words)
  input  logic        h_re, h_we, input logic [10:0] h_widx,
  input  logic [31:0] h_wdata, output logic [31:0] h_rdata
);
  logic [7:0] mem [BYTES];
  // simulation convenience: SRAM starts zeroed (pace-sim zero-fills its DMs).
  // On silicon the host must write every location a kernel reads.
  initial for (int i = 0; i < BYTES; i++) mem[i] = 8'h00;

  function automatic logic [63:0] rd(input logic [1:0] w, input logic [12:0] ad);
    logic [63:0] v = '0;
    case (w)
      2'd0:    v[7:0]  = mem[ad];
      2'd1:    v[15:0] = {mem[ad+13'd1], mem[ad]};
      default: for (int i = 0; i < 8; i++) v[8*i +: 8] = mem[ad + 13'(i)];
    endcase
    return v;
  endfunction

  always @(posedge clk) begin
    // port A
    if (a_req) begin
      if (a_we) begin
        mem[a_addr] = a_wdata[7:0];
        if (a_w != 2'd0) mem[a_addr+13'd1] = a_wdata[15:8];
        if (a_w == 2'd2) for (int i = 2; i < 8; i++) mem[a_addr + 13'(i)] = a_wdata[8*i +: 8];
      end else a_rdata <= rd(a_w, a_addr);
    end
    // port B (after A, as pace-sim processes port1 before port2)
    if (b_req) begin
      if (b_we) begin
        mem[b_addr] = b_wdata[7:0];
        if (b_w != 2'd0) mem[b_addr+13'd1] = b_wdata[15:8];
        if (b_w == 2'd2) for (int i = 2; i < 8; i++) mem[b_addr + 13'(i)] = b_wdata[8*i +: 8];
      end else b_rdata <= rd(b_w, b_addr);
    end
    // host port
    if (h_we) for (int i = 0; i < 4; i++) mem[{h_widx, 2'(i)}] = h_wdata[8*i +: 8];
    if (h_re) h_rdata <= {mem[{h_widx, 2'd3}], mem[{h_widx, 2'd2}], mem[{h_widx, 2'd1}], mem[{h_widx, 2'd0}]};
  end
endmodule

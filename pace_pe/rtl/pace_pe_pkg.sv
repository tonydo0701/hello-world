// -----------------------------------------------------------------------------
// pace_pe_pkg.sv
// Shared constants for a re-created PACE-style CGRA processing element (PE).
//
// The encoding follows the configuration-word format used by the ECO Lab
// behavioural model `pace-sim` (src/isa/binary/*.rs). The RTL is a clean-room
// re-creation from that public model; it is NOT the taped-out PACE RTL.
// -----------------------------------------------------------------------------
package pace_pe_pkg;

  // Datapath
  localparam int DW       = 64;   // router / register width (8 x FP8 SIMD)
  localparam int SW       = 16;   // scalar ALU width
  localparam int CW       = 64;   // configuration word width
  localparam int CM_DEPTH = 16;   // configuration memory entries
  localparam int CM_AW    = 4;    // log2(CM_DEPTH)

  // ---------------------------------------------------------------------------
  // Configuration word bit fields (bit positions, inclusive)
  // ---------------------------------------------------------------------------
  //  63     predicate bit        (reserved, ignored)
  //  62     immediate-valid (MSB bit): op2 := imm16
  //  61     use-float            (reserved, ignored)
  //  60     ALU bypass           (reserved, ignored)
  //  59     AGU trigger          (memory PEs: start the AGU access)
  //  50:35  imm16                (non-JUMP)
  //  49:45  jump destination     (JUMP)
  //  44:40  loop end             (JUMP)
  //  39:35  loop start           (JUMP)
  //  34:30  opcode
  //  29:26  input-register write enable   {N,S,W,E}
  //  25     update result register
  //  24:21  input-register bypass (use registered input instead of wire) {N,S,W,E}
  //  20:0   switch config: 7 x 3-bit source selects
  //         [20:18] predicate  [17:15] ALU op2  [14:12] ALU op1
  //         [11:9]  north_out  [8:6]   west_out [5:3]   south_out [2:0] east_out
  localparam int B_PRED   = 63;
  localparam int B_IMMV   = 62;
  localparam int B_FLOAT  = 61;
  localparam int B_ALUBYP = 60;
  localparam int B_AGU    = 59;
  localparam int B_UPDRES = 25;

  // Router source selects (3 bits)
  localparam logic [2:0] SRC_E      = 3'd0;
  localparam logic [2:0] SRC_S      = 3'd1;
  localparam logic [2:0] SRC_W      = 3'd2;
  localparam logic [2:0] SRC_N      = 3'd3;
  localparam logic [2:0] SRC_ALUOUT = 3'd4;  // combinational ALU output (this cycle)
  localparam logic [2:0] SRC_ALURES = 3'd5;  // registered ALU result
  localparam logic [2:0] SRC_RSVD   = 3'd6;  // invalid -> treated as OPEN
  localparam logic [2:0] SRC_OPEN   = 3'd7;  // output not driven / register holds

  // Direction bit index inside the 4-bit {N,S,W,E} masks
  localparam int D_E = 0;
  localparam int D_W = 1;
  localparam int D_S = 2;
  localparam int D_N = 3;

  // Opcodes (5 bits)
  localparam logic [4:0] OP_NOP    = 5'd0;
  localparam logic [4:0] OP_ADD    = 5'd1;
  localparam logic [4:0] OP_SUB    = 5'd2;
  localparam logic [4:0] OP_MULT   = 5'd3;
  localparam logic [4:0] OP_SEXT   = 5'd4;   // defined in ISA, not modelled
  localparam logic [4:0] OP_DIV    = 5'd5;
  localparam logic [4:0] OP_VADD   = 5'd6;
  localparam logic [4:0] OP_VMUL   = 5'd7;
  localparam logic [4:0] OP_LS     = 5'd8;
  localparam logic [4:0] OP_RS     = 5'd9;
  localparam logic [4:0] OP_ASR    = 5'd10;
  localparam logic [4:0] OP_AND    = 5'd11;
  localparam logic [4:0] OP_OR     = 5'd12;
  localparam logic [4:0] OP_XOR    = 5'd13;
  localparam logic [4:0] OP_LOADD  = 5'd14;  // deprecated (AGU does memory)
  localparam logic [4:0] OP_STORED = 5'd15;  // deprecated
  localparam logic [4:0] OP_SEL    = 5'd16;
  localparam logic [4:0] OP_CMERGE = 5'd17;
  localparam logic [4:0] OP_CMP    = 5'd18;
  localparam logic [4:0] OP_CLT    = 5'd19;
  localparam logic [4:0] OP_BR     = 5'd20;  // defined in ISA, not modelled
  localparam logic [4:0] OP_CGT    = 5'd21;
  localparam logic [4:0] OP_MOVCL  = 5'd23;  // defined in ISA, not modelled
  localparam logic [4:0] OP_LOAD   = 5'd24;  // deprecated
  localparam logic [4:0] OP_LOADB  = 5'd26;  // deprecated
  localparam logic [4:0] OP_STORE  = 5'd27;  // deprecated
  localparam logic [4:0] OP_STOREB = 5'd29;  // deprecated
  localparam logic [4:0] OP_JUMP   = 5'd30;
  localparam logic [4:0] OP_MOVC   = 5'd31;  // defined in ISA, not modelled

endpackage

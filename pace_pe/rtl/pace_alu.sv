// -----------------------------------------------------------------------------
// pace_alu.sv
// PE ALU: 16-bit scalar integer ops + 8-lane FP8 SIMD (VADD / VMUL) over the
// 64-bit operand registers. Purely combinational.
//   scalar ops : op1[15:0] (op) {imm16 | op2[15:0]}, result zero-extended to 64b
//   SIMD ops   : 8 x FP8 lanes of op1 / op2 (immediate is ignored)
// -----------------------------------------------------------------------------
module pace_alu
  import pace_pe_pkg::*;
(
  input  logic [4:0]    op,
  input  logic [DW-1:0] op1,
  input  logic [DW-1:0] op2,
  input  logic          imm_en,
  input  logic [SW-1:0] imm,
  output logic [DW-1:0] alu_out,
  output logic          illegal      // opcode not implemented by this PE
);

  logic [SW-1:0] a, b, r;
  logic [DW-1:0] vadd, vmul;

  assign a = op1[SW-1:0];
  assign b = imm_en ? imm : op2[SW-1:0];

  genvar g;
  generate
    for (g = 0; g < 8; g++) begin : g_lane
      pace_fp8_lane u_add (.a(op1[8*g +: 8]), .b(op2[8*g +: 8]), .is_mul(1'b0), .y(vadd[8*g +: 8]));
      pace_fp8_lane u_mul (.a(op1[8*g +: 8]), .b(op2[8*g +: 8]), .is_mul(1'b1), .y(vmul[8*g +: 8]));
    end
  endgenerate

  always_comb begin
    r       = '0;
    alu_out = '0;
    illegal = 1'b0;
    case (op)
      OP_NOP:    r = '0;
      OP_ADD:    r = a + b;
      OP_SUB:    r = a - b;
      OP_MULT:   r = a * b;                               // low 16 bits
      OP_DIV:    r = (b == '0) ? '1 : (a / b);           // x/0 := 0xFFFF
      OP_LS:     r = a << b[3:0];
      OP_RS:     r = a >> b[3:0];
      OP_ASR:    r = $unsigned($signed(a) >>> b[3:0]);
      OP_AND:    r = a & b;
      OP_OR:     r = a | b;
      OP_XOR:    r = a ^ b;
      OP_SEL:    r = a[SW-1] ? a : (b[SW-1] ? b : '0);
      OP_CMP:    r = {{(SW-1){1'b0}}, a == b};
      OP_CLT:    r = {{(SW-1){1'b0}}, a <= b};           // unsigned, as pace-sim
      OP_CGT:    r = {{(SW-1){1'b0}}, a >= b};           // unsigned, as pace-sim
      OP_CMERGE, OP_VADD, OP_VMUL, OP_JUMP: r = '0;      // handled below
      default:   illegal = 1'b1;
    endcase

    case (op)
      OP_CMERGE: alu_out = imm_en ? {{(DW-SW){1'b0}}, imm} : op1;
      OP_ASR:    alu_out = {{(DW-SW){r[SW-1]}}, r};     // sign-extended (pace-sim)
      OP_VADD:   alu_out = vadd;
      OP_VMUL:   alu_out = vmul;
      default:   alu_out = {{(DW-SW){1'b0}}, r};
    endcase
  end

endmodule

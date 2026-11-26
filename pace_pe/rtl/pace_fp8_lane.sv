// -----------------------------------------------------------------------------
// pace_fp8_lane.sv
// One FP8 (E4M3, bias 7) add / multiply lane, bit-exact with pace-sim's FP8:
//   * exponent 0          -> signed zero (no subnormals, any mantissa)
//   * exponent 15, man 0  -> +/- infinity ; exponent 15, man != 0 -> NaN
//   * result computed exactly, then rounded once (round-to-nearest-even)
//   * underflow (biased exp <= 0 BEFORE rounding) -> signed zero
//   * overflow  (biased exp >= 15)                -> signed infinity
//   * NaN input -> 0x79 ; generated NaN (inf-inf, 0*inf) -> 0xF9
// Purely combinational.
// -----------------------------------------------------------------------------
module pace_fp8_lane (
  input  logic [7:0] a,
  input  logic [7:0] b,
  input  logic       is_mul,
  output logic [7:0] y
);

  // Normalise an exact magnitude M (value = M * 2^(p - pos(msb)) ...) whose
  // biased exponent is (msb_index + base), then round RNE to 3 mantissa bits.
  function automatic logic [7:0] fp8_norm(input logic s, input logic [17:0] m,
                                          input int base);
    int        p, e;
    logic [17:0] sh, mask;
    logic [3:0]  top;
    logic        gd, st;
    logic [3:0]  man;      // 3 bits + carry
    p = 0;
    for (int i = 0; i < 18; i++) if (m[i]) p = i;
    e = p + base;
    if (e <= 0)  return {s, 7'h00};          // flush-to-zero (before rounding)
    if (e >= 15) return {s, 7'h78};          // overflow to infinity
    if (p >= 3) begin
      sh  = m >> (p - 3);
      top = sh[3:0];
      gd  = (p >= 4) ? m[p-4] : 1'b0;
      mask = (18'h1 << (p - 4)) - 18'h1;
      st  = (p >= 5) ? |(m & mask) : 1'b0;
    end else begin
      sh  = m << (3 - p);
      top = sh[3:0];
      gd  = 1'b0;
      st  = 1'b0;
    end
    man = {1'b0, top[2:0]};
    if (gd && (st || man[0])) begin
      man = man + 4'd1;
      if (man[3]) begin                       // mantissa overflow
        man = 4'd0;
        e   = e + 1;
        if (e >= 15) return {s, 7'h78};
      end
    end
    return {s, e[3:0], man[2:0]};
  endfunction

  logic       sa, sb;
  logic [3:0] ea, eb;
  logic [2:0] ma, mb;
  logic       a_zero, b_zero, a_inf, b_inf, a_nan, b_nan;
  logic [17:0] am, bm, msum;
  logic [7:0]  prod;
  logic        sr;

  assign sa = a[7];
  assign ea = a[6:3];
  assign ma = a[2:0];
  assign sb = b[7];
  assign eb = b[6:3];
  assign mb = b[2:0];
  assign a_zero = (ea == 4'd0);
  assign b_zero = (eb == 4'd0);
  assign a_inf  = (ea == 4'hF) && (ma == 3'd0);
  assign b_inf  = (eb == 4'hF) && (mb == 3'd0);
  assign a_nan  = (ea == 4'hF) && (ma != 3'd0);
  assign b_nan  = (eb == 4'hF) && (mb != 3'd0);
  // fixed-point magnitudes, LSB weight 2^-9   ({1,m} << (e-1))
  assign am   = a_zero ? 18'd0 : (18'({1'b1, ma}) << (ea - 4'd1));
  assign bm   = b_zero ? 18'd0 : (18'({1'b1, mb}) << (eb - 4'd1));
  assign prod = {1'b1, ma} * {1'b1, mb};

  always_comb begin
    msum = 18'd0;
    sr   = 1'b0;
    y    = 8'h00;

    if (is_mul) begin
      if (a_nan || b_nan)                        y = 8'h79;
      else if ((a_inf && b_zero) || (b_inf && a_zero)) y = 8'hF9;
      else if (a_inf || b_inf)                   y = {sa ^ sb, 7'h78};
      else if (a_zero || b_zero)                 y = {sa ^ sb, 7'h00};
      else  y = fp8_norm(sa ^ sb, {10'd0, prod}, int'(ea) + int'(eb) - 13);
    end else begin
      if (a_nan || b_nan)                        y = 8'h79;
      else if (a_inf && b_inf && (sa != sb))     y = 8'hF9;
      else if (a_inf)                            y = {sa, 7'h78};
      else if (b_inf)                            y = {sb, 7'h78};
      else begin
        if (sa == sb)      begin msum = am + bm; sr = sa; end
        else if (am >= bm) begin msum = am - bm; sr = sa; end
        else               begin msum = bm - am; sr = sb; end
        if (msum == 18'd0) y = {(a_zero && b_zero) ? (sa & sb) : 1'b0, 7'h00};
        else               y = fp8_norm(sr, msum, -2);
      end
    end
  end

endmodule

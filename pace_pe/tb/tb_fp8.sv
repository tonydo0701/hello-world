// Exhaustive FP8 check: all 65536 (a,b) pairs for VADD and VMUL lanes,
// against the table produced by pace-sim's FP8 type (model/golden fp8).
`timescale 1ns/1ps
module tb_fp8;
  logic [7:0] a, b, y_add, y_mul;
  pace_fp8_lane u_add (.a(a), .b(b), .is_mul(1'b0), .y(y_add));
  pace_fp8_lane u_mul (.a(a), .b(b), .is_mul(1'b1), .y(y_mul));
  integer fd, n, errs_add, errs_mul, cnt;
  reg [7:0] ga, gb, gs, gm;
  string fname;
  initial begin
    if (!$value$plusargs("TABLE=%s", fname)) fname = "build/fp8_golden.txt";
    fd = $fopen(fname, "r");
    if (fd == 0) begin $display("FATAL: cannot open %s", fname); $finish; end
    errs_add = 0; errs_mul = 0; cnt = 0;
    while (!$feof(fd)) begin
      n = $fscanf(fd, "%h %h %h %h\n", ga, gb, gs, gm);
      if (n == 4) begin
        a = ga; b = gb; #1;
        if (y_add !== gs) begin
          if (errs_add < 10) $display("VADD MISMATCH a=%02h b=%02h rtl=%02h gold=%02h", a, b, y_add, gs);
          errs_add++;
        end
        if (y_mul !== gm) begin
          if (errs_mul < 10) $display("VMUL MISMATCH a=%02h b=%02h rtl=%02h gold=%02h", a, b, y_mul, gm);
          errs_mul++;
        end
        cnt++;
      end
    end
    $display("FP8 exhaustive: %0d pairs, VADD errors=%0d, VMUL errors=%0d -> %s",
             cnt, errs_add, errs_mul, (errs_add + errs_mul == 0 && cnt == 65536) ? "PASS" : "FAIL");
    $finish;
  end
endmodule

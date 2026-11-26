// Array testbench: acts as the RISC-V host over the APB-style port.
//   1. replays a host write list (+IMG=...) produced by scripts/cgra_image.py
//   2. writes CTRL.START, then dumps a per-cycle trace of all 64 PEs
//      ("pc op1 op2 res" each, row-major) for every committed cycle
//   3. waits for STATUS.DONE (AGU end) or +MAXCYC, then reads all 8 data
//      memories back over the bus into +DMOUT<d> (one 64-bit word per line)
`timescale 1ns/1ps
module tb_cgra;
  logic clk = 0, rst_n = 0;
  logic psel = 0, penable = 0, pwrite = 0;
  logic [18:0] paddr = 0; logic [31:0] pwdata = 0, prdata;
  logic pready, irq;
  always #5 clk = ~clk;

  pace_cgra dut (.clk, .rst_n, .psel, .penable, .pwrite, .paddr, .pwdata, .prdata, .pready, .irq);

  task automatic apb_write(input logic [18:0] a, input logic [31:0] d);
    @(negedge clk); psel = 1; penable = 0; pwrite = 1; paddr = a; pwdata = d;
    @(negedge clk); penable = 1;
    @(negedge clk); psel = 0; penable = 0; pwrite = 0;
  endtask
  task automatic apb_read(input logic [18:0] a, output logic [31:0] d);
    @(negedge clk); psel = 1; penable = 0; pwrite = 0; paddr = a;
    @(negedge clk); penable = 1; #1 d = prdata;
    @(negedge clk); psel = 0; penable = 0;
  endtask

  // flattened observation of every PE
  logic [3:0]  pc  [64];
  logic [63:0] op1 [64], op2 [64], res [64];
  genvar gy, gx;
  generate for (gy = 0; gy < 8; gy++) for (gx = 0; gx < 8; gx++) begin : g_obs
    assign pc [gy*8+gx] = dut.g_y[gy].g_x[gx].u_pe.dbg_pc;
    assign op1[gy*8+gx] = dut.g_y[gy].g_x[gx].u_pe.dbg_op1;
    assign op2[gy*8+gx] = dut.g_y[gy].g_x[gx].u_pe.dbg_op2;
    assign res[gy*8+gx] = dut.g_y[gy].g_x[gx].u_pe.dbg_res;
  end endgenerate

  string fimg, ftrace, fdm;
  integer fd, fo, n, maxcyc, cyc, k;
  logic [18:0] a; logic [31:0] d, lo, hi, st;
  logic [3:0] pcs [64];
  logic was_commit, fin;
  string line;

  initial begin
    void'($value$plusargs("IMG=%s", fimg));
    void'($value$plusargs("TRACE=%s", ftrace));
    void'($value$plusargs("DMOUT=%s", fdm));
    if (!$value$plusargs("MAXCYC=%d", maxcyc)) maxcyc = 0;
    repeat (3) @(posedge clk); rst_n = 1;

    apb_read(19'h60010, d);
    $display("CGRA ID = 0x%08h", d);
    fd = $fopen(fimg, "r"); n = 0;
    while (!$feof(fd)) if ($fscanf(fd, "%h %h\n", a, d) == 2) begin apb_write(a, d); n++; end
    $fclose(fd);
    $display("loaded %0d host writes", n);

    fo = $fopen(ftrace, "w");
    apb_write(19'h60014, maxcyc);                // RUN_LIMIT (0 = until AGU end)
    apb_write(19'h60000, 32'h1);                 // CTRL.START
    cyc = 0;
    wait (dut.running);
    fin = 0;
    while (!fin) begin
      @(negedge clk);
      for (k = 0; k < 64; k++) pcs[k] = pc[k];
      was_commit = dut.commit;
      if (!dut.running) fin = 1;
      else begin
        @(posedge clk); #1;
        if (was_commit) begin
          line = "";
          for (k = 0; k < 64; k++)
            line = {line, $sformatf("%0h %0h %0h %0h", pcs[k], op1[k], op2[k], res[k]), (k < 63) ? " " : ""};
          $fdisplay(fo, "%s", line);
          cyc++;
        end
      end
    end
    $fclose(fo);
    apb_read(19'h60004, st);
    apb_read(19'h60008, d);
    $display("STATUS=0x%0h (busy,done,stopped) CYCLES=%0d traced=%0d", st, d, cyc);

    for (int dm = 0; dm < 8; dm++) begin
      fo = $fopen($sformatf("%s%0d", fdm, dm), "w");
      for (int w = 0; w < 1024; w++) begin
        apb_read(19'h20000 | (dm / 4) << 16 | (dm % 4) << 14 | (w << 3),     lo);
        apb_read(19'h20000 | (dm / 4) << 16 | (dm % 4) << 14 | (w << 3) | 4, hi);
        $fdisplay(fo, "%016h", {hi, lo});
      end
      $fclose(fo);
    end
    $finish;
  end
endmodule

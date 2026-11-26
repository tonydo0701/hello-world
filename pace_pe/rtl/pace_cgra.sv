// -----------------------------------------------------------------------------
// pace_cgra.sv
// 8 x 8 PACE-style CGRA: 64 PEs in a mesh, 8 data memories (4 on the left
// edge, 4 on the right edge, each 8 KB, shared by two rows), 16 AGUs (one per
// edge PE), and a 32-bit memory-mapped host port (APB-style) through which a
// RISC-V core configures, starts and reads back the array.
//
// Host address map (byte addresses, 19-bit window, 32-bit accesses):
//   [18:17]=00  PE space, [15:10] = PE index (y*8 + x)
//       [9:8]=00 PE config memory   entry [6:3], word [2] (0 = bits 31:0, 1 = bits 63:32;
//                                   write the low word first, the high word commits)
//       [9:8]=01 AGU CM             entry [5:2]       (edge PEs x = 0 / 7 only)
//       [9:8]=10 AGU ARF            entry [5:2]
//       [9:8]=11 AGU MAX            [31:24] last CM entry, [23:0] iterations
//   [18:17]=01  data memory, [16] 0 = left / 1 = right, [15:14] DM on that side
//                (top to bottom), [12:0] byte offset
//   [18:17]=11  control:  +0x0 CTRL   W: bit0 START, bit1 STOP
//                         +0x4 STATUS R: bit0 BUSY, bit1 DONE (W1C), bit2 STOPPED
//                         +0x8 CYCLES R: cycles of the last / current run
//                         +0xC IRQ_EN bit0: raise irq when DONE or STOPPED
//                         +0x10 ID    R: 0x0000013E (PACE id from FLEX globals_top.vh)
//                         +0x14 RUN_LIMIT  0 = run until AGU end, else stop after N cycles
// Matches the PE / DM fields used by pace-sim's dump_header.rs (the C header
// generated for the IME RISC-V system simulation).
// -----------------------------------------------------------------------------
module pace_cgra
  import pace_pe_pkg::*;
#(
  parameter bit PACESIM_FWD = 1'b1
)(
  input  logic        clk,
  input  logic        rst_n,
  // APB-style host slave (pready is always 1: zero wait states)
  input  logic        psel,
  input  logic        penable,
  input  logic        pwrite,
  input  logic [18:0] paddr,
  input  logic [31:0] pwdata,
  output logic [31:0] prdata,
  output logic        pready,
  output logic        irq
);
  localparam int N = 8;

  // ---------------------------------------------------------------------------
  // Run control
  // ---------------------------------------------------------------------------
  logic running, clr, done, stopped, irq_en;
  logic [31:0] cycles, run_limit;
  logic end_any;
  logic commit;                       // state updates happen this cycle
  assign commit = running && !end_any;

  // ---------------------------------------------------------------------------
  // Host decode
  // ---------------------------------------------------------------------------
  logic wr, rd_setup;
  assign wr       = psel && penable && pwrite;
  assign rd_setup = psel && !penable && !pwrite;
  assign pready   = 1'b1;

  logic [1:0]  h_tgt;
  logic [5:0]  h_pe;
  logic [1:0]  h_reg;
  assign h_tgt = paddr[18:17];
  assign h_pe  = paddr[15:10];
  assign h_reg = paddr[9:8];

  logic [31:0] cm_lo_shadow;
  always_ff @(posedge clk) if (wr && h_tgt == 2'b00 && h_reg == 2'b00 && !paddr[2]) cm_lo_shadow <= pwdata;

  logic        pe_cm_we  [64];
  logic        agu_cm_we [16], agu_arf_we [16], agu_max_we [16];
  always_comb begin
    for (int i = 0; i < 64; i++) pe_cm_we[i] = wr && h_tgt == 2'b00 && h_reg == 2'b00 && paddr[2] && h_pe == 6'(i);
    for (int a = 0; a < 16; a++) begin
      // AGU a belongs to PE (row a%8, column 0) for a < 8, column 7 otherwise
      agu_cm_we[a]  = wr && h_tgt == 2'b00 && h_pe == 6'((a % N) * N + ((a < N) ? 0 : N - 1)) && h_reg == 2'b01;
      agu_arf_we[a] = wr && h_tgt == 2'b00 && h_pe == 6'((a % N) * N + ((a < N) ? 0 : N - 1)) && h_reg == 2'b10;
      agu_max_we[a] = wr && h_tgt == 2'b00 && h_pe == 6'((a % N) * N + ((a < N) ? 0 : N - 1)) && h_reg == 2'b11;
    end
  end

  // control registers
  logic ctl_wr, ctl_start, ctl_stop;
  assign ctl_wr    = wr && h_tgt == 2'b11;
  assign ctl_start = ctl_wr && paddr[4:2] == 3'd0 && pwdata[0];
  assign ctl_stop  = ctl_wr && paddr[4:2] == 3'd0 && pwdata[1];

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      running <= 1'b0; clr <= 1'b0; done <= 1'b0; stopped <= 1'b0; irq_en <= 1'b0; cycles <= '0; run_limit <= '0;
    end else begin
      clr <= 1'b0;
      if (ctl_start && !running && !clr) begin
        clr <= 1'b1; done <= 1'b0; stopped <= 1'b0; cycles <= '0;
      end
      if (clr) running <= 1'b1;
      if (running) begin
        if (end_any) begin running <= 1'b0; done <= 1'b1; end
        else begin
          cycles <= cycles + 32'd1;
          if (run_limit != 0 && cycles + 32'd1 == run_limit) begin running <= 1'b0; stopped <= 1'b1; end
        end
        if (ctl_stop) begin running <= 1'b0; stopped <= 1'b1; end
      end
      if (ctl_wr && paddr[4:2] == 3'd1 && pwdata[1]) done <= 1'b0;
      if (ctl_wr && paddr[4:2] == 3'd3) irq_en <= pwdata[0];
      if (ctl_wr && paddr[4:2] == 3'd5) run_limit <= pwdata;
    end
  end
  assign irq = irq_en && (done || stopped);

  // ---------------------------------------------------------------------------
  // PE mesh
  // ---------------------------------------------------------------------------
  logic [DW-1:0] o_n [64], o_s [64], o_w [64], o_e [64];
  logic          trig [64];
  logic [DW-1:0] st   [64];
  logic          ldv  [64];
  logic [DW-1:0] ldd  [64];
  logic          pe_rst_n;
  assign pe_rst_n = rst_n && !clr;

  genvar gy, gx;
  generate
    for (gy = 0; gy < N; gy++) begin : g_y
      for (gx = 0; gx < N; gx++) begin : g_x
        localparam int I = gy * N + gx;
        logic [DW-1:0] i_n, i_s, i_w, i_e;
        // array boundary inputs are tied to 0
        if (gy > 0)     begin : g_n assign i_n = o_s[I-N]; end else begin : g_n0 assign i_n = '0; end
        if (gy < N - 1) begin : g_s assign i_s = o_n[I+N]; end else begin : g_s0 assign i_s = '0; end
        if (gx > 0)     begin : g_w assign i_w = o_e[I-1]; end else begin : g_w0 assign i_w = '0; end
        if (gx < N - 1) begin : g_e assign i_e = o_w[I+1]; end else begin : g_e0 assign i_e = '0; end
        pace_pe #(.MEM_PE(gx == 0 || gx == N - 1), .PACESIM_FWD(PACESIM_FWD)) u_pe (
          .clk(clk), .rst_n(pe_rst_n), .exec_en(commit),
          .cm_we(pe_cm_we[I]), .cm_waddr(paddr[6:3]), .cm_wdata({pwdata, cm_lo_shadow}),
          .in_n(i_n), .in_s(i_s), .in_w(i_w), .in_e(i_e),
          .out_n(o_n[I]), .out_s(o_s[I]), .out_w(o_w[I]), .out_e(o_e[I]),
          .agu_trigger(trig[I]), .st_data(st[I]), .ld_valid(ldv[I]), .ld_data(ldd[I]),
          .dbg_pc(), .dbg_alu_out(), .dbg_op1(), .dbg_op2(), .dbg_res(),
          .dbg_q_n(), .dbg_q_s(), .dbg_q_w(), .dbg_q_e(),
          .dbg_loop_start(), .dbg_loop_end(), .dbg_illegal());
      end
    end
  endgenerate

  // ---------------------------------------------------------------------------
  // AGUs (a = y for the left column, a = 8 + y for the right column)
  // ---------------------------------------------------------------------------
  logic        a_end [16], a_req [16], a_st [16];
  logic [1:0]  a_w   [16];
  logic [12:0] a_ad  [16];
  logic        a_trig[16];

  generate
    for (genvar a = 0; a < 16; a++) begin : g_agu
      localparam int PE = (a % N) * N + ((a < N) ? 0 : N - 1);
      assign a_trig[a] = running && trig[PE];
      pace_agu u_agu (
        .clk(clk), .rst_n(rst_n), .clr(clr),
        .cm_we(agu_cm_we[a]),   .cm_waddr(paddr[5:2]),  .cm_wdata(pwdata[7:0]),
        .arf_we(agu_arf_we[a]), .arf_waddr(paddr[5:2]), .arf_wdata(pwdata[12:0]),
        .max_we(agu_max_we[a]), .max_wdata(pwdata),
        .trigger(a_trig[a]), .commit(commit), .end_o(a_end[a]),
        .req(a_req[a]), .is_store(a_st[a]), .width(a_w[a]), .addr(a_ad[a]));
    end
  endgenerate

  always_comb begin
    end_any = 1'b0;
    for (int a = 0; a < 16; a++) end_any |= a_end[a];
  end

  // ---------------------------------------------------------------------------
  // Data memories (d = 0..3 left top->bottom, 4..7 right top->bottom)
  // port A <- PE row 2k, port B <- PE row 2k+1
  // ---------------------------------------------------------------------------
  logic [31:0] dm_hrdata [8];
  logic [2:0]  h_dm;
  assign h_dm = {paddr[16], paddr[15:14]};

  generate
    for (genvar d = 0; d < 8; d++) begin : g_dm
      localparam int AA = (d % 4) * 2 + ((d < 4) ? 0 : N);   // AGU of the upper row
      localparam int AB = AA + 1;
      localparam int PA = (AA % N) * N + ((d < 4) ? 0 : N - 1);
      localparam int PB = PA + N;
      logic [63:0] ra, rb;
      logic        lva, lvb;        // a load was issued last cycle
      pace_dmem u_dm (
        .clk(clk),
        .a_req(a_req[AA] && commit), .a_we(a_st[AA]), .a_w(a_w[AA]), .a_addr(a_ad[AA]),
        .a_wdata(st[PA]), .a_rdata(ra),
        .b_req(a_req[AB] && commit), .b_we(a_st[AB]), .b_w(a_w[AB]), .b_addr(a_ad[AB]),
        .b_wdata(st[PB]), .b_rdata(rb),
        .h_re(rd_setup && h_tgt == 2'b01 && h_dm == 3'(d)),
        .h_we(wr && h_tgt == 2'b01 && h_dm == 3'(d)),
        .h_widx(paddr[12:2]), .h_wdata(pwdata), .h_rdata(dm_hrdata[d]));
      always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)      begin lva <= 1'b0; lvb <= 1'b0; end
        else if (clr)    begin lva <= 1'b0; lvb <= 1'b0; end
        else if (running) begin
          lva <= a_req[AA] && commit && !a_st[AA];
          lvb <= a_req[AB] && commit && !a_st[AB];
        end
      end
      assign ldv[PA] = lva;  assign ldd[PA] = ra;
      assign ldv[PB] = lvb;  assign ldd[PB] = rb;
    end
  endgenerate

  // non-memory PEs: no load path
  generate
    for (genvar i = 0; i < 64; i++) begin : g_nomem
      if (i % N != 0 && i % N != N - 1) begin : g_tie
        assign ldv[i] = 1'b0;
        assign ldd[i] = '0;
      end
    end
  endgenerate

  // ---------------------------------------------------------------------------
  // Read data
  // ---------------------------------------------------------------------------
  logic [18:0] raddr_q;
  always_ff @(posedge clk) if (rd_setup) raddr_q <= paddr;
  always_comb begin
    prdata = '0;
    case (raddr_q[18:17])
      2'b01: prdata = dm_hrdata[{raddr_q[16], raddr_q[15:14]}];
      2'b11: case (raddr_q[4:2])
               3'd1: prdata = {29'd0, stopped, done, running || clr};
               3'd2: prdata = cycles;
               3'd3: prdata = {31'd0, irq_en};
               3'd4: prdata = 32'h0000_013E;
               3'd5: prdata = run_limit;
               default: prdata = '0;
             endcase
      default: prdata = '0;
    endcase
  end

endmodule

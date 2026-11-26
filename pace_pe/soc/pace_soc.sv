// -----------------------------------------------------------------------------
// pace_soc.sv
// Minimal RISC-V + CGRA system, in the shape of the PACE SoC: a RISC-V core
// is the host/controller and the CGRA is a memory-mapped accelerator.
//
//   CPU view (PicoRV32, RV32IM):
//     0x0000_0000  64 KB RAM (firmware, stack, kernel image)
//     0x1000_0000  CGRA window, 512 KB  -> pace_cgra host port (APB-style)
//                  (CPU byte address [18:0] = CGRA host address)
//     0x2000_0000  console: +0 write = putchar, +4 write = exit(code)
//   cgra_irq is wired to PicoRV32 IRQ line 3 (the firmware below polls STATUS;
//   it enables the IRQ so the line is visible in the waveform).
// -----------------------------------------------------------------------------
module pace_soc #(
  parameter string FW = "soc/fw/firmware.hex"   // path relative to the run directory
)(
  input  logic clk,
  input  logic rst_n,
  output logic [7:0] con_data,
  output logic       con_valid,
  output logic       exit_valid,
  output logic [31:0] exit_code
);
  // ---------------- CPU ----------------
  logic        mem_valid, mem_instr, mem_ready;
  logic [31:0] mem_addr, mem_wdata, mem_rdata;
  logic [3:0]  mem_wstrb;
  logic        cgra_irq;
  logic [31:0] irq;
  assign irq = {28'd0, cgra_irq, 3'd0};

  picorv32 #(
    .ENABLE_MUL(1), .ENABLE_DIV(1), .ENABLE_IRQ(1), .PROGADDR_RESET(32'h0),
    .STACKADDR(32'h0001_0000)
  ) u_cpu (
    .clk(clk), .resetn(rst_n), .trap(),
    .mem_valid(mem_valid), .mem_instr(mem_instr), .mem_ready(mem_ready),
    .mem_addr(mem_addr), .mem_wdata(mem_wdata), .mem_wstrb(mem_wstrb), .mem_rdata(mem_rdata),
    .mem_la_read(), .mem_la_write(), .mem_la_addr(), .mem_la_wdata(), .mem_la_wstrb(),
    .pcpi_valid(), .pcpi_insn(), .pcpi_rs1(), .pcpi_rs2(),
    .pcpi_wr(1'b0), .pcpi_rd(32'd0), .pcpi_wait(1'b0), .pcpi_ready(1'b0),
    .irq(irq), .eoi(),
    .trace_valid(), .trace_data()
  );

  // ---------------- RAM ----------------
  logic [31:0] ram [16384];
  initial $readmemh(FW, ram);
  logic        sel_ram, sel_cgra, sel_con;
  assign sel_ram  = mem_addr[31:28] == 4'h0;
  assign sel_cgra = mem_addr[31:28] == 4'h1;
  assign sel_con  = mem_addr[31:28] == 4'h2;

  logic        ram_ready;
  logic [31:0] ram_rdata;
  always_ff @(posedge clk) begin
    ram_ready <= 1'b0;
    if (mem_valid && sel_ram && !ram_ready) begin
      ram_ready <= 1'b1;
      ram_rdata <= ram[mem_addr[15:2]];
      for (int i = 0; i < 4; i++)
        if (mem_wstrb[i]) ram[mem_addr[15:2]][8*i +: 8] <= mem_wdata[8*i +: 8];
    end
  end

  // ---------------- bridge: PicoRV32 native bus -> APB ----------------
  logic        psel, penable, pwrite, pready;
  logic [18:0] paddr;
  logic [31:0] pwdata, prdata;
  logic        apb_done;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin psel <= 0; penable <= 0; apb_done <= 0; end
    else begin
      apb_done <= 1'b0;
      if (mem_valid && sel_cgra && !psel && !apb_done) begin       // SETUP
        psel <= 1'b1; penable <= 1'b0;
        pwrite <= |mem_wstrb; paddr <= mem_addr[18:0]; pwdata <= mem_wdata;
      end else if (psel && !penable) penable <= 1'b1;               // ACCESS
      else if (psel && penable && pready) begin psel <= 1'b0; penable <= 1'b0; apb_done <= 1'b1; end
    end
  end
  logic [31:0] cgra_rdata_q;
  always_ff @(posedge clk) if (psel && penable) cgra_rdata_q <= prdata;

  pace_cgra u_cgra (
    .clk(clk), .rst_n(rst_n), .psel(psel), .penable(penable), .pwrite(pwrite),
    .paddr(paddr), .pwdata(pwdata), .prdata(prdata), .pready(pready), .irq(cgra_irq));

  // ---------------- console ----------------
  logic con_ready;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin con_ready <= 0; con_valid <= 0; exit_valid <= 0; end
    else begin
      con_ready <= mem_valid && sel_con && !con_ready;
      con_valid <= 1'b0;
      if (mem_valid && sel_con && !con_ready && |mem_wstrb) begin
        if (mem_addr[2]) begin exit_valid <= 1'b1; exit_code <= mem_wdata; end
        else begin con_valid <= 1'b1; con_data <= mem_wdata[7:0]; end
      end
    end
  end

  assign mem_ready = ram_ready || apb_done || con_ready;
  assign mem_rdata = ram_ready ? ram_rdata : apb_done ? cgra_rdata_q : 32'd0;
endmodule

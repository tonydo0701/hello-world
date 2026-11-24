// Generic testbench for a generated matvec module.
// Defines (set by the test runner): DUT, N, K, NV, XFILE, YFILE.
// Reads NV input vectors, runs each through the DUT, writes each y as hex.
`timescale 1ns/1ps
module tb_matvec;
    localparam XW = 8, AW = 32;
    reg clk = 0, rst = 1, start = 0;
    reg  [`K*XW-1:0] x;
    wire [`N*AW-1:0] y;
    wire busy, done;

    reg [`K*XW-1:0] xmem [0:`NV-1];
    integer v, fd, cycles;

    `DUT dut (.clk(clk), .rst(rst), .start(start), .x(x), .busy(busy), .done(done), .y(y));

    always #5 clk = ~clk;

    initial begin
        $readmemh(`XFILE, xmem);
        fd = $fopen(`YFILE, "w");
        repeat (2) @(posedge clk);
        rst <= 0;
        for (v = 0; v < `NV; v = v + 1) begin
            x <= xmem[v];
            @(posedge clk) start <= 1;
            @(posedge clk) start <= 0;
            cycles = 1;
            while (!done) begin @(posedge clk); cycles = cycles + 1; end
            $fwrite(fd, "%h\n", y);
        end
        $fclose(fd);
        $display("CYCLES_PER_MATVEC %0d", cycles);
        $finish;
    end

    initial begin #100000000; $display("TIMEOUT"); $finish; end
endmodule

// Testbench for the narrow-interface <name>_top wrapper.
// Defines: DUT (the _top module), N, K, NV, XFILE, YFILE.
`timescale 1ns/1ps
module tb_matvec_top;
    localparam XW = 8, AW = 32;
    localparam XA = (`K > 1) ? $clog2(`K) : 1;
    localparam YA = (`N > 1) ? $clog2(`N) : 1;
    reg clk = 0, rst = 1, start = 0, x_we = 0;
    reg  [XA-1:0] x_addr = 0;
    reg  [XW-1:0] x_data = 0;
    reg  [YA-1:0] y_addr = 0;
    wire [AW-1:0] y_data;
    wire busy, done;

    reg [`K*XW-1:0] xmem [0:`NV-1];
    reg [`N*AW-1:0] yv;
    integer v, j, fd;

    `DUT dut (.clk(clk), .rst(rst), .x_we(x_we), .x_addr(x_addr), .x_data(x_data),
              .start(start), .busy(busy), .done(done), .y_addr(y_addr), .y_data(y_data));

    always #5 clk = ~clk;

    initial begin
        $readmemh(`XFILE, xmem);
        fd = $fopen(`YFILE, "w");
        repeat (2) @(posedge clk);
        rst <= 0;
        for (v = 0; v < `NV; v = v + 1) begin
            for (j = 0; j < `K; j = j + 1) begin          // load x, one element per cycle
                @(posedge clk);
                x_we <= 1; x_addr <= j; x_data <= xmem[v][j*XW +: XW];
            end
            @(posedge clk) begin x_we <= 0; start <= 1; end
            @(posedge clk) start <= 0;
            while (!done) @(posedge clk);
            for (j = 0; j < `N; j = j + 1) begin          // read y, one word per cycle
                y_addr <= j;
                @(posedge clk); @(posedge clk);
                yv[j*AW +: AW] = y_data;
            end
            $fwrite(fd, "%h\n", yv);
        end
        $fclose(fd);
        $display("CYCLES_PER_MATVEC 0");
        $finish;
    end
endmodule

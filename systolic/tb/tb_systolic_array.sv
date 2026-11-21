// Self-checking testbench: random signed matrices, compare with a reference.
`timescale 1ns/1ps
module tb_systolic_array;
    localparam N = 4, DW = 8, AW = 32, K = 4, TESTS = 50;

    logic clk = 0, rst = 1, clear = 0;
    logic [N*DW-1:0]   a_col, b_row;
    logic [N*N*AW-1:0] c_flat;

`ifdef GLS
    systolic_array dut (.*);   // synthesized netlist: parameters are baked in
`else
    systolic_array #(.N(N), .DW(DW), .AW(AW)) dut (.*);
`endif

    always #5 clk = ~clk;

    logic signed [DW-1:0] A [N][K];
    logic signed [DW-1:0] B [K][N];
    int errors = 0;

    task automatic run_test(int t);
        // Random inputs; test 0 uses extremes to check signed overflow paths.
        for (int i = 0; i < N; i++)
            for (int k = 0; k < K; k++) begin
                A[i][k] = (t == 0) ? -128 : $urandom;
                B[k][i] = (t == 0) ? -128 : $urandom;
            end

        @(negedge clk) clear = 1; a_col = '0; b_row = '0;
        @(negedge clk) clear = 0;
        for (int k = 0; k < K; k++) begin
            for (int i = 0; i < N; i++) begin
                a_col[i*DW +: DW] = A[i][k];
                b_row[i*DW +: DW] = B[k][i];
            end
            @(negedge clk);
        end
        a_col = '0; b_row = '0;
        repeat (3*N) @(negedge clk);

        for (int i = 0; i < N; i++)
            for (int j = 0; j < N; j++) begin
                int exp_v = 0;
                int got;
                for (int k = 0; k < K; k++) exp_v += A[i][k] * B[k][j];
                got = $signed(c_flat[(i*N+j)*AW +: AW]);
                if (got !== exp_v) begin
                    errors++;
                    $display("FAIL test %0d C[%0d][%0d]: got %0d expected %0d", t, i, j, got, exp_v);
                end
            end
    endtask

    initial begin
        a_col = '0; b_row = '0;
        repeat (3) @(negedge clk);
        rst = 0;
        for (int t = 0; t < TESTS; t++) run_test(t);
        if (errors == 0) $display("PASS: %0d random %0dx%0d matrix products", TESTS, N, N);
        else             $display("FAILED: %0d mismatches", errors);
        $finish;
    end
endmodule

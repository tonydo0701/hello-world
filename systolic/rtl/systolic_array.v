`timescale 1ns/1ps
// N x N output-stationary systolic array computing C = A * B.
//
// Interface: on each cycle k (k = 0 .. K-1) drive
//   a_col = column k of A  (a_col[i] = A[i][k])
//   b_row = row    k of B  (b_row[j] = B[k][j])
// then drive zeros. The array skews the inputs internally (row i of A and
// column j of B are delayed by i and j cycles), so the caller does not.
// C[i][j] is valid in c_flat 2N-1 clock edges after the last input cycle.
// Assert `clear` for one cycle before a new matrix product.
module systolic_array #(
    parameter N  = 4,
    parameter DW = 8,
    parameter AW = 32
) (
    input  wire              clk,
    input  wire              rst,
    input  wire              clear,
    input  wire [N*DW-1:0]   a_col,   // a_col[i*DW +: DW] = A[i][k]
    input  wire [N*DW-1:0]   b_row,   // b_row[j*DW +: DW] = B[k][j]
    output wire [N*N*AW-1:0] c_flat   // c_flat[(i*N+j)*AW +: AW] = C[i][j]
);

    // Horizontal (A) and vertical (B) links between PEs.
    wire [DW-1:0] a_link [0:N-1][0:N];
    wire [DW-1:0] b_link [0:N][0:N-1];

    genvar i, j, d;
    generate
        // Input skew: lane i is delayed by i cycles.
        for (i = 0; i < N; i = i + 1) begin : g_skew
            if (i == 0) begin : g_nodelay
                assign a_link[0][0] = a_col[0 +: DW];
                assign b_link[0][0] = b_row[0 +: DW];
            end else begin : g_delay
                reg [DW-1:0] a_sr [0:i-1];
                reg [DW-1:0] b_sr [0:i-1];
                for (d = 0; d < i; d = d + 1) begin : g_stage
                    always @(posedge clk) begin
                        if (rst) begin
                            a_sr[d] <= 0;
                            b_sr[d] <= 0;
                        end else begin
                            a_sr[d] <= (d == 0) ? a_col[i*DW +: DW] : a_sr[d-1];
                            b_sr[d] <= (d == 0) ? b_row[i*DW +: DW] : b_sr[d-1];
                        end
                    end
                end
                assign a_link[i][0] = a_sr[i-1];
                assign b_link[0][i] = b_sr[i-1];
            end
        end

        // PE grid.
        for (i = 0; i < N; i = i + 1) begin : g_row
            for (j = 0; j < N; j = j + 1) begin : g_col
                pe #(.DW(DW), .AW(AW)) u_pe (
                    .clk   (clk),
                    .rst   (rst),
                    .clear (clear),
                    .a_in  (a_link[i][j]),
                    .b_in  (b_link[i][j]),
                    .a_out (a_link[i][j+1]),
                    .b_out (b_link[i+1][j]),
                    .acc   (c_flat[(i*N+j)*AW +: AW])
                );
            end
        end
    endgenerate
endmodule

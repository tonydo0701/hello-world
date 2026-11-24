// matvec_core: y = W * x, with W supplied by an external constant ROM.
//
// Column-serial with parallelism P: each cycle the core reads P columns of W
// (all N rows) from the ROM and does N*P multiply-accumulates.
// A full matrix-vector product takes K/P cycles.
//
//   x    : K signed XW-bit activations, packed, x[j] = x[j*XW +: XW]
//   grp  : column-group index sent to the ROM (columns grp*P .. grp*P+P-1)
//   wgrp : P*N signed WW-bit weights from the ROM,
//          weight W[i][grp*P+p] = wgrp[(p*N+i)*WW +: WW]
//   y    : N signed AW-bit results, packed, valid when done pulses
//
// Protocol: pulse start for one cycle with x held stable until done.
// done pulses for one cycle when y is valid; y holds until the next start.
module matvec_core #(
    parameter N  = 64,   // output features (rows of W)
    parameter K  = 64,   // input features (columns of W)
    parameter P  = 1,    // columns processed per cycle, K % P == 0
    parameter XW = 8,    // activation width
    parameter WW = 4,    // weight width
    parameter AW = 32    // accumulator width
) (
    input  wire              clk,
    input  wire              rst,
    input  wire              start,
    input  wire [K*XW-1:0]   x,
    output wire [GW-1:0]     grp,
    input  wire [P*N*WW-1:0] wgrp,
    output reg               busy,
    output reg               done,
    output wire [N*AW-1:0]   y
);
    localparam G  = K / P;                        // number of column groups
    localparam GW = (G > 1) ? $clog2(G) : 1;      // width of group index

    reg [GW-1:0] g;
    assign grp = g;

    reg signed [AW-1:0] acc [0:N-1];

    // Sum of the P products for each row in the current group (combinational).
    reg signed [AW-1:0] psum [0:N-1];
    integer i, p;
    always @* begin
        for (i = 0; i < N; i = i + 1) begin
            psum[i] = 0;
            for (p = 0; p < P; p = p + 1)
                psum[i] = psum[i]
                        + $signed(wgrp[(p*N+i)*WW +: WW]) * $signed(x[(g*P+p)*XW +: XW]);
        end
    end

    always @(posedge clk) begin
        done <= 1'b0;
        if (rst) begin
            busy <= 1'b0;
            g    <= 0;
            for (i = 0; i < N; i = i + 1) acc[i] <= 0;
        end else if (start && !busy) begin
            busy <= 1'b1;
            g    <= 0;
            for (i = 0; i < N; i = i + 1) acc[i] <= 0;
        end else if (busy) begin
            for (i = 0; i < N; i = i + 1) acc[i] <= acc[i] + psum[i];
            if (g == G - 1) begin
                busy <= 1'b0;
                done <= 1'b1;
            end else begin
                g <= g + 1'b1;
            end
        end
    end

    genvar gi;
    generate
        for (gi = 0; gi < N; gi = gi + 1) begin : g_out
            assign y[gi*AW +: AW] = acc[gi];
        end
    endgenerate
endmodule

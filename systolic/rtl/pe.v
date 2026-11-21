`timescale 1ns/1ps
// Processing element for an output-stationary systolic array.
// Each cycle: acc += a_in * b_in, then a passes right and b passes down.
module pe #(
    parameter DW = 8,   // input data width (signed)
    parameter AW = 32   // accumulator width (signed)
) (
    input  wire                 clk,
    input  wire                 rst,     // synchronous reset
    input  wire                 clear,   // zero the accumulator
    input  wire signed [DW-1:0] a_in,
    input  wire signed [DW-1:0] b_in,
    output reg  signed [DW-1:0] a_out,
    output reg  signed [DW-1:0] b_out,
    output reg  signed [AW-1:0] acc
);
    always @(posedge clk) begin
        if (rst) begin
            a_out <= 0;
            b_out <= 0;
            acc   <= 0;
        end else begin
            a_out <= a_in;
            b_out <= b_in;
            if (clear)
                acc <= 0;
            else
                acc <= acc + a_in * b_in;
        end
    end
endmodule

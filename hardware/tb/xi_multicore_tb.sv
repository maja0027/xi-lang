// ═══════════════════════════════════════════════════════════════
// Ξ (Xi) — Multi-Core Testbench
// Copyright (c) 2026 Alex P. Slaby — MIT License
//
// Smoke test: load a simple graph, start reduction, check done.
// ═══════════════════════════════════════════════════════════════

`timescale 1ns / 1ps

module xi_multicore_tb;

    parameter N_CORES   = 4;
    parameter ADDR_W    = 16;
    parameter MEM_DEPTH = 4096;

    logic clk, rst_n;
    logic host_start;
    logic [ADDR_W-1:0] host_entry;
    logic host_done;
    logic [31:0] host_cycles, host_reductions;
    logic ext_rd_en;
    logic [ADDR_W-1:0] ext_rd_addr;
    logic [159:0] ext_rd_data;
    logic ext_rd_valid;
    logic ext_wr_en;
    logic [ADDR_W-1:0] ext_wr_addr;
    logic [159:0] ext_wr_data;
    logic [N_CORES-1:0] dbg_idle;
    logic [31:0] dbg_hits, dbg_misses;

    // External memory model
    logic [159:0] ext_mem [MEM_DEPTH];

    // Clock: 100 MHz
    initial clk = 0;
    always #5 clk = ~clk;

    // DUT
    xi_multicore_top #(
        .N_CORES(N_CORES),
        .ADDR_W(ADDR_W),
        .MEM_DEPTH(MEM_DEPTH)
    ) dut (
        .clk(clk), .rst_n(rst_n),
        .host_start(host_start),
        .host_entry_addr(host_entry),
        .host_done(host_done),
        .host_cycles(host_cycles),
        .host_total_reductions(host_reductions),
        .ext_rd_en(ext_rd_en), .ext_rd_addr(ext_rd_addr),
        .ext_rd_data(ext_rd_data), .ext_rd_valid(ext_rd_valid),
        .ext_wr_en(ext_wr_en), .ext_wr_addr(ext_wr_addr),
        .ext_wr_data(ext_wr_data),
        .dbg_core_idle(dbg_idle),
        .dbg_cache_hits(dbg_hits),
        .dbg_cache_misses(dbg_misses)
    );

    // Memory model: 1-cycle latency read
    always_ff @(posedge clk) begin
        ext_rd_valid <= ext_rd_en;
        if (ext_rd_en)
            ext_rd_data <= ext_mem[ext_rd_addr];
        if (ext_wr_en)
            ext_mem[ext_wr_addr] <= ext_wr_data;
    end

    // ── Load test graph ──
    // Simple graph: APP(LAM(body), INT(42))
    // Node 0: APP  child0=1, child1=2
    // Node 1: LAM  child0=3 (body = VAR 0 → identity)
    // Node 2: INT  data=42
    // Node 3: VAR  data=0 (de Bruijn index)
    task load_identity_42;
        // TAG_APP=1, arity=2, child0=1, child1=2
        ext_mem[0] = {4'h1, 4'd2, 8'd0, 8'd0, 16'd1, 16'd2, 16'd0, 64'd0};
        // TAG_LAM=0, arity=1, child0=3
        ext_mem[1] = {4'h0, 4'd1, 8'd0, 8'd0, 16'd3, 16'd0, 16'd0, 64'd0};
        // TAG_PRIM=9, PRIM_INT_LIT=0x03, data=42
        ext_mem[2] = {4'h9, 4'd0, 8'h03, 8'd0, 16'd0, 16'd0, 16'd0, 64'd42};
        // TAG_PRIM=9, PRIM_VAR=0x00, data=0
        ext_mem[3] = {4'h9, 4'd0, 8'h00, 8'd0, 16'd0, 16'd0, 16'd0, 64'd0};
    endtask

    // ── Test sequence ──
    initial begin
        $display("═══════════════════════════════════════════");
        $display("  Ξ Multi-Core Testbench — %0d cores", N_CORES);
        $display("═══════════════════════════════════════════");

        rst_n      = 0;
        host_start = 0;
        host_entry = 0;

        // Load graph
        load_identity_42();

        // Reset
        #100;
        rst_n = 1;
        #50;

        // Start reduction at node 0
        $display("[%0t] Starting reduction at entry=0", $time);
        host_entry = 16'd0;
        host_start = 1;
        #10;
        host_start = 0;

        // Wait for completion
        fork
            begin
                wait (host_done);
                $display("[%0t] Reduction complete!", $time);
                $display("  Cycles:     %0d", host_cycles);
                $display("  Reductions: %0d", host_reductions);
                $display("  Cache hits:  %0d", dbg_hits);
                $display("  Cache miss:  %0d", dbg_misses);
                $display("  Core idle:   %b", dbg_idle);
            end
            begin
                #100000; // 100 us timeout
                $display("[%0t] TIMEOUT — reduction did not complete", $time);
            end
        join_any

        #100;
        $display("═══════════════════════════════════════════");
        $display("  Test complete");
        $display("═══════════════════════════════════════════");
        $finish;
    end

    // Waveform dump
    initial begin
        $dumpfile("xi_multicore.vcd");
        $dumpvars(0, xi_multicore_tb);
    end

endmodule

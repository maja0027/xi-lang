// ═══════════════════════════════════════════════════════════════
// Ξ (Xi) — Zynq UltraScale+ FPGA Top Level
// Copyright (c) 2026 Alex P. Slaby — MIT License
//
// Target: ZCU104 (XCZU7EV-2FFVC1156) or ZCU102 (XCZU9EG)
//
// Architecture:
//   PS (ARM Cortex-A53) ←AXI4→ PL (Xi Multi-Core Engine)
//
//   • AXI-Lite slave: Control/status registers (start, done, stats)
//   • AXI-Full slave: Graph memory DMA (PS loads graph into PL BRAM)
//   • AXI-Full master: External DDR4 access (for large graphs)
//
// Memory Map (AXI-Lite, base 0x4000_0000):
//   0x00: CTRL    [31:0]  — bit 0: start, bit 1: reset_stats
//   0x04: STATUS  [31:0]  — bit 0: done, bit 1: busy, [7:2] idle cores
//   0x08: ENTRY   [31:0]  — entry address for root node
//   0x0C: CYCLES  [31:0]  — total clock cycles
//   0x10: REDUCTIONS [31:0] — total reductions across all cores
//   0x14: CACHE_HITS [31:0]
//   0x18: CACHE_MISS [31:0]
//   0x1C: N_CORES [31:0]  — number of instantiated cores (RO)
//   0x20: CORE_IDLE [31:0] — per-core idle bitmask
//   0x24: VERSION [31:0]  — hardware version (0x00040000 = v0.4.0)
// ═══════════════════════════════════════════════════════════════

`default_nettype none
`timescale 1ns / 1ps

module xi_zynq_top #(
    parameter N_CORES   = 4,
    parameter ADDR_W    = 16,
    parameter MEM_DEPTH = 65536,
    parameter AXI_ADDR  = 32,
    parameter AXI_DATA  = 32
)(
    // ── Clock & Reset (from PS) ──
    input  wire                    pl_clk0,       // 100-300 MHz from PS
    input  wire                    pl_resetn,

    // ── AXI-Lite Slave (control registers) ──
    input  wire [AXI_ADDR-1:0]    s_axil_awaddr,
    input  wire                    s_axil_awvalid,
    output logic                   s_axil_awready,
    input  wire [AXI_DATA-1:0]    s_axil_wdata,
    input  wire [3:0]             s_axil_wstrb,
    input  wire                    s_axil_wvalid,
    output logic                   s_axil_wready,
    output logic [1:0]            s_axil_bresp,
    output logic                   s_axil_bvalid,
    input  wire                    s_axil_bready,
    input  wire [AXI_ADDR-1:0]    s_axil_araddr,
    input  wire                    s_axil_arvalid,
    output logic                   s_axil_arready,
    output logic [AXI_DATA-1:0]   s_axil_rdata,
    output logic [1:0]            s_axil_rresp,
    output logic                   s_axil_rvalid,
    input  wire                    s_axil_rready,

    // ── AXI-Full Slave (graph DMA from PS) ──
    input  wire [AXI_ADDR-1:0]    s_axi_awaddr,
    input  wire [7:0]             s_axi_awlen,
    input  wire [2:0]             s_axi_awsize,
    input  wire [1:0]             s_axi_awburst,
    input  wire                    s_axi_awvalid,
    output logic                   s_axi_awready,
    input  wire [63:0]            s_axi_wdata,
    input  wire [7:0]             s_axi_wstrb,
    input  wire                    s_axi_wlast,
    input  wire                    s_axi_wvalid,
    output logic                   s_axi_wready,
    output logic [1:0]            s_axi_bresp,
    output logic                   s_axi_bvalid,
    input  wire                    s_axi_bready,

    // ── Debug LEDs ──
    output logic [3:0]            led
);

    wire clk   = pl_clk0;
    wire rst_n = pl_resetn;

    // ══════════════════════════════════════
    // CONTROL REGISTERS
    // ══════════════════════════════════════

    logic        ctrl_start;
    logic [ADDR_W-1:0] ctrl_entry;
    logic        mc_done;
    logic [31:0] mc_cycles;
    logic [31:0] mc_reductions;
    logic [31:0] mc_cache_hits;
    logic [31:0] mc_cache_misses;
    logic [N_CORES-1:0] mc_core_idle;

    localparam VERSION = 32'h0004_0000; // v0.4.0

    // ── AXI-Lite Write Channel ──
    logic [7:0] wr_addr_reg;
    logic       wr_addr_valid;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s_axil_awready <= 1'b0;
            s_axil_wready  <= 1'b0;
            s_axil_bvalid  <= 1'b0;
            s_axil_bresp   <= 2'b00;
            ctrl_start     <= 1'b0;
            ctrl_entry     <= '0;
        end else begin
            ctrl_start <= 1'b0; // pulse

            // Address phase
            if (s_axil_awvalid && !s_axil_awready) begin
                s_axil_awready <= 1'b1;
                wr_addr_reg    <= s_axil_awaddr[7:0];
                wr_addr_valid  <= 1'b1;
            end else
                s_axil_awready <= 1'b0;

            // Data phase
            if (s_axil_wvalid && wr_addr_valid) begin
                s_axil_wready <= 1'b1;
                wr_addr_valid <= 1'b0;
                case (wr_addr_reg)
                    8'h00: ctrl_start <= s_axil_wdata[0];
                    8'h08: ctrl_entry <= s_axil_wdata[ADDR_W-1:0];
                endcase
                s_axil_bvalid <= 1'b1;
            end else
                s_axil_wready <= 1'b0;

            // Response
            if (s_axil_bvalid && s_axil_bready)
                s_axil_bvalid <= 1'b0;
        end
    end

    // ── AXI-Lite Read Channel ──
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s_axil_arready <= 1'b0;
            s_axil_rvalid  <= 1'b0;
            s_axil_rresp   <= 2'b00;
            s_axil_rdata   <= '0;
        end else begin
            if (s_axil_arvalid && !s_axil_rvalid) begin
                s_axil_arready <= 1'b1;
                s_axil_rvalid  <= 1'b1;
                case (s_axil_araddr[7:0])
                    8'h00: s_axil_rdata <= {31'b0, ctrl_start};
                    8'h04: s_axil_rdata <= {24'b0, mc_core_idle, 5'b0, |~mc_core_idle, mc_done};
                    8'h08: s_axil_rdata <= {{(32-ADDR_W){1'b0}}, ctrl_entry};
                    8'h0C: s_axil_rdata <= mc_cycles;
                    8'h10: s_axil_rdata <= mc_reductions;
                    8'h14: s_axil_rdata <= mc_cache_hits;
                    8'h18: s_axil_rdata <= mc_cache_misses;
                    8'h1C: s_axil_rdata <= N_CORES;
                    8'h20: s_axil_rdata <= {{(32-N_CORES){1'b0}}, mc_core_idle};
                    8'h24: s_axil_rdata <= VERSION;
                    default: s_axil_rdata <= 32'hDEAD_BEEF;
                endcase
            end else
                s_axil_arready <= 1'b0;

            if (s_axil_rvalid && s_axil_rready)
                s_axil_rvalid <= 1'b0;
        end
    end

    // ══════════════════════════════════════
    // GRAPH MEMORY (Block RAM, DMA-loadable)
    // ══════════════════════════════════════

    // Simplified: BRAM for graph storage, loaded via AXI-Full
    logic [159:0] graph_mem [MEM_DEPTH];
    logic         graph_rd_valid;
    logic [159:0] graph_rd_data;

    // AXI-Full write into graph memory
    logic [ADDR_W-1:0] dma_wr_ptr;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s_axi_awready <= 1'b0;
            s_axi_wready  <= 1'b0;
            s_axi_bvalid  <= 1'b0;
            s_axi_bresp   <= 2'b00;
            dma_wr_ptr    <= '0;
        end else begin
            s_axi_awready <= s_axi_awvalid && !s_axi_awready;
            if (s_axi_awvalid && s_axi_awready)
                dma_wr_ptr <= s_axi_awaddr[ADDR_W+2:3]; // 8-byte aligned

            s_axi_wready <= s_axi_wvalid && !s_axi_wready;
            if (s_axi_wvalid && s_axi_wready) begin
                // Pack 64-bit AXI words into 160-bit nodes (3 beats per node)
                // Simplified: direct write lower 64 bits
                graph_mem[dma_wr_ptr][63:0] <= s_axi_wdata;
                dma_wr_ptr <= dma_wr_ptr + 1;
            end

            if (s_axi_wvalid && s_axi_wready && s_axi_wlast)
                s_axi_bvalid <= 1'b1;
            if (s_axi_bvalid && s_axi_bready)
                s_axi_bvalid <= 1'b0;
        end
    end

    // Multi-core engine reads from graph_mem
    wire              mc_ext_rd_en;
    wire [ADDR_W-1:0] mc_ext_rd_addr;
    wire              mc_ext_wr_en;
    wire [ADDR_W-1:0] mc_ext_wr_addr;
    wire [159:0]      mc_ext_wr_data;

    always_ff @(posedge clk) begin
        graph_rd_valid <= mc_ext_rd_en;
        if (mc_ext_rd_en)
            graph_rd_data <= graph_mem[mc_ext_rd_addr];
        if (mc_ext_wr_en)
            graph_mem[mc_ext_wr_addr] <= mc_ext_wr_data;
    end

    // ══════════════════════════════════════
    // MULTI-CORE ENGINE
    // ══════════════════════════════════════

    xi_multicore_top #(
        .N_CORES(N_CORES),
        .ADDR_W(ADDR_W),
        .MEM_DEPTH(MEM_DEPTH)
    ) engine (
        .clk(clk), .rst_n(rst_n),
        .host_start(ctrl_start),
        .host_entry_addr(ctrl_entry),
        .host_done(mc_done),
        .host_cycles(mc_cycles),
        .host_total_reductions(mc_reductions),
        .ext_rd_en(mc_ext_rd_en),
        .ext_rd_addr(mc_ext_rd_addr),
        .ext_rd_data(graph_rd_data),
        .ext_rd_valid(graph_rd_valid),
        .ext_wr_en(mc_ext_wr_en),
        .ext_wr_addr(mc_ext_wr_addr),
        .ext_wr_data(mc_ext_wr_data),
        .dbg_core_idle(mc_core_idle),
        .dbg_cache_hits(mc_cache_hits),
        .dbg_cache_misses(mc_cache_misses)
    );

    // ══════════════════════════════════════
    // DEBUG LEDs
    // ══════════════════════════════════════

    assign led[0] = mc_done;
    assign led[1] = |~mc_core_idle;   // Any core busy
    assign led[2] = &mc_core_idle;    // All cores idle
    assign led[3] = ctrl_start;       // Start pulse

endmodule

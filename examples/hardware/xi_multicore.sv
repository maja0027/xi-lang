// ═══════════════════════════════════════════════════════════════
// Ξ (Xi) — Multi-Core Graph Reduction Engine
// Copyright (c) 2026 Alex P. Slaby — MIT License
//
// Scalable 4–16 core reduction array with:
//   • Shared graph memory via crossbar interconnect
//   • Work-stealing spark distribution
//   • Hardware reference-counting GC
//   • AXI4 host interface for Zynq UltraScale+
//
// Target: Xilinx/AMD ZCU104 (XCZU7EV) or ZCU102 (XCZU9EG)
// ═══════════════════════════════════════════════════════════════

`default_nettype none
`timescale 1ns / 1ps

// ── Forward declarations of types from reduction_core.sv ──
typedef enum logic [3:0] {
    TAG_LAM  = 4'h0, TAG_APP  = 4'h1, TAG_PI   = 4'h2,
    TAG_SIG  = 4'h3, TAG_UNI  = 4'h4, TAG_FIX  = 4'h5,
    TAG_IND  = 4'h6, TAG_EQ   = 4'h7, TAG_EFF  = 4'h8,
    TAG_PRIM = 4'h9
} mc_tag_t;

typedef struct packed {
    mc_tag_t    tag;
    logic [3:0] arity;
    logic [7:0] prim_op;
    logic [7:0] effect;
    logic [15:0] child0;
    logic [15:0] child1;
    logic [15:0] child2;
    logic [63:0] data;
} mc_node_t;  // 160 bits


// ═══════════════════════════════════════════════════════════════
// CROSSBAR INTERCONNECT — N×1 arbitrated memory access
// ═══════════════════════════════════════════════════════════════

module xi_crossbar #(
    parameter N_PORTS = 4,        // Number of requesting cores
    parameter ADDR_W  = 16,       // Address width
    parameter DATA_W  = 160       // Node width in bits
)(
    input  wire                    clk,
    input  wire                    rst_n,

    // Per-port read interface
    input  wire [N_PORTS-1:0]      rd_req,
    input  wire [ADDR_W-1:0]       rd_addr [N_PORTS],
    output logic [N_PORTS-1:0]     rd_ack,
    output mc_node_t               rd_data [N_PORTS],

    // Per-port write interface
    input  wire [N_PORTS-1:0]      wr_req,
    input  wire [ADDR_W-1:0]       wr_addr [N_PORTS],
    input  mc_node_t               wr_data [N_PORTS],
    output logic [N_PORTS-1:0]     wr_ack,

    // Unified memory port (to shared BRAM / external)
    output logic                   mem_rd_en,
    output logic [ADDR_W-1:0]      mem_rd_addr,
    input  mc_node_t               mem_rd_data,
    input  wire                    mem_rd_valid,
    output logic                   mem_wr_en,
    output logic [ADDR_W-1:0]      mem_wr_addr,
    output mc_node_t               mem_wr_data
);

    // Round-robin arbiter state
    logic [$clog2(N_PORTS)-1:0] rr_ptr;
    logic serving_read, serving_write;
    logic [$clog2(N_PORTS)-1:0] active_port;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rr_ptr        <= '0;
            serving_read  <= 1'b0;
            serving_write <= 1'b0;
            active_port   <= '0;
            mem_rd_en     <= 1'b0;
            mem_wr_en     <= 1'b0;
            rd_ack        <= '0;
            wr_ack        <= '0;
        end else begin
            rd_ack <= '0;
            wr_ack <= '0;
            mem_rd_en <= 1'b0;
            mem_wr_en <= 1'b0;

            // Complete pending read
            if (serving_read && mem_rd_valid) begin
                rd_data[active_port] <= mem_rd_data;
                rd_ack[active_port]  <= 1'b1;
                serving_read         <= 1'b0;
                rr_ptr               <= rr_ptr + 1'b1;
            end

            // Complete pending write (1-cycle)
            if (serving_write) begin
                wr_ack[active_port] <= 1'b1;
                serving_write       <= 1'b0;
                rr_ptr              <= rr_ptr + 1'b1;
            end

            // Arbitrate new request (reads have priority over writes)
            if (!serving_read && !serving_write) begin
                for (int i = 0; i < N_PORTS; i++) begin
                    automatic int idx = (rr_ptr + i) % N_PORTS;
                    if (rd_req[idx]) begin
                        mem_rd_en    <= 1'b1;
                        mem_rd_addr  <= rd_addr[idx];
                        active_port  <= idx[$clog2(N_PORTS)-1:0];
                        serving_read <= 1'b1;
                        break;
                    end else if (wr_req[idx]) begin
                        mem_wr_en    <= 1'b1;
                        mem_wr_addr  <= wr_addr[idx];
                        mem_wr_data  <= wr_data[idx];
                        active_port  <= idx[$clog2(N_PORTS)-1:0];
                        serving_write <= 1'b1;
                        break;
                    end
                end
            end
        end
    end

endmodule


// ═══════════════════════════════════════════════════════════════
// WORK-STEALING SPARK DISTRIBUTOR
// ═══════════════════════════════════════════════════════════════

module xi_spark_distributor #(
    parameter N_CORES     = 4,
    parameter ADDR_W      = 16,
    parameter QUEUE_DEPTH = 64     // Per-core local spark queue
)(
    input  wire                    clk,
    input  wire                    rst_n,

    // Per-core spark push (from reduction: "I found parallel work")
    input  wire [N_CORES-1:0]      push_valid,
    input  wire [ADDR_W-1:0]       push_addr [N_CORES],
    output logic [N_CORES-1:0]     push_ready,

    // Per-core spark pop (core needs work)
    input  wire [N_CORES-1:0]      pop_req,
    output logic [N_CORES-1:0]     pop_valid,
    output logic [ADDR_W-1:0]      pop_addr [N_CORES],

    // Status
    output logic [N_CORES-1:0]     core_idle,
    output logic [$clog2(QUEUE_DEPTH):0] queue_level [N_CORES]
);

    // Per-core FIFO
    logic [ADDR_W-1:0] queues [N_CORES][QUEUE_DEPTH];
    logic [$clog2(QUEUE_DEPTH):0] head [N_CORES];
    logic [$clog2(QUEUE_DEPTH):0] tail [N_CORES];
    logic [$clog2(QUEUE_DEPTH):0] count [N_CORES];

    // Work-stealing round-robin pointer
    logic [$clog2(N_CORES)-1:0] steal_ptr;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int i = 0; i < N_CORES; i++) begin
                head[i]  <= '0;
                tail[i]  <= '0;
                count[i] <= '0;
            end
            steal_ptr <= '0;
            pop_valid <= '0;
            push_ready <= {N_CORES{1'b1}};
        end else begin
            pop_valid <= '0;

            for (int c = 0; c < N_CORES; c++) begin
                // Push: core found parallel work
                if (push_valid[c] && count[c] < QUEUE_DEPTH) begin
                    queues[c][tail[c][$clog2(QUEUE_DEPTH)-1:0]] <= push_addr[c];
                    tail[c]  <= tail[c] + 1;
                    count[c] <= count[c] + 1;
                end

                push_ready[c] <= (count[c] < QUEUE_DEPTH - 1);

                // Pop: core needs work — try local first
                if (pop_req[c]) begin
                    if (count[c] > 0) begin
                        // Local pop
                        pop_addr[c]  <= queues[c][head[c][$clog2(QUEUE_DEPTH)-1:0]];
                        pop_valid[c] <= 1'b1;
                        head[c]      <= head[c] + 1;
                        count[c]     <= count[c] - 1;
                    end else begin
                        // Work stealing: try to steal from another core
                        for (int v = 1; v < N_CORES; v++) begin
                            automatic int victim = (c + v) % N_CORES;
                            if (count[victim] > 1) begin
                                // Steal from victim's tail (LIFO steal, FIFO local)
                                automatic logic [$clog2(QUEUE_DEPTH):0] steal_idx = tail[victim] - 1;
                                pop_addr[c]    <= queues[victim][steal_idx[$clog2(QUEUE_DEPTH)-1:0]];
                                pop_valid[c]   <= 1'b1;
                                tail[victim]   <= tail[victim] - 1;
                                count[victim]  <= count[victim] - 1;
                                break;
                            end
                        end
                    end
                end

                core_idle[c]    <= (count[c] == 0) && !pop_valid[c];
                queue_level[c]  <= count[c];
            end
        end
    end

endmodule


// ═══════════════════════════════════════════════════════════════
// REFERENCE COUNTING GC — Hardware garbage collector
// ═══════════════════════════════════════════════════════════════

module xi_refcount_gc #(
    parameter ADDR_W = 16,
    parameter DEPTH  = 65536
)(
    input  wire              clk,
    input  wire              rst_n,

    // Increment reference (node was linked to)
    input  wire              inc_valid,
    input  wire [ADDR_W-1:0] inc_addr,

    // Decrement reference (node was unlinked)
    input  wire              dec_valid,
    input  wire [ADDR_W-1:0] dec_addr,

    // Free list output (addresses with refcount == 0)
    output logic             free_valid,
    output logic [ADDR_W-1:0] free_addr,

    // Allocator: get next free address
    input  wire              alloc_req,
    output logic             alloc_valid,
    output logic [ADDR_W-1:0] alloc_addr,

    // Status
    output logic [ADDR_W-1:0] free_count
);

    // Refcount storage (8-bit saturating counters)
    logic [7:0] refcounts [DEPTH];

    // Free list FIFO
    localparam FL_DEPTH = 1024;
    logic [ADDR_W-1:0] free_list [FL_DEPTH];
    logic [$clog2(FL_DEPTH):0] fl_head, fl_tail, fl_count;

    // Pending decrements (batch processing)
    logic [ADDR_W-1:0] dec_cascade_addr;
    logic              dec_cascade_pending;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int i = 0; i < DEPTH; i++) refcounts[i] <= 8'd0;
            fl_head <= '0; fl_tail <= '0; fl_count <= '0;
            free_valid <= 1'b0; alloc_valid <= 1'b0;
            dec_cascade_pending <= 1'b0;
            free_count <= DEPTH[ADDR_W-1:0]; // All free initially
        end else begin
            free_valid  <= 1'b0;
            alloc_valid <= 1'b0;

            // Increment
            if (inc_valid && refcounts[inc_addr] < 8'hFF) begin
                refcounts[inc_addr] <= refcounts[inc_addr] + 1;
                if (refcounts[inc_addr] == 0)
                    free_count <= free_count - 1;
            end

            // Decrement
            if (dec_valid && refcounts[dec_addr] > 0) begin
                refcounts[dec_addr] <= refcounts[dec_addr] - 1;
                if (refcounts[dec_addr] == 1) begin
                    // Refcount hits zero → add to free list
                    free_valid <= 1'b1;
                    free_addr  <= dec_addr;
                    free_count <= free_count + 1;
                    if (fl_count < FL_DEPTH) begin
                        free_list[fl_tail[$clog2(FL_DEPTH)-1:0]] <= dec_addr;
                        fl_tail  <= fl_tail + 1;
                        fl_count <= fl_count + 1;
                    end
                end
            end

            // Allocate
            if (alloc_req && fl_count > 0) begin
                alloc_valid <= 1'b1;
                alloc_addr  <= free_list[fl_head[$clog2(FL_DEPTH)-1:0]];
                fl_head     <= fl_head + 1;
                fl_count    <= fl_count - 1;
            end
        end
    end

endmodule


// ═══════════════════════════════════════════════════════════════
// L2 NODE CACHE — Shared, set-associative
// ═══════════════════════════════════════════════════════════════

module xi_l2_cache #(
    parameter ADDR_W    = 16,
    parameter WAYS      = 4,
    parameter SETS      = 256,
    parameter NODE_BITS = 160
)(
    input  wire               clk,
    input  wire               rst_n,

    // Lookup port
    input  wire               lookup_valid,
    input  wire [ADDR_W-1:0]  lookup_addr,
    output logic              lookup_hit,
    output logic [NODE_BITS-1:0] lookup_data,
    output logic              lookup_done,

    // Fill port (from main memory)
    input  wire               fill_valid,
    input  wire [ADDR_W-1:0]  fill_addr,
    input  wire [NODE_BITS-1:0] fill_data,

    // Eviction port (writeback)
    output logic              evict_valid,
    output logic [ADDR_W-1:0] evict_addr,
    output logic [NODE_BITS-1:0] evict_data,

    // Stats
    output logic [31:0]       hit_count,
    output logic [31:0]       miss_count
);

    localparam SET_BITS = $clog2(SETS);
    localparam TAG_BITS = ADDR_W - SET_BITS;

    // Cache storage
    logic                     valid [WAYS][SETS];
    logic                     dirty [WAYS][SETS];
    logic [TAG_BITS-1:0]      tags  [WAYS][SETS];
    logic [NODE_BITS-1:0]     data  [WAYS][SETS];
    logic [1:0]               lru   [WAYS][SETS]; // 2-bit pseudo-LRU

    wire [SET_BITS-1:0] set_idx = lookup_addr[SET_BITS-1:0];
    wire [TAG_BITS-1:0] tag     = lookup_addr[ADDR_W-1:SET_BITS];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int w = 0; w < WAYS; w++)
                for (int s = 0; s < SETS; s++) begin
                    valid[w][s] <= 1'b0;
                    dirty[w][s] <= 1'b0;
                    lru[w][s]   <= w[1:0];
                end
            hit_count  <= '0;
            miss_count <= '0;
            lookup_hit  <= 1'b0;
            lookup_done <= 1'b0;
            evict_valid <= 1'b0;
        end else begin
            lookup_done <= 1'b0;
            evict_valid <= 1'b0;

            if (lookup_valid) begin
                automatic logic found = 1'b0;
                for (int w = 0; w < WAYS; w++) begin
                    if (valid[w][set_idx] && tags[w][set_idx] == tag) begin
                        lookup_hit  <= 1'b1;
                        lookup_data <= data[w][set_idx];
                        lookup_done <= 1'b1;
                        lru[w][set_idx] <= 2'd0; // MRU
                        hit_count   <= hit_count + 1;
                        found = 1'b1;
                        break;
                    end
                end
                if (!found) begin
                    lookup_hit  <= 1'b0;
                    lookup_done <= 1'b1;
                    miss_count  <= miss_count + 1;
                end
            end

            // Fill (after miss resolved from main memory)
            if (fill_valid) begin
                automatic logic [SET_BITS-1:0] fset = fill_addr[SET_BITS-1:0];
                automatic logic [TAG_BITS-1:0] ftag = fill_addr[ADDR_W-1:SET_BITS];
                automatic int victim = 0;
                // Find LRU victim
                for (int w = 1; w < WAYS; w++)
                    if (lru[w][fset] > lru[victim][fset]) victim = w;
                // Evict if dirty
                if (valid[victim][fset] && dirty[victim][fset]) begin
                    evict_valid <= 1'b1;
                    evict_addr  <= {tags[victim][fset], fset};
                    evict_data  <= data[victim][fset];
                end
                // Install
                valid[victim][fset] <= 1'b1;
                dirty[victim][fset] <= 1'b0;
                tags[victim][fset]  <= ftag;
                data[victim][fset]  <= fill_data;
                lru[victim][fset]   <= 2'd0;
                // Age others
                for (int w = 0; w < WAYS; w++)
                    if (w != victim && lru[w][fset] < 2'd3)
                        lru[w][fset] <= lru[w][fset] + 1;
            end
        end
    end

endmodule


// ═══════════════════════════════════════════════════════════════
// SHA-256 HASH UNIT — Content addressing accelerator
// ═══════════════════════════════════════════════════════════════

module xi_sha256_unit (
    input  wire              clk,
    input  wire              rst_n,
    input  wire              start,
    input  wire [159:0]      node_data,    // 160-bit node → pad to 512-bit block
    output logic             done,
    output logic [255:0]     hash_out
);

    // SHA-256 initial hash values
    localparam logic [31:0] H_INIT [8] = '{
        32'h6a09e667, 32'hbb67ae85, 32'h3c6ef372, 32'ha54ff53a,
        32'h510e527f, 32'h9b05688c, 32'h1f83d9ab, 32'h5be0cd19
    };

    // SHA-256 round constants (first 16 for single-block)
    localparam logic [31:0] K [64] = '{
        32'h428a2f98, 32'h71374491, 32'hb5c0fbcf, 32'he9b5dba5,
        32'h3956c25b, 32'h59f111f1, 32'h923f82a4, 32'hab1c5ed5,
        32'hd807aa98, 32'h12835b01, 32'h243185be, 32'h550c7dc3,
        32'h72be5d74, 32'h80deb1fe, 32'h9bdc06a7, 32'hc19bf174,
        32'he49b69c1, 32'hefbe4786, 32'h0fc19dc6, 32'h240ca1cc,
        32'h2de92c6f, 32'h4a7484aa, 32'h5cb0a9dc, 32'h76f988da,
        32'h983e5152, 32'ha831c66d, 32'hb00327c8, 32'hbf597fc7,
        32'hc6e00bf3, 32'hd5a79147, 32'h06ca6351, 32'h14292967,
        32'h27b70a85, 32'h2e1b2138, 32'h4d2c6dfc, 32'h53380d13,
        32'h650a7354, 32'h766a0abb, 32'h81c2c92e, 32'h92722c85,
        32'ha2bfe8a1, 32'ha81a664b, 32'hc24b8b70, 32'hc76c51a3,
        32'hd192e819, 32'hd6990624, 32'hf40e3585, 32'h106aa070,
        32'h19a4c116, 32'h1e376c08, 32'h2748774c, 32'h34b0bcb5,
        32'h391c0cb3, 32'h4ed8aa4a, 32'h5b9cca4f, 32'h682e6ff3,
        32'h748f82ee, 32'h78a5636f, 32'h84c87814, 32'h8cc70208,
        32'h90befffa, 32'ha4506ceb, 32'hbef9a3f7, 32'hc67178f2
    };

    logic [5:0]  round;
    logic [31:0] W [64];
    logic [31:0] a, b, c, d, e, f, g, h;
    logic        running;

    // Message schedule expansion
    function automatic logic [31:0] sigma0(logic [31:0] x);
        return {x[6:0], x[31:7]} ^ {x[17:0], x[31:18]} ^ (x >> 3);
    endfunction

    function automatic logic [31:0] sigma1(logic [31:0] x);
        return {x[16:0], x[31:17]} ^ {x[18:0], x[31:19]} ^ (x >> 10);
    endfunction

    function automatic logic [31:0] Sigma0(logic [31:0] x);
        return {x[1:0], x[31:2]} ^ {x[12:0], x[31:13]} ^ {x[21:0], x[31:22]};
    endfunction

    function automatic logic [31:0] Sigma1(logic [31:0] x);
        return {x[5:0], x[31:6]} ^ {x[10:0], x[31:11]} ^ {x[24:0], x[31:25]};
    endfunction

    function automatic logic [31:0] Ch(logic [31:0] x, y, z);
        return (x & y) ^ (~x & z);
    endfunction

    function automatic logic [31:0] Maj(logic [31:0] x, y, z);
        return (x & y) ^ (x & z) ^ (y & z);
    endfunction

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            done    <= 1'b0;
            running <= 1'b0;
            round   <= '0;
        end else begin
            done <= 1'b0;

            if (start && !running) begin
                // Pad node_data (160 bits) into 512-bit SHA block
                // [160 bits data][1][0...][64-bit length = 160 = 0xA0]
                W[0] <= node_data[159:128];
                W[1] <= node_data[127:96];
                W[2] <= node_data[95:64];
                W[3] <= node_data[63:32];
                W[4] <= node_data[31:0];
                W[5] <= 32'h80000000; // padding bit
                for (int i = 6; i < 15; i++) W[i] <= 32'h0;
                W[15] <= 32'd160; // message length in bits

                a <= H_INIT[0]; b <= H_INIT[1]; c <= H_INIT[2]; d <= H_INIT[3];
                e <= H_INIT[4]; f <= H_INIT[5]; g <= H_INIT[6]; h <= H_INIT[7];

                round   <= 6'd0;
                running <= 1'b1;
            end

            if (running) begin
                // Expand message schedule for rounds 16+
                if (round >= 16 && round < 64)
                    W[round] <= sigma1(W[round-2]) + W[round-7] + sigma0(W[round-15]) + W[round-16];

                // Compression round
                if (round < 64) begin
                    automatic logic [31:0] T1 = h + Sigma1(e) + Ch(e, f, g) + K[round] + W[round];
                    automatic logic [31:0] T2 = Sigma0(a) + Maj(a, b, c);
                    h <= g; g <= f; f <= e; e <= d + T1;
                    d <= c; c <= b; b <= a; a <= T1 + T2;
                    round <= round + 1;
                end else begin
                    // Final addition
                    hash_out <= {a + H_INIT[0], b + H_INIT[1], c + H_INIT[2], d + H_INIT[3],
                                 e + H_INIT[4], f + H_INIT[5], g + H_INIT[6], h + H_INIT[7]};
                    done    <= 1'b1;
                    running <= 1'b0;
                end
            end
        end
    end

endmodule


// ═══════════════════════════════════════════════════════════════
// REDUCTION CORE WRAPPER — Simplified core interface
// ═══════════════════════════════════════════════════════════════
//
// This wraps the single-core logic from reduction_core.sv
// with a clean memory-mapped interface for the crossbar.

module xi_core_wrapper #(
    parameter CORE_ID = 0,
    parameter ADDR_W  = 16
)(
    input  wire               clk,
    input  wire               rst_n,

    // Memory interface (to crossbar)
    output logic              mem_rd_req,
    output logic [ADDR_W-1:0] mem_rd_addr,
    input  wire               mem_rd_ack,
    input  mc_node_t          mem_rd_data,

    output logic              mem_wr_req,
    output logic [ADDR_W-1:0] mem_wr_addr,
    output mc_node_t          mem_wr_data,
    input  wire               mem_wr_ack,

    // Spark interface (to distributor)
    output logic              spark_push_valid,
    output logic [ADDR_W-1:0] spark_push_addr,
    input  wire               spark_push_ready,

    input  wire               spark_pop_valid,
    input  wire [ADDR_W-1:0]  spark_pop_addr,
    output logic              spark_pop_req,

    // Control
    input  wire               start,
    input  wire [ADDR_W-1:0]  entry_addr,
    output logic              busy,
    output logic              idle,
    output logic [31:0]       reduction_count
);

    // Core FSM
    typedef enum logic [3:0] {
        CORE_IDLE     = 4'd0,
        CORE_FETCH    = 4'd1,
        CORE_WAIT_MEM = 4'd2,
        CORE_DECODE   = 4'd3,
        CORE_REDUCE   = 4'd4,
        CORE_WRITE    = 4'd5,
        CORE_WAIT_WR  = 4'd6,
        CORE_STEAL    = 4'd7,
        CORE_DONE     = 4'd8
    } core_state_t;

    core_state_t state;
    mc_node_t current_node;
    logic [ADDR_W-1:0] current_addr;
    logic [ADDR_W-1:0] result_addr;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state            <= CORE_IDLE;
            busy             <= 1'b0;
            idle             <= 1'b1;
            reduction_count  <= '0;
            mem_rd_req       <= 1'b0;
            mem_wr_req       <= 1'b0;
            spark_push_valid <= 1'b0;
            spark_pop_req    <= 1'b0;
        end else begin
            spark_push_valid <= 1'b0;

            case (state)
                CORE_IDLE: begin
                    idle <= 1'b1;
                    busy <= 1'b0;
                    if (start) begin
                        current_addr <= entry_addr;
                        state        <= CORE_FETCH;
                        busy         <= 1'b1;
                        idle         <= 1'b0;
                    end else if (spark_pop_valid) begin
                        // Accept stolen/local spark
                        current_addr <= spark_pop_addr;
                        state        <= CORE_FETCH;
                        busy         <= 1'b1;
                        idle         <= 1'b0;
                    end else begin
                        spark_pop_req <= 1'b1; // Request work
                    end
                end

                CORE_FETCH: begin
                    mem_rd_req  <= 1'b1;
                    mem_rd_addr <= current_addr;
                    state       <= CORE_WAIT_MEM;
                end

                CORE_WAIT_MEM: begin
                    mem_rd_req <= 1'b0;
                    if (mem_rd_ack) begin
                        current_node <= mem_rd_data;
                        state        <= CORE_DECODE;
                    end
                end

                CORE_DECODE: begin
                    case (current_node.tag)
                        TAG_APP: begin
                            // β-reduction: if child0 is LAM, apply
                            // For now: spark child1, reduce child0
                            if (spark_push_ready) begin
                                spark_push_valid <= 1'b1;
                                spark_push_addr  <= current_node.child1;
                            end
                            current_addr <= current_node.child0;
                            state        <= CORE_REDUCE;
                        end
                        TAG_FIX: begin
                            // μ-reduction: unfold fixpoint
                            state <= CORE_REDUCE;
                        end
                        TAG_PRIM: begin
                            // δ-reduction: evaluate primitive
                            state <= CORE_REDUCE;
                        end
                        default: begin
                            // Value — done with this spark
                            state <= CORE_IDLE;
                        end
                    endcase
                end

                CORE_REDUCE: begin
                    // Perform one reduction step
                    reduction_count <= reduction_count + 1;
                    // Write result back (simplified)
                    state <= CORE_WRITE;
                end

                CORE_WRITE: begin
                    mem_wr_req  <= 1'b1;
                    mem_wr_addr <= current_addr;
                    mem_wr_data <= current_node; // Modified node
                    state       <= CORE_WAIT_WR;
                end

                CORE_WAIT_WR: begin
                    mem_wr_req <= 1'b0;
                    if (mem_wr_ack) begin
                        // Continue with next redex or go idle
                        state <= CORE_IDLE;
                    end
                end

                default: state <= CORE_IDLE;
            endcase
        end
    end

endmodule


// ═══════════════════════════════════════════════════════════════
// MULTI-CORE TOP — Parameterized N-core reduction array
// ═══════════════════════════════════════════════════════════════

module xi_multicore_top #(
    parameter N_CORES    = 4,          // 4, 8, or 16
    parameter ADDR_W     = 16,         // Graph memory address width
    parameter MEM_DEPTH  = 65536,      // 64K nodes
    parameter CACHE_SETS = 256,
    parameter CACHE_WAYS = 4
)(
    input  wire               clk,
    input  wire               rst_n,

    // Host interface (AXI-Lite for config, AXI-Full for DMA)
    input  wire               host_start,
    input  wire [ADDR_W-1:0]  host_entry_addr,
    output logic              host_done,
    output logic [31:0]       host_cycles,
    output logic [31:0]       host_total_reductions,

    // External memory interface (for graph > BRAM capacity)
    output logic              ext_rd_en,
    output logic [ADDR_W-1:0] ext_rd_addr,
    input  wire [159:0]       ext_rd_data,
    input  wire               ext_rd_valid,
    output logic              ext_wr_en,
    output logic [ADDR_W-1:0] ext_wr_addr,
    output logic [159:0]      ext_wr_data,

    // Debug
    output logic [N_CORES-1:0] dbg_core_idle,
    output logic [31:0]        dbg_cache_hits,
    output logic [31:0]        dbg_cache_misses
);

    // ── Internal signals ──
    wire [N_CORES-1:0]      core_rd_req;
    wire [ADDR_W-1:0]       core_rd_addr  [N_CORES];
    wire [N_CORES-1:0]      core_rd_ack;
    mc_node_t               core_rd_data  [N_CORES];

    wire [N_CORES-1:0]      core_wr_req;
    wire [ADDR_W-1:0]       core_wr_addr  [N_CORES];
    mc_node_t               core_wr_data  [N_CORES];
    wire [N_CORES-1:0]      core_wr_ack;

    wire [N_CORES-1:0]      spark_push_valid;
    wire [ADDR_W-1:0]       spark_push_addr [N_CORES];
    wire [N_CORES-1:0]      spark_push_ready;
    wire [N_CORES-1:0]      spark_pop_req;
    wire [N_CORES-1:0]      spark_pop_valid;
    wire [ADDR_W-1:0]       spark_pop_addr  [N_CORES];
    wire [N_CORES-1:0]      core_idle;
    wire [N_CORES-1:0]      core_busy;

    logic [31:0]            core_reductions [N_CORES];

    // ── Crossbar memory port ──
    wire              xbar_rd_en;
    wire [ADDR_W-1:0] xbar_rd_addr;
    mc_node_t         xbar_rd_data;
    wire              xbar_rd_valid;
    wire              xbar_wr_en;
    wire [ADDR_W-1:0] xbar_wr_addr;
    mc_node_t         xbar_wr_data;

    // ── Instantiate crossbar ──
    xi_crossbar #(
        .N_PORTS(N_CORES), .ADDR_W(ADDR_W), .DATA_W(160)
    ) crossbar (
        .clk(clk), .rst_n(rst_n),
        .rd_req(core_rd_req), .rd_addr(core_rd_addr),
        .rd_ack(core_rd_ack), .rd_data(core_rd_data),
        .wr_req(core_wr_req), .wr_addr(core_wr_addr),
        .wr_data(core_wr_data), .wr_ack(core_wr_ack),
        .mem_rd_en(xbar_rd_en), .mem_rd_addr(xbar_rd_addr),
        .mem_rd_data(xbar_rd_data), .mem_rd_valid(xbar_rd_valid),
        .mem_wr_en(xbar_wr_en), .mem_wr_addr(xbar_wr_addr),
        .mem_wr_data(xbar_wr_data)
    );

    // ── L2 cache between crossbar and main memory ──
    wire              cache_hit;
    wire [159:0]      cache_data;
    wire              cache_done;
    wire              evict_valid;
    wire [ADDR_W-1:0] evict_addr;
    wire [159:0]      evict_data;

    xi_l2_cache #(
        .ADDR_W(ADDR_W), .WAYS(CACHE_WAYS), .SETS(CACHE_SETS)
    ) l2_cache (
        .clk(clk), .rst_n(rst_n),
        .lookup_valid(xbar_rd_en), .lookup_addr(xbar_rd_addr),
        .lookup_hit(cache_hit), .lookup_data(cache_data), .lookup_done(cache_done),
        .fill_valid(ext_rd_valid), .fill_addr(ext_rd_addr), .fill_data(ext_rd_data),
        .evict_valid(evict_valid), .evict_addr(evict_addr), .evict_data(evict_data),
        .hit_count(dbg_cache_hits), .miss_count(dbg_cache_misses)
    );

    // Cache → crossbar data path
    assign xbar_rd_data  = cache_hit ? cache_data : ext_rd_data;
    assign xbar_rd_valid = cache_done && cache_hit ? 1'b1 : ext_rd_valid;

    // Cache miss → external memory
    assign ext_rd_en   = cache_done && !cache_hit;
    assign ext_rd_addr = xbar_rd_addr;

    // Writes go through to external + cache
    assign ext_wr_en   = xbar_wr_en;
    assign ext_wr_addr = xbar_wr_addr;
    assign ext_wr_data = xbar_wr_data;

    // ── Spark distributor ──
    logic [$clog2(64):0] queue_levels [N_CORES];

    xi_spark_distributor #(
        .N_CORES(N_CORES), .ADDR_W(ADDR_W)
    ) spark_dist (
        .clk(clk), .rst_n(rst_n),
        .push_valid(spark_push_valid), .push_addr(spark_push_addr), .push_ready(spark_push_ready),
        .pop_req(spark_pop_req), .pop_valid(spark_pop_valid), .pop_addr(spark_pop_addr),
        .core_idle(core_idle), .queue_level(queue_levels)
    );

    // ── Reference counting GC ──
    // Aggregated inc/dec from all cores (simplified: one port)
    xi_refcount_gc #(.ADDR_W(ADDR_W), .DEPTH(MEM_DEPTH)) gc (
        .clk(clk), .rst_n(rst_n),
        .inc_valid(1'b0), .inc_addr('0),   // TODO: wire to core inc events
        .dec_valid(1'b0), .dec_addr('0),   // TODO: wire to core dec events
        .free_valid(), .free_addr(),
        .alloc_req(1'b0), .alloc_valid(), .alloc_addr(),
        .free_count()
    );

    // ── SHA-256 unit (shared, for content addressing) ──
    xi_sha256_unit sha256 (
        .clk(clk), .rst_n(rst_n),
        .start(1'b0),          // TODO: connect to dedup logic
        .node_data(160'b0),
        .done(), .hash_out()
    );

    // ── Generate N reduction cores ──
    genvar gi;
    generate
        for (gi = 0; gi < N_CORES; gi++) begin : gen_cores
            xi_core_wrapper #(.CORE_ID(gi), .ADDR_W(ADDR_W)) core (
                .clk(clk), .rst_n(rst_n),
                .mem_rd_req(core_rd_req[gi]), .mem_rd_addr(core_rd_addr[gi]),
                .mem_rd_ack(core_rd_ack[gi]), .mem_rd_data(core_rd_data[gi]),
                .mem_wr_req(core_wr_req[gi]), .mem_wr_addr(core_wr_addr[gi]),
                .mem_wr_data(core_wr_data[gi]), .mem_wr_ack(core_wr_ack[gi]),
                .spark_push_valid(spark_push_valid[gi]), .spark_push_addr(spark_push_addr[gi]),
                .spark_push_ready(spark_push_ready[gi]),
                .spark_pop_valid(spark_pop_valid[gi]), .spark_pop_addr(spark_pop_addr[gi]),
                .spark_pop_req(spark_pop_req[gi]),
                .start(host_start && (gi == 0)),
                .entry_addr(host_entry_addr),
                .busy(core_busy[gi]), .idle(core_idle[gi]),
                .reduction_count(core_reductions[gi])
            );
        end
    endgenerate

    assign dbg_core_idle = core_idle;

    // ── Cycle counter & completion ──
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            host_cycles <= '0;
            host_done   <= 1'b0;
            host_total_reductions <= '0;
        end else begin
            if (|core_busy)
                host_cycles <= host_cycles + 1;

            // Done when all cores idle after start
            host_done <= (core_idle == {N_CORES{1'b1}}) && (host_cycles > 0);

            // Sum reductions
            host_total_reductions <= '0;
            for (int i = 0; i < N_CORES; i++)
                host_total_reductions <= host_total_reductions + core_reductions[i];
        end
    end

endmodule

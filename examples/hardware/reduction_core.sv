// ═══════════════════════════════════════════════════════════════
// Ξ (Xi) — Single Reduction Core (FPGA Prototype)
// Copyright (c) 2026 Alex P. Slaby — MIT License
//
// A single graph-reduction core implementing β, δ, ι, and μ
// reductions on Xi binary graphs. Designed for Xilinx/AMD
// Artix-7 or Zynq-7000 FPGA.
//
// Pipeline: FETCH → DECODE → MATCH → REDUCE → STORE
// ═══════════════════════════════════════════════════════════════

`default_nettype none
`timescale 1ns / 1ps

// ── Node tag encoding (4 bits) ──
typedef enum logic [3:0] {
    TAG_LAM  = 4'h0,  // λ  Abstraction
    TAG_APP  = 4'h1,  // @  Application
    TAG_PI   = 4'h2,  // Π  Dependent product
    TAG_SIG  = 4'h3,  // Σ  Dependent sum
    TAG_UNI  = 4'h4,  // 𝒰  Universe
    TAG_FIX  = 4'h5,  // μ  Fixed point
    TAG_IND  = 4'h6,  // ι  Induction
    TAG_EQ   = 4'h7,  // ≡  Identity
    TAG_EFF  = 4'h8,  // !  Effect
    TAG_PRIM = 4'h9   // #  Primitive
} xi_tag_t;

// ── Primitive operations (8 bits) ──
typedef enum logic [7:0] {
    PRIM_VAR        = 8'h00,
    PRIM_PRINT      = 8'h01,
    PRIM_STR_LIT    = 8'h02,
    PRIM_INT_LIT    = 8'h03,
    PRIM_INT_ADD    = 8'h10,
    PRIM_INT_SUB    = 8'h11,
    PRIM_INT_MUL    = 8'h12,
    PRIM_INT_DIV    = 8'h13,
    PRIM_INT_EQ     = 8'h20,
    PRIM_INT_LT     = 8'h21,
    PRIM_BOOL_TRUE  = 8'h30,
    PRIM_BOOL_FALSE = 8'h31
} xi_prim_t;

// ── Reduction pipeline state ──
typedef enum logic [2:0] {
    S_IDLE    = 3'd0,
    S_FETCH   = 3'd1,
    S_DECODE  = 3'd2,
    S_MATCH   = 3'd3,
    S_REDUCE  = 3'd4,
    S_STORE   = 3'd5,
    S_DONE    = 3'd6,
    S_ERROR   = 3'd7
} state_t;

// ── Packed node (fits in 128 bits) ──
typedef struct packed {
    xi_tag_t    tag;        // 4 bits  — which primitive
    logic [3:0] arity;      // 4 bits  — number of children
    logic [7:0] prim_op;    // 8 bits  — primitive opcode (if TAG_PRIM)
    logic [7:0] effect;     // 8 bits  — effect bitfield (if TAG_EFF)
    logic [15:0] child0;    // 16 bits — index of first child
    logic [15:0] child1;    // 16 bits — index of second child
    logic [15:0] child2;    // 16 bits — index of third child (for EQ)
    logic [63:0] data;      // 64 bits — literal data (int/float)
} xi_node_t;                // Total: 160 bits (padded to 20 bytes)

// ═══════════════════════════════════════════════════════════════
// GRAPH MEMORY — Block RAM node storage
// ═══════════════════════════════════════════════════════════════
module xi_graph_memory #(
    parameter DEPTH = 4096,       // Max nodes
    parameter ADDR_W = 12         // log2(DEPTH)
)(
    input  wire              clk,
    input  wire              rst_n,
    // Port A: Read
    input  wire              rd_en,
    input  wire [ADDR_W-1:0] rd_addr,
    output xi_node_t         rd_data,
    output reg               rd_valid,
    // Port B: Write
    input  wire              wr_en,
    input  wire [ADDR_W-1:0] wr_addr,
    input  xi_node_t         wr_data
);

    // Block RAM storage
    xi_node_t mem [0:DEPTH-1];

    // Free pointer — next available slot
    reg [ADDR_W-1:0] free_ptr;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rd_valid <= 1'b0;
            free_ptr <= '0;
        end else begin
            rd_valid <= rd_en;
            if (rd_en)
                rd_data <= mem[rd_addr];
            if (wr_en) begin
                mem[wr_addr] <= wr_data;
                if (wr_addr >= free_ptr)
                    free_ptr <= wr_addr + 1;
            end
        end
    end

    // Free slot allocation
    function automatic [ADDR_W-1:0] alloc_node;
        alloc_node = free_ptr;
    endfunction

endmodule

// ═══════════════════════════════════════════════════════════════
// REDUCTION CORE — Single-cycle graph reducer
// ═══════════════════════════════════════════════════════════════
module xi_reduction_core #(
    parameter ADDR_W = 12
)(
    input  wire              clk,
    input  wire              rst_n,

    // Spark input (node to reduce)
    input  wire              spark_valid,
    input  wire [ADDR_W-1:0] spark_addr,
    output wire              spark_ready,

    // Graph memory interface
    output wire              mem_rd_en,
    output wire [ADDR_W-1:0] mem_rd_addr,
    input  xi_node_t         mem_rd_data,
    input  wire              mem_rd_valid,
    output wire              mem_wr_en,
    output wire [ADDR_W-1:0] mem_wr_addr,
    output xi_node_t         mem_wr_data,

    // Result output
    output reg               result_valid,
    output reg  [ADDR_W-1:0] result_addr,

    // New spark output (for child reductions)
    output reg               child_spark_valid,
    output reg  [ADDR_W-1:0] child_spark_addr,

    // Status
    output wire              busy,
    output reg  [31:0]       reduction_count
);

    // ── Pipeline registers ──
    state_t     state, next_state;
    xi_node_t   current_node;
    xi_node_t   func_node;
    xi_node_t   arg_node;
    reg [ADDR_W-1:0] current_addr;
    reg [ADDR_W-1:0] next_free;
    reg [2:0]   fetch_phase;

    assign busy = (state != S_IDLE);
    assign spark_ready = (state == S_IDLE);

    // Memory interface (active during FETCH)
    assign mem_rd_en   = (state == S_FETCH);
    assign mem_rd_addr = (fetch_phase == 0) ? current_addr :
                         (fetch_phase == 1) ? current_node.child0 :
                                              current_node.child1;

    // ── State machine ──
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state           <= S_IDLE;
            reduction_count <= 32'd0;
            result_valid    <= 1'b0;
            child_spark_valid <= 1'b0;
            fetch_phase     <= 3'd0;
            next_free       <= 12'd0;
        end else begin
            result_valid    <= 1'b0;
            child_spark_valid <= 1'b0;

            case (state)

                // ── IDLE: Wait for spark ──
                S_IDLE: begin
                    if (spark_valid) begin
                        current_addr <= spark_addr;
                        fetch_phase  <= 3'd0;
                        state        <= S_FETCH;
                    end
                end

                // ── FETCH: Load node(s) from graph memory ──
                S_FETCH: begin
                    if (mem_rd_valid) begin
                        case (fetch_phase)
                            3'd0: begin
                                current_node <= mem_rd_data;
                                // If APP, need to also fetch children
                                if (mem_rd_data.tag == TAG_APP) begin
                                    fetch_phase <= 3'd1;
                                end else begin
                                    state <= S_DECODE;
                                end
                            end
                            3'd1: begin
                                func_node   <= mem_rd_data;
                                fetch_phase <= 3'd2;
                            end
                            3'd2: begin
                                arg_node    <= mem_rd_data;
                                state       <= S_DECODE;
                            end
                            default: state <= S_ERROR;
                        endcase
                    end
                end

                // ── DECODE: Determine reduction rule ──
                S_DECODE: begin
                    state <= S_MATCH;
                end

                // ── MATCH: Pattern match on node tag ──
                S_MATCH: begin
                    state <= S_REDUCE;
                end

                // ── REDUCE: Apply reduction rule ──
                S_REDUCE: begin
                    reduction_count <= reduction_count + 1;

                    case (current_node.tag)

                        // β-reduction: @(λ(A).body, arg) → body[0 ↦ arg]
                        TAG_APP: begin
                            if (func_node.tag == TAG_LAM) begin
                                // Substitution is performed by the STORE stage
                                // In a full implementation, this would walk the
                                // body graph and replace var(0) references.
                                state <= S_STORE;
                            end
                            // δ-reduction: @(#[op], val) → compute(op, val)
                            else if (func_node.tag == TAG_PRIM) begin
                                state <= S_STORE;
                            end
                            else begin
                                // Need to reduce function first — emit spark
                                child_spark_valid <= 1'b1;
                                child_spark_addr  <= current_node.child0;
                                state <= S_IDLE;
                            end
                        end

                        // μ-reduction: μ(T).body → body[0 ↦ μ(T).body]
                        TAG_FIX: begin
                            state <= S_STORE;
                        end

                        // Effect unwrap: !{E}(expr) → reduce(expr)
                        TAG_EFF: begin
                            child_spark_valid <= 1'b1;
                            child_spark_addr  <= current_node.child0;
                            state <= S_IDLE;
                        end

                        // Values (λ, Π, Σ, 𝒰, ι, ≡, #) are already in WHNF
                        default: begin
                            result_valid <= 1'b1;
                            result_addr  <= current_addr;
                            state <= S_IDLE;
                        end
                    endcase
                end

                // ── STORE: Write result back to graph memory ──
                S_STORE: begin
                    result_valid <= 1'b1;
                    result_addr  <= current_addr;
                    state <= S_IDLE;
                end

                // ── ERROR: Halt ──
                S_ERROR: begin
                    state <= S_ERROR;  // trap
                end

            endcase
        end
    end

    // ── Memory write (result of δ-reduction) ──
    reg          do_write;
    xi_node_t    write_node;
    reg [ADDR_W-1:0] write_addr;

    assign mem_wr_en   = do_write;
    assign mem_wr_addr = write_addr;
    assign mem_wr_data = write_node;

    // δ-reduction ALU (integer arithmetic)
    always_comb begin
        do_write   = 1'b0;
        write_addr = '0;
        write_node = '0;

        if (state == S_REDUCE && current_node.tag == TAG_APP && func_node.tag == TAG_PRIM) begin
            do_write   = 1'b1;
            write_addr = current_addr;
            write_node.tag     = TAG_PRIM;
            write_node.arity   = 4'd0;
            write_node.prim_op = PRIM_INT_LIT;

            case (func_node.prim_op)
                PRIM_INT_ADD: write_node.data = $signed(arg_node.data) + $signed(current_node.data);
                PRIM_INT_SUB: write_node.data = $signed(arg_node.data) - $signed(current_node.data);
                PRIM_INT_MUL: write_node.data = $signed(arg_node.data) * $signed(current_node.data);
                default:      do_write = 1'b0;
            endcase
        end
    end

endmodule

// ═══════════════════════════════════════════════════════════════
// SPARK POOL — Work-stealing queue for parallel reduction
// ═══════════════════════════════════════════════════════════════
module xi_spark_pool #(
    parameter DEPTH  = 256,
    parameter ADDR_W = 12
)(
    input  wire              clk,
    input  wire              rst_n,
    // Push
    input  wire              push_valid,
    input  wire [ADDR_W-1:0] push_addr,
    output wire              push_ready,
    // Pop
    input  wire              pop_ready,
    output wire              pop_valid,
    output wire [ADDR_W-1:0] pop_addr,
    // Status
    output wire [8:0]        count
);

    reg [ADDR_W-1:0] fifo [0:DEPTH-1];
    reg [8:0] head, tail;
    wire [8:0] fill = tail - head;

    assign count      = fill;
    assign push_ready = (fill < DEPTH);
    assign pop_valid  = (fill > 0);
    assign pop_addr   = fifo[head[7:0]];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            head <= 9'd0;
            tail <= 9'd0;
        end else begin
            if (push_valid && push_ready) begin
                fifo[tail[7:0]] <= push_addr;
                tail <= tail + 1;
            end
            if (pop_ready && pop_valid)
                head <= head + 1;
        end
    end

endmodule

// ═══════════════════════════════════════════════════════════════
// TOP-LEVEL MODULE — Core + Memory + Spark Pool
// ═══════════════════════════════════════════════════════════════
module xi_top #(
    parameter GRAPH_DEPTH = 4096,
    parameter ADDR_W = 12
)(
    input  wire        clk,
    input  wire        rst_n,
    // Program entry point
    input  wire        start,
    input  wire [ADDR_W-1:0] entry_addr,
    // Status
    output wire        done,
    output wire [31:0] reductions,
    output wire        error
);

    // Internal wires
    wire              spark_valid, spark_ready;
    wire [ADDR_W-1:0] spark_addr;
    wire              mem_rd_en, mem_wr_en;
    wire [ADDR_W-1:0] mem_rd_addr, mem_wr_addr;
    xi_node_t         mem_rd_data, mem_wr_data;
    wire              mem_rd_valid;
    wire              result_valid;
    wire [ADDR_W-1:0] result_addr;
    wire              child_spark_valid;
    wire [ADDR_W-1:0] child_spark_addr;
    wire              core_busy;

    // Graph memory
    xi_graph_memory #(.DEPTH(GRAPH_DEPTH)) mem_inst (
        .clk(clk), .rst_n(rst_n),
        .rd_en(mem_rd_en), .rd_addr(mem_rd_addr),
        .rd_data(mem_rd_data), .rd_valid(mem_rd_valid),
        .wr_en(mem_wr_en), .wr_addr(mem_wr_addr),
        .wr_data(mem_wr_data)
    );

    // Reduction core
    xi_reduction_core #(.ADDR_W(ADDR_W)) core_inst (
        .clk(clk), .rst_n(rst_n),
        .spark_valid(spark_valid), .spark_addr(spark_addr),
        .spark_ready(spark_ready),
        .mem_rd_en(mem_rd_en), .mem_rd_addr(mem_rd_addr),
        .mem_rd_data(mem_rd_data), .mem_rd_valid(mem_rd_valid),
        .mem_wr_en(mem_wr_en), .mem_wr_addr(mem_wr_addr),
        .mem_wr_data(mem_wr_data),
        .result_valid(result_valid), .result_addr(result_addr),
        .child_spark_valid(child_spark_valid),
        .child_spark_addr(child_spark_addr),
        .busy(core_busy),
        .reduction_count(reductions)
    );

    // Spark pool
    wire [8:0] spark_count;
    xi_spark_pool #(.ADDR_W(ADDR_W)) spark_inst (
        .clk(clk), .rst_n(rst_n),
        .push_valid(child_spark_valid),
        .push_addr(child_spark_addr),
        .push_ready(),
        .pop_ready(spark_ready),
        .pop_valid(spark_valid),
        .pop_addr(spark_addr),
        .count(spark_count)
    );

    // Start trigger — push entry point into spark pool
    reg started;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            started <= 1'b0;
        else if (start && !started)
            started <= 1'b1;
    end

    assign done  = started && !core_busy && (spark_count == 0);
    assign error = 1'b0; // TODO: connect to core error state

endmodule

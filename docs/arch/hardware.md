# Hardware Architecture

The Xi-Machine is a purpose-built graph reduction processor that executes Xi programs directly in silicon.

---

## 1. Overview

Unlike conventional CPUs that execute sequential instructions, the Xi-Machine operates on graph nodes. Each reduction core performs β, δ, ι, and μ reductions in hardware, with parallelism extracted automatically via spark-based work distribution.

```
┌─────────────────────────────────────────────────────┐
│              Xi-Machine SoC                          │
│                                                      │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐     ┌────┐            │
│  │Core│ │Core│ │Core│ │Core│ ... │Core│  ×4–256     │
│  │ 0  │ │ 1  │ │ 2  │ │ 3  │     │ N  │            │
│  └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘     └──┬─┘            │
│     └───────┴──────┴──────┴──────────┘               │
│                    │                                  │
│           ┌────────┴────────┐                        │
│           │ Crossbar (N×1)  │  Round-robin arbiter   │
│           └────────┬────────┘                        │
│                    │                                  │
│           ┌────────┴────────┐                        │
│           │ L2 Node Cache   │  4-way SA, LRU         │
│           └────────┬────────┘                        │
│                    │                                  │
│  ┌─────┐  ┌───────┴──────┐  ┌──────────┐           │
│  │SHA- │  │ Ref-Count GC │  │ Spark    │           │
│  │256  │  │ Free list    │  │ Distrib. │           │
│  └─────┘  └──────────────┘  └──────────┘           │
│                    │                                  │
│           ┌────────┴────────┐                        │
│           │ Memory Interface│  LPDDR4X / HBM         │
│           └─────────────────┘                        │
└─────────────────────────────────────────────────────┘
```

## 2. Reduction Core Pipeline

Each core has a 5-stage pipeline:

| Stage | Cycles | Description |
|-------|--------|-------------|
| **FETCH** | 1–3 | Load node from L2 cache; on miss, fetch from main memory |
| **DECODE** | 1 | Extract tag, arity, children, data from packed node |
| **MATCH** | 1 | Determine which reduction rule applies (β/δ/ι/μ/none) |
| **REDUCE** | 1–4 | Apply reduction rule, compute result node |
| **STORE** | 1–2 | Write result back, update reference counts |

Values (lambdas, literals, constructors) pass through without reduction.

## 3. Spark-Based Parallelism

When a core encounters an application `f a` where both `f` and `a` are reducible:

1. Core continues reducing `f` (the function)
2. Core pushes `a` (the argument) as a **spark** into its local queue
3. Idle cores steal sparks from busy cores' queues

This is work-stealing with FIFO local access and LIFO stealing (Cilk-style):

- **Local access:** FIFO — process sparks in order
- **Stealing:** LIFO — steal most recently pushed (likely largest work unit)
- **Queue depth:** 64 entries per core

## 4. Memory Hierarchy

```
Core L1 (per core)  →  Shared L2 Cache  →  Main Memory
   implicit              256 KB              LPDDR4X / HBM
   1 cycle               2–4 cycles          50–100 cycles
```

Nodes are 160 bits (20 bytes) packed:

```
┌─────┬──────┬────────┬────────┬────────┬────────┬────────┬─────────┐
│ Tag │Arity │PrimOp  │Effect  │Child 0 │Child 1 │Child 2 │  Data   │
│ 4b  │ 4b   │ 8b     │ 8b     │ 16b    │ 16b    │ 16b    │  64b    │
└─────┴──────┴────────┴────────┴────────┴────────┴────────┴─────────┘
                                Total: 160 bits (20 bytes)
```

## 5. Content Addressing

The SHA-256 accelerator computes node hashes in 64 clock cycles (pipelined). Used for:

- **Deduplication:** Before storing a new node, check if hash already exists
- **Integrity:** Verify graph structure after DMA transfer
- **Module linking:** Resolve imports by hash

## 6. Reference-Counting GC

Hardware garbage collector with 8-bit saturating reference counters:

- **Increment:** When a node gains a new parent (STORE phase)
- **Decrement:** When a node loses a parent (reduction overwrites)
- **Free:** When counter hits zero → added to free list
- **Allocation:** Pop from free list (O(1))

No stop-the-world pauses — GC runs concurrently with reduction.

## 7. FPGA Implementations

| Board | Part | Cores | Freq | Use Case |
|-------|------|-------|------|----------|
| ZCU104 | XCZU7EV | 4 | 200 MHz | Functional validation |
| ZCU102 | XCZU9EG | 8 | 150 MHz | Performance characterization |
| VCU118 | XCVU9P | 16 | 100 MHz | Full system test |

PS↔PL communication via AXI4 (DMA for graph loading, AXI-Lite for control).

## 8. ASIC Specifications

| Parameter | Xi-4 | Xi-16 | Xi-64 | Xi-256 |
|-----------|------|-------|-------|--------|
| Process | N7 | N7 | N7 | N5 |
| Cores | 4 | 16 | 64 | 256 |
| Cache | 64 KB | 256 KB | 1 MB | 4 MB |
| Clock | 1.2 GHz | 1.0 GHz | 800 MHz | 1.0 GHz |
| Power | 150 mW | 514 mW | 1.8 W | 6 W |
| Area | 1.5 mm² | 4 mm² | 14 mm² | 40 mm² |

See `hardware/asic/TAPE_OUT.md` for the full tape-out specification.

## 9. RTL Source Files

| File | Lines | Description |
|------|-------|-------------|
| `reduction_core.sv` | 455 | Single-core pipeline + spark pool |
| `xi_multicore.sv` | 908 | N-core array, crossbar, cache, GC, SHA-256 |
| `xi_zynq_top.sv` | 260 | Zynq UltraScale+ wrapper with AXI |
| `xi_asic_top.sv` | 308 | ASIC SoC with LPDDR4 bridge |
| `xi_multicore_tb.sv` | 140 | Testbench |

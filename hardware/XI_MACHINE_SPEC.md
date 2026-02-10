# Xi-Machine Hardware Specification

**Version:** 0.1-draft
**Author:** Alex P. Slaby
**Status:** Conceptual Design

---

## 1. Overview

The Xi-Machine is a System-on-Chip (SoC) designed from first principles for graph reduction of Xi programs. Unlike conventional CPUs which execute sequential instructions, the Xi-Machine operates directly on binary DAGs, performing β, δ, ι, and μ reductions in hardware.

## 2. Block Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Xi-Machine SoC (~15B transistors)           │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │             Graph Memory Pool (GMP)                       │  │
│  │  256 GB HBM4  ·  SHA-256 indexed  ·  Auto-dedup          │  │
│  │  Hardware ref-counting GC  ·  64 MB SRAM cache            │  │
│  └───────────────────────┬──────────────────────────────────┘  │
│                          │ 512-bit crossbar                    │
│  ┌───────────┐  ┌────────────────┐  ┌────────────────────┐   │
│  │ Reduction  │  │ Type Checker    │  │ Effect Control     │   │
│  │ Cores ×256 │  │ Coprocessors×4  │  │ Unit (ECU)         │   │
│  │            │  │                 │  │                    │   │
│  │ β-reduce   │  │ Bidirectional   │  │ IO queue           │   │
│  │ δ-reduce   │  │ type inference  │  │ Effect isolation   │   │
│  │ ι-reduce   │  │ Unification     │  │ DMA controller     │   │
│  │ μ-reduce   │  │ Universe check  │  │ NVMe / NIC / UART  │   │
│  │            │  │ Termination     │  │                    │   │
│  │ Spark pool │  │                 │  │                    │   │
│  └───────────┘  └────────────────┘  └────────────────────┘   │
│                                                                 │
│  ┌──────────────────────┐  ┌──────────────────────────────┐   │
│  │ SHA-256 Accelerator   │  │ Host Interface               │   │
│  │ 4 cycles / 64 bytes   │  │ PCIe Gen5 x16               │   │
│  │ Pipelined, 8 units    │  │ JTAG debug                   │   │
│  └──────────────────────┘  └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 3. Reduction Core (×256)

### Pipeline Stages

| Stage | Cycles | Description |
|-------|--------|-------------|
| FETCH | 1-3 | Load node from GMP cache; on miss, fetch from HBM4 |
| DECODE | 1 | Extract tag, arity, edges, data |
| MATCH | 1 | Determine applicable reduction rule |
| REDUCE | 1-4 | Apply rule, compute result node |
| STORE | 1-2 | Write result back to GMP, update ref counts |

### Spark Pool

Each core has a local spark deque (256 entries). When a core encounters an APP node with two reducible children, it pushes the second child as a spark. Idle cores steal sparks from busy cores (work-stealing protocol).

### Register File

| Register | Width | Description |
|----------|-------|-------------|
| NODE | 160 bits | Current node being reduced |
| FUNC | 160 bits | Function node (for APP reduction) |
| ARG | 160 bits | Argument node (for APP reduction) |
| RESULT | 160 bits | Reduction result |
| STATUS | 8 bits | Core state flags |

## 4. Graph Memory Pool (GMP)

### Addressing

Nodes are addressed by SHA-256 content hash (256 bits). The GMP implements a hardware hash table:

```
hash[255:0] → bucket_index[23:0]
bucket_index → {node_data, overflow_ptr}
```

### Deduplication

On every STORE, the GMP computes the hash of the new node. If it already exists, the existing node is returned (free deduplication).

### Garbage Collection

Hardware reference counting:
- Each node has a 16-bit reference counter
- STORE increments refs for children
- When ref count reaches 0, node is added to free list
- Cycle detection via periodic mark-sweep (handled by dedicated GC core)

## 5. Type Checker Coprocessors (×4)

Dedicated hardware for bidirectional type checking:
- Unification engine (pattern unification, first-order)
- Universe level arithmetic
- Effect set operations (bitwise AND/OR)
- Termination oracle (structural recursion check)

These run asynchronously: code executes immediately, type errors are flagged retroactively.

## 6. Effect Control Unit (ECU)

All IO operations are sequenced through the ECU:
- IO request queue (ordered by program order)
- DMA controller for file/network operations
- UART for console IO
- NVMe interface for persistent storage
- Ethernet MAC for network effects

Pure computations bypass the ECU entirely.

## 7. SHA-256 Accelerator

8 pipelined SHA-256 units, each computing a full hash in 4 cycles (for 64-byte blocks). Throughput: ~16 hashes/cycle at 3 GHz = ~48 billion hashes/second.

## 8. Estimated Specifications

| Parameter | Value |
|-----------|-------|
| Process node | 3nm (TSMC N3E) |
| Die area | ~200 mm² |
| Transistors | ~15 billion |
| Reduction cores | 256 |
| Type checker coprocessors | 4 |
| SHA-256 units | 8 |
| Clock frequency | 2-4 GHz |
| Graph cache (SRAM) | 64 MB |
| Graph memory (HBM4) | 256 GB |
| Memory bandwidth | 2 TB/s |
| TDP | 60-120W |
| Host interface | PCIe Gen5 x16 |
| Reductions/sec (est.) | 50-200 billion |

## 9. Security Properties

| Vulnerability | Status | Why |
|---|---|---|
| Buffer overflow | **Impossible** | No arrays, no pointers — only typed graph nodes |
| Use-after-free | **Impossible** | Reference counting; no manual memory management |
| Null pointer | **Impossible** | No null in the type system (use Option) |
| Race condition | **Impossible** | All data is immutable; effects are sequenced by ECU |
| Spectre/Meltdown | **Impossible** | No speculative execution; reduction is deterministic |
| Cache side-channel | **Mitigated** | Content-addressed; access patterns leak graph structure only |
| Code injection | **Impossible** | Code = typed graph; malformed nodes fail type check |

## 10. Research Roadmap

| Phase | Target | Description |
|-------|--------|-------------|
| Phase 1 | 2026-2027 | FPGA prototype: single core on Xilinx Artix-7 |
| Phase 2 | 2027-2028 | Multi-core FPGA: 4-16 cores on Zynq UltraScale+ |
| Phase 3 | 2028-2029 | ASIC tape-out: 256 cores, 3nm, HBM4 |
| Phase 4 | 2029-2030 | Full SoC with type checker and ECU |
| Phase 5 | 2030+ | Production Xi-Machine |

## 11. File Listing

| File | Description |
|------|-------------|
| `reduction_core.sv` | SystemVerilog: single reduction core + spark pool + top module |
| `XI_MACHINE_SPEC.md` | This document |

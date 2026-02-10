# Ξ (Xi) — ASIC Tape-Out Specification

**Version:** 0.1-draft
**Author:** Alex P. Slaby
**Status:** Design Complete, Pre-Silicon
**Date:** 2026-02-10

---

## 1. Executive Summary

The Xi-Machine ASIC is a purpose-built graph reduction processor implementing the Xi type theory in silicon. It executes Xi binary programs directly in hardware, performing β, δ, ι, and μ reductions without a traditional instruction pipeline.

**Key Metrics (16-core variant, TSMC N7):**

| Parameter | Value |
|-----------|-------|
| Process | TSMC N7 (7nm FinFET) |
| Die Area | ~4.0 mm² |
| Core Count | 16 reduction cores |
| Clock Frequency | 1.0 GHz (target) |
| Power | ~500 mW (typical) |
| Gate Count | ~3.6M gates |
| Package | FCBGA, 15×15 mm, 256 balls |
| Memory Interface | LPDDR4X, 256-bit, 3200 MT/s |
| Host Interface | AXI4, PCIe Gen4 x4 optional |
| On-chip Cache | 256 KB L2 (4-way SA) |
| Transistor Count | ~15B (estimated with SRAM) |

---

## 2. Process Technology Options

### 2a. Primary: TSMC N7 (7nm)

- **Advantages:** High density (91.2M Tr/mm²), proven for crypto/AI ASICs, excellent power efficiency.
- **Foundry:** TSMC (Taiwan). Access via shuttle services (Europractice, MUSE, CMP).
- **Cost:** ~$8M for full mask set; ~$50K–$200K for MPW shuttle (shared wafer).
- **Timeline:** 6 months from tapeout to silicon.

### 2b. Alternative: GlobalFoundries 12LP+ (12nm)

- **Advantages:** Lower cost (~$3M mask set), US-based fab, good for prototyping.
- **Trade-off:** ~2× area, ~30% lower frequency vs N7.
- **Die area:** ~8 mm² for 16 cores.

### 2c. Academic: SkyWater SKY130 (130nm, open-source PDK)

- **Advantages:** Free PDK, Google/Efabless shuttle ($0 for academics).
- **Trade-off:** 4 cores max at reasonable area (~25 mm²), ~100 MHz.
- **Use case:** Proof-of-concept, publishable, reproducible.

---

## 3. Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    Xi-Machine ASIC (4 mm²)                 │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │   Core 0   Core 1   Core 2   Core 3    ...  Core 15 │ │
│  │  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐       ┌─────┐ │ │
│  │  │FETCH│  │FETCH│  │FETCH│  │FETCH│       │FETCH│ │ │
│  │  │DECOD│  │DECOD│  │DECOD│  │DECOD│       │DECOD│ │ │
│  │  │MATCH│  │MATCH│  │MATCH│  │MATCH│       │MATCH│ │ │
│  │  │REDUC│  │REDUC│  │REDUC│  │REDUC│       │REDUC│ │ │
│  │  │STORE│  │STORE│  │STORE│  │STORE│       │STORE│ │ │
│  │  │spark│  │spark│  │spark│  │spark│       │spark│ │ │
│  │  └──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘       └──┬──┘ │ │
│  └─────┼────────┼────────┼────────┼──────────────┼────┘ │
│        └────────┴────────┴────────┴──────────────┘      │
│                          │                               │
│                 ┌────────┴────────┐                      │
│                 │ Crossbar (16×1) │                      │
│                 │  Round-Robin    │                      │
│                 │  2-cycle arb    │                      │
│                 └────────┬────────┘                      │
│                          │                               │
│              ┌───────────┴───────────┐                   │
│              │  L2 Node Cache (256KB)│                   │
│              │  4-way SA, 1024 sets  │                   │
│              │  LRU, write-back      │                   │
│              └───────────┬───────────┘                   │
│                          │                               │
│  ┌───────────┐  ┌───────┴───────┐  ┌─────────────────┐ │
│  │ SHA-256    │  │ Ref-Count GC  │  │ Work-Stealing   │ │
│  │ Accelerator│  │ 8-bit saturate│  │ Spark Distrib.  │ │
│  │ 64 cycles  │  │ Free list     │  │ FIFO per core   │ │
│  └───────────┘  └───────────────┘  └─────────────────┘ │
│                          │                               │
│              ┌───────────┴───────────┐                   │
│              │   AXI4 Memory Bridge  │                   │
│              │   → LPDDR4X / HBM PHY │                   │
│              └───────────────────────┘                   │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐ │
│  │ JTAG TAP │  │ Config   │  │ Power Management      │ │
│  │ Debug    │  │ Registers│  │ Per-core clock gating  │ │
│  └──────────┘  └──────────┘  └───────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

---

## 4. Floorplan

```
    ┌─────────────────────────────────────────────────────┐
    │  C0   C1   C2   C3  │  C4   C5   C6   C7          │
    │  ██   ██   ██   ██  │  ██   ██   ██   ██          │ ~1.5mm
    │                      │                              │
    ├──────────────────────┤                              │
    │  C8   C9  C10  C11  │ C12  C13  C14  C15          │
    │  ██   ██   ██   ██  │  ██   ██   ██   ██          │ ~1.5mm
    │                      │                              │
    ├──────────────────────┼──────────────────────────────┤
    │  Crossbar            │  L2 Cache (SRAM macros)     │
    │  Spark Distributor   │  256 KB                      │ ~0.5mm
    ├──────────────────────┼──────────────────────────────┤
    │  SHA-256  │ GC │ AXI │  Config │ JTAG │ PwrMgmt   │ ~0.5mm
    └──────────────────────┴──────────────────────────────┘
                          ~2.0mm
```

**Total die: 2.0 × 2.0 = 4.0 mm²** (N7)

Each core: ~0.15 mm² (200K gates × 4.6 Tr/gate ÷ 91.2M Tr/mm²)
16 cores: ~2.4 mm²
L2 Cache: ~0.8 mm² (256 KB SRAM)
Interconnect + shared: ~0.8 mm²

---

## 5. Power Analysis

### 5a. Per-Core Power Breakdown

| Component | Dynamic (mW) | Leakage (mW) | Total (mW) |
|-----------|-------------|-------------|-----------|
| Fetch unit | 3.2 | 0.5 | 3.7 |
| Decoder | 2.1 | 0.3 | 2.4 |
| Matcher | 4.5 | 0.6 | 5.1 |
| Reducer | 6.8 | 0.8 | 7.6 |
| Store unit | 3.0 | 0.4 | 3.4 |
| Spark queue | 1.2 | 0.2 | 1.4 |
| **Core total** | **20.8** | **2.8** | **23.6** |

### 5b. SoC Power Budget

| Block | Power (mW) |
|-------|-----------|
| 16 × Reduction Cores | 378 |
| L2 Cache (256 KB SRAM) | 45 |
| Crossbar + Arbitration | 18 |
| SHA-256 Accelerator | 12 |
| Reference Count GC | 8 |
| Spark Distributor | 6 |
| AXI Bridge + Config | 15 |
| Clock tree + PLL | 12 |
| I/O pads + PHY | 20 |
| **Total** | **~514 mW** |

**Power density:** ~128 mW/mm² (well within N7 thermal limits)

### 5c. Power Modes

| Mode | Cores Active | Power | Use Case |
|------|-------------|-------|----------|
| Full | 16 | 514 mW | Maximum throughput |
| Half | 8 | 280 mW | Balanced |
| Quarter | 4 | 160 mW | Low power |
| Idle | 0 | 35 mW | Standby (leakage only) |

Per-core clock gating cuts dynamic power by ~95% for idle cores.

---

## 6. Verification Plan

### 6a. RTL Simulation

| Level | Tool | Coverage Target |
|-------|------|----------------|
| Unit (per module) | Verilator / Icarus | >95% line coverage |
| Core integration | VCS / Xcelium | >90% toggle + FSM |
| Multi-core | VCS + UVM | >85% functional |
| Full SoC | VCS + UVM + AXI VIP | >80% |

### 6b. Formal Verification

| Property | Tool | Status |
|----------|------|--------|
| Crossbar deadlock-free | JasperGold | Planned |
| GC refcount consistency | JasperGold | Planned |
| AXI protocol compliance | VC Formal AXI | Planned |
| Core FSM liveness | JasperGold | Planned |

### 6c. FPGA Prototyping (Pre-Silicon)

| Board | Config | Purpose |
|-------|--------|---------|
| ZCU104 (XCZU7EV) | 4 cores @ 200 MHz | Functional validation |
| ZCU102 (XCZU9EG) | 8 cores @ 150 MHz | Performance characterization |
| VCU118 (XCVU9P) | 16 cores @ 100 MHz | Full system test |

Validated programs:
- Fibonacci (fib 20) — correctness + cycle count
- Factorial (fact 10) — correctness
- Church numerals — parallel spark generation
- Large graph (10K+ nodes) — memory stress test

---

## 7. Design Flow

```
RTL (SystemVerilog)
    │
    ├─→ Lint: Spyglass / Ascent
    ├─→ Simulation: VCS + UVM testbench
    ├─→ Formal: JasperGold
    ├─→ FPGA: Vivado → ZCU104 bitstream
    │
    ▼
Synthesis (Design Compiler / Genus)
    │ Target: N7 std cell library
    │ Clock: 1 GHz, WC corner
    │ SDC: hardware/asic/constraints.sdc
    │
    ▼
Place & Route (Innovus / ICC2)
    │ Floorplan: Section 4
    │ Power grid: 0.72V VDD, mesh + straps
    │ Clock tree: H-tree, <50 ps skew
    │
    ▼
Signoff
    │ STA: PrimeTime (all PVT corners)
    │ Power: PrimePower (VCD-based)
    │ DRC/LVS: Calibre
    │ IR Drop: RedHawk / Voltus
    │ EM: PrimeTime-EM
    │
    ▼
GDSII → Tape-out → TSMC N7 fab
    │
    ▼
Package & Test
    │ FCBGA 256 balls
    │ ATPG: scan chains, BIST for SRAM
    │ Production test: <2 seconds/die
```

---

## 8. Test Infrastructure

### 8a. DFT (Design for Test)

- **Scan chains:** Full-scan insertion, 16 chains (1 per core + shared)
- **SRAM BIST:** Built-in self-test for L2 cache macro
- **JTAG:** IEEE 1149.1 boundary scan + internal access
- **ATPG coverage:** Target >98% stuck-at, >90% transition

### 8b. Production Test Flow

1. **Power-on:** Verify supply current in standby mode
2. **JTAG:** Boundary scan (connection test)
3. **BIST:** L2 cache SRAM built-in self-test
4. **Scan:** ATPG patterns (stuck-at + transition)
5. **Functional:** Load fib(10), verify result = 55, measure cycle count
6. **Speed grade:** Binary search for max frequency (Fmax binning)
7. **Leakage:** Measure IDDQ in all-gates-idle mode

---

## 9. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Crossbar becomes bottleneck at 16 cores | Medium | Banked memory (4 banks), 2-port SRAM |
| Cache thrashing on irregular graphs | Medium | Prefetch hints from core, victim cache |
| GC pause causes latency spike | Low | Incremental GC (no stop-the-world) |
| SHA-256 latency too high for inline dedup | Low | Dedup only on allocation, not lookup |
| Timing closure at 1 GHz | Medium | Fallback to 800 MHz; pipeline match stage |
| LPDDR4 bandwidth insufficient | Low | HBM2E option for high-end SKU |

---

## 10. SKU Planning

| SKU | Cores | Cache | Clock | Process | Package | Price Point |
|-----|-------|-------|-------|---------|---------|-------------|
| Xi-4 | 4 | 64 KB | 1.2 GHz | N7 | QFN-64 | $15 |
| Xi-16 | 16 | 256 KB | 1.0 GHz | N7 | BGA-256 | $45 |
| Xi-64 | 64 | 1 MB | 800 MHz | N7 | BGA-484 | $120 |
| Xi-256 | 256 | 4 MB | 1.0 GHz | N5 | BGA-900 | $350 |

Xi-4 targets embedded/IoT (smart contracts, formal verification).
Xi-16 is the reference design (this document).
Xi-64 and Xi-256 are future roadmap with HBM memory.

---

## 11. Bill of Materials (PCB)

| Component | Part Number | Qty | Cost |
|-----------|------------|-----|------|
| Xi-Machine ASIC | XI-16-BGA256 | 1 | $45 |
| LPDDR4X 4GB | Micron MT53E512M32D2 | 2 | $12 |
| PCIe Gen4 PHY | - (integrated) | - | - |
| 1.0V LDO | TPS7A85 | 1 | $2 |
| 0.72V core supply | TPS543620 | 1 | $3 |
| 100 MHz XTAL | ECS-100-20-30B | 1 | $1 |
| Decoupling caps | Various | 50 | $5 |
| **Total BOM** | | | **~$68** |

---

## 12. Schedule

| Milestone | Date | Status |
|-----------|------|--------|
| RTL freeze (4-core) | 2026-02 | ✅ Complete |
| RTL freeze (16-core) | 2026-02 | ✅ Complete |
| FPGA validation (4-core, ZCU104) | 2026-Q1 | 🔄 In progress |
| UVM testbench complete | 2026-Q2 | Planned |
| Formal verification signoff | 2026-Q2 | Planned |
| Synthesis + P&R (N7) | 2026-Q3 | Planned |
| STA/DRC/LVS signoff | 2026-Q3 | Planned |
| Tape-out (MPW shuttle) | 2026-Q4 | Planned |
| Silicon back | 2027-Q2 | Planned |
| Bring-up & characterization | 2027-Q2 | Planned |
| Production release | 2027-Q4 | Planned |

---

## 13. References

1. **Xi Language Specification** — `docs/spec/language.md`
2. **Xi-Machine Spec** — `hardware/XI_MACHINE_SPEC.md`
3. **Single-Core RTL** — `hardware/reduction_core.sv`
4. **Multi-Core RTL** — `hardware/xi_multicore.sv`
5. **Zynq UltraScale+ Top** — `hardware/xi_zynq_top.sv`
6. **ASIC Top** — `hardware/asic/xi_asic_top.sv`
7. **Timing Constraints** — `hardware/asic/constraints.sdc`
8. **Lean 4 Type Safety Proof** — `formal/Xi/Basic.lean`

---

*Copyright © 2026 Alex P. Slaby. All rights reserved under MIT License.*

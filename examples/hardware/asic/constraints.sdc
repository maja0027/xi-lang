# ═══════════════════════════════════════════════════════════════
# Ξ (Xi) — ASIC Timing Constraints (SDC)
# Copyright (c) 2026 Alex P. Slaby — MIT License
#
# Target: TSMC N7 (7nm) / GF 12LP+ (12nm)
# ═══════════════════════════════════════════════════════════════

# ── Primary Clock — 1 GHz ──
create_clock -name clk -period 1.0 [get_ports clk]
set_clock_uncertainty 0.05 [get_clocks clk]
set_clock_transition  0.03 [get_clocks clk]

# ── Memory Clock — 800 MHz ──
create_clock -name clk_mem -period 1.25 [get_ports clk_mem]
set_clock_uncertainty 0.06 [get_clocks clk_mem]

# ── JTAG Clock — 50 MHz ──
create_clock -name tck -period 20.0 [get_ports tck]
set_clock_uncertainty 0.5 [get_clocks tck]

# ── Clock Domain Crossings ──
set_false_path -from [get_clocks clk]     -to [get_clocks tck]
set_false_path -from [get_clocks tck]     -to [get_clocks clk]
set_false_path -from [get_clocks clk]     -to [get_clocks clk_mem]
set_false_path -from [get_clocks clk_mem] -to [get_clocks clk]

# ── Reset ──
set_false_path -from [get_ports rst_n]
set_false_path -from [get_ports test_mode]

# ── I/O Delays ──
# AXI Master (to LPDDR4 PHY)
set_output_delay -clock clk_mem 0.3 [get_ports m_axi_*]
set_input_delay  -clock clk_mem 0.3 [get_ports m_axi_rdata*]
set_input_delay  -clock clk_mem 0.3 [get_ports m_axi_*ready]
set_input_delay  -clock clk_mem 0.3 [get_ports m_axi_bresp*]
set_input_delay  -clock clk_mem 0.3 [get_ports m_axi_rresp*]
set_input_delay  -clock clk_mem 0.3 [get_ports m_axi_rlast]
set_input_delay  -clock clk_mem 0.3 [get_ports m_axi_rvalid]
set_input_delay  -clock clk_mem 0.3 [get_ports m_axi_bvalid]

# AXI-Lite Slave (from host CPU)
set_input_delay  -clock clk 0.2 [get_ports s_axil_*]
set_output_delay -clock clk 0.2 [get_ports s_axil_*]

# JTAG
set_input_delay  -clock tck 5.0 [get_ports {tdi tms}]
set_output_delay -clock tck 5.0 [get_ports tdo]

# ── Multi-Cycle Paths ──
# SHA-256 operates over 64 rounds; result sampled once
set_multicycle_path 64 -setup -from [get_cells engine/sha256/round_reg*] \
                               -to   [get_cells engine/sha256/hash_out_reg*]
set_multicycle_path 63 -hold  -from [get_cells engine/sha256/round_reg*] \
                               -to   [get_cells engine/sha256/hash_out_reg*]

# Crossbar arbitration (2-cycle)
set_multicycle_path 2 -setup -through [get_cells engine/crossbar/*]
set_multicycle_path 1 -hold  -through [get_cells engine/crossbar/*]

# ── Power Intent ──
# Core power gating — each core can be independently shut down
set_false_path -from [get_ports core_enable*]

# ── Wire Load ──
set_wire_load_model -name "ZeroWireload"

# ── Design Rule Constraints ──
set_max_fanout 32 [current_design]
set_max_transition 0.08 [current_design]
set_max_capacitance 0.05 [current_design]

# ── Operating Conditions ──
# Worst case: SS corner, 0.72V, 125°C
set_operating_conditions -library slow ss_0p72v_125c

# ── Area ──
# Target: 4 mm² for 16 cores @ 7nm
# Estimated: ~200K gates per core + 400K shared logic = 3.6M gates total

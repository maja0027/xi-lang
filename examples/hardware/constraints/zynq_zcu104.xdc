## ═══════════════════════════════════════════════════════════════
## Ξ (Xi) — FPGA Constraints for ZCU104 (XCZU7EV-2FFVC1156)
## Copyright (c) 2026 Alex P. Slaby — MIT License
## ═══════════════════════════════════════════════════════════════

## ── Clock ──
## PL clock from PS (200 MHz target)
create_clock -period 5.000 -name pl_clk0 [get_pins {zynq_ps/pl_clk0}]

## ── Timing Constraints ──
## Multi-cycle path for SHA-256 (64 rounds)
set_multicycle_path 2 -setup -from [get_cells {engine/sha256/*}]
set_multicycle_path 1 -hold  -from [get_cells {engine/sha256/*}]

## False paths between independent cores
for {set i 0} {$i < 4} {incr i} {
    for {set j 0} {$j < 4} {incr j} {
        if {$i != $j} {
            set_false_path -from [get_cells "engine/gen_cores[$i].core/*"] \
                           -to   [get_cells "engine/gen_cores[$j].core/*"]
        }
    }
}

## Crossbar → core paths (relaxed: 2-cycle arbitration)
set_multicycle_path 2 -setup -through [get_cells {engine/crossbar/*}]
set_multicycle_path 1 -hold  -through [get_cells {engine/crossbar/*}]

## ── I/O Constraints ──
## LEDs on ZCU104
set_property PACKAGE_PIN D5  [get_ports {led[0]}]
set_property PACKAGE_PIN D6  [get_ports {led[1]}]
set_property PACKAGE_PIN A5  [get_ports {led[2]}]
set_property PACKAGE_PIN B5  [get_ports {led[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {led[*]}]

## ── Area Constraints ──
## Place reduction cores in separate clock regions for better routability
create_pblock pblock_core0
add_cells_to_pblock pblock_core0 [get_cells {engine/gen_cores[0].core}]
resize_pblock pblock_core0 -add CLOCKREGION_X0Y0

create_pblock pblock_core1
add_cells_to_pblock pblock_core1 [get_cells {engine/gen_cores[1].core}]
resize_pblock pblock_core1 -add CLOCKREGION_X1Y0

create_pblock pblock_core2
add_cells_to_pblock pblock_core2 [get_cells {engine/gen_cores[2].core}]
resize_pblock pblock_core2 -add CLOCKREGION_X0Y1

create_pblock pblock_core3
add_cells_to_pblock pblock_core3 [get_cells {engine/gen_cores[3].core}]
resize_pblock pblock_core3 -add CLOCKREGION_X1Y1

## ── Power ──
set_operating_conditions -process maximum
set_switching_activity -static_probability 0.25 -toggle_rate 12.5

## ── Bitstream Config ──
set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
set_property BITSTREAM.CONFIG.UNUSEDPIN PULLDOWN [current_design]
set_property CONFIG_VOLTAGE 1.8 [current_design]

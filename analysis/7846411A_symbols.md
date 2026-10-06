# 7846411A (1M) symbols

CPU addresses. Confidence: **high** = behavior read directly from code and cross-checked against an
external fact (CAN id/DLC/period, vector usage); **med** = behavior read from code only.

## Functions

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x06C9B2 | `reset_entry` | high | vector 0 |
| 0x070D2C | `isr_wss_edge_ch0` | high | IRQ vec 59; F8 module ctrl +0x8E; timestamps edges, rfi |
| 0x070DB2 | `isr_wss_edge_ch1` | high | IRQ vec 57; F8 +0x9E |
| 0x070E3C | `isr_wss_edge_ch2` | high | IRQ vec 58; D8 +0x8E |
| 0x070EC6 | `isr_wss_edge_ch3` | high | IRQ vec 56; D8 +0x9E |
| 0x0D5B4C | `wss_capture_read(ch)` | med | jump table over 4+ channels, returns capture register |
| 0x0D5CDC | `wss_capture_config(ch, flags)` | med | jump table, writes channel ctrl/enable regs |
| 0x079D96 | `can_rx_process` | high | iterates msg records from n_tx to n_tx+n_rx (23-byte stride), unpacks signals |
| 0x079874 | `can_tx_process` (probable) | med | uses same tables, TX side |
| 0x079D24 | `can_rx_signal_dispatch(sig, payload)` | high | var table lookup, bit extract, calls var callback |
| 0x07A03C | `can_extract_bits` | med | called with payload+byte, bit, length |
| 0x06D4F8 | `can_read_mailbox` (probable) | med | called per RX message before unpacking |
| 0x07ABE8 | `can_tx_0CE_wheelspeed_0` | high | var 0x061 callback; 0x0CE bytes 0-1 |
| 0x07AC44 | `can_tx_0CE_wheelspeed_1` | high | var 0x062; bytes 2-3 |
| 0x07AC9E | `can_tx_0CE_wheelspeed_2` | high | var 0x063; bytes 4-5 |
| 0x07ACFA | `can_tx_0CE_wheelspeed_3` | high | var 0x064; bytes 6-7 |
| 0x0B9524 | `wheel_direction_valid(w)` | med | gated by 0x4029DA bit5, speed <= 70.00 km/h, wheel ok; bit w of 0x4029D9 |
| 0x0B94DC | `wheel_direction(w)` | med | bit 4+w of 0x4029D9; -1 for bad index |
| 0x0B9118 | `wheel_direction_update` | high | sole writer of 0x4029D2..0x4029DE; see wss report |

| 0x0B1044 | `kwp_10_start_diag_session` | high | KWP service table entry SID 0x10 |
| 0x0B1156 | `kwp_20_stop_diag_session` | high | SID 0x20 |
| 0x0B1196 | `kwp_14_clear_dtc` | high | SID 0x14 |
| 0x0B1E7E | `kwp_18_read_dtc_by_status` | high | SID 0x18 |
| 0x0B2E02 | `kwp_17_read_dtc_status` | high | SID 0x17 |
| 0x0B1F26 | `kwp_1A_read_ecu_id` | high | SID 0x1A |
| 0x0B1632 | `kwp_21_read_data_local_id` | high | SID 0x21 |
| 0x0B12AA | `kwp_27_security_access` | high | SID 0x27 |
| 0x0B14EA | `kwp_30_io_control` | high | SID 0x30 |
| 0x0B2904 | `kwp_31_start_routine` | high | SID 0x31 |
| 0x0B2120 | `kwp_3B_write_data_local_id` | high | SID 0x3B |
| 0x0B21B4 | `kwp_22_read_data_common_id` | high | SID 0x22; checks ids 0x2501, 0x1601, 0x2502 |
| 0x0B265C | `kwp_2E_write_data_common_id` | high | SID 0x2E |
| 0x0B100C | `kwp_3E_tester_present` | high | SID 0x3E |
| 0x0B31F0 | `kwp_33_*` | high | SID 0x33 (table entry) |
| 0x0B3136 / 0x0B30D2 | `kwp_29_*` / `kwp_28_*` | high | SIDs 0x29 / 0x28 (table entries) |
| 0x0B3198 / 0x0B31B2 | `kwp_81_start_comm` / `kwp_82_stop_comm` | high | SIDs 0x81 / 0x82 |
| 0x0B31BE | `kwp_11_ecu_reset` | high | SID 0x11 |
| 0x0B146E | `kwp_09_*` | high | SID 0x09 (table entry) |
| 0x0B2EFA | `kwp_23_read_memory` | high | SID 0x23; state 3: logical EEPROM addr+len <= 0x800, len < 5; state 7: only fixed blocks (addr 0/18 → descriptors 22/21 at 0xF34BC) |
| 0x0B3036 | `kwp_3D_write_memory` | high | SID 0x3D; logical EEPROM addr < 0x800, NRC 0x31/0x12 otherwise; queues NVM write |
| 0x06E338 | `nvm_request(buf, addr, len, mode)` | med | addr < 0x800; mode 10 = sync read via 0x06EA74, else queued via 0x06E21C |
| 0x06E21C | `nvm_queue_job` | med | used by 0x22/0x2E/0x23/0x3D paths |
| 0x06EA74 | `nvm_read_sync` | med | calls SPI driver 0x0D5400 / 0x0D5590 under interrupt lock |
| 0x0D5400 / 0x0D5590 | `spi_*` | med | program 0x00DB0000 queued-SPI regs (+0x08/+0x0C/+0x10/+0x14, queue RAM +0x400..+0x480) |
| 0x06C754 / 0x06C764 | `irq_disable` / `irq_restore` (probable) | med | bracket critical sections around psrclr/psrset |

### Platform (from analysis/agents/platform/REPORT.md; key sites verified)

| Address | Name | Conf |
|---|---|---|
| 0x0D6C80 | `timer_prescale_cfg(mod, flags, val)` (val 79 → 1 µs) | high |
| 0x0D6C70 / 0x0D6D28 | `timer_counter_read` / `arm_D8_from_counter` | high |
| 0x042B68 | `intc_prio_selfcheck` (error 0xA601) | high |
| 0x0D5654 / 0x077BEA | `mpu_set_region` / `mpu_violation_handler` | med-high |
| 0x0D5684 | `jump_to_bootloader` ('SBL!' at 0x4010 → jsr [0x4000]) | high |
| 0x06CF86 / 0x06CFA6 | `sw_reset` / `ecu_reset_dispatcher` | high / med |
| 0x06DEFE / 0x06DDE4 | `rom_test_init` / `rom_test_step` (HW signature 0xD50200, error 0x10004) | high |
| 0x0D4434 | `can_ram_test` | high |
| 0x070F94 | `startup_window_and_counters` | med-high |
| 0x076030 / 0x076056 / 0x076074 | `protocol_enter` / `protocol_normal` / `protocol_exit` | med |
| 0x078B20 | `t0_set_output_levels` | med |

### Application layer (from analysis/agents/app/REPORT.md; object graph + T3 order verified)

| Address | Name | Conf |
|---|---|---|
| 0x071040 | `task_T3_main_cycle` (10 ms) | high |
| 0x070C58 | `task_T1_body` (4×/frame) | high |
| 0x070CB4 | `task_T2_body` (10×/frame) | high |
| 0x0783F8 / 0x078256 / 0x078268 | `rt_get_object` / `rt_count_activation` / `rt_call_body` | med |
| 0x0786FC | `rt_supervise_frame` (error 0xA010) | med |
| 0x073B78 | `slot0_overrun_check_and_wss_swap` (error 0x10001) | high |
| 0x08CAD8 | `control_dispatcher` | high (structure) |
| 0x0B3DA8 | `monitoring_pass` | high (structure) |
| 0x07944C | `can_stack_cycle` | high |
| 0x0AFEDC | `diag_main` | med |
| 0x076092 | `test_protocol_state_machine` (ASCII serial mfg/test protocol; sets ecu_mode) | med |
| 0x0C4B4C | `comms2_state_machine` | med |
| 0x0850A2 | `channel_logic(ch, phase)` | low-med |
| 0x074F42 | `spi_job_engine` | med |
| 0x07772C | `ecu_mode_ge(n)` (test-protocol level 0x400A11 b7:5) | high |
| 0x06D17C / 0x06D190 | `abs16_sat` / `abs32_sat` | high |
| 0x06D1B2 / 0x06D1C6 / 0x06D1CE | `sat16` / `divs16` / `divu16` | high |
| 0x0711FA / 0x071158 | `interp1d` / `interp1d_limited` | high / med |
| 0x0B40FA | `is_error` | high |

### Wheel-speed chain (from analysis/agents/wss/REPORT.md; key sites verified)

| Address | Name | Conf |
|---|---|---|
| 0x06FD70 | `asic_sensor_poll` (QSPI CS5) | high |
| 0x0D52E8 | `qspi_xfer_cs(cs, n, tx, rx)` | high |
| 0x06F78A | `asic_init` | med |
| 0x075CC8 | `asic_decode_post` → 0x400A34[w] | high |
| 0x075AF0 / 0x075B50 | `asic_wheel_dir(w)` / `asic_wheel_airgap(w)` | high |
| 0x075ABA | `validate_dir_cfg` | high |
| 0x075ADE | `dir_invert_mask` | high |
| 0x073B78 | `wss_window_rollover` (slot 0) | high |
| 0x071040 | `wss_main_job` | high |
| 0x075204 | `wheel_cal_prepare` | high |
| 0x0752B8 | `wheel_speed_update` → 0x0040094A[w] | high |
| 0x08EE30 / 0x0B65DC | `wheel_post_loop` / `wheel_speed_filter` → 0x0040BF1A+0x40w | high / med |
| 0x08F000 | `wheel_struct_init` | high |
| 0x0B3DA8 | `esp_cycle_a` (calls wheel_direction_update) | high |
| 0x0B4064 | `dtc_report(id)` | med |
| 0x0B94AA | `vehicle_direction` | med |

### OS / startup (from analysis/agents/startup/REPORT.md; tables verified, names med)

| Address | Name | Conf |
|---|---|---|
| 0x06CA78 | `ram_clear` | high |
| 0x06C784 | `pll_init` | med |
| 0x06C4B6 | `intc_init` (INTC 0x00E10000) | high |
| 0x0788EE | `app_main` | med |
| 0x042F9A | `OS_Start` | high |
| 0x042BD2 | `OS_Init_and_Start` | high |
| 0x042DA4 | `OS_Dispatcher` (vec32) | high |
| 0x043974 / 0x043BEA | `ActivateTask` / `TerminateTask` | med |
| 0x0430EC / 0x04330E / 0x0434B4 / 0x0436BC | `SetEvent` / `ClearEvent` / `GetEvent` / `WaitEvent` | med |
| 0x043060 | `os_error_report` | high |
| 0x042A68 | `ShutdownOS` | high |
| 0x070A86 | `isr_timeslot` (vec60, 13 slots) | high |
| 0x043FD8 | `isr_tick_F8` (vec61) | med |
| 0x06DB0C | `isr_can` (vec40, CAN module 0x00DD0000) | med |
| 0x0785DA / 0x0785EA / 0x078602 / 0x078778 / 0x0785BE | `task_T0`..`task_T4` | high |
| 0x0D6CF8 / 0x0D6D10 | `compare_rearm_F8` / `compare_rearm_D8` | high |

## RAM

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0040BF1A + 0x40*w | `wheel[w].speed` (s16, 0.01 km/h) | high | sent on 0x0CE as v*4/25 (1/16 km/h), clamp 4800 = 300 km/h |
| 0x00400952 + w | `wheel[w].fault` (bit0) | med | 0x0CE sends 0x8000 when set |
| 0x0040094A + 2w | `wheel_speed_alt[w]` (s16) | med | compared to 7000 (70 km/h) in direction gate |
| 0x004029D9 | `wheel_dir_bits` | med | bits0-3 valid, bits4-7 direction |
| 0x004029DA | `wheel_dir_status` | med | bit5 = direction info enabled (global gate) |
| 0x0040339A..9D | `wss_edge_count[ch]` | high | incremented per edge in ISRs, cap 57 |
| 0x00401174 | `can_payload_buf` | med | RX payload bytes, indexed by per-message offset |

## Flash tables

| Address | What |
|---|---|
| 0x040000 | vector table (128 x u32) |
| 0x040200 | app header "LOCK"; 0x402F4 → BMY block, 0x402F8 ROM-test value A |
| 0x040300 | calibration block directory (12 × {tag, addr, len}) |
| 0x0D7584 | ROM self-test range table |
| 0x0F59E0 | reference string "0182H200020A" (BMY header points here) |
| 0x0F6664 | ID record "AZ2RAB00039" |
| 0x0D82D5 | CAN config header ("@ECU00001" tag just before; +0x10 n_tx=20, +0x11 n_rx=27) |
| 0x0D82F5 | CAN message records, 23 B (see `tools/can_map.py`) |
| 0x0D872E | CAN signal descriptors, 5 B |
| 0x0D8C34 | CAN variable table, 8 B (type, default, callback) |
| 0x0F33A8 | KWP2000 service table, 23 x 12 B: SID, min len, 00 00, handler u32, flags u16, pad |
| 0x0F34BC | diagnostic response/data descriptors, 12 B: RAM ptr, u16, u16 len, u16 offset, idx |

## Peripherals (inferred)

| Base | What | Conf |
|---|---|---|
| 0x00D80000, 0x00F80000 | timer/input-capture module x2 (2 wheel channels each) | high |
| 0x00DB0000 | queued SPI controller (queue RAM at +0x400) | med |

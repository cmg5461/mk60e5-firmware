# 7846816A (E9x M3) symbols

CPU addresses (file offset = CPU + 0x8000). Companion to the 1M `7846411A_symbols.md`; the M3 is
the same M·CORE platform at shifted addresses. Shared disassembly: `analysis/7846816A_main.lst`.

Confidence: **high** = behavior read from code and cross-checked against an external fact
(CAN id/DLC, vector, cal-block layout, loader indexing) OR byte-verified by the main session ·
**med** = read from code only · **low** = inference.

## Functions

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x06C906 | `reset_entry` | high | vector 0 (first word of vector table at 0x40000) |
| 0x0710FC | `curve_interp_s16(rec, x)` | high | piecewise-linear reader; strict-less segment search, Q10 truncating multiply, clamp [lo,hi]. M3 analogue of 1M 0x71158. Byte-verified on multiple curves |
| 0x05DE44 | `vehmodel_load_singletrack_coeffs` | high | indexed by `0x4031AA+1` (variant), `ld.h [base+2*var]`; writes single-track state-space coeffs to RAM 0x400AA4..0x400AD8 |
| 0x05E424 | `vehmodel_load_axle_derived` | high | indexed by `0x4031AA+1`; writes axle-derived terms to RAM 0x400AE8..0x400AF8; contains the `Cr*l_r − Cf*l_f` understeer term (fixes Cf=0xD6ECA, Cr=0xD6EE2) |
| 0x054D9A | `abs_pair_logic` | high | contains the ABS entry-slip evaluation; loads curve 0x40DB6, x = vref (0x408DA8), calls 0x710FC at +0x1B0/+0x2C8/+0x540 (0x54F4A/55062/552DA are **call sites**, not separate fns), result compared vs `vref − wheelspeed` |
| 0x0C795E | `tcs_driveslip_curve` | high | addr = 0xF625C+0x22·mode (mode=`0x4031AA+7`), replaced by 0xF61F6+0x22·mode when `0x402F6C` bit4 set; x = vref (0x403066) |
| 0x0C7996 | `tcs_driveslip_total` | med | `tcs_driveslip_curve + s16(0x4030B6)/4` → RAM 0x402FC2 |
| 0x0C7948 | `tcs_curve_f61e6` | med | reader of the 0xF61E6 curve |
| 0x0CB576 | `tcs_cap_eval` | high | addr = 0xF654C+0x22·mode, output ÷20; divisor from TCS+0x1A4 table; 2nd stage 0xF65B2+0x22·idx |
| 0x06D102 | `clamp_s16` (probable) | med | called after divs/multiply chains in the model loaders |
| 0x08E25E | `coding_field_read_geom(record, idx)` | high | = 1M 0x8E066 (byte-identical); unpacks EEPROM coding fields (variant at record 24 idx 1) for the vehicle-model loaders. (Distinct from `coding_field_read` 0xCFC00 used by kwp_22.) |

## Variables (RAM / coding)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x004031AA | `coding_block` (variant at +1, TCS mode at +7, brake front +3 / rear +4) | high | indexed `ld.b` in both model loaders and the TCS curve/cap readers |
| 0x00402F6C | `tcs_flags` (bit4 selects drive-slip set A vs B) | high | tested in `tcs_driveslip_curve` |
| 0x00403066 | `vref_tcs` (reference speed = min of front wheels, 0.01 km/h) | high | x input to TCS drive-slip curve |
| 0x00408DA8 | `vref_abs` (0.01 km/h) | high | x input to `abs_entry_slip_eval` |
| 0x00402FC2 | `tcs_driveslip_threshold` | med | store target of `tcs_driveslip_total` |
| 0x00400AA4 | `vehmodel_ram` (single-track coeffs block, ..0x400AF8) | high | store targets of the two model loaders |

## Calibration directory (0x40300, ver 2, 12 blocks) — byte-verified

| Tag | Addr | Len | | Tag | Addr | Len |
|---|---|---|---|---|---|---|
| ABS | 0x4039C | 0xB0A | | COA | 0x41978 | 0x36C |
| CSI | 0x40EA8 | 0x114 | | BFU | 0x41CE4 | 0x1C |
| TCS | 0x40FBC | 0x1D4 | | VAR | 0x41D00 | 0xE |
| AYC | 0x41190 | 0x5C6 | | DDS | 0x41D10 | 0x118 |
| BCO | 0x41758 | 0x220 | | CSW | 0x41E28 | 0x1A |
| | | | | LVC | 0x41E44 | 0x5E0 |
| | | | | VMO | 0x42424 | 0x6C |

## Key calibration addresses (byte-verified)

- **Vehicle-model variant table** (12 s16 per row, stride 2, indexed by coding variant 0..11;
  variants 0–4 == 5–9, 10/11 unique): l_f 0xD6F42 (Q10 m), l_r 0xD6F5A (Q10 m),
  mass 0xD6F72 (kg), Jz 0xD6F8A (kg·m²), Cf 0xD6ECA, Cr 0xD6EE2 (stiffness, units TBD),
  track front 0xD6FA2, track rear 0xD6FBA (mm), override-enable flag 0xD7032 (all 0).
- **ABS entry-slip curve** 0x40DB6 (lo0,hi900,n2,bp5000,c150/115,k−4/+3; threshold ~1.3–2.0 km/h).
- **ABS decel scalars** (ABS=0x4039C): gain front +0x27E=40, gain rear +0x280=25, floor +0x282=−240,
  base +0x284=−116; floor<20 +0x2A8 (12×, −127 then −120); floor<60 +0x2C0 (12×, −132×10, −140×2);
  ladder +0x76C; staged A +0xAC2 {−62,−78,−94}, staged B +0xB02 {−25,−44,−62}.
- **ABS front speed-term curve family** 0x40412 + 0x28·m (m=0..11); **rear** single 0x405F2;
  **g-term curve family** 0x40674 + 0x40·m. Variants 0–9 identical; 10/11 more permissive.
- **TCS drive-slip** set B 0xF625C + 0x22·mode (default), set A 0xF61F6 + 0x22·mode (mode 0..2,
  from `0x4031AA+7`); **TCS caps** 0xF654C + 0x22·j (j=0..5, ÷20). Relocated to const ROM.

## CAN / F-CAN (known inputs — verification root)

Method: byte-pattern match of the 1M tables into the M3 image + opcode-level diff of each function
(identical opcodes, only `lrw` literal-pool constants shift). CAN id/DLC/period/mailbox sets are
**byte-identical** to the 1M for all 47 TX+RX main-CAN and all 44 F-CAN messages; only per-signal
variable ids and callback addresses relocate. Working files `analysis/agents/m3can/`.

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0xD7F45 | `can_config_header` (20 TX, 27 RX) | high | counts + record bytes match 1M; byte-verified |
| 0xD7F65 | `can_message_table` (23-byte records) | high | ids/DLC/period identical to 1M; byte-verified |
| 0xD839E | `can_signal_table` (5-byte records) | high | = CAN_HDR+0x0D + u16(CAN_HDR+0x0C) |
| 0xD88C0 | `can_variable_table` (8-byte records) | high | per-variable callback |
| 0x07AB8C | `can_tx_0CE_wheelspeed_0` | high | var 0x061; opcode-identical to 1M 0x7ABE8 |
| 0x07ABE8 | `can_tx_0CE_wheelspeed_1` | high | var 0x062 |
| 0x07AC42 | `can_tx_0CE_wheelspeed_2` | high | var 0x063 |
| 0x07AC9E | `can_tx_0CE_wheelspeed_3` | high | var 0x064 |
| 0x07B7AC | `can_tx_629_diagresp_cb` | med | diag response, addr 0x29 |
| 0x07CC02 | `can_rx_6F1_tester_cb` | med | tester RX, mailbox 31 mask 0x7F0 |
| 0x0C4D64 | `comms2_state_machine` (F-CAN poll) | high | opcode window match to 1M 0xC4B4C |
| 0xF59C3 | `fcan_config_header` (14 TX, 18 RX) | high | byte-identical to 1M 0xF5CCB (shift −0x308); decodes to the 1M F-CAN id set (corrects cycle-1's wrong 0xED9C3) |
| 0xF59DD | `fcan_message_table` (23-byte records) | high | TX 0x080/0CE/11E/130/374/79x/7Dx; RX 0x0CD/0D1/0C9/118/0D4/… |
| 0xF5CBD | `fcan_signal_table` | high | shift −0x308 from 1M 0xF5FC5 |
| 0xF5ED0 | `fcan_variable_table` | high | shift −0x308 from 1M 0xF61D8 (now located) |

## Diagnostics (KWP2000) — service table 0xF30A0 (23 × 12B, byte-verified)

| SID | Handler | Name | | SID | Handler | Name |
|---|---|---|---|---|---|---|
| 0x10 | 0xB125C | `kwp_10_start_diag_session` | | 0x2E | 0xB2874 | `kwp_2E_write_data_common_id` |
| 0x14 | 0xB13AE | `kwp_14_clear_dtc` | | 0x30 | 0xB1702 | `kwp_30_io_control` |
| 0x17 | 0xB301A | `kwp_17_read_dtc_status` | | 0x31 | 0xB2B1C | `kwp_31_start_routine` |
| 0x18 | 0xB2096 | `kwp_18_read_dtc_by_status` | | 0x33 | 0xB3408 | `kwp_33_io_or_ctrl` |
| 0x1A | 0xB213E | `kwp_1A_read_ecu_id` | | 0x3B | 0xB2338 | `kwp_3B_write_data_local_id` |
| 0x20 | 0xB136E | `kwp_20_stop_diag_session` | | 0x3D | 0xB324E | `kwp_3D_write_memory` |
| 0x21 | 0xB184A | `kwp_21_read_data_local_id` | | 0x3E | 0xB1224 | `kwp_3E_tester_present` |
| 0x22 | 0xB23CC | `kwp_22_read_data_common_id` | | 0x11 | 0xB33D6 | `kwp_11_ecu_reset` |
| 0x23 | 0xB3112 | `kwp_23_read_memory` | | 0x28/0x29 | 0xB32EA/0xB334E | `kwp_28_*`/`kwp_29_*` |
| 0x27 | 0xB14C2 | `kwp_27_security_access` | | 0x81/0x82 | 0xB33B0/0xB33CA | `kwp_81/82_comm` |
| | | | | 0x09 | 0xB1686 | `kwp_09_*` |

- **0x22 DIDs**: checks the same record ids as the 1M — **0x2501, 0x1601, 0x2502** (verified in-line).
- **SecurityAccess 0x27** (`kwp_27_security_access` 0xB14C2, seed sub `0x0AFAF0`): seed =
  `(u16 @0x40095C) XOR 0x1B09` (forced 0x53A1 if zero); XOR const from ID-record bytes 0xF6910/11 = 09 1B
  (little-endian). ID record 0xF690C = ECU **"AZ1RAE00008"** (1M "AZ2RAB00039", const 0x3008). Key algorithm
  (ROR16 + bit-network + ID-record XOR) opcode-identical to 1M. Granted level written to RAM 0x409537 = 3.
- **RAM landmark**: the diag/security scratch block is shifted **+0x24** vs the 1M (e.g. 1M 0x409513 → M3
  0x409537); the coding/EEPROM-mirror RAM (0x4031xx, 0x40095C) is **unshifted**.

## NVM / coding (byte-verified by clean opcode diff)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x06E16C | `nvm_queue_job` | high | called from kwp_22/2E/23/3D |
| 0x06E288 | `nvm_request` | med | opcode window match |
| 0x06E9C4 | `nvm_read_sync` | high | calls the SPI drivers |
| 0x0D4DC0 | `spi_driver_a` (CS2 coding EEPROM) | high | clean opcode diff vs 1M 0xD5400 (0xD4CA8 was a false match) |
| 0x0D4F50 | `spi_driver_b` | high | clean opcode diff vs 1M 0xD5590 |
| 0x0CFC00 | `coding_field_read(record, idx)` | high | clean opcode diff vs 1M 0xD0240; jsri from kwp_22; reads 0x4031F4/F6 |
| 0x06C6A8 / 0x06C6B8 | `irq_disable` / `irq_restore` | high | bracket SPI critical sections |
| 0x004031F4/F6 | `coding_block_packed` | high | unshifted RAM, clean function diff |

## Control / ABS controller (cycle 2 — ported by opcode diff, all clean unless noted)

The ABS controller (1M 0x44000–0x5E000) maps to the M3 with a constant shift (−0x220 for 0x44xxx–0x4Bxxx,
−0x200 for ≥0x4Cxxx); 196 functions mapped (`analysis/agents/m3control/abs_fnmap.txt`). ABS/vref working
RAM is shifted **+0x24** vs the 1M. The ABS cal block is re-laid-out: offsets ≤+0x74 unchanged, +0xC6..CE
shifted +0x1B8, ≥+0x134 shifted +0x4A4.

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x08CCB8 | `control_dispatcher` | high | flat 41-`jsri` per-frame call sequencer (NOT a jump table); tail-jumps to 0x88D00; = 1M 0x8CAD8 |
| 0x08CE5E | `dispatch_slot00_driver_pressure` | high | master-cylinder pressure; = 1M 0x8CC7E |
| 0x08428C | `abs_pressure_arbiter` | high | dispatcher slot 31; = 1M 0x840AC |
| 0x0833DA | `req_arbiter_submit(op,id,ch,start,target,rate,flag)` | high | = 1M 0x831FA |
| 0x083720 | `channel_owner_select` | high | priority arbitration → 0x401960; = 1M 0x83540 |
| 0x0853A8 | `valve_pulse_sequencer` | high | = 1M 0x851C8 |
| 0x0819FE | `coa_vol_to_pressure` | high | = 1M 0x8181E |
| 0x04FC3C | `abs_phase_sm` | high | per-wheel rec[0] state machine; = 1M 0x4FE3C |
| 0x0449D0 | `vref_update` | high | rate-limited vref integrator; = 1M 0x44BF0 (constants unchanged) |
| 0x0D20DC | `wheel_accel_update` | high | struct+0x20 two-frame mean, literal 0xE287=58023 unchanged; = 1M 0xD271C |
| 0x0443F4 | `abs_apply_ramp` | high | request id 19; = 1M 0x44614 |
| 0x05424C | `abs_dump_stage` | high | = 1M 0x5444C |
| 0x051B54 | `abs_decision_classify` | high | writes decision code 0x408DDE; = 1M 0x51D54 |
| 0x047BDC | `abs_decel_threshold_builder` | high(entry)/med(body) | **M3-rewritten**: variant-indexed curves (0x40412/405F2/40674 by 0x4031AA+1) vs 1M fixed curves; = 1M 0x47DFC |
| 0x046390 | `wheel_peak_decel_byte` | high | w.39 = a/16; = 1M 0x465B0 |

Key M3 ABS/vref RAM (shifted +0x24): `vref` 0x408DA8, decision code 0x408DDE, decel-threshold array
0x4090E6, dump target/reduction 0x4091AE/0x4091AC. Hard-coded speed-dependent ROM curves relocated to
**0xD6AFC–0xD6D50 (byte-identical to 1M 0xD713C–0xD7390)**. Hard-coded (code-patch only, not cal):
clamps 25000/−8000, wheel-speed-delta clamp ±5714 (0x75540/44), accel scale 58023, vref rise/fall/snap.

## Wheel-speed chain (cycle 2 — vectors + opcode diff, clean)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x070CD0 | `isr_wss_edge_ch0` | high | vector 59; F8 +0x8E; capture ch0; 0 opcode diffs vs 1M |
| 0x070D56 | `isr_wss_edge_ch1` | high | vector 57; F8 +0x9E; ch1 |
| 0x070DE0 | `isr_wss_edge_ch2` | high | vector 58; D8 +0x8E; ch2 |
| 0x070E6A | `isr_wss_edge_ch3` | high | vector 56; D8 +0x9E; ch3 |
| 0x0D550C | `wss_capture_read(ch)` | high | 7-case jump table at 0xD551C; called from all ISRs; = 1M 0xD5B4C |
| 0x0D569C | `wss_capture_config(ch, flags)` | high | called ch 0..3 with 0x91 at 0x6F52C..3E; = 1M 0xD5CDC |
| 0x07525C | `wheel_speed_update` | high | 291 insns, 0 diffs; `jsri wheel_accel_update` at 0x75482; = 1M 0x752B8 |
| 0x0751A8 | `wheel_cal_prepare` | high | reads BFU circumferences ×900/60000 → floor 0x4032D0; = 1M 0x75204 |
| 0x0B67F4 | `wheel_speed_filter` | high | output 0x40BF1A+0x40·k; = 1M 0xB65DC |
| 0x0B9330 | `wheel_direction_update` | high | sole writer 0x4029D2..DE; = 1M 0xB9118 |
| 0x0B973C | `wheel_direction_valid` | high | 57 insns, 0 diffs; reports when speed ≤ 70 km/h; = 1M 0xB9524 |
| 0x075A5E | `validate_dir_cfg` | high | `jsri` after `movi r2,15` (0xB93C4); writes mask 0x4029D6 |

BFU geometry **identical to 1M**: standstill 0x41CF2=72, circumference 0x41CF4/F6=2073 mm, teeth 0x41CF8/FA=48.
VDA hard-configured on all 4 channels (0x91 at 0x6F524..3E); direction-expected mask 15; invert pair 05/09
at 0xD766C (coding 0x4031F4 bit8). VMO monitor block 0x42424 (window threshold 0x42430=2000, %-scales 0x42466/68=85/75).

## AYC / yaw control & DSC mode (cycle 2 — opcode diff, clean unless noted)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x05EBC4 | `yaw_observer` | med-high | dynamic observer (β 0x400C42, r 0x400C44); **variant-indexed** on M3 (reads 0x4031AA+1, cal 0xD704A/0xD70AA + AYC arrays 0x415F8/0x41610/0x41628); = 1M 0x5ECB0 |
| 0x05F7BA | `yaw_pd_moment` | high | PD moment demand; = 1M 0x5F882 |
| 0x065078 | `engine_torque_request` | high | reads AYC torque-ceiling tables; = 1M 0x6514C |
| 0x090E5C | `yaw_ref_closedform` | high | r_ref via RAM 0x400AE8/AEA (v_ch); = 1M CSI 0x90C44 |
| 0x060CA0 | `yaw_error_B46_minus_B1A` | high | yaw error; = 1M 0x60D68 |
| 0x0CF2EA | `dsc_mode_select` | high | m∈{0,1,2}→0x4031B1; m=0 if 0x4030A4∈{1,4,5} or 0x4030A2≠3; else m=2 if (0x4031F4&0x80) else 1; = 1M 0xCF92A |
| 0x0CFC98 | `dsc_coding_bit_get` | high | reads 0x4031F4 mask 0x80 (bit7 of 0x4031F5); = 1M 0xD02D8 |
| 0x0CF248 | `dsc_state_commit` | med | commits request 0x4030A3 → state 0x4030A4 (valid 1..5, state 3 gated by 0x8DD1C) |
| 0x060714 | `ayc_gain_stage` | med | computes B76/B78 P/D gains, applies mode % curves |
| 0x0602DA | `ayc_threshold_stage` | med | computes B6C entry / B70 hold |
| 0x060682 | `ayc_threshold_clamp` | med | clamps B6C/B70 to per-mode ceilings |

AYC RAM: target B1A 0x400B1A, measured B46 (F-CAN 0x0CD), entry B6C, hold B70, P/D B76/B78, mode 0x4031B1.
**v_ch is runtime-derived from the variant model (loader 0x5E424), not a constant**: M3 varies 105.5–142.1 km/h
by coding variant (1M fixed 97.65). **m=1 is the most permissive** (torque ceiling 2000 vs m0 400 / m2 330).
DSC-mode→driver-mode (DSC/DTC/MDM/OFF) mapping is live EEPROM/RAM state — not statically resolvable.

## CSI / steering / yaw reference (cycle 3 — byte/opcode verified)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x09032E | `steer_ratio_convert` | high | interp CSI steer-ratio curve; `0x40212E = angle·29360/ratio`; = 1M 0x9012E |
| 0x0901D4 | `steer_capture` | high | 0x4020D0 = steering angle; LP filter |
| 0x09020C | `steer_offset_learn` | med | zero-offset estimator → 0x402132 |
| 0x090D10 | `yawref_stage_main` (label `yaw_ref_closedform` at 0x90E5C) | high | r_ref via AE8/AEA; writes 0x4020EC; = 1M 0x90AF8/0x90C44 |
| 0x0C5C78 | `canrx_steer_angle_0C9` | med | F-CAN 0x0C9 sig 43 (var 0x020); valid window, ·1029/1024 → 0x401644 |
| 0x0C583C | `cluster_sensor_get(idx)` | high | idx0..5 → 0x402F1C/20/24/1E/22/26 (F-CAN 0x0CD/0x0D1 yaw/ay cluster) |
| 0x08FE70 | `csi_cond_sensor2` | high | ay channel; = 1M 0x8FC78 |
| 0x0905E4 | `csi_cond_sensor0` | med | yaw-rate channel |
| 0x07119E | `interp_linear_xy(x,xtab,ytab,n)` | high | plain piecewise-linear (end-clamped); distinct from `curve_interp_s16` |

CSI block 0x40EA8 (len 0x114, grew +0x62 vs 1M): steer-ratio x sets 0x40EB4 / y sets 0x40ECC (3 sets × 4 pts,
coding 0x4031AA+5), sign tables 0x40EE4/0x40F14 (12× per variant, all −1), tail (0x40F2E..) byte-identical to
1M. **Internal yaw-rate LSB ≈ 1/20480 rad/s** [agent, med] (self-consistent across wheel + closed-form paths);
steering ≈0.043 deg/LSB [med, unverified]; r·v clamp ≈1.24 g (hard-coded). v_ch enters r_ref via RAM 0x400AE8/AEA
(from the variant model), no CSI constant in the denominator.

## Brake coding — COA / BCO (cycle 3 — bodies byte-identical to 1M)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0819FE | `coa_vol_to_pressure(wheel)` | high | front uses coding +3 / COA+0x1EA, rear +4 / COA+0x212; = 1M 0x8181E |
| 0x0816E8 | `coa_pressure_to_vol(wheel)` | high | inverse; = 1M 0x81508 |
| 0x081750 | `coa_init_wheel_vol_offsets` | high | COA+0x16E/+0x17A per code |
| 0x084E38 | `coa_wheel_gain_apply` | med-high | gain curve (COA+0xC0/+0x12C) eval at x=500, ×gain/100, clamp 20000 |
| 0x06B6F4 | `bco_pressure_threshold_stage` | med | |v| vs BCO+0x18/+0x1C per code → 0x400EBA |
| 0x06B85E | `bco_main_state_machine` | med | BCO+0x50/10 wait, BCO+0x5C scale |
| 0x0CFDD8 | `coding_unpack_block` | high | 0x4031AA block from coding record: +3=(rec[2]>>3)&7, +4=rec[2]&7, +1=rec[1]&0x1F (variant) |
| 0x07119E | `interp_linear_xy` | high | p-V interpolator (shared) |

COA 0x41978 (len 0x36C) and BCO 0x41758 (len 0x220) bodies are **byte-identical to the 1M** — not retuned.
Brake coding selects code 0 vs 1 per axle only (codes 2–7 undefined). COA p-V: shared pressure axis 0x41B4E
(0..32700), front volume sets 0x41B62/0x41B76, rear 0x41B8A/0x41B9E; gain curves 0x41A38/0x41AA4; BCO coded
thresholds 0x41764.. Rotor/piston geometry is folded into these curves (not stored scalars).

## DDS / RPA, LVC, fault manager (cycle 3)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0A623A | `rpa_correlate_step` | high(code) | per-wheel 40-tap sin/cos quadrature correlator; = 1M 0xA6022 |
| 0x0A7140 | `rpa_state_machine` | med | per-wheel 400-step; hour counter (÷3600); coding-gated |
| 0x09706A | `dds_entry` | high | dispatcher slot (0x8CCEE); modes 3/4 |
| 0x0CFC44 | `coding_dds_rpa_enable` | high | bit4 of 0x4031F4 |
| 0x0BFB6C | `lvc_main` | high | dispatcher slot; runs when (0x408CDE&0xF)==3 |
| 0x0BFF34 | `lvc_speed_level` | med | max wheel speed → 5-level ladder |
| 0x08DC2E | `mode_request(id, state)` | med | 12-record mode table at 0xDA43C (id→callback) |
| 0x0B3FC0 | `monitoring_main` | high | ~26 sub-monitors; = 1M 0xB3DA8 |
| 0x0B427C | `fault_set(id)` | high | id=group<<16\|mask; latch array 0x402838[group], NVM-pending 0x408CBC; = 1M 0xB4064 |
| 0x0B4312 | `fault_is_set(id)` | high | tests the latch |
| 0x0B9330 | `wss_direction_plausibility` | high | logs dir-fault ids at 175 counts |

Spectral tables (Q12 s16, relocated −0x308, byte-identical to 1M): sin A 0xDAFD0 (8000), B 0xDEE50 (16000),
cos C 0xE6B50 (8000), D 0xEA9D0 (16000). DDS block 0x41D10 body byte-identical to 1M (enable overrides
0x41D48/0x41D4A). **LVC block 0x41E44 body byte-identical to 1M except ONE scalar 0x4226A = 75 (1M 50)** — the
only M3-specific calibration difference in DDS/LVC/FSF. Direction-fault id table 0xF576C = {0x00020040,
0x00030040, 0x00040040, 0x00050040}. No fault-id→BMW-DTC-number table found in these ranges.

## OS / scheduler / startup / ROM self-test (cycle 4 — byte/vector/MISR verified)

OS code shift −0x220; app/wrapper −0x5C; reset/startup −0xAC; ROM tables/objects −0x390.

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x06C906 | `reset_entry` | high | vector 0; → ram_clear, PLL, VBR, INTC, timers |
| 0x06C9CC | `ram_clear` | high | clears 0x400000–0x40C000 |
| 0x06C6D8 | `pll_init` | high | programs 0xDC0000; 80 MHz (inferred) |
| 0x06C96C | `set_vbr` | high | `mtcr 0x40000, cr1` |
| 0x06C40A | `intc_init` | high | INTC 0xE10000, prio table 0xE10040 |
| 0x0D6640 | `timer_prescale_cfg` | high | called r4=79 (÷80 → 1 µs tick); writes 0xF8000F/0xD8000F |
| 0x078892 | `app_main` | high | → app_init 0x7884C, OS_Start 0x42D7A |
| 0x042D7A | `os_start` | high | → OS_Init_and_Start 0x429B2 |
| 0x042B84 | `os_scheduler` (vec32) | high | dispatcher |
| 0x070A2A | `isr_timeslot` (body 0x70A86) | high | slot counter 0x4009FA; 13-slot jump table 0x70ACC; deltas sum 10000 (10 ms frame) |
| 0x070FE4 | `T3_body` (10 ms main cycle) | high | obj 0xD7D1C; = 1M 0x71040 |
| 0x070C58 | `T2_body` (1 ms) | high | obj 0xD7DDC |
| 0x070BFC | `T1_body` (2.5 ms) | high | obj 0xD7D7C |
| 0x06DD34 | `rom_selftest_driver` | high | references range table 0xD71F4 |

**ROM self-test (re-signing critical):** range table **0xD71F4** = {0x40000–0x402F8}, **{0x40300–0x4249C}** (calibration),
{0x424A0–0xF691C}. MISR (poly 0x00400007, seed 0, BE u32 words) recomputed by the main session, matches the stored
words byte-exact: 0x402F8→0x66E81879, **0x4249C→0x310A99BD**, 0xF691C→0xC791DCD2. **After any cal edit, recompute and
write the word at 0x4249C** (error 0x10004 otherwise). This is the in-ECU MISR only; the BMY RSA signature is separate.
OS tables: entries 0x424E0, prio 0x424F4 {3,0,1,2,4}, autostart 0x42514 {1,0,0,0,1}, stacks 0x424B8/0x424CC;
runtime obj 0xD7B84 → class 0xD7E64 → objects 0xD7E40, task map 0xD7B78 {3,4,2,1,0}.

## TCS controller + engine-torque-reduction path (cycle 4 — byte/opcode verified)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0CC9A0 | `tcs_torque_ctrl_entry` (dispatch slot 17) | high | → 0xCC9B4, tail 0xCD7FE; = 1M 0xCCF5C |
| 0x0CD1E8 | `tcs_torque_pi` | high | P clamp 0x41068/6A, I clamp 0x4106E/70, out 0x40304C, flag 0x40303C bit7 |
| 0x0CD070 | `tcs_pi_gain_select` | med | gains 0x41072–78, driveline-ratio thr 0x41172 |
| 0x0CCED4 | `tcs_slip_target` | high | curve 0x41046 → 0x403054 |
| 0x0CD7FE | `tcs_reduction_floor` | med | writes floor 0x403060; **retuned vs 1M** |
| 0x0C846A | `tcs_gross_slip_check` | high | min(1500, 4000−vref); limit is **hard-coded** (not cal); = 1M 0xC8384 |
| 0x0C7D48 | `tcs_entry_gate` | high | gates **hard-coded** (>120, >300, vref<3000) vs 1M cal fields |
| 0x0CC2C2 | `dme_torque_request_compose` (slot 23) | high | writes 0x402F74/76, type flags 0x402F6D; = 1M 0xCC87E |
| 0x0CC26C | `dme_torque_inputs_scale` (slot 6) | high | DME torque RX·S/100 |
| 0x07E7A4 | `can_dme_iface_update` (0x0B6 pack at 0x7F530) | high/med | sole writer of 0x4046E6/E8 |
| 0x07AB52/0x07AB58/0x07AB48 | `can_tx_0B6_sig19/sig18/sig20` | high | getters for 0x4046E8/E6 + type |
| 0x0CBF58 | `msr_cycle_entry` (slot 16) | med | MSR/engine-drag; tail → dsc_mode_select |

**Torque-reduction path (RESOLVES the open TCS question):** TCS PI (0xCD1E8) → torque delta 0x40304C /
floor 0x403060 → arbiter `dme_torque_request_compose` 0xCC2C2 (merges TCS/ASR + MSR + AYC `engine_torque_request`
+ external limit) → **CAN TX 0x0B6** (DSC→DME, DLC5, 20 ms): sig19/sig18 = torque values (·0x333/4096 ≈ ÷5, inverse
of the ÷DME-LSB), sig20 = request type (0 none / 1 single=ASR / 2 pair). 0x800 = "no request". Negative = reduce torque.

## Hydraulic actuation (cycle 4 — byte-verified data; valve/pump roles inferred)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0843BC | `hydraulic_actuation_pipeline` (slot 32) | med | calls valve seq + pump; entry to actuation |
| 0x0853A8 | `valve_pulse_sequencer` | high | builds 10-step inlet current profile per wheel |
| 0x084460 | `inlet_mode_select(w)` | med | mode {1 hold, 2 build, 4 release} from pressure-error sign |
| 0x085A42 | `outlet_dump_time_calc` | med | → valve_pulse_set(4+w,…) |
| 0x0740BC | `valve_pulse_set(ch 0..11, ticks)` | med | primary valve SW interface |
| 0x0D4CA8 | `qspi_xfer(cs, n, tx, rx)` | high | QSPI 0xDB0000; = 1M 0xD52E8 |
| 0x0D4A30 | `asic_reg_xfer32` (CS5, cmd 0xFA) | high | combined sensor+valve/pump ASIC |
| 0x0D4BF4 | `spi_cs4_out16` (CS4, cmd 0xFB) | med | 16-bit digital-valve output latch |
| 0x088EC0 | `pump_motor_control` | med | level = clamp(0x401D2E/33, 15); cal 0x419D4/D8/DA |
| 0x073250 | `pump_motor_set_level` | med | timer-PWM, 4000 ticks/level |
| 0x070314 | `pump_motor_pwm_isr` | med | F8 timer compare 0xF80170 |
| 0x0B0154 | `kwp_valve_pump_test_drive` | med | diagnostic actuator test (SID 0x30/0x31 path) |

**12 solenoid channels** (mask table 0xD7634; test order 0xF2EF0 = [0,4,1,5,2,6,3,7,8,9,10,11]): ch0-3 inlet
(analog current via CS5), ch4-7 outlet (digital via CS4), ch8-11 USV/HSV circuit valves (roles inferred). Pump is a
timer-PWM on module 0xF80000 (not SPI). **Tunable (COA block):** valve start offsets 0x41A72/74 (40/20), build-mode
gains 0x41A76/78 (800/350), pump cal 0x419D4/D8/DA (0/100/50). **Code-literal (patch-only):** hold/boost currents
(1100/1524/1532), profile clamp 1540, ×51/400 scale, pump 4000 ticks/level, 10-step frame. Failsafe byte 0x40287D.
Dispatcher 0x8CCB8 is a flat 41-slot sequencer; slots 0–39 now named (med) in `analysis/agents/m3actuation/`.

## CAN signal dictionary — torque interface, DSC status, physical RX (cycle 5)

Signal-table backbone re-walked and byte-verified; semantic names are inference (low/med) unless noted.

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x07BB0A | `can_rx_0A8_torque_set` | high(arith) | sext12·5 → 0x401146 ("indicated engine torque"); invalid 0x800 |
| 0x07BCDC | `can_rx_0A9_torque_set` | high(arith) | −(sext12·5) → 0x401148 (engine-drag/min-torque, MSR reference) |
| 0x07BE3C | `can_rx_0AA_torque_set` | high(arith) | sext12·5 → 0x401144 (driver-demand torque) |
| 0x07BE90 | `can_rx_0AA_pedal_u8` | med/low | u8 → 0x401142 (accelerator pedal) |
| 0x07BEFC | `can_rx_0AA_rpm` | med | raw>>1 → 0x40113E, gradient 0x40113C |
| 0x07C0CC | `can_rx_0BA_gear` | med | jump table 0x7C13C → 0x4010F7 (M-DCT 7-spd) |
| 0x07F530 | `can_tx_0B6_pack` | high | 0x4046E6/E8 = 0x402F76/74·0x333/4096 (≈÷5, inverse of RX ×5), clamp ±2047, type 0x402F6D |
| 0x07AB52/58/48 | `can_tx_0B6_sig19/sig18/sig20` getters | high | 0x4046E8/E6/(0x4046D4>>5&3) |
| 0x07D24C | `can_tx_checksum8` | high | S = Σ(DLC bytes) + CAN id; out = low8(S + S>>8); last signal of every TX |
| 0x07AEAA | `can_tx_19E_status_flags` (sig39) | med | DSC/ABS/torque-intervention status bits (sources in m3cansig) |
| 0x07B1F2 | `can_tx_1A0_vspeed` | med | Σ wheel speed /20 (or /10 with 1 fault) |
| 0x07B0AC/06A/104 | `can_tx_1A0_ax/ay/yaw` | med | ×4 / ×803/2048 / ×939/16384 |
| 0x07B6D4 | `can_tx_0C4_steer_angle` | high | relays 0x401644 (F-CAN 0x0C9 steering) |
| 0x0CD7D8 | `torque_x144_lowpass` | med | 0x40305E tracks driver-demand; TCS entry gate |

DME↔DSC torque handshake: RX 0x0A8/0x0A9/0x0AA carry three 12-bit signed torques (internal unit = raw LSB ÷5,
absolute LSB unverified — likely 0.1% ref torque); `S = 0x4030A0>>6` converts wheel-torque↔engine-%. DSC's reply
is **TX 0x0B6** (see cycle 4). Lamp/warning state is broadcast on **TX 0x19E** (no GPIO lamp output exists). Yaw/ay
raw LSBs from F-CAN 0x0CD are stored unscaled (`!R`), so sensor LSB is not statically resolvable. Full per-signal
dictionary (both buses, 286 callbacks): `analysis/agents/m3cansig/`.

## Pressure/volume model + CSW/VAR/FSF/lamps (cycle 5)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x082EF4 | `hydraulic_model_step` (dispatch slot 8, 10 ms) | high | volume-domain model; calls the below |
| 0x08216E | `wheel_volume_delta(c,w)` | high | per-wheel valve-flow dV |
| 0x0826C0 | `circuit_volume_update(c)` | high | applies dV, dump to LPA, clamp V≤30000 |
| 0x00818B6 | `valve_flow(dp,k,open)` | high | Q = isqrt(|dp|)·open·k/4096, clamp 2000 |
| 0x084D42 | `supply_pressure(w)` | med-high | max(P_MC, own PM, partner PM), clamp [0,20000] |
| 0x0819FE | `coa_vol_to_pressure(w)` | high | PM 0x4016E2[w] = Vcurve⁻¹(V 0x4016DA[w]) |
| 0x08CE8E | `driver_pressure_from_sensor` | med | 0x404994 master-cylinder pressure |
| 0x0955EC | `ddsrpa_value_range_monitor` | med | uses CSW+0x18 (0x41E40=1562); faults 0xC0100.. |
| 0x0B433A | `nvm_fault_slot_commit` | high | FSF descriptor table 0xF57F8; NVM blocks 0x31/0x1B1/0x1C1 |
| 0x0B4140 | `fault_history_push` | high | 14-entry ring at 0x4028E4 |
| 0x0BAD80 | `speed_dependent_accumulator_monitor` | med | FSF 0xF57D6/DA; fault 0x124000 |
| 0x0812FA | `indicator_lamp_output_update` (slot 39) | high | 14-handler table 0xD9FB4 → lamp vector 0x40165E → TX 0x19E |
| 0x08119C | `lamp_vector_read` | high | 3-byte lamp status, read by the 0x19E getters |

Pressure model is **volume-domain** (not a simple integrator): V tracked per wheel via the COA p↔V curves, valve
flow Q = isqrt(dp)·open·k/4096, low-pressure accumulator per circuit. Tunable COA fields (k_in 957/421, k_out
755/465, k_cross, k_back 705, LPA tables, pump ramp/gain/filter, temp-comp) in the XDF. **Pressure unit ~0.01 bar**
is consistent (LPA 1.3–5.0 bar, pedal 8 bar, clamp 200 bar) but still unproven. **CSW** 0x41E28: only +0x18=1562 is
live (DDS/RPA reference); rest vestigial. **VAR** 0x41D00: empty placeholder (payload 0). **FSF** 0xF57C4: fault-NVM
slot descriptors + a speed monitor + mask tables; body byte-identical to the 1M.

## ABS controller core — pressure pipeline + decision layer (cycle 6)

ABS/vref RAM shifted +0x24; code shift −0x220/−0x200. Full work in `analysis/agents/m3abscore/`, `m3absslip/`.

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0559CC | `abs_pm_snapshot` | high | PM 0x408F2A[w] = modelled pressure 0x4016E2[ch]; dispatcher-direct after model step |
| 0x045F54 | `abs_pressure_frame` | high | per-wheel slip update, phase dispatch, dump-stage coord, decision chain |
| 0x04D270 | `abs_event_classifier` | med-high | builds the per-wheel threshold scratch, then → abs_phase_sm |
| 0x0504D0 | `abs_wheel_phase_dispatch` | high | switch on rec[0] → 5 phase handlers |
| 0x050580 | `abs_phase_armed_handler` (0x80) | med-high | RAMP=8000; CMD=min(PM+500, arbiter out) |
| 0x050894 | `abs_phase_precontrol_handler` (0xC0) | med | slow ramp to 25000; ROM curve 0xD6AFC |
| 0x04AAA8 | `abs_phase_dump_handler` (0x21) | high | → 0x55F06 target; events bit31 re-accel / bit30 |
| 0x04CA3C | `abs_phase_hold_handler` (0x09) | high | entry 0x57200; TGT = PMMIN + headroom·n/16 |
| 0x04B680 | `abs_phase_reapply_handler` (0x11/0x15) | high | step code → 0x581BA; PM+1000 end clamp |
| 0x055F06 | `abs_dump_entry_target` | high | R; 0x408F94 = max(LOCKEST − R, 0); RAMP=−8000 |
| 0x057200 | `abs_hold_entry_sync` | high | PM=CMD=SNAP=X; headroom 0x408FA4 |
| 0x05898C | `abs_slip_and_lockon_update` | high | slip 0x408F84; lock-onset latch 0x408FBC |
| 0x05862C | `abs_lockon_pressure_estimator` | high | writes LOCKEST 0x408FD0 (min-selected with PM, clamp 25000) |
| 0x044502 / 0x0447C4 | `abs_frame_entry_a/b` | high | dispatcher slots 12/13 |
| 0x0443F4 | `abs_apply_ramp` (id 19) | high | CMD +400/frame → 25000; vref gate 0x442AC = 4 km/h |
| 0x046B6… →0x0446B6 | `abs_emit_pressure_request` | high | arbiter id 1 / 11-rear, start SNAP, target UP, rate RAMP |
| 0x0584CC | `abs_cmd_slew_limiter` | med-high | CMD=min(CMD,TGT); RAMP=min(RAMP, CMD−SNAP) |
| 0x05DC08 | `abs_arbiter_output_snapshot` | high | 0x408F6E[w] = arbiter_channel_output 0x836C8(ch) |
| 0x051B54 | `abs_decision_classify` | high | writes code 0x408DDE (1/32/64/128/1024/16) |
| 0x058B30 | `abs_decision_resolve` | high | 64→16, 128→256/2, 16→8 |
| 0x058FF4 | `abs_decision_pressure_exec` | high | switch on code 2/8/32/256 |
| 0x054D9A | `abs_pair_logic` | high | partner-in-slip test (curve 0x40DB6); writes 32/1024/16/2 |
| 0x05184C | `abs_rear_lead_select` | med-high | rear select-low; DDE+10 index fields |
| 0x052380 | `abs_gross_slip_threshold` | high | **real arming threshold** curve 0xD6CE2 (≈11 % vref) |
| 0x04FC3C | `abs_phase_sm` | high | 0x80→0x21→0x09→0x11 transitions re-verified |

Key ABS RAM: PM 0x408F2A, CMD 0x408F22, LOCKEST 0x408FD0, PMMIN 0x408FC4, dump reduction R 0x409134+10w,
request flags 0x408D9C (bit7 dump/hold → id 1/11, bit4 apply → id 19), decision code 0x408DDE.

## Inter-ECU inputs (cycle 6)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x06ACC6 | `fcan_peer_exchange_task` | med | external torque-limit exchange; gated by cal 0x4182A (=0, disabled) |
| 0x06AF8A | `fcan_rx_78F_78E_parse` | high | parses the aux torque-limit frame → 0x404634/36 |
| 0x0C56D0 | `fcan_rx_queue_push` | med | F-CAN→PT-CAN gateway queue 0x402E84 |
| 0x07A172 | `fcan_to_can_gateway_drain` | med | re-sends 0x0C8/0x194/0x1D6/0x2A6/0x1D9 on PT-CAN |
| 0x07FB8A | `nm_rx_frame_process` | med | network-management, node 0x29; RX 0x480 |
| 0x07F9A6… | `can_rx_dead_stubs` | high | bare `jmp r15` setters for 0x0AC/0x0B4/0x1B4/0x0D5/0x388 and F-CAN 0x118/0x11F |

**Correction:** the old FACTS "F-CAN 0x118/0x11F = AFS" is wrong — those frames are dead (all signals discarded).

## Sensor conditioning, AYC observer & distribution, RPA (cycle 7)

**Sensor LSBs (byte-derived):** internal yaw-rate = **1/20000 rad/s = 0.0028648 deg/s/count** (349.07 counts/deg·s⁻¹);
lateral-accel = **1 mg**; wheel-derived longitudinal = 0.01 g; steering ≈ 0.044 deg/bit. AYC thresholds in physical
units: entry 4.0 (A) / 8.0 (B) deg/s, hold hysteresis 2.0 deg/s, mode ceilings 30/23 deg/s, r·v friction clamp 1.27 g.

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0905E4 | `csi_cond_sensor0` (yaw) | high | raw·sign → slew 872 → LP 241/256; unity gain |
| 0x08FE70 | `csi_cond_sensor2` (lat-g) | high | slew 49, LP 241/256; unity gain |
| 0x090B78 | `yaw_lp_to_402100` | high | feeds measured yaw B46 |
| 0x08F344 | `pressure_adc_track` | med-high | dual-track ratiometric (0x5EE8/0x97D/0x556A) → driver pressure |
| 0x05EBC4 | `yaw_observer` | high | nonlinear single-track; states β 0x400C42 / r 0x400C44; target B1A 0x400B1A; 3-regime tyre force, μ·g/v clip |
| 0x05EAC8 | `ayc_obs_wrapper` | med | inputs + μ default; calls observer |
| 0x0647D4 | `ayc_input_gather` | high | fills B38–B4C from the signal getters |
| 0x05F50E | `ayc_moment_stage` | high | → PD chain + combine → M (0x400B1C) |
| 0x05F7BA | `yaw_pd_moment` | high | dead-zone P+D, same-sign clip |
| 0x0616A4 | `ayc_moment_to_wheel_pressure` | high | oversteer→outer front, understeer→same-side rear; mode 0x400BB8[7:6]; demand 0x400B0C[4] |
| 0x064A62 | `ayc_wheel_request_submit` | high | arbiter id 3 (brake) + id 20 (front-outer pre-fill) |
| 0x065494 | `ayc_torque_cap_B30` | high | 0x400B30 = min(0x400D24, 0x400DB0) → min-merged into TX 0x0B6 |
| 0x04A254 | `abs_yaw_deviation_monitor` | med-high | **AYC→ABS link**: e = measured yaw (0x408ECC) − target B1A (0x400B1A) |

**ABS sensor-gather RAM (corrects cycle 6):** 0x408EB2 = **driver brake pressure** (not yaw); 0x408ECA = lateral accel
(the x for the decision-32 yaw-limited-build curves); 0x408ECC = measured yaw rate; 0x408ECE = yaw accel.

### DDS/RPA spectral algorithm (cycle 7 — resonance-shift tyre-pressure monitor)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0AA550 | `rpa_tooth_period_proc` | high | 48-tooth period capture + learned per-tooth correction |
| 0x0AA758 | `rpa_resample_uniform_time` | high | angle→uniform-time resample (~400 Hz) |
| 0x0AA812 | `rpa_window_dc` | high | windows 0xF26D0 (flat-top, fronts) / 0xF29F0 (bell, rears), Q13 |
| 0x0A623A | `rpa_correlate_step` | high | 40-bin direct DFT bank over the sin/cos tables |
| 0x0A61D8 | `rpa_power_spectrum` | high | re²+im², 80 words; band 14–151 Hz |
| 0x0A5EA8 | `rpa_spectrum_learn_step` | high | per-context (speed×load) learned baseline spectrum |
| 0x0AABDA | `rpa_peak_shift_hyst` | high | peak-shift vs baseline, 1.2× ROM thresholds 0xDAC58/0xDACD0 |
| 0x09D574 | `rpa_verdict` | med | plausibility gate → fault 0x001B8000 |
| 0x097490 | `rpa_warning_set` | med | dash/CAN low-pressure warning request |

The correlator computes a **wheel-speed vibration power spectrum (14–151 Hz)**; the decision is a per-wheel
**resonance-frequency shift vs a speed/load-context-learned baseline** with persistence. Coding-gated (0x4031F4 bit4).
Physical "tyre deflation" purpose inferred; the DSP chain and thresholds are byte-verified.

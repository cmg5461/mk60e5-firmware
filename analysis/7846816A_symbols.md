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
| 0x0710FC | `s16 curve_interp_s16(const curve_t *rec, s16 x)` | high | piecewise-linear reader; strict-less segment search, Q10 truncating multiply, clamp [lo,hi]. Layout `{s16 lo, hi, n; x[n-1]; y[n]; slope[n]}`: out = y[i] + x·slope[i]/1024 (truncating), i = count of x < X (the scan runs one slot into y[0], harmless). Instances: BCO pedal curve 0x4177A (x {38,62,100,150,200}, y {15,9,11,50,50,50}, slope {269,427,404,0,0,0}), 0x41802, 0x417D0. M3 analogue of 1M 0x71158. Byte-verified on multiple curves |
| 0x05DE44 | `void vehmodel_load_singletrack_coeffs(void)` | high | indexed by `0x4031AA+1` (variant), `ld.h [base+2*var]`; writes single-track coeffs to RAM 0x400AA4..0x400AE6 (formulas: § "Vehicle-model derived coefficients"). Only reader (with 0x5E424) of the vehicle-model rows |
| 0x05E424 | `void vehmodel_load_axle_derived(void)` | high | indexed by `0x4031AA+1`; writes 0x400AE8..0x400AF8 (v_ch terms, sensor lever arms, wheel-yaw factor); contains the `Cr*l_r − Cf*l_f` understeer term (fixes Cf=0xD6ECA, Cr=0xD6EE2). Replayed against the image 2026-10-26: a neutral model divides by 0, an oversteering one divides unsigned by a negative |
| 0x054D9A | `abs_pair_logic` | high | contains the ABS entry-slip evaluation; loads curve 0x40DB6, x = vref (0x408DA8), calls 0x710FC at +0x1B0/+0x2C8/+0x540 (0x54F4A/55062/552DA are **call sites**, not separate fns), result compared vs `vref − wheelspeed` |
| 0x040D80 / 0x040D82 | `abs_pair_logic_enable_a/b` (cal, 1 / 1) | high | `abs_decision_classify` 0x51F78–0x51FA0: both non-zero and code 64 or 32 → call `abs_pair_logic`; 0 disables µ-split yaw-moment limiting |
| 0x053720 | `abs_decel_est_filter` | high | writes 0x408EE8 (DAF source = 0x408EE8 / 21): IIR 20/21 of the mean rec+0x22, slew ±200, clamp ±2667 |
| 0x0C795E | `tcs_driveslip_curve` | high | brake-TCS (channel A) base threshold: addr = 0xF625C+0x22·m (m = `0x4031AA+7`), replaced by 0xF61F6+0x22·m when `0x402F6C` b4 (gearbox type 1/3, never on a valid M3 coding); x = vref_tcs 0x403066. `TCS_7846816A.md` §4.1 |
| 0x0C7996 | `tcs_driveslip_total` | high | `tcs_driveslip_curve + trunc(s16(0x4030B6)/4)` → 0x402FC2 (replayed, TCS doc §13) |
| 0x0C7948 | `tcs_curve_f61e6` | med | reader of the 0xF61E6 curve (inside `tcs_state_b` 0xC7818) |
| 0x0CB576 | `asr_target_cap_up` (was `tcs_cap_eval`) | high | ASR (channel B) split-side target raise, only when \|ay\| 0x403098 > 0.25 g: min(curve(0xF654C+0x22·m, vref)/20, (0x403098 − 2500)/0x41160[m]), further capped by a 0x4030B8 term; the companion lower is `asr_target_cap_down` 0xCB622 (0xF65B2+0x22·m, 0x41166/0x4116C). TCS doc §5.1 |
| 0x06D102 | `s16 sat_s16(s32 x)` | high | clamp to [−32768, 32767] (`bmaski 15` / 0xFFFF8000 compare), then `sexth`. Called after divs/multiply chains in the model loaders and CSI |
| 0x08E25E | (not a function) | – | mid-function code inside `sub_08E144` (byte-identical to 1M 0x8E066, also mid-function), never called, does not touch the coding block. The M3 variant is read directly (`ld.b 0x4031AA+1`); the `0x8E066(24, sel)` calls seen near the model loaders are `state_nibble_get`, not a coding accessor |

## Variables (RAM / coding)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x004031AA | `coding_block` (12 B: +1 variant, +2 gearbox, +3/+4 brake front/rear, +5 steering-ratio set, +6 feature row, +7 DSC mode m (run time), +8 RPA threshold, +9 hill-start level, +10 LVC rpm limit; +0/+11 unused) | high | indexed `ld.b` in both model loaders and the TCS curve/cap readers; field table in `CODING_BYTES_7846816A.md` |
| 0x00402F6C | `asr_flags` (was `tcs_flags`) | high | b7 ASR active, b6 ASR request (slip over target), b5 second ASR entry path (writer open), b4 = `gearbox_type` ∈ {1,3} (slot 6 0xCC26C; selects the alternate brake-TCS set 0xF61F6), b2 = 0x402F6A b1. Byte +1 (0x402F6D): b3 torque-reduction request, b2 torque-increase (MSR) request (arbiter 0xCC2C2). TCS doc |
| 0x00403066 | `vref_tcs` (reference speed = min of front wheels, 0.01 km/h) | high | x input to TCS drive-slip curve |
| 0x00408DA8 | `vref_abs` (0.01 km/h) | high | x input to `abs_entry_slip_eval` |
| 0x00402FC2 | `tcs_driveslip_threshold` | high | store target of `tcs_driveslip_total`; zeroed while channel A is inhibited |
| 0x00400AA4 | `vehmodel_ram` (single-track coeffs block, ..0x400AF8) | high | store targets of the two model loaders; per-word formulas in § "Vehicle-model derived coefficients" |
| 0x00409534 | `diag_routine_id` (u8) | high | SID-31 routine id (RLI) from the diag RX buffer; jump-table index in `kwp_31` (`0xB2B22`, `index = id−5`) |
| 0x00409535 | `diag_routine_arg` (u8) | high | SID-31 argument byte; **must be 0** for cal routines `0x20/0x22/0x24` (`0xB2C74`), else NRC `0x12` |
| 0x00409537 | `diag_access_token` (u8) | high | KWP "last-qualifying-op" sequence token. `31` routines need 3 (set by StartCommunication `0xB33B0`); coding write needs 51 (set by `22 30 00` read). Compared, never auto-set, by the dispatcher/handlers |
| 0x00409538 | `diag_nrc` (u8) | high | pending negative-response code; a non-zero value short-circuits `kwp_31` to the error exit (`0xB2C96`) |
| 0x00409435 | `diag_resp_ready` (u8) | high | response-ready flag; set to 1 by StartCommunication (`0xB33B6`) and on routine success (`0xB300C`) |

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
  variants 0–4 == 5–9 (Competition twins of sedan/Custom ESM/?/coupe/convertible),
  10/11 unique (GTS coupe / GTS sedan)): l_f 0xD6F42 (Q10 m), l_r 0xD6F5A (Q10 m),
  mass 0xD6F72 (kg), Jz 0xD6F8A (kg·m²), Cf 0xD6ECA, Cr 0xD6EE2 (stiffness, units TBD),
  track front 0xD6FA2, track rear 0xD6FBA (**Q10 m**, not mm), override-enable flag 0xD7032 (all 0).
  All rows: s16[12]. Patcher param patch: `mk60e5_patcher` `basic/vehicle_model`. More rows (2026-10-26):

  | Address | Name | Type / unit | Stock | Conf | Evidence |
  |---|---|---|---|---|---|
  | 0xD6F2A | `vm_sensor_x` | s16[12], Q10 m | −1204 (−1.176 m) | med | −(yaw/lat sensor distance behind the front axle). 0x5E424: l_f + x, x, L + x → lever arms 0x400AEC / AF0 / AF2 |
  | 0xD6F12 | `vm_sensor_y` | s16[12], Q10 m | 446 (0.436 m) | med | sensor lateral offset from the centreline, toward +ay. 0x400AEE = round(10240000 / (167·y)); `ay_axle_est_calc` adds ω²·y: (yaw/256)²/AEE mg matches ω²·0.4355 m exactly. 0 skips the term |
  | 0xD6EFA | `vm_aux_h` | s16[12] | 532 | low | divisor in 0x400ACA/ACC = 112613·t²/1024/(m·532). Possibly CG height (0.52 m in Q10); role not traced |
  | 0xD7002 | `vm_pair_d7002` | s16[12][2] (stride 4, `ixw`) | {50, 20} ×12 | med | 0x400AE4/AE6 = pair · Cf · 1024 / 40039. Spans the old "row" 0xD701A |
  | 0xD6FD2 | `vm_pair_d6fd2` | s16[12][2] (assumed, same pattern) | {10000, 14000} ×12 | low | single reader 0x5ED9E (observer); spans 0xD6FEA |
  | 0xD6E3A..0xD6EB2 | `vm_override_{a,b,c}_{f,r}` | s16[12] ×6 | 687/694, 300/306, 9609/9513 | med | copied to 0x400AC6..ACE/AD0 instead of the track-derived values when 0xD7032[var] ≠ 0 and var ≠ 1; dead on this ROM |

  The steering-ratio sets 0x40EB4 / 0x40ECC (s16[3][4] each: SW counts, ratio × 1024) are in § CSI.
- **ABS entry-slip curve** 0x40DB6 (lo0,hi900,n2,bp5000,c150/115,k−4/+3; threshold ~1.3–2.0 km/h).
- **ABS decel scalars** (ABS=0x4039C): gain front +0x27E=40, gain rear +0x280=25, floor +0x282=−240,
  base +0x284=−116; floor<20 +0x2A8 (12×, −127 then −120); floor<60 +0x2C0 (12×, −132×10, −140×2);
  ladder +0x76C; staged A +0xAC2 {−62,−78,−94}, staged B +0xB02 {−25,−44,−62}.
- **ABS front speed-term curve family** 0x40412 + 0x28·m (m=0..11); **rear** single 0x405F2;
  **g-term curve family** 0x40674 + 0x40·m. Variants 0–9 identical; 10/11 (GTS) more permissive.
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
| 0xF59DD | `fcan_message_table` (32 × 23 B = 736 B) | high | TX 0x080/0CE/11E/130/374/79x/7Dx; RX 0x0CD/0D1/0C9/118/0D4/… |
| 0xF5CBD | `fcan_signal_table` (90 × 5 B = 450 B) | high | shift −0x308 from 1M 0xF5FC5 |
| 0xF5ED0 | `fcan_variable_table` (≥ 81 × 8 B = 648 B) | high | shift −0x308 from 1M 0xF61D8 |

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
- **`kwp_31_start_routine` 0xB2B1C** — internal two-stage gate, **no SecurityAccess**:
  reads routine id `0x409534` and arg `0x409535` from the diag RX buffer, dispatches via jump table
  `0xB2B98` (index `id−5`). Stage 1 (gate `0xB2C82`): requires `0x409537 == 3` and, for the
  calibration ids `0x20/0x22/0x24` (shared handler `0xB2C72`), the **arg byte `0x409535 == 0`** →
  else NRC `0x12`. Stage 2 (preconditions `0xB2D08`–`0xB2D44`): requires the per-sensor ready bit in
  `0x40200C` (b7 pressure/`20`, b5 steering/`21`, b6 lateral/`22`, b0 long-accel/`24`) → else NRC
  `0x22`. On pass re-stamps `0x409537=3`, sets `0x409435=1`, body dispatched via second table
  `0xB2D8C`. The token-3 prerequisite is **set by StartCommunication `kwp_81_comm` 0xB33B0**
  (`st.b 3 → 0x409537`), not by `0x27`; capture-confirmed `31 22 00` works after a bare
  `10 81 → 10 87` with no seed/key. Full spec: `analysis/SERVICE_ROUTINES_7846816A.md` §3d.

## NVM / coding (byte-verified by clean opcode diff)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x06E16C | `nvm_queue_job` | high | called from kwp_22/2E/23/3D |
| 0x06E288 | `nvm_request` | med | opcode window match |
| 0x06E9C4 | `nvm_read_sync` | high | calls the SPI drivers |
| 0x0D4DC0 | `spi_driver_a` (CS2 coding EEPROM) | high | clean opcode diff vs 1M 0xD5400 |
| 0x0D4F50 | `spi_driver_b` | high | clean opcode diff vs 1M 0xD5590 |
| 0x0CFC00 | `coding_field_read(record, idx)` | high | clean opcode diff vs 1M 0xD0240; jsri from kwp_22; reads 0x4031F4/F6 |
| 0x06C6A8 / 0x06C6B8 | `irq_disable` / `irq_restore` | high | bracket SPI critical sections |
| 0x004031F4/F6 | `coding_block_packed` | high | unshifted RAM, clean function diff |

## Coding write validator (`2E 30 00`, read from code)

Chain: `kwp_2E_did3000_write` → `coding_validate_write` → `coding_validate_unpack`, which runs the five
stages below over the 48-byte RX buffer and records them in `coding_validate_status`. Every stage
returns 0 = pass, non-zero = fail (stages 2–5 return 1; the checksum stage returns the raw XOR residue,
of which only bit 0 reaches the status byte, though the full value is OR'd into the result); any
failure → NRC 0x31. Field-level constraints: `CODING_BYTES_7846816A.md`.

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0B2A16 | `kwp_2E_did3000_write` | high | DID-3000 branch inside `kwp_2E_write_data_common_id` (0xB2874), not a function start; requires `diag_access_token` 0x409537 == 0x33 else NRC 0x12, 0x409544 == 16 else NRC 0x22; NRC 0x31 only if `coding_validate_write` returns exactly 1; otherwise queues block-10 write via descriptor 0xF31B4 + 0xB4 = 0xF3268 |
| 0x0CF432 | `u8 coding_validate_write(const u8 *buf)` | high | 0 = pass, 1 = fail. If `state_nibble_get(24, 1)` == 4 → returns 0xFE without validating, which the handler accepts (raw bytes stored, active image untouched); else returns `coding_validate_unpack(buf)` |
| 0x0D02E6 | `u8 coding_validate_unpack(const u8 *buf)` | high | 0 = pass, 1 = fail; sets 0x4030D2 = 1, calls `coding_image_clear`, then the five stages in order; each stage sets a "ran" bit in 0x4030D2 and its fail bit in 0x4030D3 (checksum b2, fields b3, flag words b4, word array b5, feature combo b6); result OR'd into `coding_validate_finish` |
| 0x0CF3EE | `void coding_image_clear(void)` | high | zeroes `coding_block` 0x4031AA+0..11 and 44 u16 at 0x4031B6 (also called by the EEPROM boot loader on a bad image) |
| 0x0CF41E | `void coding_image_clear_seal(void)` | low | `coding_image_clear` then `coding_image_seal(0)`. **Unreferenced:** well-formed body (follows a `jmp r15`, `subi r0,8` prologue, tail `jmpi`) but no `bsr`/`jsri` to it and no `0x000CF41E` literal in the image, so probably dead code; Ghidra does not create a function here |
| 0x0CFDB8 | `u8 coding_checksum_check(const u8 *buf)` | high | returns `(c0 − 1) ^ c1 ^ … ^ c47`; non-zero = fail, i.e. requires `c0 = XOR(c1..c47) + 1` |
| 0x0CFDD8 | `u8 coding_unpack_block(const u8 *buf)` | high | stage 2; see the entry under Brake coding below |
| 0x0CFF1A | `u8 coding_pack_flag_words(const u8 *buf)` | high | stage 3; packs flag words A/B (0x4031F4/F6) from c3, c10, c13–c15, c18–c20, c30; fails if c3 b5 = 0 (SDR_CTC), c18 b6 = 1, c14 b4 = 1, or c10 b4 (DDS Plus) = 1 with c3 b3 (RPA) = 0 |
| 0x0D0064 | `u8 coding_unpack_words(const u8 *buf)` | high | stage 4; fills `w[]` at 0x4031B6 from c4..c47; fails if c25 or c26 has b6/b7 set, if variant (f+1) = 1 and any of c31–c34, c37, c38 = 0 (check at 0xD01AA), or if f+5 = 1 and any of c41–c47 = 0 |
| 0x0D024C | `u8 coding_feature_combo_check(const u8 *buf)` | high | stage 5; builds requested feature bits from c3 b2/b3, c18 b6, c13 b5/b6 and calls `coding_feature_row_select(val0, 0x1C16, val1, 0x0002, val2, 0x0100)`; fails (returns 1) if no feature row matches |
| 0x0CF5D8 | `u16 coding_feature_row_select(u16 val0, u16 mask0, u16 val1, u16 mask1, u16 val2, u16 mask2)` | med | for each of the three feature-word tables 0xF677A / 0xF67DC / 0xF683E (u16 × 49): word = (val & mask) \| (tbl[f+6] & ~mask), flag 0x80 if val has bits outside mask; then searches rows 1..48 for one matching all three words and writes its index to f+6 (`coding_block`+6, the row `coded_feature` reads). Returns 0 = found, 0x80 = bad request / no match. Also called from 0xCF67C (which passes two more u16 on the stack) |
| 0x0D02C4 | `u8 coding_validate_finish(u8 fail)` | high | fail: `fault_set(0xC0002)`, `coding_image_clear`, `coding_image_seal(-1)`, returns 1; pass: `coding_image_seal(0)`, returns 0 |
| 0x0CF9C8 | `u8 coding_image_checksum(void)` | high | XOR of `coding_block` +0..11 and both bytes of the 44 u16 words at 0x4031B6, plus 1 (same XOR+1 scheme as wire byte 0) |
| 0x0CFA10 | `void coding_image_seal(s32 poison)` | med | stores `coding_image_checksum` to 0x4030DC, +1 when poison = −1 so the stored image deliberately fails its check; sets b3/b5–b7 and clears b4 of 0x4030DD |
| 0x08E066 | `u8 state_nibble_get(u32 id, u32 sel)` | low | id 24: `(0x401FAC >> (sel == 1 ? 2 : 5)) & 7`; other ids: nibble of 0x401F94[i] found via table 0xDA43C (11 × 12 B). Meaning of value 4 (blocks the coding write) unknown. Callers pass (24, 0/1) from the vehicle-model, ABS/DSC (0xB7E5E…) and validator code and (16, 0) from NVM code (0x6DF54…), comparing against 1–4: an operating-state getter. NB: 1M 0x8E066 is mid-function code (= M3 0x8E25E), not this function |
| 0x00403320 | `coding_write_buf` | high | 48-byte `2E 30 00` payload; NVM write descriptor 0xF3268 |
| 0x004030D2 | `coding_validate_status` (2 B) | high | +0 stages-run bits, +1 stages-failed bits (see `coding_validate_unpack`) |
| 0x004030DC | `coding_image_check` | med | checksum byte of the unpacked image (EEPROM block 7), written by `coding_image_seal` |
| 0x0CF396 | `void coding_boot_load(void)` | med | `0xCFB14` (load + check block 7), `0xCF81C`, then tail `coding_custom_words_check` |
| 0x0CFB14 | `coding_image_load` | med | loads EEPROM block 7 into 0x4030DC / 0x4031AA / 0x4031B6, checks the check byte (mismatch → fault 0xC0040, `coding_image_clear`, invalid flag) and runs `coding_field_limit_check` (0xCFBA6); see `EEPROM_MAP_7846816A.md` |
| 0x0CF32C | `void coding_custom_words_check(void)` | high | boot re-check: variant 1 needs w11, w12, w15, w18 ≠ 0; f+5 = 1 needs w22–w28 ≠ 0; else `fault_set(0xC0002)` |
| 0x0CF3C2 / 0x0CF3C8 | `u16 coding_invalid_flags_get(void)` / `void coding_invalid_flags_set(u16 mask)` | med | read / OR into 0x4030E0 |
| 0x0CF67C / 0x0CF6D2 | `u8 coding_feature_row_change(...)` (two variants; 0xCF6D2 also checks `state_nibble_get(24,1)` ≠ 4) | low | run `coding_feature_row_select` starting from the live f+6 row and reseal the image if f+6 changed (failure: `fault_set(0xC0001)` + invalid flag); would change coded features at run time. **Unreferenced**: no `bsr`/`jsri` and no pointer literal in the image |
| 0x0CF750 | `u8 coding_feature_row_exists(u16 val0, u16 mask0, u16 val1, u16 mask1, u16 val2, u16 mask2)` | low | same merge/search as `coding_feature_row_select` but only returns 1 if a row matches (does not write f+6). **Unreferenced** |

## Control / ABS controller (cycle 2 — ported by opcode diff, all clean unless noted)

The ABS controller (1M 0x44000–0x5E000) maps to the M3 with a constant shift (−0x220 for 0x44xxx–0x4Bxxx,
−0x200 for ≥0x4Cxxx); 196 functions mapped (`analysis/agents/m3control/abs_fnmap.txt`). ABS/vref working
RAM is shifted **+0x24** vs the 1M. The ABS cal block is re-laid-out: offsets ≤+0x74 unchanged, +0xC6..CE
shifted +0x1B8, ≥+0x134 shifted +0x4A4.

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x08CCB8 | `control_dispatcher` | high | flat 41-`jsri` per-frame call sequencer (NOT a jump table); tail-jumps to 0x88D00; = 1M 0x8CAD8 |
| 0x08CE5E | `dispatch_slot00_driver_pressure` | high | driver pressure 0x404994 from master sensor, wheel-sensor mean as fallback; = 1M 0x8CC7E |
| 0x08428C | `abs_pressure_arbiter` | high | dispatcher slot 31; = 1M 0x840AC |
| 0x0833DA | `req_arbiter_submit(op,id,ch,start,target,rate,flag)` | high | = 1M 0x831FA |
| 0x083F26 | `s16 req_slot_step(slot_t *slot)` | med-high | slot (rec 0x401728 + 56·w, slot k at +8+12k): +0 id, +4 current (start), +6 rate, +8 target (s16, 0.01 bar), +10 flag. rate 0x2710 → rate := target − current; rates ±8000 / 9000 → current := target; other rates step current by ±\|rate\| (0.01 bar) per 10 ms frame toward target. Returns current |
| 0x083FEC | `void req_channel_resolve(u8 w)` | med | steps every slot of wheel w via 0x83F26 into `0x401A2A[id]` (s16), then `0x4019FE[w]` = output of the owner id (`0x401960[w]`), flags into 0x401A56 |
| 0x083720 | `channel_owner_select` | high | priority arbitration → 0x401960; = 1M 0x83540 |
| 0x0853A8 | `valve_pulse_sequencer` | high | = 1M 0x851C8 |
| 0x0819FE | `coa_vol_to_pressure` | high | = 1M 0x8181E |
| 0x04FC3C | `abs_phase_sm` | high | per-wheel rec[0] state machine; = 1M 0x4FE3C |
| 0x0449D0 | `vref_update` | high | rate-limited vref integrator; = 1M 0x44BF0 (constants unchanged). Falls only when vref > fastest wheel: fixed steps (normally −22/−32/−44) bounded by a limiter on 0x408DAF, or `vref_fall_from_ax` 0x50FF4 when ax is trusted and all chassis sensors are valid (`agents/abs_full/10_vref_and_ax.md`) |
| 0x0D20DC | `wheel_accel_update` (void, s16 dv) | high | called by `wheel_speed_update` with Δv (0.01 km/h per frame, clamped ±5714): rec+0x1E = trunc(trunc(dv·57991/2048)/10) ≈ dv·2.8316 (instant, 0.01 g); rec+0x20 = (rec+0x1E + previous rec+0x1E)/2. Literal 0xE287 = **57991** (older notes said 58023, a conversion slip); = 1M 0xD271C. `WHEEL_SPEED_CHAIN_7846816A.md` §4.3 |
| 0x0443F4 | `abs_apply_ramp` | high | request id 19; = 1M 0x44614 |
| 0x05424C | `abs_dump_stage` | high | = 1M 0x5444C |
| 0x051B54 | `abs_decision_classify` | high | writes decision code 0x408DDE; = 1M 0x51D54 |
| 0x047BDC | `abs_decel_threshold_builder` | high(entry)/med(body) | **M3-rewritten**: variant-indexed curves (0x40412/405F2/40674 by 0x4031AA+1) vs 1M fixed curves; = 1M 0x47DFC |
| 0x046390 | `abs_wheel_decel_filter` (was `wheel_peak_decel_byte`) | high | from `abs_wheel_signal_frame`. rec+0x24 = a + 210/256·(rec+0x24 − a), a = rec+0x20, clamped −1000…500; reset to 0 when the phase byte gains b4 and when rec+0x18 b3 is newly set (a ≥ 17, braking regime); limited to 200 (400 while vref − v > 500) under 0x40493A b5 + 0x40905E flags. rec+0x39 = a/16 peak (a clamped ±2032, +100 below 5 km/h if a ≥ 0), braking regime only, else 0; = 1M 0x465B0 |

Key M3 ABS/vref RAM (shifted +0x24): `vref` 0x408DA8, decision code 0x408DDE, decel-threshold array
`abs_decel_thr` 0x4090E6 (s16[4], 0.01 g, written by 0x47BDC), dump target/reduction 0x4091AE/0x4091AC. Hard-coded speed-dependent ROM curves relocated to
**0xD6AFC–0xD6D50 (byte-identical to 1M 0xD713C–0xD7390)**. Hard-coded (code-patch only, not cal):
clamps 25000/−8000, wheel-speed-delta clamp ±5714 (0x75540/44), accel scale 57991/20480 (0xE287), vref rise/fall/snap.

ABS estimation RAM: ax `0x408E80` (s16, 0.01 g; source byte `0x4049FC`), ax-valid copy `0x408E1B` b4 (`0x408E6D`
b3 is set and cleared again in the same gather pass), ax trusted `0x408E1C` b7, wheel-derived decel estimate `0x408DAF` (s8 = `0x408EE8`/21), vref slope `0x408DB8`, vref shadow
`0x408E7E`, regime flag `0x408DA1` b4, broadcast speed `0x404720`. Wheel records `wheel_rec` 0x40BF00 + 0x40·w
(w = 0 FL, 1 FR, 2 RL, 3 RR). Timer edge → record, with every speed/accel field and the constants that set it:
`WHEEL_SPEED_CHAIN_7846816A.md`.

## Wheel-speed chain (cycle 2 — vectors + opcode diff, clean)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x070CD0 | `isr_wss_edge_ch0` | high | vector 59; F8 +0x8E; **wheel 0 (FL)**; 0 opcode diffs vs 1M. Per edge: n ≥ 57 → disable this capture IRQ and return; else t_b = t_a, t_a = capture >> 2 (u16), 32-bit stamp history 0x40933C/0x40934C, first 22 edges: same-polarity period → RPA buffer *0x4091CC; n++ |
| 0x070D56 | `isr_wss_edge_ch1` | high | vector 57; F8 +0x9E; **wheel 3 (RR)** |
| 0x070DE0 | `isr_wss_edge_ch2` | high | vector 58; D8 +0x8E; **wheel 1 (FR)** |
| 0x070E6A | `isr_wss_edge_ch3` | high | vector 56; D8 +0x9E; **wheel 2 (RL)** |
| 0x073B1C | `wss_frame_latch` | high | vec60 time base slot 0 (0x70B06), once per frame before T3. Latch part 0x73B5C: `wss_edge_capture` → `wss_edge_latch` (20 B); latch+24/26 = old +20/22, latch+20/22 = F8/D8 time >> 2 (now); swaps RPA buffers 0x4091CC/0x4091C8; clears the edge counts |
| 0x0D550C | `wss_capture_read(ch)` | high | 7-case jump table at 0xD551C; called from all ISRs; = 1M 0xD5B4C |
| 0x0D569C | `wss_capture_config(ch, flags)` | high | called ch 0..3 with 0x91 at 0x6F52C..3E; = 1M 0xD5CDC |
| 0x07525C | `wheel_speed_update` | high | T3 (0x71018; also the mode ≥ 3 body 0x70FC2). Per wheel: n edges → v = 100·m·(K/100)/P with P over an even number m of intervals (n even: t_a − ref_a, m = n; n odd: t_a − ref_b, m = n + 1; n = 1: m = 2); n = 0: v = min(v_prev, 2K/(now − ref_b)), refs held ≥ 60000 behind now, so a stopped wheel settles at 2K/60000; clamp [floor, 30000] → `wheel_speed_raw`; n ≥ 57 re-enables the capture IRQ; sets `wss_status` b7 on no-edge frames. Unless `ecu_mode_ge(3)`: `wss_speed_plausibility`, then `wheel_accel_update`(Δv clamped ±5714). = 1M 0x752B8. `WHEEL_SPEED_CHAIN_7846816A.md` §4 |
| 0x0751A8 | `wheel_cal_prepare` | high | init (literal 0x6F9D8). 0x40935C = BFU circumferences; K = 900·C → 0x4033CC/0x4033D0; floor 0x4032D0 = **max** over axles of 2K/60000 (`cmplt r2,r3; movf r3,r2`); = 1M 0x75204 |
| 0x0751E2 | `wheel_circ_get(u16 out[2])` | high | copies 0x40935C front/rear; caller 0x9EDE0 (RPA) |
| 0x075226 | `bfu_teeth_get(u8 out[2])` | high | BFU teeth front/rear as bytes; RPA callers 0x9EB2C, 0x9EDF2, 0xA11A6, 0xA65CE. 0x751EE / 0x7520A next to it are unreferenced |
| 0x0754A2 | `wheel_edge_count_get(u8 out[4])` | high | copies `wheel_edge_count` 0x4033D4 |
| 0x06EC18 | `wss_speed_plausibility` | low | per wheel from `wheel_speed_update` (Δv, m, P, K/100 as u16); thresholds BFU teeth·200 / teeth·900, 5,000,000/(4·P/m) count-down, gated > 20 km/h; can `fault_set` a per-wheel id. Not decoded |
| 0x0B67F4 | `wheel_speed_filter` | high | per record from `wheel_post_frame`. Normal: rec+0x1A = raw. Slew mode (rec+0x19 b7) entered on \|rec+0x1E\| > 10000 (12000 with rec+0x10 b1) or ≥ 57 edges: seeds vref, zeroes rec+0x20/22; then f += clamp((v − f)/8, ±56), rec+0x20 = d·283/100; exits when \|v − f\| or \|v − vref\| < 200 and n < 57. Low-speed reseed to 800. rec+0x19 b5 = b7; b6 after S (0x402910) reaches 102 (+6/frame). Init phase (0x400966 b6): passthrough. = 1M 0xB65DC. `WHEEL_SPEED_CHAIN_7846816A.md` §5 |
| 0x08F028 | `wheel_post_frame` | high | T3 (0x7101A): `wheel_speed_filter` × 4, 0xB85EC, 0xB92A6, chassis sensors 0x92E6E / 0x91A7C / 0x91008, 0x8F0A8, 0x8F010 (→ `wheel_minmax_select`), `abs_wheel_signal_frame`, `ax_from_front_wheels`, 0xC953C, 0x94828, tail 0x92840 |
| 0x08F1F8 | `wheel_struct_init` | high | init (0x6F7FA, after `wheel_cal_prepare`; also 0x94A0E): rec+0x2A = w, vref 0x408DA8 = floor, 0x408DB6 = 1, slowest/fastest pointers = wheel 0 |
| 0x0461C0 | `abs_wheel_signal_frame` | med | from `wheel_post_frame`. First decides the **factory-stagger switch 0x408DF1 b7** (front main slip on rec+0x1C): 0 unless \|FL.b − FR.b\| < 5, \|RL.b − RR.b\| < 5 and 2·cal − 20 < (RL.b + RR.b − FL.b − FR.b) < 2·cal + 10 with cal ABS+0x66 (0x40402) = 25; then 1 if 0x403210 b0 and (0x403212 & 31) ≥ 9, else unchanged (`TYRE_TOLERANCE_LEARNING_7846816A.md` §3.1). Then per record: 0x4A7B0, `abs_wheel_decel_filter`, `wheel_accel_abs_mean`, 0x47298 (rec+6), 0x5D6F8, 0x5D618, 0x46594 (rec+0x3A), 0x47294, 0x46ADC, 0x4F9D4, `abs_decel_onset_latch` |
| 0x046340 | `wheel_accel_abs_mean` | high | rec+0x26 = \|a\| + 210/256·(rec+0x26 − \|a\|), a = rec+0x20, cap 500; 0 while phase byte has b3 or b5 |
| 0x0D210C | `wheel_accel_lp_peak` | high | from `vehicle_estimators_frame`. a' = clamp(rec+0x20, ±2032): rec+0x38 = signed peak of a'/16 (up when a' > 0, down when a' < 0); rec+0x22 = rec+0x20 + 210/256·(rec+0x22 − rec+0x20), clamped −1000…500 |
| 0x071CC0 | `count_standstill_wheels` (s8) | high | wheels with rec+0x1A < BFU 0x41CF2 (72): counter 0x4033D9 −1 with ≥ 3 such wheels, else +1 (0..10); 0x4033DA b7 set at 10 (moving), cleared at 0. Returns 1 stopped, 0 moving, −1 invalid (0x40288C b2 or ≥ 2 faulted wheels). Caller 0x71D98 (writes 0xF80116 bits) |
| 0x0B9330 | `wheel_direction_update` | high | sole writer 0x4029D2..DE (38 stores); = 1M 0xB9118; see "Wheel direction" below |
| 0x0B973C | `wheel_direction_valid(w)` | high | 57 insns, 0 diffs; = 1M 0xB9524. Returns **1 above 70 km/h** (no further check); below that needs the valid bit and no fault bit |
| 0x075A5E | `validate_dir_cfg(x)` | high | constant map: returns 15 for x ∈ {0,1,2,3,15}, else 0. Called with 15 (0xB93C4) → mask 0x4029D6, and with w = 0..3 (0x7E9F8) → 0x4046D7 b3..b0. So every wheel is direction-sensing in this image |

| 0x0D144A | `tyre_tol_learn` | high | per-wheel tyre factor learner; writes rec+0x1C (corrected speed) and steps 0x403214; detail `TYRE_TOLERANCE_LEARNING_7846816A.md` |
| 0x0D10EC | `tyre_tol_spare_detect` | med | three wheels matched (< 1.5 %) and one 8.1–20 % fast for 13 passes → 0x40320E b1, factors loaded at once |
| 0x0D0480 | `tyre_tol_normalise(u8 *b)` | high | adds 255 − max to all four bytes (slowest wheel = 1.0) |
| 0x0D0444 | `clamp_s16(lo, hi, x)` | high | r2 = lo, r3 = hi, r4 = x |
| 0x0B6A08 | `wss_ratio_plausibility` | high | pairwise sorted-speed ratios; band lo 150 → 125 % (20 → 40 km/h, ROM 0xF56E6/EA), hi 250 %; limit 3000 → 1000 (0xF56EE); → 5Dx5 (bit 10) on fast wheel(s), 5Dx3 (bit 11) on a slow wheel |
| 0x0B651C | `wss_wheel_monitor` | med | per wheel: 5Dx3 start-up comparison, 5Dx1 extrapolation (rec+0x19 b6, vref > 20 km/h), 5Dx4 long-term (dump/hold with rec+0x28 > 2800 in the braking regime); commits pending bits via `fault_set` |
| 0x00408DF1 | b7 `abs_front_slip_corrected` | high | set/cleared by `abs_wheel_signal_frame` (factory-stagger switch); makes `abs_event_classifier` use rec+0x1C for the front main slip |
| 0x40402 | `abs_stagger_expect` (ABS+0x66, s16) | CAL | 25: expected rear − front factor-byte difference per wheel (≈ 2.4 %, the stock 245/265 stagger); window 2·cal − 20 … 2·cal + 10 on the axle sums |
| 0x00403214 | `tyre_factor_table` (u8[4]) | high | factor = (745 + b)/1000, 255 = 1.0; EEPROM copy 0x403255 (block 22); restored per axle, floored at 225 |

BFU geometry **identical to 1M**: standstill 0x41CF2=72, circumference 0x41CF4/F6=2073 mm, teeth 0x41CF8/FA=48.
VDA hard-configured on all 4 channels (0x91 at 0x6F524..3E); direction-expected mask 15; invert pair 05/09
at 0xD766C (coding 0x4031F4 bit8). VMO monitor block 0x42424 (window threshold 0x42430=2000, %-scales 0x42466/68=85/75).

### Wheel direction

Chain: ASIC reply words → `wss_dir_protocol_update` 0x75C6C → `wss_dir_proto[w]` 0x400A34 →
`wss_dir_raw_get(w)` 0x75A94 → `wheel_direction_update` 0xB9330 (once per cycle, 4 wheels) → the state bytes
0x4029D2..0x4029DE → getters. Wheel index w = 0..3 = FL, FR, RL, RR. Speeds in 0.01 km/h; "speed" =
`wheel_speed_raw[w]` 0x40094A.

**Functions**

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x06FCC0 | `wss_asic_spi_poll` | high | two `qspi_xfer` 0xD4CA8 bursts on CS5: 4 words (tx 0xD73D4) → 0x4009C6, then 9 words (tx 0xD7402 = 02A0 02C0 02B0 02C0 02B8 02C0 02A8 02C0 0000) → 0x400F1C. The second burst selects slot 0..3 (02A0/02B0/02B8/02A8), each followed by a 02C0 read |
| 0x075C6C | `wss_dir_protocol_update` | high | for each ASIC slot k (wheel = table 0xD7668[k]): data = u16 0x400F1E+4k, qual = u16 0x400F20+4k. Clears qual b4 (direction received) unless AK b3 GDR was received and = 1. Flips data b4 if the wheel's bit is in the polarity-invert mask 0x75A82 (table 0xD766C). Clears qual b4 if the direction bit differs from last cycle. Stores byte0 = data, byte1 = qual |
| 0x075A94 | `wss_dir_raw_get(w)` | high | `wss_dir_proto[w]`: byte1 b4 clear → −2 (no direction info); else byte0 b4 → 1 forward / −1 reverse |
| 0x075CC2 | `wss_ak_update` | high | stub `br 0x75C6C`; called once per poll from `wss_asic_spi_poll` (0x6FD84). 0x75C6C then tail-calls `wss_ak_airgap_stats_update` (`br 0x75B74`) |
| 0x075AB4 | `wss_ak_amplitude_valid_get(w)` | high | AK b1 (amplitude-measurement validity): not received → −2; else the bit (1/0). The stats only run when it reads **0**, so 0 is treated as valid; check the polarity against the spec/bench. Only caller `wss_ak_airgap_stats_update` |
| 0x075AD4 | `wss_ak_airgap_reserve_ok(w)` | high | AK b0 (air-gap reserve error): not received → −2; else **inverted** (error → 0, OK → 1). Only caller `wss_ak_airgap_stats_update` |
| 0x075AF4 | `wss_ak_airgap_gauge_get(w)` | high | AK b7:5 air-gap gauge (0..7); −2 if AK b5 was not received. Only b5's received bit is checked, so a frame clipped after b5 or b6 would still be read with b6/b7 taken from `data`. Only caller `wss_ak_airgap_stats_update` |
| 0x075B10 | `wss_ak_bit2_get(w)` | high | AK b2 (unused bit): not received → −2; else the bit. **No callers** (no call, branch or pointer anywhere in the image) |
| 0x075B2C | `wss_ak_airgap_stats_init` | high | start-up (0x6F7FC). Per wheel, only if `wss_ak_airgap_stats[w]` is all zero (byte0 = 0, byte1 & 0xF8 = 0): byte0 = 0xF0 (min 15 / max 0), byte1 b3 = 1. `wss_ak_airgap_gauge_prev[w]` = −2, `wss_ak_airgap_ok_mask` = 15 |
| 0x075B74 | `wss_ak_airgap_stats_update` | high | per wheel, when the amplitude bit reads 0: if the gauge was received, track its min (byte0 hi nibble), max (byte0 lo nibble) and largest cycle-to-cycle change (byte1 hi nibble). If the air-gap reserve error bit is set: clear the wheel's bit in `wss_ak_airgap_ok_mask` and byte1 b3. Store the field (or −2) as prev. Nothing else in the image reads the results |
| 0x075A82 | `wss_dir_invert_mask` | med | 0xD766C[0xCFCAE()] |
| 0x0B96F4 | `wheel_dir_forward(w)` | high | `wheel_dir_state` bit (4+w): 1 forward, 0 reverse; −1 for w > 3. No validity check, so callers pair it with `wheel_direction_valid` |
| 0x0B96C2 | `vehicle_dir_get` | high | −2 unless `dir_status` b7:6 ≠ 0, b5 set, b4 clear and `dir_expected_mask` ≠ 0; then 1 if b7:6 = 1 (forward), else −1 (reverse) |
| 0x075A44 | `wss_sensor_mode(w)` | high | constant: 4 (VDA) for w 0..3, else 0 (see FACTS "sub_075A44 mode value") |
| 0x075CC4 | `wss_wheel_to_slot(w)` | high | linear search of the slot→wheel table 0xD7668 (= 00 01 02 03, identity in this image); returns the slot, or 0 if not found |
| 0x075DD8 | `popcount32(x)` | high | 32 × `lsrc` + `inct`; called on the u16 sensor reply word 0x400F20 + 4·slot |
| 0x075DEE | `wss_asic_present_bit(w)` | high | 1 if the wheel's bit is set in the ASIC status halfword 0x4009CA (w0 b1, w1 b5, w2 b7, w3 b3), else 0; 0 for w > 3. Used by the mode-2 path to step the confidence counter 0x4010D6[w] |
| 0x075E38 | `wss_startup_presence_check(reset)` | high | = 1M 0x75E94. r2 ≠ 0: clears 0x4010CE/0x4010D2[w] and 0x400952[w] b5. Otherwise runs while cycle counter 0x400960 ≤ 1000. Per wheel, mode `wss_sensor_mode(w)` 0x75A44 (= 4): mode 4 → popcount(ASIC reply 0x400F20[slot 0x75CC4(w)]) ≥ 3 sets presence-OK 0x4010CE[w], decided at cycle 100; mode 2 (latent) → period-pair confidence 0x4010D2/D6; other → immediate fail. Fail = 0x400952[w] \|= 0x31 + `wss_dir_fault_set(w)` (5Dx6), unless 5Dx0 is already set or inhibited by 0x400957 b5 && 0x40288C b6 |
| 0x075D3E | `wss_dir_fault_set(w)` | high | `fault_set((2+w)<<16 \| 0x40)` = 5D96/5DA6/5DB6/5DC6. Only caller: `wss_startup_presence_check` 0x75E38 (0x75F60) |
| 0x075D72 | `wss_electrical_fault_present(w)` | high | `fault_is_set((2+w)<<16 \| 0x01) \| fault_is_set((2+w)<<16 \| 0x100)` = 5Dx0 "elektrisch defekt" |
| 0x0F367C | `dtc_table` (12 B records) | high | {u16 internal id, u16 DTC, u32 flags, u32}. Internal id = group<<4 \| bit for fault id (group<<16 \| 1<<bit). Wheel groups 2..5 = FL, FR, RL, RR: bit 0/8 → x0 electrical, 1/9 → x1 extrapolation, 2/10 → x5 double frequency, 3/11 → x3 start-up v-comparison, 4/12 → x4 long-term, 5/13 → x2 tone-ring periodic, 6 → x6 direction (x = 5D9/5DA/5DB/5DC). Pressure-sensor groups 0x11 (sensor 1) and 0x1C-0x1F (FL, FR, RL, RR): bit 15 = hydraulic leakage (0x11F → 5DA7, 0x1CF/0x1DF → 5D9D, 0x1EF/0x1FF → 5DBD, FR/RR aliased to FL/RL), bit 0 of each group x0 = 5E20 / 5D9A / 5DAA / 5DBA / 5DCA electrical. Id 0x2021 → D378 (namespace 0x2000 = CAN timeouts, 0xBF994 r4 = 2) |
| 0x07C712 | `can_rx_3B0_reverse_gear` | high | PT-CAN 0x3B0 (944, "Status_Gang_Rueckwaerts") byte0 b0-1, only when 0x4046D9 b7. Reloads timeout 0x4046FA = 500; 0x401112 b2 = received; value 1 → b7:5 = 0 (not engaged), 2 → 1 (engaged), 0/3 → 3 + b1 (invalid). Not used by the wheel-direction code |
| 0x07D130 | `can_rx_3B0_timeout` | high | called by 0x7E7A4 when 0x4046FA counts to 0: 0x401112 → invalid; unless fault 0xA0002 is latched and if 0x401163 b4, reports 0xBF994(0x20002, 0xA0010). This is the D378 path (DSC_87.prg: "D378 PT_CAN_Timeout Botschaft 944 (Status_Gang_Rueckwaerts) fehlt"); the id↔DTC mapping is not traced |
| 0x0BB1F0 | `reverse_gear_plausibility` | med | reverse engaged (0x401112 b7:5 = 1), vref ≥ 40 km/h and yaw/steer sign checks hold → counter 0x402ABE; above 100 → 0x402A16 b1 and, if `coded_feature(11)` (HSA), `fault_set(0xB4000)`. Probably 5E2E "Schalter Rueckwaertsgang Plausibilitaet" (not confirmed) |
| 0x08EFB0 | `wheel_minmax_select` | high | sets `wheel_slowest_rec` 0x40097C (min rec+0x1A below 30001) and `wheel_fastest_rec` 0x400980 (max above floor−1) |

**Variables**

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x00400A34 | `wss_dir_proto` (u8[4][2]) | high | per wheel: [0] = low byte of `wss_asic_reply.slot[k].data`, [1] = low byte of `.qual` (qual acts as a per-field valid mask). b4 is direction / direction-valid, after the polarity flip; qual b4 is also cleared unless data b3 & qual b3, and when the direction changed since last cycle. Bit n = AK bit n (data = value, qual = received). Other fields: b0 air-gap reserve error, b1 amplitude validity, b2 unused, b7:5 air-gap gauge (accessors 0x75AD4 / AB4 / B10 / AF4). The high bytes (parity b8) are dropped. Writer 0x75C6C |
| 0x00400A3C | `wss_ak_airgap_stats` (u8[4][2]) | high | per wheel: [0] hi nibble = min / lo nibble = max air-gap gauge; [1] hi nibble = largest gauge step between cycles, b3 = no air-gap reserve error seen yet (set at init). Not cleared at start-up if non-zero. No consumer (FACTS "air-gap quality bytes") |
| 0x00400A44 | `wss_ak_airgap_gauge_prev` (s8[4]) | high | last air-gap gauge, −2 = not received |
| 0x00400A48 | `wss_ak_airgap_ok_mask` (u8) | high | 15 at init; a wheel's bit is cleared the first time it reports an air-gap reserve error (with the amplitude bit = 0) |
| 0x0040094A | `wheel_speed_raw` (s16[4], 0.01 km/h) | high | from `wheel_speed_update`; the direction code gates on it |
| 0x0040097C | `wheel_slowest_rec` (ptr to wheel record) | high | `wheel_minmax_select`; also set to record 0 at init (0x8F232) |
| 0x00400980 | `wheel_fastest_rec` (ptr to wheel record) | high | `wheel_minmax_select` |
| 0x004029D2 | `dir_mismatch_cnt` (u8) | high | +1 per cycle while the slowest wheel > 20 km/h, the system is enabled with no fault, and the wheels don't agree. "Not agreeing" means: all 4 valid with mixed bits, or all expected wheels report but `vehicle_dir` is still 0. Otherwise −1 toward 0. At 175 → `dir_status` b4 (no DTC from this path) |
| 0x004029D3 | `dir_expected_cnt` (u8) | high | per cycle: number of wheels in `dir_expected_mask` (4 normally) |
| 0x004029D4 | `dir_fwd_cnt` (u8) | high | per cycle: expected wheels whose raw direction = forward |
| 0x004029D5 | `dir_rev_cnt` (u8) | high | per cycle: expected wheels whose raw direction = reverse |
| 0x004029D6 | `dir_expected_mask` (u8, b0..3 = wheel) | high | `validate_dir_cfg(15)` = 15 on reset. 0 disables the whole function (the bench image patched this) |
| 0x004029D7 | `dir_fault_mask` (u8, b0..3 = wheel) | high | per-wheel direction-fault latch (set together with the DTC); cleared only by reset |
| 0x004029D8 | `dir_fault_cnt` (u8) | high | per cycle: popcount of `dir_fault_mask`; ≥ 2 → `wheel_direction_valid` = 0 for every wheel |
| 0x004029D9 | `wheel_dir_state` (u8) | high | b0..3 = wheel w has direction info (`wheel_dir_valid`), b4..7 = wheel w forward (`wheel_dir_fwd`). Both are only updated while that wheel is below 55 km/h, so above 55 they hold the last value |
| 0x004029DA | `dir_status` (u8 bitfield) | high | b2 reset done · b3 locked (every expected wheel has reported direction at once) · b4 direction fault (any wheel or mismatch) · b5 enabled (set the first cycle vref < 55 km/h after init) · b7:6 `vehicle_dir` 0 unknown / 1 forward / 2 reverse · b0/b1 unused (only preserved) |
| 0x004029DB | `dir_missing_cnt` (u8[4]) | high | +1 per cycle while wheel w is expected, enabled, 4.01–54.99 km/h and has no direction info; else −1 toward 0. At 175 → DTC |
| 0x00400960 | `cycle_count` (u32) | high | +1 per main cycle in 0x70F38 (next to 0x40095C, also +1); zeroed by 0x6D1B4. The presence check runs while ≤ 1000 and decides at = 100 (mode 4) / = 1000 (mode 2) |
| 0x00400952 | `wss_status` (u8[4]) | med | per-wheel sensor status. **b7 = no edge this frame** (`wheel_speed_update`, cleared each frame). b0 = wheel faulted (0x0CE → 0x8000, excluded from speed/accel/standstill); presence-check failure sets b0\|b4\|b5 (0x31); b5 cleared on presence-check reset. Other bits come from the wheel-speed monitors (0xB651C, 0xB6A08, 0xB4924/76 clear b0/b1). Bench: 0x80 connected at rest, 0x08 moving, 0x99 unplugged |
| 0x004010CE | `wss_presence_ok` (u8[4]) | high | presence-check result, 0 = fail at decision time. Mode 4: 1 once popcount(reply word) ≥ 3, i.e. a VDA data frame was seen. Mode 2: recomputed every cycle as (`wss_pulse_ok_cnt` < 10 && `wss_asic_present_cnt` < 3), so it passes only while **no** protocol-like activity is seen. Bench mode-2 reading 01 01 01 01 matches |
| 0x004010D2 | `wss_pulse_ok_cnt` (u8[4]) | high | mode 2: +1 (cap 254) per cycle with `wss_edge_latch` width in 6..25 and edge count ≥ 2. Cleared by reset |
| 0x004010D6 | `wss_asic_present_cnt` (u8[4]) | high | mode 2: +1 (cap 254) per cycle with `wss_asic_present_bit(w)`. Not cleared by the presence-check reset |
| 0x004009CA | `wss_asic_status` (u16) | high | = `wss_asic_status_rx`[2]. 0x4009C6 is a 4-halfword QSPI CS5 receive buffer, `qspi_xfer(5, 4, 0xD73D4 = {02D0, 0290, 0248, 0000}, 0x4009C6)` in 0x6FCC0. Per-wheel bits FL b1, FR b5, RL b7, RR b3 (`wss_asic_present_bit`) |
| 0x004009C6 | `wss_asic_status_rx` (u16[4]) | high | see the row above |
| 0x00400F1C | `wss_asic_reply` (`wss_asic_reply_t`, 18 B) | high | QSPI CS5 receive buffer, 9 halfwords, filled by `wss_asic_spi_poll` 0x6FCC0 (`qspi_xfer(5, 9, 0xD7402, 0x400F1C)`). Word 0 is the reply clocked in during the first command (unused); then {data, qual} per slot. data b4 = direction; qual b4 = direction valid; b3 in both = frame OK; the presence check popcounts qual. Slot k → wheel via 0xD7668 (identity) |
| 0x0040338A | `wss_edge_capture` (struct, 20 B) | high | written by the capture ISRs: +4w u16 t_a (last edge, capture >> 2), +4w+2 t_b (edge before), +16+w u8 edge count (cap 57); counts cleared by `wss_frame_latch` |
| 0x0040339E | `wss_edge_latch` (same struct + 8 B) | high | per-frame copy of `wss_edge_capture` (0x73B5C); +20 / +22 now (F8 / D8 time >> 2; wheels 0,3 / 1,2), +24 / +26 previous now. Mode-2 input: width = t_a − t_b |
| 0x004033BA | `wheel_edge_ref` (u16[4][2]) | high | per wheel: ref_a (last edge used), ref_b (edge before), kept by `wheel_speed_update` |
| 0x004033CC | `wheel_speed_k` (u32[2]) | high | K = 900·C front / rear (`wheel_cal_prepare`) |
| 0x004033D4 | `wheel_edge_count` (u8[4]) | high | edge-count snapshot at `wheel_speed_update` entry; read by `wheel_speed_filter` (57 test) |
| 0x004033D9 | standstill counter (u8) / 0x4033DA b7 moving | high | `count_standstill_wheels` |
| 0x004032D0 | `wheel_speed_floor` (s16) | high | max over axles of 2K/60000 (62 stock); speed clamp, CAN 0x0CE zero, vref init and clamps (~25 readers) |
| 0x0040935C | `wheel_circ_copy` (u16[2]) | high | BFU circumferences, `wheel_circ_get` |
| 0x0040933C / 0x0040934C | `wss_edge_stamp32` / previous (u32[4]) | high | unshifted capture stamps, ISR only (RPA intervals) |
| 0x004091C8 / 0x004091CC | RPA interval buffer pointers | med | swapped each frame by `wss_frame_latch`; ISRs fill *0x4091CC |
| 0x0040290C | `wss_lowspeed_cnt` (u8[4] by rec+0x2A, b7:6) | high | `wheel_speed_filter`: 3 while raw < 16 km/h, −1 per frame otherwise |
| 0x00402910 | `wss_slew_timer` (u8[4]) | high | `wheel_speed_filter` S: +6/frame in slew mode (b6 at 102), −1 every 2nd frame outside, −13 with b6 outside braking regime (b6 clears below 14); 0 while 0x402904 b7 |

**`wheel_direction_update` 0xB9330, per cycle**
- **Reset** (every cycle while `0x400966` b6 start-up, or `0x402904` b7, which is written by the monitoring and
  clear-fault code and is not decoded): zeroes 0x4029D2..D9 and `dir_missing_cnt`, keeps `dir_status` b0/b1, then
  `dir_expected_mask` = 15 and `dir_status` = b2. The enable bit b5 is set on the first later cycle with vref
  0x408DA8 < 55.00 km/h.
- **Per wheel**, skipped entirely if `dir_expected_mask` = 0. raw = `wss_dir_raw_get(w)`.
  1. Update `dir_missing_cnt[w]` (above). At ≥ 175 → `dir_status` b4, `fault_set(0xF576C[w])`
     (0x00020040/30040/40040/50040 = DTC 5D96/5DA6/5DB6/5DC6; the start-up presence check raises the same codes), `dir_fault_mask` |= bit.
  2. Below 55 km/h: valid bit = (raw ≠ −2 and wheel expected).
  3. 25.01–54.99 km/h with `dir_status` b3: if raw ≠ −2 and raw ≠ the stored direction → same fault as step 1
     (direction flipped while driving).
  4. Below 55 km/h: raw 1 → set the forward bit, −1 → clear it, −2 → leave it.
  5. Above 120 km/h, with the slowest wheel above 25 km/h and `dir_status` b3 and b5: stored direction = reverse
     → same fault (reverse at speed is implausible).
  6. Count into `dir_expected_cnt` / `dir_fwd_cnt` / `dir_rev_cnt`, store `wheel_dir_state`, and recount
     `dir_fault_cnt`.
- **After the loop.** `dir_status` b3 is set when every expected wheel reported a direction this cycle (with 4
  expected: all 4 valid bits). `vehicle_dir` (b7:6): with 4 expected, 1 if all four valid bits are set and all four
  are forward, 2 if all four are reverse, else 0. With fewer expected: 1 / 2 when every expected wheel reported
  and they all agree, else 0. Then the `dir_mismatch_cnt` update.

**Getter semantics.** `wheel_direction_valid(w)` returns 0 if `dir_status` b5 is clear, `dir_fault_cnt` ≥ 2,
`dir_expected_mask` = 0, or `0x400952[w]` b0. It returns **1 if speed > 70 km/h**. Otherwise it returns 1 only
when `wheel_dir_valid` bit w is set and `dir_fault_mask` bit w is clear. Above 70 km/h the sign used by
0x0CE / 0x1A0 is therefore the direction latched below 55 km/h (normally forward). Reverse latched above 120 km/h
sets the fault.

Bench check: FACTS (2026-10) saw `0x4029D3 = 0x02`, `0x4029DA = 0x24` constant with a front-direction-masked
image. That is 2 expected wheels, and `dir_status` = enabled + reset done, with no direction ever locked. This
matches the decode.

```c
/* Ghidra: Data Type Manager → Parse C Source, then apply at the addresses above */
typedef struct { unsigned char data, qual; } wss_dir_proto_t;    /* 0x400A34[4]: low bytes of wss_asic_slot_t; qual = per-field valid mask */
typedef unsigned short u16;
typedef struct {
    u16 data;           /* AK bit values (bit n = AK bit n, before the coding polarity flip of b4) */
    u16 qual;           /* AK bits received: bit n set if AK bit n arrived (frames are clipped at speed);
                           popcount >= 3 = an AK frame was seen */
} wss_asic_slot_t;
/* AK bits (user-supplied; matches every reader):
   b0 air-gap reserve error · b1 amplitude-measurement validity · b2 unused · b3 direction valid (GDR, 1 = valid)
   b4 direction · b7:5 air-gap gauge · b8 parity (dropped: only the low byte reaches 0x400A34) */
typedef struct {
    u16 first;          /* reply clocked in during the first command (0x02A0); not read */
    wss_asic_slot_t slot[4];   /* slot k -> wheel 0xD7668[k] (identity: FL, FR, RL, RR) */
} wss_asic_reply_t;     /* at 0x400F1C, 18 bytes = QSPI CS5 rx of 9 words (wss_asic_spi_poll 0x6FCC0) */
typedef unsigned char u8;
/* 0x4029D9 wheel_dir_state:  b0..3 dir valid (FL,FR,RL,RR), b4..7 forward (FL,FR,RL,RR)                        */
/* 0x4029DA dir_status:       b2 reset_done, b3 locked, b4 fault, b5 enabled, b7:6 vehicle_dir (0/1 fwd/2 rev) */
typedef struct {
    u8 mismatch_cnt;    /* 0x4029D2 */
    u8 expected_cnt;    /* 0x4029D3 */
    u8 fwd_cnt;         /* 0x4029D4 */
    u8 rev_cnt;         /* 0x4029D5 */
    u8 expected_mask;   /* 0x4029D6 */
    u8 fault_mask;      /* 0x4029D7 */
    u8 fault_cnt;       /* 0x4029D8 */
    u8 wheel_state;     /* 0x4029D9 */
    u8 status;          /* 0x4029DA */
    u8 missing_cnt[4];  /* 0x4029DB */
} wheel_dir_t;          /* at 0x4029D2, 13 bytes */
```

## AYC / yaw control & DSC mode (cycle 2 — opcode diff, clean unless noted)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x05EBC4 | `yaw_observer` | med-high | dynamic observer (β 0x400C42, r 0x400C44); **variant-indexed** on M3 (reads 0x4031AA+1, cal 0xD704A/0xD70AA + AYC arrays 0x415F8/0x41610/0x41628); = 1M 0x5ECB0 |
| 0x05F7BA | `yaw_pd_moment` | high | PD moment demand; = 1M 0x5F882 |
| 0x065078 | `engine_torque_request` | high | reads AYC torque-ceiling tables; = 1M 0x6514C |
| 0x090E5C | `yaw_ref_closedform` | high | r_ref via RAM 0x400AE8/AEA (v_ch); = 1M CSI 0x90C44 |
| 0x060CA0 | `yaw_error_B46_minus_B1A` | high | yaw error; = 1M 0x60D68 |
| 0x0CF2E8 | `void dsc_mode_select(void)` | high | entry is 0xCF2E8 (`subi r0,8`; tail-jumped from `msr_cycle_entry` 0xCBFA6); m∈{0,1,2}→0x4031B1 (`coding_block`+7); m=0 if 0x4030A4∈{1,4,5} or 0x4030A2≠3; else m=2 if (0x4031F4&0x80) else 1; = 1M 0xCF92A |
| 0x0CFC98 | `dsc_coding_bit_get` | high | reads 0x4031F4 mask 0x80 (bit7 of 0x4031F5); = 1M 0xD02D8 |
| 0x0CF248 | `dsc_state_commit` | med | commits request 0x4030A3 → state 0x4030A4 (valid 1..5, state 3 gated by 0x8DD1C) |
| 0x060714 | `ayc_gain_stage` | med | computes B76/B78 P/D gains, applies mode % curves |
| 0x0602DA | `ayc_threshold_stage` | med | computes B6C entry / B70 hold |
| 0x060682 | `ayc_threshold_clamp` | med | clamps B6C/B70 to per-mode ceilings |

AYC RAM: target B1A 0x400B1A, measured B46 (F-CAN 0x0CD), entry B6C, hold B70, P/D B76/B78, mode 0x4031B1.

AYC calibrations (byte values from the image; roles from `yawmodel/REPORT.md`, FACTS Cycle 7, XDF notes). Yaw units
1/20000 rad/s (349 = 1°/s). m = DSC mode 0x4031B1 (m0 DSC on, m1 rest-of-world MDM, m2 US MDM = coding c10 b5).

| Address | Name | Type | Stock | Conf |
|---|---|---|---|---|
| 0x413BA / 0x413BC | `ayc_entry_base_a` / `_b` | s16 | 1396 (4°/s) / 2792 (8°/s); set A/B selector not traced | high |
| 0x413BE | `ayc_hold_seed[2]` | s16[2] | 698 / 2094 | med |
| 0x4141E | `ayc_hold_offset[m]` | s16[3] | 698 ×3 (B70 = B6C − this) | high |
| 0x41424 / 0x4142A | `ayc_entry_ceiling[m]` / `ayc_hold_ceiling[m]` | s16[3] | 10471/10471/8028, 9773/9773/7330 | high |
| 0x41478 / 0x41490 | `ayc_thr_speed_a_x[m][4]` / `_y` | s16[3][4] | x 0.01 km/h, y /128 (m0/m1 320→128) | high |
| 0x414D8 / 0x414F0 | `ayc_thr_speed_b_x[m][4]` / `_y` | s16[3][4] | set B | high |
| 0x413AA / 0x413AE | `ayc_pd_gain_base[2]` / `_2[2]` | s16[2] | 47/47, 36/36 (B76 P, B78 D) | high |
| 0x41448 / 0x41460 | `ayc_pgain_pct_x[m][4]` / `_y` | s16[3][4] | m0/m1 30/60/70/100 %, m2 70/80/100/100 % | high |
| 0x41430 | `ayc_pgain_pct2[m][4]` | s16[3][4] | m0/m1 80/80/90/100 % | med |
| 0x411FE / 0x4120A | `ayc_torque_ceil_x[m][2]` / `_y` | s16[3][2] | x 50/80 (lat), y m0 150/400, m1 200/2000, m2 180/330 | high |
| 0x41216 | `ayc_torque_scale_pct[m]` | s16[3] | 78 ×3 | med |
| 0xD6DA4 | `ayc_feature_enable[m]` | s16[3] | 1/0/0; feature not identified | low |
| 0x4155E | `ayc_us_rear_share` | s16, /256 | 256 (understeer: rear only) | high |
| 0x413C4 | `ayc_small_yaw_rear_gain` | s16, /256 | 64 | high |
| 0x41552 | `ayc_req_rate_cap[2]` | s16[2] | 300 / 500 | high |
| 0x411B4 | `ayc_prefill_front_outer` | s16, 0.01 bar | 500 | high |
| 0x415E8 | `ayc_driver_press_gate_pct` | s16, % | 60 | med |
| 0x415F8 / 0x41610 / 0x41628 | `ayc_obs_tyre_{alim, fk, mu}[var]` | s16[12] | 1835 / 90 / 11905 (17854 for var 1, 6) | med |
| 0xD704A / 0xD70AA | `ayc_obs_lag_y[var][4]` (Q13) / `_x` | s16[12][4] | v0–9 7229/6560/5200/3014; 10/11 differ | med |

AYC RAM (med; the Bxx shorthand above = 0x400Bxx, B46 = AYC copy of measured yaw from `ayc_input_gather`): 0x400B6C `ayc_entry_thr` (s16), 0x400B70 `ayc_hold_thr` (s16), 0x400B76 / 0x400B78 `ayc_kp` / `ayc_kd` (s16),
0x400B1C `ayc_moment` (s16, ~0.1 bar per count per wheel), 0x400B0C `ayc_wheel_demand[4]` (s16), 0x400B30
`ayc_torque_cap` (s16), 0x400BB8 b7:6 `ayc_dist_mode`, 0x400C42 / 0x400C44 `obs_beta` / `obs_yaw` (s16).

TCS drive-slip records (`curve_t`, 0x22 B each), read by `tcs_driveslip_curve`: set B 0xF625C + 0x22·m (always used
on the M3), set A 0xF61F6 + 0x22·m (gearbox type 1/3 only). These are the **brake-TCS** base thresholds; the entry
limit adds 5 km/h and a low-speed extra (`TCS_7846816A.md` §4.1). Set B at 15 / 25 / 50 / 80 km/h: m0 2.7 / 1.0 / 2.3 / 3.8, m1 8.7 / 8.1 / 6.5 / 6.8, m2 7.7 / 7.1 /
5.5 / 5.8 km/h; all ≈ equal above 100 km/h.
**v_ch is runtime-derived from the variant model (loader 0x5E424), not a constant**: M3 varies 105.5–142.1 km/h
by coding variant (1M fixed 97.65). **m=1 is the most permissive** (torque ceiling 2000 vs m0 400 / m2 330).
DSC-mode→driver-mode (DSC/DTC/MDM/OFF) mapping is live EEPROM/RAM state — not statically resolvable.

### DSC button / driver mode (FACTS "DSC driver mode")

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x06FEE4 | `dsc_button_input_get` | high (code) | latch 0x4009F4 b1 (GPIO, same latch as BLS b0), **active-low** (0 = pressed); valid needs 0x4009F4 b4 and 0x4009F5 b4 |
| 0x08D542 | `mode_button_get(idx)` | med | idx0 = DSC button (0x6FEE4); idx1 = CAN RAM 0x401109 b5–b7 (second button, fault 0x92000 → 5E5C) |
| 0x08D1BE | `driver_mode_init` | high | power-up: 0x4049B4[0] = 1 (DSC on), param 0; store at 0x8D204 `960E` (st.w r6) |
| 0x08D214 | `button_mode_sm` | high | dispatcher slot 0x8CCC2, per button: SM state 0x4049AC[b] (2 idle, 3 pressed, 4 held, 5 released, 6 stuck check), press counter 0x4049C4[b] |
| 0x0DA1BC | `button_transition_table` | high | 20 × 32 B {btn, sm, next_sm, func_cur (15 any), func_new (15 keep), param_cur (3 any), param_new (3 keep), u16 count}. Button 0: ON → OFF after 50 frames held; OFF → ON after 15; MDM → OFF after 50; 1000 → stuck (5E5B, fault 0x91000) |
| 0x08D570 | `mode_transition_valid(idx, cur, &new, &param)` | high | idx0 only. → 0 (from 1/4) needs 0x400B0A b2 (= NOT b7, no AYC intervention); → 1 (from 0/4) and 0 → 4 need 0x402F6A b7 and 0x400B0A b3 (= 0x400B50 & 0xC0 = 0); 1 → 4 needs b2. Rejected → new = last applied 0x4049D2[idx] |
| 0x08D4AE | `driver_mode_apply(idx, func, param)` | high | writes 0x4049B4/0x4049BC, clears 0x4049CC b6, records 0x4049D2 (0x8D5CC) |
| 0x08D70A | `can_mode_request_apply` | high | from 0x8D7FE (dispatcher 0x8CD0E). Slot 0: if button idle (0x8D4CA = 0), enable 0x4049CC[0] b7, 0x40113B b5:4 ≠ 0 and 0x40113A b6 = 0: x = 0x401139 b5:4: 0 → (0, 1), 1 → (1, 0), 2/3 → (4, 2). Slot 1: x = 0x401139 b3:2 → states 8/9/10 |
| 0x08D7FE | `driver_mode_can_update` | med | calls 0x8D70A; when CAN is not driving slot 0 this cycle, sets 0x4049CC[0] b7 = 1 unless 0xC7818 ∈ {2, 5} and `dsc_function_state` = 1 |
| 0x08DA30 | `tcs_mode_from_driver_mode` | high | on change of 0x4049B4[0]: 4 → 0x4030A2 = 3; 1/2/5 → 1; 0/3 → 2 (via 0xC7794) |
| 0x08D060 / 0x08D082 / 0x08D0B6 | `driver_mode_is_on` / `_is_off` / `_is_mdm` | high | mode ∈ {1,2,5} / {0,6} / {4,7}. `is_on` feeds the yaw-control state select 0x68E5E (not on → 0x400DF5 state 2 unless 0x400E24 > 2000) and the DSC-inhibit flag 0x400DF4 b6 (0x69F6E) |
| 0x004049B4 | `driver_mode_state` (u32[2]) | high | [0]: 0 OFF, 1 ON, 2 stuck, 4 MDM. Param 0x4049BC[0]: OFF lamp needs param ≠ 0 (0x80CFE) |
| 0x00401139–0x0040113B | `can_mode_request` | high | b5:4 slot-0 request, b3:2 slot-1; 0x40113A b6/b5 invalid; 0x40113B = received flags, cleared each 10 ms by 0x78CE2 |
| 0x00400E24 | `dsc_active_cycles` (u16) | high | counts cycles with 0x400DF4 b7 (DSC active), reset when inactive (0x69A44) |

## CSI / steering / yaw reference (cycle 3 — byte/opcode verified)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x09032E | `void steer_ratio_convert(void)` | high | 0x4020D4 = old 0x40212E; k = f+5 0x4031AF; a = 0x402132 clamped to ±(0x40EB4+8k)[3]; `0x40212E = 29360·a / interp(\|a\|, 0x40EB4+8k, 0x40ECC+8k, 4)`; = 1M 0x9012E (single set 0x40A10/0x40A18) |
| 0x0901D4 | `void steer_capture(void)` | high | 0x401644 → raw 0x4020D0; IIR 0x4020D2 (k 241/256) |
| 0x091008 | `void steer_task(void)` | high | `steer_capture` then `steer_offset_and_ratio`; called from 0x8F028 (← 0x7101A); period not traced |
| 0x090384 | `void steer_offset_and_ratio(void)` | high | `bsr steer_offset_learn`, tail branch to `steer_ratio_convert` |
| 0x090BC0 | `void steer_yaw_residual_update(void)` | low | 0x40211C = clamp(0x4020F8 − 0x402118, ±31415); curve-B input of the offset learner |
| 0x091070 | `void chassis_state_flags_update(void)` | low | builds 0x402144: byte 0 b4 / b5 = \|road-wheel 0x40212E\| > 8208 / > 1127, b6 = \|0x402178\| > 244, b7 from ABS 0x408DA1 / TCS 0x402FC0 / AYC 0x400B0A; +3 b3 / b0 yaw tests (0x402100 vs 2268, 0x4020F6); clears +4 |
| 0x092104 | `void sensor_offset_record_sm(void)` | med | state 0x402142. State 1: `xor16_checksum`(0x4020B0, 16) vs record word 0 → mismatch `fault_set(0x81000)`; else restore 0x4020FA and offsets 0x4020A6..AC, each clamped by 0xDA974 = {29257, 30581, 16000, 21600}. Sets 0x4020FD b5 / b6 / b7 (b7 enables the steering learner). Called from 0x92846 |
| 0x0920D8 | `u16 xor16_checksum(const u16 *p, u16 n)` | high | XOR of n halfwords; 0 or 0xFFFF → 0x4852; returns the complement |
| 0x0BF868 | `void steer_offset_fault_monitor(void)` | high | with 0x4020FD b6 and (0x402904 & 0x84) = 0x80: \|raw 0x4020D0\| > 16457 (when 0x40164D & 0xC0 = 0) or \|offset 0x4020A6\| > 0x3924 (14628 Q6 = 228.6 counts ≈ 10°) → `fault_set(0x120001)` |
| 0x06D0CC | `s16 abs_sat16(s16 x)` | high | \|x\|, −32768 → 32767 |
| 0x091A0E / 0x091A26 | `s16 clamp_sym16(s16 x, s16 lim)` | high | clamp to [−lim, lim]; 0x91A26 does not sign-extend its input |
| 0x09020C | `void steer_offset_learn(void)` | high | zero-offset estimator. Every call: corrected angle 0x402132 = 0x4020D0 − offset 0x4020A6/64. Every 100 calls (0x402134), with 0x4020FD b7 + 0x402147 b7 and not 0x402884 b3: `offset += (clamp(0x4020D2, offset/64 ± 228)·64 − offset) / D`, D = min(curve 0xDA8FA/0xDA8FE (alt 0xDA902 if 0x4020FD b4) over \|0x4020DC\|, curve 0xDA906/0xDA90A over \|0x40211C\|)·1200/[0x400B2C]; then clamp ±0x7249 (457 counts). **±228 is a step clamp, not a window.** Also 0x402136 += vref/360 (cap 60000). `DSC_STEERING_AND_VEHICLE_MODEL_7846816A.md` §2 |
| 0x090408 | `steer_rate_update` | low-med | steering rate 0x402130: differentiator on raw 0x4020D0 with hold counters 0x4049F2–0x4049F8, then IIR (k ≈ 204/256). Units not confirmed (≈ counts/s) |
| 0x090D10 | `void yawref_stage_main(void)` (label `yaw_ref_closedform` at 0x90E5C, mid-function) | high | builds the redundant yaw rates (1/20000 rad/s): front-wheel 0x40215A and rear-wheel 0x40215C = LP 221/256 of `wheel_yaw_k` 0x400AF4 · (speed difference 0x402A24−0x402A22 / 0x402A28−0x402A26, side not pinned); closed-form r_ref 0x4020EC = 4·δ(0x40212E)·v/16 / ((v²/16 + 2·AE8·AEA)/(8·AEA)), clamped to ±(0x558C/(v/16))<<8 (1.27 g friction limit) → LP 221/256 0x40215E; lateral 0x402160 = ay(0x402AB6)·88290·8/v (v > 10.8 km/h), same clamp. Also LPs 0x4020EE (205/256) and 0x402166 (241/256) of r_ref; 0x402168 = 0x40215A, 0x40216A LP 227/256 of it; = 1M 0x90AF8/0x90C44 |
| 0x09001E | `void ay_axle_est_update(void)` | high | 0x40212C += (0x4020DA − 0x40212C)·189/256 (LP ay, mg); c = (yaw 0x402100/256)²/AEE (0 if AEE = 0); `ay_axle_est_calc` with lever arm AEC / AF2 / AF0 → 0x402126 CG / 0x402125 rear axle / 0x402124 front axle; 0x402AB6 = clamp(0x40212C/10, ±127) |
| 0x09053C | `void yaw_steer_equiv_update(void)` | med | den = (AE8/4)·(1 + v²/v_ch²) computed as AE8/4 + (v²/16)/(8·AEA); above vref 10.01 km/h converts 0x40215A / 0x40215C / measured yaw 0x402100 / 0x402160 into steering-equivalent road-wheel angles 0x40217A / C / E / 0x402180 (δ = r·L·(1 + v²/v_ch²)/v). Readers 0xB987E.. (`steering_angle_init_monitor` 0xB97D4) and 0xBA6F6.. |
| 0x090520 | `s16 yaw_to_steer_equiv(s16 yaw, s16 den)` | med | sat16(4 · `div_sat16`(yaw·den, vref 0x408DA8)) |
| 0x0919E2 | `s16 div_sat16(s32 num, s16 den)` | high | num clamped to ±32767·den (`clamp_sym32`), then `divs` |
| 0x0919D0 | `s32 clamp_sym32(s32 x, s32 lim)` | high | clamp to [−lim, lim] |
| 0x0919FA | `s16 sat_toward(s16 x, s16 ref)` | high | ref + sat_s16(x − ref) |
| 0x0BB888 | `void steer_yaw_consistency_check(void)` | med | 0x402A60 = sat16(16·(0x402A3E·v/16)/AF6 − 16·(ay 0x402AB6·v/16)/AF8), the linear bicycle yaw v·(δ − K·ay)/L (AF6 ∝ L, AF8 ∝ v_ch²); counter 0x402ABD counts up (≤ 175) while \|0x402A60\| − \|r_ref LP 0x40215E\| > 698 (2°/s), else clamps to ≤ 50. 0x402A3E comes from `steering_angle_init_monitor` 0xB97D4 (a steering angle, [I]) |
| 0x0C5C78 | `canrx_steer_angle_0C9` | med | F-CAN 0x0C9 sig 43 (var 0x020); valid window, ·1029/1024 → 0x401644 |
| 0x0C583C | `cluster_sensor_get(idx)` | high | idx0..5 → 0x402F1C/20/24/1E/22/26 (F-CAN 0x0CD/0x0D1 yaw/ay cluster). idx5 = 0x402F26 = 0x0D1 bytes 4–5 = longitudinal accel (inferred) |
| 0x08FE70 | `csi_cond_sensor2` | high | ay channel; = 1M 0x8FC78 |
| 0x0905E4 | `csi_cond_sensor0` | med | yaw-rate channel |
| 0x07119E | `interp_linear_xy(x,xtab,ytab,n)` | high | plain piecewise-linear (end-clamped); distinct from `curve_interp_s16` |

CSI block 0x40EA8 (len 0x114, grew +0x62 vs 1M): steer-ratio x sets 0x40EB4 / y sets 0x40ECC (3 sets × 4 pts,
coding 0x4031AA+5), sign tables 0x40EE4/0x40F14 (12× per variant, all −1), tail (0x40F2E..) byte-identical to
1M. Internal yaw-rate LSB = **1/20000 rad/s** (FACTS Cycle 7);
steering ≈0.044 deg/LSB [med, unverified]; r·v clamp ≈1.24 g (hard-coded). v_ch enters r_ref via RAM 0x400AE8/AEA
(from the variant model), no CSI constant in the denominator.

Steering cals (2026-10-22, `DSC_STEERING_AND_VEHICLE_MODEL_7846816A.md`): ratio set k = f+5 (0 = E90, 2 = E92/E93
per NCS, 1 = copy of 0; field limit 3, a set 3 would overlap y set 0 / the sign tables). Learner curves 0xDA8FA
x {299, 3199} / 0xDA8FE y {3000, 9000} / 0xDA902 alt y {700, 3000}; 0xDA906 x {1745, 6981} / 0xDA90A y {3000, 700};
restore clamps 0xDA974 = {29257, 30581, 16000, 21600}. Code literals: step clamp 228, hard clamp 0x7249, fault
0x3924, raw range 16457, divisor ×1200.

## Vehicle-model derived coefficients and yaw references (2026-10-26)

From the loaders 0x5DE44 / 0x5E424, the yaw-reference builder 0x90D10 and its consumers. Formulas were read from code
and checked by replaying both loaders against the image: stock variant 0 gives the values shown (AF4 = 36 and v_ch =
128.8 km/h match FACTS), and the closed forms for AA4–AB8, AC2, ACA, ADA–AE2, AE8, AEA, AF4 and AF6 match the replay
within 1 count for 280 random cars. Inputs are the coded column of the vehicle-model rows: l_f, l_r, L = l_f + l_r, t_f,
t_r (Q10 m), m (kg), Jz (kg·m²), Cf, Cr, sensor x / y (Q10 m). Divisions truncate. "sat" = `sat_s16`. All RAM is
s16 unless noted.

| RAM | Name | Formula | Stock v0 | Conf |
|---|---|---|---|---|
| 0x400AA4 | `vm_lr_over_jz` | −763548·l_r / Jz / 128 | −2810 | high |
| 0x400AA6 | `vm_inv_cf` | 614399998 / Cf / 16 | 5101 | high |
| 0x400AA8 | `vm_cf_a` | (Cf·65536 / 37499) / 10 | 1315 | high |
| 0x400AAA | `vm_inv_m_a` | 14380460 / m | 8047 | high |
| 0x400AAC | `vm_lf_over_lr_cr` | sat(552960002 / (16·l_r) · l_f / Cr) | 3261 | high |
| 0x400AAE | `vm_cf_b` | Cf·131072 / 24999 / 3 (wraps above Cf 18745) | 13154 | high |
| 0x400AB0 | `vm_front_axle_load` | sat(180·m·l_r / (L·3665 / 256)) = 12.57 × front axle load (kg) | 11234 | high |
| 0x400AB2 | `vm_cr_b` | Cr·131072 / 99999 (wraps above Cr 25000) | 13888 | high |
| 0x400AB4 | `vm_lf_over_jz` | 572661·l_f / Jz / 128 | 2107 | high |
| 0x400AB6 | `vm_inv_m_b` | 19173933 / m (wraps below m 586) | 10729 | high |
| 0x400AB8 | `vm_balance_a` | 17854·Cf / l_r · l_f / (10·Cr) | 1268 | high |
| 0x400ABA / ABC / AC0 | `vm_lf_arm` / `vm_lr_arm` ×2 | −l_f·10815/1024, l_r·10815/1024, l_r·10815/1024 | −14923 / 14923 | high |
| 0x400ABE | `vm_const_abe` | 24278 (constant) | 24278 | high |
| 0x400AC2 | `vm_understeer_grad` | sat((966037735 / (Cf·Cr/m)) · ((Cr·l_r − Cf·l_f)/2048) / 16 / L), ∝ understeer gradient K | 1013 | high |
| 0x400AC4 | `vm_wheelbase_a` | L·338/1024 | 932 | high |
| 0x400AC6 / AC8 | `vm_track_f` / `_r` | t·464/1024 (override rows when 0xD7032[var] ≠ 0) | 713 / 712 | high |
| 0x400ACA / ACC | `vm_track_sq_f` / `_r` | (112613·t/1024)·t / (m·vm_aux_h) | 286 / 286 | high |
| 0x400ACE / AD0 | `vm_inv_track_f` / `_r` | 14563328 / t | 9246 / 9258 | high |
| 0x400AD2 / AD4 | `vm_track_f_b` / `_r_b` | t·180/1024 | 276 / 276 | high |
| 0x400AD6 | `vm_track_f_c` | t_f·100/1024 | 153 | high |
| 0x400AD8 | `vm_vch2_obs` | ∝ L²·Cf·Cr / (m·(Cr·l_r − Cf·l_f)) ≈ 0.871·v_ch² (km/h)². Saturates at v_ch ≈ 194 km/h. Read by `sub_05F942` (0x5F9CC, ÷ 0x400B2C) | 14444 | high |
| 0x400ADA | `vm_cf_l2` | L²/1024 · Cf / l_r · 1013 / m. Saturates above ≈ 3.1 m wheelbase at M3 per-kg stiffness | 23550 | high |
| 0x400ADC | `vm_balance_q9` | sat(512·Cf·l_f / (Cr·l_r)), the understeer balance (< 512 = understeer) | 363 | high |
| 0x400ADE | `vm_jz_over_mlr` | sat(Jz·23040 / (l_r·m/32)) | 875 | high |
| 0x400AE0 | `vm_cf_front` | ((L·Cf·16/m)/32 · 12271 / l_r) / 4, no saturation (wraps) | 12920 | high |
| 0x400AE2 | `vm_jz_cf` | (Jz·Cf/m)·1024 / l_r · 719 / Cr, no saturation | 621 | high |
| 0x400AE4 / AE6 | `vm_pair_cf` | `vm_pair_d7002`[var][0 / 1] · Cf · 1024 / 40039 | 9625 / 3850 | high |
| 0x400AE8 | `vm_wheelbase_vch` | L·675/1024; v_ch² = 32·AEA·AE8 (0.01 km/h)² | 1862 | high |
| 0x400AEA | `vm_vch_term` | sat(383·((Cf·Cr/m)·L / 128) / ((Cr·l_r − Cf·l_f)/32)) | 2784 | high |
| 0x400AEC / AF0 / AF2 | `vm_arm_cg` / `_front` / `_rear` | (p·10000 ± 890000)/1916/1024 with p = l_f + x, x, L + x (rounded toward the sign of p): position relative to the sensor, + = rearward, ≈ 0.1916 m per count | 1 / −6 / 8 | high |
| 0x400AEE | `vm_cent_div` | (167·y/2 + 10240000)/167/y (0 when y = 0) | 137 | high |
| 0x400AF4 | `wheel_yaw_k` | round(56888 / t_f): wheel-speed difference → yaw (1/20000 rad/s) | 36 | high |
| 0x400AF6 | `vm_wheelbase_b` | (100000·L/148)/1024, ∝ L | 1864 | high |
| 0x400AF8 | `vm_vch2_b` | ∝ v_ch² (AD8/AF8 = 61.5 for any input) | 235 | high |

Yaw references and steering equivalents (1/20000 rad/s unless noted):

| RAM | Name | Type | Meaning | Conf |
|---|---|---|---|---|
| 0x4020EC | `yaw_ref_closed` | s16 | closed-form steering yaw reference r = δ·v/(L·(1+v²/v_ch²)), 1.27 g friction-clamped | high |
| 0x4020EE / 0x402166 | `yaw_ref_lp205` / `yaw_ref_lp241` | s16 | low-passes of 0x4020EC (205/256, 241/256) | high |
| 0x40215A | `yaw_wheel_front` | s16 | front-axle wheel-speed yaw, LP 221/256 | high |
| 0x40215C | `yaw_wheel_rear` | s16 | rear-axle wheel-speed yaw, LP 221/256 | high |
| 0x40215E | `yaw_ref_closed_lp` | s16 | LP 221/256 of 0x4020EC | high |
| 0x402160 | `yaw_from_ay` | s16 | ay·88290·8/v (above 10.8 km/h), friction-clamped | high |
| 0x402168 / 0x40216A | `yaw_wheel_front_copy` / `_lp227` | s16 | copy and LP 227/256 of 0x40215A | high |
| 0x40217A / 7C / 7E / 80 | `steer_equiv_{wheel_f, wheel_r, yaw_meas, ay}` | s16, road-wheel units | the four yaw rates as equivalent road-wheel angles, δ = r·L·(1+v²/v_ch²)/v | med |
| 0x402A22 / 24 / 26 / 28 | `wheel_speed_yaw_in[4]` | s16 | wheel records 0..3 (`0x40BF00`+26+64·w) × (745 + rec+53 byte)/1001; inputs to the wheel yaw | med |
| 0x402A3E | `steer_mon_angle` | s16 | steering angle held by `steering_angle_init_monitor` 0xB97D4 | low |
| 0x402A60 | `yaw_lin_model` | s16 | v·(δ − K·ay)/L from `steer_yaw_consistency_check` | med |
| 0x402ABD | `steer_yaw_mismatch_cnt` | u8 | up to 175 while \|0x402A60\| exceeds \|0x40215E\| by > 2°/s | med |
| 0x40212C | `ay_lp` | s16, mg | LP 189/256 of 0x4020DA | high |
| 0x402AB6 | `ay_centi` | s8, 0.01 g | clamp(0x40212C/10, ±127); `abs_ay_get` value | high |
| 0x402124 / 125 / 126 | `ay_est_front` / `_rear` / `_cg` | s8, 0.01 g | `ay_axle_est_calc` at the front axle / rear axle / CG | high |

## Brake coding — COA / BCO (cycle 3 — bodies byte-identical to 1M)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0819FE | `coa_vol_to_pressure(wheel)` | high | front uses coding +3 / COA+0x1EA, rear +4 / COA+0x212; = 1M 0x8181E |
| 0x0816E8 | `coa_pressure_to_vol(wheel)` | high | inverse; = 1M 0x81508 |
| 0x081606 | `brake_torque_hold_submit(slot, torque, flags)` | med | 9 slots at 0x401684 (8 B each); callers 0x68BF8, 0x6AC86/98 (BCO), 0x83890, 0x86678 (COA), 0xBFDAE (LVC) |
| 0x08163C | `brake_torque_hold_arbitrate` | med | picks the winning slot (priority byte, then lowest torque) → whole-car torque 0x40167C, slot 0x401680, active flag 0x401678 |
| 0x0444C0 | `abs_hold_pressure_from_torque` | med | `brake_torque_to_pressure(0x40167C, 6)` (factor 2·(1762+1016)) → 0x408F32[w], same value for all wheels; read at 0x442F8 for wheels whose channel owner (0x401960) is 1 or 11 |
| 0x081750 | `coa_init_wheel_vol_offsets` | high | COA+0x16E/+0x17A per code |
| 0x084E38 | `coa_wheel_gain_apply` (void, void) | med-high | **Manufacturing test protocol only** (sole caller 0x76980 in `mfg_test_cycle` 0x76036, test-frame modes 4/6); not part of ABS control. Per wheel w = 0..3: dp = master pressure (`master_pressure_get`) - measured wheel pressure, 0 if either is invalid, clamped 0..20000; base current = `inlet_current_for_dp`(w, dp) (mA) * `coa_inlet_gain_front`/`_rear`[code] (%, `curve_interp_s16` at the constant x = 500: 91 % front / 92 % rear) / 100 -> `inlet_base_current_set`. See `INLET_VALVE_CONTROL_7846816A.md` |
| 0x06B280 | `void bco_trigger_eval(void)` | med | ready-alert pre-fill trigger. Builds `bco_cond` 0x400EC2 (b6 master pressure 0x401FF8 < 300 ∧ `pressure_get` valid ∧ 0x400B09 b5 clear; b5 no AYC/ABS/TCS/DSC intervention; b4 vref 0x408DA8 inside 0x417C0..0x417A6 = 60..500 km/h; b3 trigger) and go flag 0x400EBE. Trigger = pedal valid (0x401150 b5 clear) ∧ ((`curve_interp`(0x4177A, pedal 0x401142) < gradient 0x400F0C) ∧ A.10 ∧ `driver_mode_is_on` ∧ 0xD7156[front code] ≠ 1  ∨  0x400EBA b6 ∧ A.9 ∧ 0x41768 ≠ 0 ∧ (mode off ∨ 0xD7156[code] ≠ 0)). Detail: `BCO_PREFILL_7846816A.md` |
| 0x06B6F4 | `u8 bco_residual_stage(void)` | med | \|`ay_axle_est` 0x402126\| (0.01 g) (getter 0x93C22, lateral fitted/valid) vs 0x41770/0x41774[front code], debounce 0x41764/0x4176C on 0x400EBC → 0x400EBA b4–b7 (b6 = fired); returns b6. Invalid lateral → resets (b3) |
| 0x06B85E | `void bco_main_state_machine(void)` | med | calls trigger eval, state 0x400EC1/0xEC0 (0 idle, 1 request). State 1: submits `req_arbiter_submit(1, 17, rec+0x2A, 0, 20·scale, 10000)` for wheels 0..3 (wheels 0,1 target 0x400E9E·scale, 2,3 target 0x400E9F·scale; scale 100, or 0x417B4[code] = 50/150 when 0x400EBA b6) and `req_slot_store` ch 0/1. Reset (`bco_reset`) if go flag clear, 0x400E9D = 1, 0x400EC8 = 1 or 0x400ECE = 1 |
| 0x06B490 | `void bco_inhibit_eval(void)` | med | writes `bco_inhibit` 0x400E9D (**1 = inhibited**): 0x401150 b5, 0x402888 b5, 0x402889 & 0x0F, 0x402888 & 0x0D (steering/lateral/yaw), 0x40288C b1/b5, 0x400952[0..3] b0, `dsc_func_state_get()` ≠ 3, fault ids 35/57/59/61/63 `<<15` latched (`fault_latched`): pressure-sensor hydraulic-leakage bit 15 of groups 0x11, 0x1C-0x1F (5DA7 / 5D9D / 5DBD), never set in this image, so these never inhibit |
| 0x06B436 | `void bco_init(void)` | med | 0x400E9B = A.10, 0x400E9C = A.9 (via 0xCFCC8 / 0xCFD60), zeroes BCO state |
| 0x06B51A | `void bco_dme_status_monitor(void)` | med | signal 0 = 0x40470C (0x0AA byte 6 bits 7:4). Value in {8, 9, 11}: ECC 0x400ECC++, ECD 0x400ECD--; else the reverse. ECC = 100 → clear both, ECE 0x400ECE = 0; ECD = 100 → ECE = 1 for one loop and clear both. `bco_main_state_machine` resets mode A on ECE = 1. Invalid / timed-out field → ECE = 0 |
| 0x06B254 | `void bco_reset(void)` | med | zeroes 0x400EC0/C1/9A/9E/9F/C4/C3/BE, clears 0x400EBA b6 |
| 0x06B220 | `void bco_ramp_step(void)` | med-high | while 0x400EC4 < 0x417A4/10 (3): 0x400E9E = 0x400E9F = **20 (immediate `movi r1,20`, no table or curve)**, counter++. Not a ramp: the value stays 20 until `bco_reset`. Final mode-A target = 20 × scale (100, or 0x417B4[code]) = 2000 / 1000 / 3000 |
| 0x06C31C | `void pedal_gradient_update(void)` | med | every 2nd call (0x400F13): 0x400F0C = prev(0x400F0E) − pedal(0x401142) scaled by Δt from `0x6C2C8(0x401157 b3:2, 32, 0x5555)`; positive = lift; skipped when 0x401157 & 0x0C = 0 (source of 0x401157 open) |
| 0x0CFCC8 | `u16 coding_A10(void)` | high | bit 10 of 0x4031F4 (byte 13 b4, ready-alert brake) |
| 0x0CFD60 | `u16 coding_A9(void)` | high | bit 9 of 0x4031F4 (byte 13 b3, soft-stop assist) |
| 0x093E1C | `s16 master_pressure_get(u8 want, sensor_sig_t *out)` | high | fixed single-sensor getter: always the master cylinder value, never selects between sensors; out->value = 0x401FF8; fitted `sensor_fitted(5)`; invalid from 0x402888 b5 / 0x402884 b4; returns `want` when valid (st b7) |
| 0x093C22 | `s16 lat_resid_get(u8 want, sensor_sig_t *out)` | high | out->value = (s8)0x402126; fitted `sensor_fitted(6)`; invalid from 0x402888 b2 / 0x402884 b5 |
| 0x08FFE8 | `s8 ay_axle_est_calc(s16 arm, s16 ay, s16 cent, s16 d)` | high | clamp(cent + ay − (arm·yaw_accel 0x402102)>>8, ±1270)/10 (0.01 g): the sensor's lateral acceleration moved to a point `arm` along the car (rigid body: ay_P = ay_S + α·x + ω²·y_S). ay = LP ay 0x40212C (mg), cent = (yaw 0x402100/256)²/0x400AEE (ω²·y_S, mg), arm = lever arm 0x400AEC (CG) / AF2 (rear axle) / AF0 (front axle), in ≈ 0.19 m steps → 0x402126 / 125 / 124 (from `ay_axle_est_update` 0x9001E); see BCO doc §11 |
| 0x0835F0 | `s8 req_slot_store(u8 ch, u32 id, u8 *tuple3)` | med | channel table 0x4018F0 + 32·ch, max 4 entries (3-byte tuple + id word) |
| 0x06A8F8 | `s8 req_id_enabled(u8 id)` | med | gate in `req_arbiter_submit`; non-zero for id 17 |
| 0x08338A | `u8 req_id_blocked(u8 id)` | med | gate in `req_arbiter_submit`; 0 for id 17 |
| 0x0B4312 | `bool fault_latched(u32 id)` | high | `0x402838[id >> 16] & (u16)id` (0 if `ecu_mode_ge(3)` fails) |
| 0x068A6A | `u8 dsc_func_state_get(void)` | med | returns 0x404605 (state 0..5 set by 0x68ABA from 0x404604; BCO needs 3; meaning open) |
| 0x08D060 | `u8 driver_mode_is_on(void)` | high | mode 0x4049B4[0] ∈ {1,2,5} (also listed under DSC driver mode) |
| 0x06C090 | `void bco_dry_main(void)` | med-high | **mode B, wiper-driven brake-disc drying**: calls `pedal_gradient_update`, state `0x400EDB` (0 idle, 1 accumulate, 2 request), submits arbiter id 17 to wheels 0/1 with target `0x400EE8` and to wheels 2/3 with 0, rate 10000. Resets via 0x6BB5E on abort/end/inhibit. Detail `BCO_PREFILL_7846816A.md` §9 |
| 0x06BCFE | `void bco_dry_cond_eval(void)` | med-high | builds `bco_dry_cond` 0x400EDC (b7 wiper enable per cal 0x417C2, b6 pressure<300 ∧ valid ∧ no pedal switch, b5 no intervention ∧ 0x400E9A=0, b4 82..500 km/h, b3 pedal>25 ∧ gradient<38, b2 exposure due, b1 finished) and arm/abort/fire/end 0x400ED6/D7/D8/D9; calls 0x6BBBE, 0x7D1F6, 0x7D206 |
| 0x06BBBE | `void bco_dry_wiper_decode(void)` | med | wiper active 0x400EDD b4 / level b3:2 from F-CAN 0x2A6 byte0 3-bit (0x402E4C b7:5, b1 invalid) and PT-CAN 0x226 byte0 (0x404714: 0xAA lvl1, 0xFD lvl2, 0x55 lvl3, 0 off); diagnostic counters 0x400EF2–0x400F04 |
| 0x06BAE8 | `void bco_dry_exposure_update(void)` | med-high | `0x400ED0` (u32) += 10·vref/3600 per loop above 0x41824 (70 km/h), subtract below; threshold cal 0x417CC / 0x417C4 / 0x41828 (by wiper level) × 100 × scale; sets b2 |
| 0x06BFCC | `void bco_dry_target(void)` | med-high | `0x400EE8` = (`curve_interp`(0x417D0, vref)/100 · `curve_interp`(0x41802, 0x400EE0·10))/10, 0.01 bar (0.01 bar; 0 at t = 0, peak 100 at 82 km/h to 140 at ≥ 150 km/h, back to 1 at 3 s) |
| 0x06BFFE | `void bco_dry_inhibit_eval(void)` | med | writes `bco_dry_inhibit` 0x400EEA (1 = inhibited); same list as `bco_inhibit_eval` plus 0x402E4C b1 |
| 0x06BB82 | `void bco_dry_init(void)` | med-high | `0x400EE7` = (`coded_feature`(18) == 1) (disc-drying coding); zeroes the mode-B state; entered by `jmpi` from 0x68A00. `bco_dry_main` and CAN status 0x7B668 test `0x400EE7` |
| 0x06BB5E | `void bco_dry_reset(void)` | med | zeroes 0x400EE6/DA/DB/ED0/ED4/EE8/EE0/EDE |
| 0x07D1F6 | `s16 outside_temp_index(void)` | med | `400 − 3·0x4046E0` (outside temp raw 0x310 byte0) |
| 0x07D206 | `u8 outside_temp_invalid(void)` | med | 0x4046D8 b1 |
| 0x07F70E | `bool rx_sig_fetch(u8 n, sig_t *out)` | med | 13-case dispatcher copying a CAN-derived signal block; n = 2 → 0x404714 (PT-CAN 0x226 byte0) |
| 0x0CFADC | `coding_field_limit_check` | high | f+0..11 < table 0xF68A0 `[1,12,3,2,2,3,49,3,4,32,4,2]`; = 1M 0xD011C (table 0xF6606) |
| 0x0D2898 | `brake_torque_to_pressure(val, sel)` | med-high | clamp ±85000; 25000·val/factor, factor = front 0x403268 / rear 0x40326A / sum by sel 0–5; 8 callers |
| 0x0D2888 | `brake_torque_factor_init` | high | constants front 1762, rear 1016 (non-M computes these from coding: `CODING_BYTES_6862873A.md`) |
| 0x0CFDD8 | `u8 coding_unpack_block(const u8 *buf)` | high | 0x4031AA block from coding record: +3=(rec[2]>>3)&7, +4=rec[2]&7, +1=rec[1]&0x1F (variant). Also write-validator stage 2: fails if `coding_field_limit_check` fails, gearbox f+2 = 1, c1 b5–7 ≠ 0, any of c17–c19, c21–c24, c25–c29 ≠ 0, c14 low nibble ≠ 0, c20 & 0x3F ≠ 0, or c30 b5/b6 set |
| 0x07119E | `interp_linear_xy` | high | p-V interpolator (shared) |

BCO variables, mode A (all RAM 0x400E9A–0x400F13); mode B (0x400ED0–0x400F04): `bco_dry_exposure` 0x400ED0 u32, `bco_dry_exposure_d10` 0x400ED4 u16, `bco_dry_state_prev/cur` 0x400EDA/DB u8, `bco_dry_cond` 0x400EDC u8, `bco_dry_wiper` 0x400EDD u8 (b4 active, b3:2 level), `bco_dry_phase` 0x400EDE u8, `bco_dry_hold` 0x400EE0 u16, `bco_dry_scale` 0x400EE2 s16, `bco_dry_active` 0x400EE6 u8, `bco_dry_target` 0x400EE8 s16, `bco_dry_inhibit` 0x400EEA u8; cal 0x417C2 mode, 0x417C4/CC/828 thresholds, 0x417C6 warm scale, 0x417CE/CA/C8 temp/pedal limits, 0x417D0 speed curve, 0x41800 hold, 0x41802 time curve, 0x41824/26 speed limits. Mode A: `bco_active` 0x400E9A u8; `bco_cod_A10/A9` 0x400E9B/9C u8; `bco_inhibit` 0x400E9D u8; `bco_req_front/rear` 0x400E9E/9F u8 (0 → 20); `bco_flags` 0x400EBA u8 (b1 mode on, b2 gradient fast, b3 reset, b4/b5 phase, b6 fired, b7 armed); `bco_debounce` 0x400EBC s16; `bco_go` 0x400EBE u8; `bco_not_go` 0x400EBF u8; `bco_state_prev/cur` 0x400EC0/C1 u8; `bco_cond` 0x400EC2 u8; `bco_trig_cnt` 0x400EC3 u8 (hold, limit 0x41778/10); `bco_ramp_cnt` 0x400EC4 u8; `bco_wait_cnt` 0x400EC6 u16 (idle re-arm timer vs 0x417A8/10); `bco_press_lockout` 0x400EC8 u8 + `bco_lockout_cnt` 0x400ECA u16; `pedal_gradient` 0x400F0C s16; `pedal_prev` 0x400F0E u8; `pedal_u8` 0x401142 u8; `dme_invalid_flags` 0x401150 u8 (b5 pedal invalid); `master_pressure` 0x401FF8 s16 (0.01 bar); `ay_resid` 0x402126 s8; `dsc_func_state` 0x404605 u8. Calibration (BCO 0x41758): 0x41764 debounce 1 (500/500), 0x41768 A.9 enable (1), 0x4176A pedal level (12), 0x4176C debounce 2 (400/100), 0x41770 (60/87), 0x41774 (20/76), 0x41778 hold (500), 0x4177A pedal→gradient curve, 0x417A2 lockout gradient (−12), 0x417A4 ramp (30), 0x417A6 vref max (50000), 0x417A8 lockout time (1500/500), 0x417B4 scale % (50/150), 0x417C0 vref min (6000 = 60 km/h). Full write-up: `BCO_PREFILL_7846816A.md`.

COA 0x41978 (len 0x36C) and BCO 0x41758 (len 0x220) bodies are **byte-identical to the 1M** — not retuned.
Brake coding selects code 0 vs 1 per axle only (codes 2–7 rejected by the limit check; NCS: 0 = M3, 1 = M3 GTS).
Only the p-V curves and the front BCO thresholds differ between the codes; gain curves and offsets are identical
(full list in `CODING_BYTES_7846816A.md`). ("Byte-identical to 1M" excludes 5 header bytes at +7..+11 of each block.) COA p-V: shared pressure axis 0x41B4E
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
| 0x043754 | `ActivateTask` | high | called with task id from every timeslot case; = 1M 0x43974 |
| 0x0439CA | `TerminateTask` | high | tail of task1/2/3 entries; = 1M 0x43BEA |
| 0x0430EE | `ClearEvent` | high | task0 loop; = 1M 0x4330E |
| 0x04349C | `WaitEvent` | high | task0 loop; = 1M 0x436BC |
| 0x042848 | `ShutdownOS` | high | = 1M 0x42A68 |
| 0x0776D0 | `ecu_mode_ge` | high | (0x400A11 b7:5) ≥ n; = 1M 0x7772C |
| 0x07857E | `task0_event_loop` | high | task_entry[0]; loop {WaitEvent(1); ClearEvent(1); task0_worker} |
| 0x07858E | `task1_entry` | high | task_entry[1]; rt obj 3 → rt_task_prologue, rt_task_run, TerminateTask |
| 0x0785A6 | `task2_entry` | high | task_entry[2]; rt obj 2, same wrapper |
| 0x07871C | `task3_entry` | high | task_entry[3]; rt_frame_supervision, then rt obj 0, same wrapper |
| 0x078562 | `task4_stack_monitor_loop` | high | task_entry[4]; endless rt_measure_stack_usage over 5 rt objects |
| 0x078AC4 | `task0_worker` | med | gated by 0x400966 b5; → 0xD46CC(2), 0xD46E4(6,5,17) |
| 0x070FE4 | `task3_10ms_body` | high | vtbl 0xD7CE8 slot +40 (word 0xD7D10); only caller of control_dispatcher (0x71026); = 1M 0x71040 |
| 0x070FB6 | `task3_10ms_testmode_cycle` | high | runs instead of the full body when ecu_mode_ge(3); I/O and CAN only, no control/monitoring |
| 0x070BFC | `task1_2p5ms_body` | high | vtbl 0xD7D48 slot +40 (word 0xD7D70); 4× per frame |
| 0x070C58 | `task2_1ms_body` | high | vtbl 0xD7DA8 slot +40 (word 0xD7DD0); 10× per frame |
| 0x07839C | `rt_get_task_obj` | high | (rt, i) → rt->cls(+0)->objs(+16)[i], array 0xD7E40 |
| 0x0781FA | `rt_task_prologue` | med | bumps obj activation counter; closes runtime/budget measurement (timer 0xF80000) |
| 0x07820C | `rt_task_run` | high | optional pre-hook, then `jsr r7` at 0x78224 = obj->vtbl[+40](obj): the indirect call to the task bodies |
| 0x070A24 | `rt_task_activation_count` | high | obj->ram(+8)[0]; used as phase by the 1 ms / 2.5 ms bodies |
| 0x0786F0 | `rt_frame_supervision` | med | stack measurement + prologue for rt objs 1 and 4 (tasks 4 and 0, no wrapper of their own) |
| 0x078532 | `rt_measure_stack_usage` | med | obj → task id via 0xD7B78 → OS stack-usage query |
| 0x0785BE | `rt_shutdown` | med | (rt, flag): set/clear flag bit → ShutdownOS(0); T3 calls it when 0x6FAC2() is true |
| 0x0785D6 | `rt_fatal_error` | med | 0x7800C(10) → ShutdownOS(10); called with 0xA010 on budget overrun |
| 0x078AE2 / 0x078AE4 | `rt_checkpoint_begin` / `rt_checkpoint_end` | med | empty `jmp r15` stubs bracketing T3 sections (n=1 estimators, n=2 control_dispatcher); compiled-out profiling hooks |
| 0x06DD34 | `rom_selftest_driver` | high | references range table 0xD71F4 |

**ROM self-test (re-signing critical):** range table **0xD71F4** = {0x40000–0x402F8}, **{0x40300–0x4249C}** (calibration),
{0x424A0–0xF691C}. MISR (poly 0x00400007, seed 0, BE u32 words) recomputed by the main session, matches the stored
words byte-exact: 0x402F8→0x66E81879, **0x4249C→0x310A99BD**, 0xF691C→0xC791DCD2. **After any cal edit, recompute and
write the word at 0x4249C** (error 0x10004 otherwise). This is the in-ECU MISR only; the BMY RSA signature is separate.

### OSEK task config tables (byte-verified)

Parallel arrays (not an array of structs), 5 entries each, indexed by task id 0–4; block 0x424AC–0x4251B,
vector stubs start at 0x4251C. Element size from the indexing instruction (`ixw` 4 B, `ixh` 2 B, `addu` 1 B).
1M has the same layout at +0x220.

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0424AC | `os_task_preemptable` | med | u8[5] {1,0,0,1,1}; dispatcher 0x42C42 stores !flag → 0x40085B; when 0, ActivateTask/SetEvent defer the dispatch IRQ (OSEK SCHEDULE=NON) |
| 0x0424B1 | `os_unk_424B1` | low | 7 B `00 02 02 00 00 00 00`; no code reference found |
| 0x0424B8 | `os_task_stack_top` | high | u32[5] {0x400578, 0x400708, 0x400708, 0x400320, 0x400834}; loaded into SP at 0x42C8A |
| 0x0424CC | `os_task_stack_bottom` | high | u32[5] {0x40044C, 0x400578, 0x400578, 0x400000, 0x400708}; 0xAA canary fill 0x4270E |
| 0x0424E0 | `os_task_entry` | high | code*[5] {0x7857E, 0x7858E, 0x785A6, 0x7871C, 0x78562}; dispatcher loads cr5 then `rfi` (0x42C74), so no call xrefs |
| 0x0424F4 | `os_task_priority` | high | u16[5] {3,0,1,2,4} (0 = highest) + 2 B pad |
| 0x042500 | `os_task_ready_mask` | high | u32[5] = 1 << (31 − prio); OR'd into ready bitmap 0x400864 |
| 0x042514 | `os_task_autostart` | high | u8[5] {1,0,0,0,1} + 3 B 0xFF pad; read by StartOS 0x42A24 |

Tasks 1 and 2 share a stack (neither can preempt the other); task 3 runs on the startup stack 0x400000–0x400320.
0x424A0 (start of MISR range 3) = `AF FE DE AD 03 01 03 01 B6 00 FF FF`, unreferenced by the app.

### Runtime-object layer (how the task bodies are reached)

Task entry stubs call `rt_get_task_obj(0xD7B84, i)` then `rt_task_run`, whose `jsr r7` at 0x78224 calls
`obj->vtbl[+40](obj)`. The bodies' addresses exist only as vtable words, so a static call graph shows them uncalled.
Root 0xD7B84 → class 0xD7E64 → object array 0xD7E40; object→task-id map 0xD7B78 {3,4,2,1,0}.

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0D7B84 | `rt_root` | high | +0 class 0xD7E64 |
| 0x0D7E40 | `rt_task_objs` | high | {0xD7D1C, 0xD7C18, 0xD7DDC, 0xD7D7C, 0xD7C78} |
| 0x0D7B78 | `rt_obj_task_id_map` | high | u16[5] {3,4,2,1,0} |
| 0x0D7D1C / 0x0D7C18 / 0x0D7DDC / 0x0D7D7C / 0x0D7C78 | `rt_obj_task3` / `rt_obj_task4` / `rt_obj_task2` / `rt_obj_task1` / `rt_obj_task0` | high | +0 vtbl, +8 RAM block |
| 0x0D7CE8 / 0x0D7D48 / 0x0D7DA8 | `rt_vtbl_task3` / `rt_vtbl_task1` / `rt_vtbl_task2` | high | slot +40 = task3_10ms_body / task1_2p5ms_body / task2_1ms_body; tasks 0 and 4 have no body slot |

## TCS controller + engine-torque path (cycle 4; roles corrected 2026-10-26, `TCS_7846816A.md`)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0CC9A0 | `msr_cycle` (was `tcs_torque_ctrl_entry`; dispatch slot 17) | high | MSR (channel C): → 0xCC9B4, tail 0xCD7FE; = 1M 0xCCF5C |
| 0x0CD1E8 | `msr_pid` (was `tcs_torque_pi`) | high | MSR PID. D term clamp 0x41068/6A (±2500), integrator-input clamp 0x4106E/70 (±200; earlier "P / I clamp" was wrong), I ≤ 2·drag, output 0x40304C = u − drag, flag 0x40303C b7; decel-dependent deadband; DSC-off zeroing at 0xCD34A only with `dme_0A8_flags` b4. TCS doc §6.3 |
| 0x0CD070 | `msr_gains` (was `tcs_pi_gain_select`) | med | Kd 0x41072 = 180, Ki 0x41074 = 100, Kp 0x41076 = 60, ABS-mode Kp 0x41078 = 25; gear scaling about pivot 0x41172 = 70 |
| 0x0CCED4 | `msr_slip_target` (was `tcs_slip_target`) | high | curve 0x41046(vref) ×2 idle / ×1.5 active below it, + decel term, + 5 % vref, − curve 0x41030(4·0x4030A8) → 0x403054 (replayed, TCS doc §6.2) |
| 0x0CD7FE | `msr_floor` (was `tcs_reduction_floor`) | med | writes 0x403060 / 0x403062 b7, used by the arbiter as a lower bound on the MSR request; retuned vs 1M; formula open |
| 0x0C846A | `tcs_a_phase_hint` (was `tcs_gross_slip_check`) | med | brake-TCS freeze decision → `0x402FFF[w]` b6 (demand held in 0xC8576). Classifies demand vs PM (± 3.5 bar, 0.75 bar) into 0–3; only with rec+0x10 b4; freeze cancelled when filtered slip > clamp(40 − vref, 0, 15) km/h (hard-coded; 1M had cal fields) and ASR active (0x402F6C b7) outside split-µ, or in release with 0x402F70 < 1500 under the same condition. TCS doc §8.1; = 1M 0xC8384 |
| 0x0C7D48 | `tcs_lowspeed_pair_exit` (was `tcs_entry_gate`) | med | below 30 km/h, when the other rear also spins (filtered > 1.2, raw > 3 km/h, rate ≥ 0, PM < 5 bar), returns 1 = exit for the wheel with more pressure / beyond 20 bar and sets 0x402FFC b5 (rear) / b6 (front) |
| 0x0CC2C2 | `dme_torque_request_compose` (slot 23) | high | reduction (ASR / ABS 0x408D58 / AYC 0x400B30 / external) or increase (MSR / external) → 0x402F74/76, type 0x402F6D b3/b2; replayed (TCS doc §7); = 1M 0xCC87E |
| 0x0CC26C | `dme_torque_inputs_scale` (slot 6) | high | 0x402F70 = 0x401146·S/100, 0x402F72 = 0x401144·S/100 (S = 0x4030A0>>6), clamp s16; 0x402F6C b4 = gearbox type ∈ {1,3} |
| 0x07E7A4 | `can_dme_iface_update` (0x0B6 pack at 0x7F530) | high | sole writer of 0x4046E6/E8: reduction → sig19 = F74·819/4096, sig18 = F76·819/4096, type 2; increase → both F74·819/4096, type 1; none → 0x800, type 0; fields clamped ±2047 |
| 0x07AB52/0x07AB58/0x07AB48 | `can_tx_0B6_sig19/sig18/sig20` | high | getters for 0x4046E8/E6 + type |
| 0x0CBF58 | `asr_cycle` (was `msr_cycle_entry`; slot 16) | high | **engine ASR** (channel B): targets 0xCB27A, controller 0xCAF26, inhibits 0xCE1E8, 0xCB708; tail → dsc_mode_select |

**Torque path (corrected 2026-10-26):** the ASR torque limit is channel B (`tcs_b_entry` 0xCAD00, `tcs_b_control`
0xCAB4E) → 0x402F7A / 0x402F7C. The MSR request is channel C (`msr_pid` 0xCD1E8) → 0x40304C, floor 0x403060.
`dme_torque_request_compose` 0xCC2C2 merges these with AYC 0x400B30, ABS 0x408D58 and the dormant external limit,
then **CAN TX 0x0B6** (DSC→DME, DLC 5, 20 ms). sig20 = request type: 0 none, **1 increase (MSR)**, **2 reduction**
(pair sig19/sig18). 0x800 = "no request". The cycle-4 reading (TCS PI → reduction, type 1 = ASR) was wrong.

## Traction control (TCS / ASR / MSR) — 2026-10-26 (`TCS_7846816A.md`)

Channel roles: **A = brake TCS** (rear wheels, arbiter id 2), **B = engine ASR** (torque limit), **C = MSR** (torque
increase). All 10 ms, task 3. "Replayed" = matched by `tools/mcore_replay.py` against the doc's formula (§13).

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0C953C | `tcs_wheel_signals` | high | from the wheel loop 0x8F05C: `tcs_slip_raw`, per rear `tcs_slip_filter` + `tcs_slip_rate`, 0xCC7DE, `tcs_axle_osc_detect`, 0xCBAE4, tail 0xC9298 |
| 0x0C9450 | `tcs_slip_raw` | high | 0x40307E[w] = rec+0x1C − same-side front tracker; rears + cornering term ((v·k1(x))>>10·k2(v))>>10, x = 2048·y/max(v,50), y = \|yaw\|/75 or 2·0x4030A8; k1 0xF6158/68, k2 0xF6178/8A. Replayed |
| 0x0C9368 | `tcs_slip_filter` | high | 0x403086[w] = s + trunc((256N−2560)/N)·(f − s)/256, N = 150 (rec+0x10 b4) / 110 (split-µ) / 30. Replayed |
| 0x0C93E2 | `tcs_slip_rate` | med | 0x40308E[w] = 10q + 233/256·(rate − 10q), q = trunc(28·Δ/10) (≈ 1 mg units) |
| 0x0C91A4 | `tcs_axle_osc_detect` | med | 0x402FFC b1 (56-frame hold) on opposite-sign rear rates beyond ±320 mg with low slip; pairs from 0xF619C |
| 0x0CDBA0 | `tcs_vref_update` | high | front trackers 0x403076/78 via 0xCD9D0 / 0xCDB00 (braking) / 0xCDB42; vref_tcs 0x403066 = min; AYC re-seed; floor 0xCDAA6 |
| 0x0CD9D0 | `tcs_front_tracker(f) → f'` | high | rise ≤ 2.14 km/h/frame ×3 then jump; hold 10/30 frames; fall 0.05 / 0.11 / 0.45 km/h per frame. Replayed |
| 0x0CC0DC | `tcs_front_dv_est` | med | 0x4030A8 = capped \|FL − FR\|/4 (0.04 km/h, yaw proxy); 0x403098 = \|ay\|·100 (0.0001 g) via 0xCC208, side 0x402F7F b7; zero above 180 km/h (0xCBFD4) |
| 0x0CC568 | `tcs_rear_speed_lp` | med | 0x40309E = lp of mean raw rear speed, N from 0xF61A0 (30/112/150/150) |
| 0x0CC4E0 | `tcs_driveline_ratio` | med | 0x40306A = clamp(lp(rpm·58/0x40309E), 15, 180); 0x4030A0 = clamp(lp(0x40306A<<6), 1410, 10256); S = 0x4030A0>>6 |
| 0x0C95B8 | `tcs_engine_bog_margin` | high | 0x403024: below 20 km/h, lp((curve 0xF6380(pedal) − rpm)/16 − 3.5·lp(rpm gradient)) clamp −50…240; else ×7/8. Replayed |
| 0x0C9A22 | `tcs_split_mu_detect` | med | 0x402F7E b7 (split-µ) from rear PM imbalance below 50 km/h vs curve 0xF6634(0x4030AF) |
| 0x0CF120 | `tcs_a_slot14` | high | skips channel A (and zeroes 0x402FC2) while 0x402F6A b3; else 0xC8238 |
| 0x0C8238 | `tcs_a_frame` | high | 0xC81BE, limits per rear, rec+3 → rec+4 copy, `tcs_a_wheel_eval` per rear |
| 0x0C81BE | `tcs_a_mdm_mode` | high | 0x402FC0 b6 = 1 in MDM (unless both rears non-idle); cleared outside MDM when a rear slip < 2 km/h |
| 0x0C7A92 | `tcs_a_limits` | high | entry 0x403014[w] = T + E − R + 500, exit 0x40300C[w] = T + E/2 − R + 300, ≥ 30000 → both 30000. Replayed |
| 0x0C79B6 | `tcs_a_rate_term` | high | trunc(p·rate/100), p = 2 (split-µ, rec+0x10 b4 clear) else 10 |
| 0x0C7A3C | `tcs_a_extras` | high | curve 0xF62EE+28·m(vref) when not split-µ, 0x402F7E b4 clear and vref ≥ 2.5 km/h |
| 0x0C79E8 | `tcs_a_split_addon` | med | split-µ only: min(0xF62C8[m]·0x4030AF/178, curve 0xF62CE) on one side (0xF62C8 = 0 → 0) |
| 0x0C7A78 | `tcs_a_mdm_lockout` | high | +20000 if tcs_mode 3 and 0x402FC0 b6 clear (practically unreachable) |
| 0x0C7E40 | `tcs_a_wheel_eval` | med | per-rear command b4 enter / b5 hold / b6 exit / b3 both idle; gates 0x403024 ≤ 80 / > 110 / > 150; pair exits |
| 0x0C7BB4 | `tcs_a_phase_update(cmd)` | med | rec+3 phase bits b7 idle, b6 hold, b5 release, b4 build, b3 end, b2 release entry, b1 active, b0 entry |
| 0x0CF17A | `tcs_a_slot15` | high | 0xC95B8, 0xC82F0, then 0xC8866 (or 0xCF13C reset + zero 0x402FC2 when inhibited) |
| 0x0C82F0 | `tcs_a_active_update` | high | 0x402FC0 b4 = b0 = any rear rec+3 b1; inhibit / ABS 0x408DA2 b6 → both idle |
| 0x0C8866 | `tcs_a_pressure_frame` | high | per rear: 0xC83C4 (fast-fill counter), `tcs_a_demand` 0xC88F8, `tcs_a_target` 0xC8576; then `tcs_a_submit` |
| 0x0C88F8 | `tcs_a_demand` | med | by phase: idle → 0, release → 0xC8C5A, build → 0xC9084, hold → keep (≤ cap − 1 bar) |
| 0x0C9084 | `tcs_a_build` | med | fast fill 0xC8E6E, first step 0xC8D14, +5 bar every N frames (`tcs_a_build_interval` 0xC8D8A, map 0xF643A), MDM cap 0xC9024 |
| 0x0C8C5A | `tcs_a_release` | med | first step 0xC8ADA (d % of peak), then −max(15 %, 3 bar) every N frames (`tcs_a_release_interval` 0xC89C0, map 0xF63B8) |
| 0x0C8576 | `tcs_a_target` | med | 0x402FEC[w] = demand capped by `0x89A7C(2)` = 130 bar; rises smoothed ¾ old + ¼ new outside the fast fill |
| 0x0C8740 | `tcs_a_submit` | high | `req_arbiter_submit(1, 2, w, PM, 0x402FEC[w], target − PM)` per non-idle rear; 0x835F0 circuit requests for circuits 0/1 |
| 0x089A7C | `req_id_max_pressure(id)` | high | id 0 → COA 0x419E4, 1 → 200, 2 → 13000 (130 bar), else 0 |
| 0x0CEEDC | `tcs_disc_thermal` | med | all four discs, all braking. 23-frame round robin (0x403038): 0xCEC7C flag, then heat (0xCEB0C, PM·v·k[brake code]) / cool (0xCEBAE, speed-dependent, 3 regimes) per wheel, so once per 230 ms each. Start: off-time cool-down 0xCED38 from CAN 0x310 time (0xCED08; skipped while the time is invalid). Power-down save to NVM 0xCEA0E (high bytes + timestamp, job 0xF61A8). 0x402FC0 b1 set ≥ 0x9976 / clear ≤ 0x6F9B (rears) → 0x402FFF[w] b3. TCS doc §4.7 |
| 0x0CB27A | `tcs_b_targets` | med | 0x402FB6/B8 = curves 0xF66E0/0xF669E+22·m + cornering terms + split caps, floor max(70, vref/100) |
| 0x0C96B8 | `tcs_b_sort` | high | lead wheel 0x402F83 b4; 0x402FAA..B4 = targets, filtered slips, PM in lead/other order |
| 0x0CA1E0 | `tcs_b_request` | med | 0x402F6C b6 while lead slip ≥ target ± 0.10 km/h (more cases below 20 km/h / split-µ). Hold threshold vs 0x40309C = curve 0xF64F8, or 1500 when 0x402F7F b1 or (brake-TCS entry limit 0x403018/1A = 30000 ∧ 0x402F7E b7 ∧ b5): reads channel A state (TCS doc §8.1) |
| 0x0CAD00 | `tcs_b_entry` | med | starts ASR (0xCACA4) when engine torque 0x402F70 > 0x402F92 + 100 with the request bit (or b5 and > 800); start limit, cut 0x402FA4 |
| 0x0CAF26 | `tcs_b_control_frame` | med | 0xCA1E0, 0xC97AC; active: 0xCAB4E (restore 0xCA94C, 0xCA860 / 0xCA006), 0xCA3E4, 0xCA074 exit; inactive: 0xCAD00 |
| 0x0CA074 | `tcs_b_exit` | med | exit request when the limit has headroom (2.50/3.50 by rpm), driver demand below limit, DSC off or pedal < 13; commits after 19 frames; 0x402F7A = 0x7FFF |
| 0x0CC9B4 | `msr_frame` | med | MSR slip 0xCCC8C, target, PID or idle (0x40304C = −drag) |
| 0x0CCC8C | `msr_slip_inputs` | med | d = front reference − rear raw per side, filtered 0x403042[2] (`msr_slip_filter` 0xCCBE8, N 0x41066) |
| 0x0CE3D0 | `tcs_a_inhibit_update` | high | builds mask → 0x402F6A b3 (channel A inhibit): fault reaction b4, 0x40288C b5, 0x4030A4 = 3, DSC off, ABS vref > 120 km/h idle, DME 0x40114F b5, 0x402F6C b5, 0x402FFF[w] b3 (latches release on 0x402F86 b2) |

| RAM | Name | Type / unit | Meaning |
|---|---|---|---|
| 0x403076 / 0x403078 | `tcs_front_ref_L/R` | s16, 0.01 km/h | front trackers; hold 0x40307A/7B, rise count 0x40307C/7D (u8) |
| 0x40307E | `tcs_slip_raw[4]` | s16, 0.01 km/h | wheel − same-side tracker (+ cornering term on rears) |
| 0x403086 | `tcs_slip_filt[4]` | s16, 0.01 km/h | filtered drive slip (rears) |
| 0x40308E | `tcs_slip_rate[4]` | s16, ≈ 1 mg | filtered slip rate (rears) |
| 0x403014 / 0x40300C | `tcs_a_entry[4]` / `tcs_a_exit[4]` | s16, 0.01 km/h | brake-TCS limits |
| 0x402FC4 | `tcs_a_wheel[4]` | 10 B | +0 PM (from 0x4016E2), +2 demand, +4 u8 fast-fill counter, +6 peak (0.01 bar) |
| 0x402FEC | `tcs_a_target[4]` | s16, 0.01 bar | target sent to arbiter id 2 |
| 0x40301C / 0x403020 | `tcs_a_steps[4]` / `tcs_a_interval[4]` | u8 | step count (≤ 20) / frames since step |
| 0x402FFF | `tcs_a_wheel_flags[4]` | u8 | b1 pair hand-over, b3 disc overheat, b6 freeze, b2 ← b6 |
| 0x402FC0 | `tcs_a_flags` | u8 | b4 = b0 brake TCS active (0x19E bit 1), b6 MDM pair mode, b1 rear disc overheat |
| 0x402FF4 | `tcs_disc_energy[4]` | u16 | thermal accumulator; 0x37CE / 0x6F9B / 0x9976 / 0xFB1E ≈ 200 / 400 / 550 / 900 at 0.014 per count [I °C] |
| 0x402FFC | `tcs_pair_flags` | u8 | b1 axle oscillation, b5 / b6 low-speed pair (rear / front) |
| 0x403024 | `tcs_engine_bog_margin` | s16, 8 rpm | (n_ref − rpm)/16 based, below 20 km/h |
| 0x4030A8 | `tcs_front_dv` | u8, 0.04 km/h | \|FL − FR\| yaw proxy |
| 0x403098 / 0x4030AC | `tcs_ay_abs` / peak | s16, 0.0001 g | \|ay\| |
| 0x40306A / 0x4030A0 | `tcs_ratio` / `tcs_ratio_lp` | s16 | driveline ratio; S = 0x4030A0>>6 |
| 0x402F70 / 0x402F72 | `tcs_eng_torque` / `tcs_drv_demand` | s16, wheel domain | DME torques ·S/100 |
| 0x402F7A / 0x402F7C | `asr_torque_limit` / `asr_torque_2` | s16, wheel domain | ASR limit (0x7FFF none) / second value |
| 0x402FA4 | `asr_cut_pending` | s16 | torque cut at entry, restored in steps |
| 0x402FB6 / 0x402FB8 | `asr_target_L/R` | s16, 0.01 km/h | ASR allowed slip |
| 0x402FAA…0x402FB4 | `asr_sorted` | s16[6] | lead/other target, slip, PM |
| 0x402F7E | `tcs_state_bits` | u8 | b7 split-µ, b6/b5 side, b4, b2 \|ay\| > 0.42 g, b0 front side; +1 b7 ay < 0, b2 / b5 ASR bits |
| 0x402F6A | `tcs_inhibit_summary` | u8 | **b3 channel A inhibited** (0xCE3D0), b2 / b1 MSR / ASR summaries (0xCE748 / 0xCE812), b0/b4/b5/b6 as before |
| 0x403042 / 0x403040 | `msr_slip[2]` / `msr_slip_rate` | s16 | MSR slip per side / rate |
| 0x403054 | `msr_target` | s16, 0.01 km/h | |
| 0x40304A / 0x403050 / 0x403052 | `msr_i` / `msr_p` / `msr_d` | s16 | PID terms |
| 0x40304C | `msr_request` | s16, wheel domain | u − drag (active) / −drag (idle) |
| 0x402F74 / 0x402F76 | `dme_req_a` / `dme_req_b` | s16, engine domain | arbiter outputs → 0x0B6 sig19 / sig18 |

TCS calibrations (const ROM unless "TCS+"; m = mode index): brake TCS 0xF625C + 34m (`curve_t` n5, threshold),
0xF61F6 + 34m (alt, unused on M3), 0xF62EE + 28m (n4, low-speed extra), 0xF62C2[m] (s16[3] −4/0/0, cornering per
0x4030A8), 0xF62C8[m] (0), 0xF62CE (n2), TCS+0x40FC8 (n3, hold re-entry accel), 0xF61B4 (n3, hold rate),
0xF61CA (n4, exit offset), 0xF6342 (n4, zero), 0xF635E (n5, MDM cap ÷10 bar), 0xF6408 / 0xF6424 (n4 / n3, fast
fill), 0xF648A[m] (8/4/8), maps 0xF643A (u16[5][8], build frames) and 0xF63B8 (u16[5][8], release frames),
0xF6158/68/78/8A (cornering k1/k2 xs/ys), 0xF619C (oscillation pairs), 0xF6380 / 0xF639C (n4, pedal → n_ref);
ASR 0xF66E0 + 22m / 0xF669E + 22m (n3, targets), 0xF6688 (n3, zero), 0xF6722[m] (20/30/30), 0xF6728[m]
(−2500/0/0), 0xF654C / 0xF65B2 + 34m (n5, split caps), TCS+0x41160/66/6C (cap divisors), 0xF64F8 + 28m (n4),
0xF6618 (zero), 0xF6634 (n5, split-µ), 0xF64C6 / 0xF64CC / 0xF64E2, 0xF6496 / 0xF64AE, TCS+0x40FDE–0x41010 (output
stage); MSR TCS+0x41046 (n3, target), TCS+0x41030 (n3), TCS+0x41064/66 (90, filters), TCS+0x41068/6A (±2500),
TCS+0x4106E/70 (±200), TCS+0x41072/74/76/78 (180/100/60/25), TCS+0x41172 (70), TCS+0x4102C (2000), TCS+0x4106C
(400); disc 0xF674E / 0xF6752 (65 / 45 by brake code), 0xF672E–0xF674A (cooling). XDF labels here are stale.

## Hydraulic actuation (cycle 4 — byte-verified data; valve/pump roles inferred)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0843BC | `hydraulic_actuation_pipeline` (slot 32) | med | calls valve seq + pump; entry to actuation |
| 0x0853A8 | `valve_pulse_sequencer` (void, int w) | high | 10 ms per-wheel inlet profile s16[10] mA, by `wheel_p_request`[w].mode. **Hold (1) / dump (4):** all steps min(I, 1540), I = 1524 (hold) / 1532 (dump) on the first frame (`inlet_closed_frames`), then `inlet_holdin_current` 1100. **Build (2):** I_hold = `inlet_current_for_dp`(w, `supply_pressure`(w) - PM); y = interp(dp, {0, 20, 80 bar} -> front {0, 10, 40} / rear {0, 5, 20} %, y2 = COA 0x41A72/74); D = `curve_slope_fwd`(PM, axis 0x41B4E, coded p-V volume curve 0x41B62/0x41B8A, 10, 100) (dV/dp per bar) * dp / (0x41A76/78 (800/350) + temp 0x401FF7); k = clamp(100 - rate * y / D, 100 - y, 100) (D <= 0 -> k = 100 - y); I_build = I_hold * k / 100 -> `inlet_build_current` 0x401C00[w]. Open steps n = f((target - PM) * 10 / rate) clamped 0..10, at least 3 when the valve was not already fully open; `valve_cmd`[w] = 2n; profile = n steps at min(I_build, 1540), rest 1540. **Rate 9000 (full build):** I_build = 0 (valve de-energised), n from 0x85340. Profile -> `seq_profile_stage` / `seq_profile_commit`; only uploaded for rate 9000 (normal rates use the fast loop's profile) |
| 0x084460 | `inlet_mode_select` (void, int w) | high | `wheel_p_request`[w].mode from the sign of .rate with transition rules: 0 hold (1), > 0 build (2), < 0 dump (4); previous mode copied to 0x401AC8[w]; forced 0 when 0x40199C[w] == 0; result also to 0x401C34[w] |
| 0x085A42 | `outlet_dump_time_calc` (void, int w, s16 rate) | high | 10 ms, from `wheel_valve_frame` for wheels with mode != 0; rate = request+6, target = request+8 (R = *0x4019A8[w]). Open-loop outlet open time in 1 ms steps. acc = `wheel_p_request`[w]+4 (s16, ms, <= 0, dump time still owed), ref = `dump_ref_pressure`. **Build** (rate > 0): acc = 0, ref = PM. **Hold** (rate 0): if ref < target, acc = 0, ref = PM; n0 = `outlet_hold_bleed`. **Dump** (rate < 0): on entry from hold/build (0x401AC8) ref = PM; if target < ref and PM - `dump_step_dp` >= target (a minimum pulse will not undershoot): acc += `outlet_dump_time_for_target`, ref = target. target == 0 and ref == 0 -> acc = -10. Then n0 = acc, acc = min(acc + 10, 0). n = -10 if n0 <= -10; 10 if n0 >= 11; -lvl if -lvl < n0 < 0 and `valve_cmd` != -20 (round up to the minimum pulse lvl = interp(PM, `coa_dump_predict_p_axis`, `coa_dump_predict_level`, 4) = 4 ms flat); else n0. rate <= 0: `valve_cmd`[w] = 2n (feeds the hydraulic model). n < 0 and `abs_active_any`: `valve_pulse_set`(4 + w, -2n) = outlet on for steps 0..|n|-1. `outlet_cmd_last`[w] = n |
| 0x085958 | `outlet_dump_time_for_target` (s16 ms, int w) | high | t = 10 * (V(target) - V(ref)) / q, V = `wheel_volume_at`, q = `valve_flow`(max(ref - `lpa_pressure`[c], 0), k_out 0x41B30[w/2] (755 front / 465 rear), 80) = volume per full 10 ms opening at the starting dp; c = 0xDA1B4[w]. q < 11 -> 10 * sign(dV) (= -10, one frame). Negative = outlet time. Flow taken at the start pressure, so t is short; the next frame re-plans from ref = target |
| 0x085924 | `wheel_volume_at` (s16, int w, s16 p) | high | max(interp(p, axis 0x41B4E, coded p-V curve front 0x41B62 / rear 0x41B8A + 20 * code, 10), 0); same curve as `curve_slope_fwd` in the sequencer |
| 0x0859C8 | `outlet_hold_bleed` (s16, int w) | med | -10 (a full outlet frame) or 0. -10 only in hold with request target 0, partner wheel 0xDA1B0[w] not in control (0x40199C), request+10 b1 clear and frame counter 0x40095C % 100 > 30 (70 of 100 frames). Request type request+0 must be 1, 5 or 11 unless 0x400AFA[w] b7 clear and 0x401C10[w] b5 set; any other type returns -10 at once. Purpose (bleeding residual pressure to zero) is inference |
| 0x0858D0 | `outlet_idle_reset` (void, int w) | high | mode 0 (from `wheel_valve_frame`): acc = 0, `dump_ref_pressure` = PM, `outlet_cmd_last` = 10, `valve_cmd` = 20 (model: inlet fully open) |
| 0x0858FE | `inlet_idle_reset` (void, int w) | high | mode 0: `wheel_p_request`[w]+6 = 0, 0x401C08[w] = PM, `inlet_closed_halves`[w] = 0 |
| 0x0836D2 | `abs_active_any_get` (u8, void) | med | returns 0x401980; gates outlet pulses here and in 0x872B0, 0x885EC, 0x88C96, 0x89206, 0x8CEAC |
| 0x06D0F4 | `sign_s16` (s16, int x) | high | (x >> 31) \| 1: -1 or +1 (0 -> +1) |
| 0x0740BC | `valve_pulse_set` (void, int ch 0..11, s16 n2) | high | n = n2 / 2 clamped -10..10. n > 0: steps 0..n-1 on; n < 0: steps \|n\|..9 on. ch 0..3 (inlets): `inlet_out_stage`[ch][i] = 229 (~1800 mA, closed); ch 4..11: bit 0xD7634[ch] set in `valve_dig_stage`[i]. Normal-control callers use ch >= 4 only (outlets via `outlet_dump_time_calc`, ch 9 0x87CC0, ch 11 0x88A18); ch 0..3 only from the mfg test protocol, 0x744E4 (all channels n = 10) and KWP 0xB018A |
| 0x0D4CA8 | `qspi_xfer(cs, n, tx, rx)` | high | QSPI 0xDB0000; = 1M 0xD52E8 |
| 0x0D4A30 | `asic_reg_xfer32` (CS5, cmd 0xFA) | high | combined sensor+valve/pump ASIC |
| 0x0D4BF4 | `spi_cs4_out16` (CS4, cmd 0xFB) | med | 16-bit digital-valve output latch |
| 0x0852B6 | `curve_slope_fwd` (s16, s16 x, s16 *xs, s16 *ys, int n, int scale) | high | forward-difference slope of a piecewise-linear curve: (`interp_linear_xy`(x + 500) - `interp_linear_xy`(x)) * scale / 500, scale < 1 -> 1. Returns 0 when n < 2 or x is outside [min(xs), max(xs)]. Quirk: for x >= max(xs) - 500 the difference is never computed and the caller's r10 is used (unreachable for wheel pressures, max(xs) = 32700). Only caller `valve_pulse_sequencer` (scale 100: brake compliance dV/dp per bar at PM; front code 0: 360 / 130 / 115 / 103 / 85 at 0 / 10 / 20 / 50 / 100 bar, rear code 0: 233 / 100 / 65 / 55 / 46) |
| 0x085D64 | `wheel_valve_frame` (void, void) | high | 10 ms, from `hydraulic_actuation_pipeline`. Per wheel: `wheel_p_request`.rate = request+6, `inlet_mode_select`, 0x85D10; mode != 0 -> `valve_pulse_sequencer`, `inlet_holdin_current_set`; then `outlet_dump_time_calc`(w, rate) |
| 0x085888 | `inlet_holdin_current_set` (void, int w) | high | `inlet_holdin_current`[w] = 1100 (only writer) |
| 0x08143A | `seq_profile_stage` (void, int w, s16 *mA) | high | copies 10 steps to 0x404892[w] (s16[4][10]), flag 0x404932[w] = 1 |
| 0x0813F0 | `seq_profile_commit` (u8, int w) | high | flag 0x404932[w] = (flag == 1) ? 2 : 0 |
| 0x081460 | `seq_profile_latch` (void, int w, int half) | high | half 0 and flag == 2: 0x404892[w] -> 0x4048E2[w], 0x404936[w] = 2; flag cleared |
| 0x0814A8 | `seq_profile_upload` (void, int w, int half) | high | 0x404936[w] == 2: `inlet_profile_upload`(w, &0x4048E2[w][half * 5], half) |
| 0x085282 | `inlet_fast_loop` (void, int w, int half) | high | 2.5 ms task 0x70BFC, phase 0 (half 0) and phase 2 (half 1), w = 0..3, i.e. every 5 ms per wheel. Runs 0x8454E (struct -> prev copy 0x401B48), `inlet_fast_capture`, `seq_profile_latch`, `inlet_fast_pressure_update`, `inlet_setpoint_ramp`, `inlet_fast_mode_refine`, `inlet_fast_current`, then `inlet_profile_select_upload` |
| 0x084584 | `inlet_fast_capture` (void, int w, int half) | high | half 0 only: 0x401CC4 = `driver_pressure`; ctl.mode = request mode; ctl.target = request+8; ctl.rate = request rate mapped: 9000 kept, <= 0 kept, 1..100 -> 100, > 100 -> min(rate, 600); 0x401BFC[w] = open-step count from `valve_cmd` |
| 0x084620 | `inlet_fast_pressure_update` (void, int w, int half) | high | ctl.p_meas = measured wheel pressure sample 0x40206A[w][half]; ctl.dp = clamp(max(`driver_pressure`, own, partner (0xDA1B0)) - p_meas, 0, 20000) |
| 0x0846BE | `inlet_setpoint_ramp` (void, int w) | high | ctl.p_sp = p_meas when mode 0 / 4, or on build entry from dump; else p_sp += rate / 2 per half-frame, capped at target, >= 0. ctl.err_tgt = target - p_meas, ctl.err_sp = p_sp - p_meas |
| 0x084772 | `inlet_fast_mode_refine` (void, int w) | med | 5 ms hysteresis on ctl.err_tgt: band +14 / +16 (start 100 = 1 bar; +200 when rate > 500; grows while the error stalls, counter 0x401CD0; cap 800) switches ctl.mode between 1 (hold), 2 (build) and 8 (settle, countdown 0x401BF8 from 5). Not every branch traced |
| 0x08519E | `inlet_fast_current` (void, int w, int half) | high | 0x401CB4[w] = `inlet_rate_achieved`; by ctl.mode: 0 -> clear `inlet_build_learn`, counter 0x401AE8; 1 / 4 / 8 -> `inlet_profile_fill`(w, 1524 / 1532 / 1492 for the first two half-frames, then 1100); 2 -> `inlet_build_profile`. If achieved > 100 %: `inlet_build_learn`[w] += `inlet_build_adapt` |
| 0x084A56 | `inlet_build_profile` (void, int w, int half) | med-high | metered reapply. I = `inlet_build_current`[w] - `inlet_build_learn`[w] (learn >= -150, I >= 180 mA unless learn <= 0, I >= 0); learn += err_sp / 200 after 1 / 3 / 7 stalled half-frames with err_sp > 8 / 4 / 2 bar (0x401C3C). Rate lower than last half -> I = 1508. Steps open (I) when err_tgt * 10 / rate >= 1 (all 5), else closed (1540, or 1100 after two closed halves). Rate 9000: open-step bucket 0x401CD8 from accumulated demand (not uploaded; seq profile used) |
| 0x084F02 | `inlet_rate_achieved` (u16 %, int w) | med | measured dp/dt from a 6-tap weighted history {4, 6, 10, 10, 6, 4}/40 of p_meas differences (0x401C54 / 0x401C84); 100 * min(recent gradient) / rate at build start (0x401CBC); 100 outside modes 1 / 2 / 8 |
| 0x0850AA | `inlet_build_adapt` (s16 mA, int half, int w) | med | when achieved > 130 % (or 30 % above the last trigger): learn >= 6 -> learn * 100 / achieved - learn, else (7800 - 60 * achieved) / 300; negative = more current = slower build |
| 0x0844E6 | `inlet_profile_select_upload` (void, int w, int half) | high | ctl.mode 0, or rate 9000 -> `seq_profile_upload` (sequencer profile); modes 1 / 2 / 4 / 8 -> `inlet_profile_upload`(w, `inlet_current_profile`[w], half) |
| 0x073BD4 | `inlet_profile_upload` (void, int w, s16 *mA, int half) | high | skipped when 0xD7570[w] & 0x4009B1 (failsafe-forced wheel); `inlet_out_dac`[w][half*5 + i] = min(mA[i], 1800) * 51 / 400, i = 0..4 |
| 0x074320 | `valve_output_frame_merge` (void, void) | high | 2.5 ms phase 0, before the fast loop. 0x4009B1 = failsafe mask from 0x40287D; digital: `valve_dig_out`[i] = (`valve_dig_stage`[i] & ~mask) \| forced, stage cleared. Inlets: per wheel by 0x40287D (w0 b3, w1 b2; rears b1 / b0): normal -> `inlet_out_dac`[w][i] = stage ? stage : `inlet_base_current_dac`[w], stage cleared; forced-off -> 0; forced-closed (rears b1 & b0) -> 229 |
| 0x0741F4 | `valve_output_1ms` (void, int step) | high | 1 ms task 0x70C58 (step = activation count - 1); 0x74B56(step), then tail-jumps to `valve_output_step` |
| 0x073DBC | `valve_output_step` (void, int step) | med | per wheel: v = `inlet_out_dac`[w][step]; enable bit 0xD7570[w] in 0x401040 set if v != 0; words to `qspi_xfer`(CS5, 8, tx, rx) (valve/sensor ASIC); readback history 0x400FEA / 0x401012 (10 steps), 0x73C46 per wheel (role not traced) |
| 0x076036 | `mfg_test_cycle` (void, void) | med | called from both 10 ms bodies (0x70FD2, 0x7103C); contains the manufacturing/test serial protocol state machine (state 0x400A28, `analysis/agents/mfgproto/REPORT.md`). Its valve-drive command: modes 0/5 base currents from the frame, 4/6 `coa_wheel_gain_apply`; 4-bit pulse lengths + sign mask -> `valve_pulse_set` ch 0..11; also writes `usv_current_set` |
| 0x00400F2E | `inlet_out_dac` (u8[4][10]) | high | per-wheel inlet current per 1 ms step, DAC code = mA * 51 / 400 (229 = 1800 mA). Filled by `valve_output_frame_merge`, overwritten per half-frame by `inlet_profile_upload`, clocked out by `valve_output_step` |
| 0x00400F56 | `inlet_out_stage` (u8[4][10]) | high | `valve_pulse_set` ch 0..3 staging; consumed and cleared by the merge |
| 0x00400998 | `valve_dig_stage` (u16[10]) | high | per-step on/off bitmask for ch 4..11 (bits 0xD7634); consumed by the merge |
| 0x00400984 | `valve_dig_out` (u16[10]) | med | merged digital-valve bitmask per step (out via CS4 `spi_cs4_out16`, inferred) |
| 0x00401AF8 | `inlet_ctl` (struct[4], 20 B) | high | fast-loop state: +0 u8 mode (0/1/2/4/8), +2 s16 target, +4 s16 p_sp (ramped setpoint), +6 s16 rate, +8 err_tgt, +10 p_meas, +12 dp (supply - p_meas), +14 / +16 hysteresis bands, +18 err_sp. Previous half-frame copy at 0x401B48 |
| 0x00401AF0 | `inlet_holdin_current` (s16[4], mA) | high | 1100; closed-valve hold-in current after the first frame / two half-frames (peak 1492..1532 first) |
| 0x00401C00 | `inlet_build_current` (s16[4], mA) | high | I_build from `valve_pulse_sequencer` (10 ms); base of the fast-loop metered current |
| 0x00401BC0 | `inlet_build_learn` (s16[4], mA) | med | learned reapply current offset, subtracted from I_build; + when pressure lags the setpoint, - when the rise rate overshoots by > 30 %; cleared in mode 0 |
| 0x00401AE8 | `inlet_closed_halves` (u8[4]) | high | fast-loop count of closed half-frames, saturates at 2 (peak -> hold-in current) |
| 0x00401AEC | `inlet_closed_frames` (u8[4]) | high | sequencer counterpart, saturates at 1 |
| 0x088EC0 | `pump_motor_control` | med | level = clamp(0x401D2E/33, 15); cal 0x419D4/D8/DA |
| 0x088A18 | `pump_circuit_demand(c)` | med | per-circuit pump demand 0..10; called for c = 0, 1 at 0x843CE/0x843D2. See "Pump volume model" |
| 0x073250 | `pump_motor_set_level` | med | timer-PWM, 4000 ticks/level |
| 0x070314 | `pump_motor_pwm_isr` | med | F8 timer compare 0xF80170 |
| 0x0B0154 | `kwp_valve_pump_test_drive` | med | diagnostic actuator test (SID 0x30/0x31 path) |

**12 solenoid channels** (mask table 0xD7634; test order 0xF2EF0 = [0,4,1,5,2,6,3,7,8,9,10,11]): ch0-3 inlet
(analog current via CS5), ch4-7 outlet (digital via CS4), ch8-11 USV/HSV circuit valves (roles inferred). Pump is a
timer-PWM on module 0xF80000 (not SPI). **Tunable (COA block):** valve start offsets 0x41A72/74 (40/20), build-mode
gains 0x41A76/78 (800/350), pump cal 0x419D4/D8/DA (0/100/50). **Code-literal (patch-only):** closing currents
(peak 1524 hold / 1532 dump / 1492 settle, hold-in 1100), rate-drop current 1508, metering floor 180 mA, rate clamp 100..600, profile clamp 1540, ×51/400 scale, pump 4000 ticks/level, 10-step frame. Failsafe byte 0x40287D.
Inlet control chain end to end (10 ms sequencer, 5 ms fast loop, 1 ms output): `INLET_VALVE_CONTROL_7846816A.md`.
Dispatcher 0x8CCB8 is a flat 41-slot sequencer; slots 0–39 named (med) in `analysis/agents/m3actuation/`.

## Pump volume model

Traced from the listing; detail in FACTS.md, "Pump volume model, and M3 vs 335 hydraulic calibration".
Circuits: c = 0 is wheels 0/1 and c = 1 is wheels 2/3 (ROM map 0xDA1B8). Volumes use the p-V curve unit
(0.1 mm³ per count; see FACTS.md, "Hydraulic-model volume unit"); pressures are 0.01 bar.
Overview, valve topology and simulator: `HYDRAULIC_MODEL_7846816A.md`.

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x081782 | `pump_flow_estimate_update` (void) | med | from `hydraulic_model_step` 0x82F22. Main path: x = sum of 0x4016EA[c]/2 over circuits with 0x4016FA[c] != 0; 0x40170C += (interp(x, 0xDA604, 0x41B38) - 0x40170C) * 0x41B4C / 256. Branches on 0x4019F8 b5 / 0x408DA1 b4 (0x41B42) not traced |
| 0x082824 | `pump_supply_store_update` (void) | med | from `hydraulic_model_step` 0x82F24; loops c = 0, 1. While c is pumped (0x8258C), 0x401702[c] += 0x401A1A[c] * r / 20 (doubled from 0), r = 0x41B36 * ROM factor 0xDA5F8 / 100, clamped to 0x41B34; then drawn down by the delivered volume interp(0x40170C, 0x41B3C, 0x41B44) * 0x401A1A[c] / 20 |
| 0x08258C | `pump_circuit_active(c)` (bool) | low | reads 0x401A1A[c] and failsafe byte 0x40287D (mask 0x40 for c = 0, 0x80 for c = 1) |
| 0x086054 | `circuit_volume_shortfall(c)` (s16) | med | per wheel of c: p = max(0x401A20[w] if 0x40199C[w], 0x401D28[c]); V(p) via the coded p-V curve (axis 0x41B4E; front 0x41B62 + 20 * coding byte 3, rear 0x41B8A + 20 * byte 4) minus V 0x4016DA[w]. How the two wheels are combined is not traced. Result stored to 0x401D32[c] at 0x86288 |
| 0x088A18 | `pump_circuit_demand(c)` (s16, 0..10) | med | when 0x401D32[c] > 0x401702[c] + 125 and 0x401E4E == 1: (0x401D32[c] - min(0x401702[c] + rate, 0x41B34)) * 10 / interp(0x40170C, 0x41B3C, 0x41B48), clamped 0..10 (rate = 0x41B36, doubled when the store is 0) |

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x00401702 | `pump_supply_store` (s16[2], volume) | med | per circuit; filled and drawn down by 0x82824, capped by 0x41B34; read by 0x88A18 |
| 0x0040170C | `pump_flow_est` (s16) | med | low-passed pump flow (0x81782); x for 0x41B3C curves |
| 0x00401D32 | `circuit_volume_shortfall_v` (s16[2], volume) | med | written from `circuit_volume_shortfall` at 0x86288 |
| 0x004016EA | `circuit_pressure` (s16[2], 0.01 bar) | med | per-circuit pressure; set from driver pressure 0x404994 at 0x8257C (other writers not traced) |
| 0x00401A1A | `pump_circuit_share` (s8[2], 0..20 = /20) | low | multiplies the store fill and delivered volume per circuit |

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x41B34 | `coa_pump_store_cap` (s16, volume) | med | cap on 0x401702[c]. M3 / 1M 1150; 335 (6862873A, 6791524A) 650 |
| 0x41B36 | `coa_pump_store_rate` (s16, %) | med | fill step of 0x401702[c]; 100 in M3 and 335 |
| 0x41B38 | `coa_pump_flow_vs_p` (s16[2]) | med | y over ROM axis 0xDA604; 4300 / 2600; same in 335 |
| 0x41B3C | `coa_pump_flow_axis` (s16[2]) | med | x = pump flow 0x40170C; 0 / 4300 |
| 0x41B44 | `coa_pump_dv_vs_flow` (s16[2]) | med | delivered volume per frame on the 0x41B3C axis; 0 / 340 |
| 0x41B48 | `coa_pump_demand_div` (s16[2]) | med | demand divisor on the 0x41B3C axis; 0 / 265 (also read at 0x829CE, 0x87CF2) |
| 0x41B4C | `coa_pump_flow_filter` (s16, /256) | med | low-pass coefficient for 0x40170C; 187 |
| 0x0DA604 | `pump_flow_p_axis` (s16[2], 0.01 bar) | med | ROM x axis for 0x41B38: 0 / 25000 |
| 0x0DA1B8 | `circuit_wheel_map` (u8[2][2]) | high | {0, 1}, {2, 3} |
| 0x0DA5F8 | `pump_store_rate_factor` (s16[], %) | low | factor table for 0x41B36, indexed through 0x401FF7 (20 when 0x402888 b7); layout not fully decoded |

## Circuit volume model

`circuit_volume_update(c)` 0x826C0 runs once per circuit from `hydraulic_model_step`. The order is 826C0(0),
`lpa_update`(0), 826C0(1), `lpa_update`(1). Wheels per circuit come from 0xDA1B8. Pressures are 0.01 bar; volumes
are in the p-V curve unit (0.1 mm³ per count). "Level" = valve opening 0..10. pV_w(p) = interp(p, axis 0x41B4E, front 0x41B62 +
20 * coding byte 3 or rear 0x41B8A + 20 * byte 4, n = 10). Interpretations of USV/HSV are inferred.

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0826C0 | `circuit_volume_update` (void, int c) | high | dVa/dVb = `wheel_volume_delta`; if `circuit_supply_fed(c)`: 0x81C46, 0x81BC8 fill 0x4016FE[0..1] as scratch and replace dVa/dVb when their sum is not smaller; V += dV; Da/Db = `wheel_dump_volume`; if both < 0, each is limited to max(D, min(draw - LPA volume, 0) / 2); `lpa_inflow`[c] = Da + Db; V -= D; `wheel_volume_temp_comp` per wheel; V clamped to <= 30000 |
| 0x08216E | `wheel_volume_delta` (s16, int c, int w) | high | p_w >= driver pressure: if request record 0x401AA8[w].mode == 2 and dp != 9000: V target = pV_w(min(p_w + dp * inlet level / 10, `circuit_pressure`[c])), 0 when the level is 0; else valve_flow(driver p - p_w, k_in 0x41B26[w/2], `inlet_open_effective`). p_w > driver pressure: 0 if `circuit_supply_fed`; in supply mode, relax toward supply: pV_w(s + (p_w - s) * 224/256) - V when s < p_w, else 0; otherwise backflow -valve_flow(dp, k_back 0x41B2E, (10 - 0x401A1C[c]/2) * 8), halved when dp > -500. Result >= -V; in supply mode part of a backflow goes to the partner wheel (k_in / (k_in + k_back) * partner level / 10), and backflow is 0 when the partner pressure is higher |
| 0x0825F8 | `wheel_dump_volume` (s16, int c, int w) | high | 0 unless `outlet_valve_level(w)` >= 1. q = valve_flow(p_w - `lpa_pressure`[c], k_out 0x41B30[w/2], level * 8); avail = V - pV_w(`lpa_pressure`[c]). dp >= 1: min(q, avail), q halved when dp < 500. dp <= 0: max(-q, avail, draw - LPA volume), i.e. a negative value = backflow from the LPA |
| 0x0825B6 | `lpa_pump_draw` (s16, int c) | high | pumped circuit (0x8258C): 250 if `lpa_pressure`[c] >= driver pressure, else 0; otherwise `pump_volume_frame`[c]; capped at `lpa_volume`[c] |
| 0x0827BA | `lpa_update` (void, int c) | high | LPA volume += `lpa_inflow`[c] - `lpa_pump_draw`(c); zeroed when 0x73348() and 0x401C34[0..3] are all 0; clamped to 0x41B1E[3]; `lpa_pressure`[c] = interp(volume, 0x41B1E, 0x41B16, n = 4) |
| 0x081AF4 | `circuit_supply_pressure` (s16, int c) | high | supply mode ? min(0x401DB8[c], 0x401DBC[c]) : 0x401DB2; >= 0; plus driver pressure when that is <= 19767; saturates at 32767 |
| 0x081EA0 | `circuit_supply_fed` (bool, int c) | high | 0x401A1C[c] == 20 and `circuit_supply_pressure`(c) >= `circuit_pressure`[c] and failsafe 0x40287D bit (0x10 for c = 0, 0x20 for c = 1) clear |
| 0x087B0C | `supply_mode_active` (bool, void) | med | 0x401DB0 b6 |
| 0x0818E6 | `inlet_valve_level` (s8 0..10, int w) | high | 0x401A16[w] / 2, clamped 0..10; failsafe 0x40287D forces 10 (w0 bit 0x08, w1 bit 0x04; rear wheels via b1/b0) |
| 0x0819A8 | `outlet_valve_level` (s8 0..10, int w) | high | -0x401A16[w] / 2, clamped 0..10; same failsafe overrides |
| 0x081938 | `inlet_open_effective` (s16, int w, s16 dp) | med | inlet level * 8 minus a dp-dependent offset (interp(dp, 0xDA5D6, front 0xDA5E0 / rear 0xDA5EA, n = 5); 0 when 0x401706[w] is set), capped at 80 |
| 0x081BC8 | `supply_inflow_split` (void, int c) | med | when 0x401722[c] >= 2 and either wheel's inlet level >= 1: K = (k_cross[a] * lvl_a + k_cross[b] * lvl_b) * 10; 0x4016FE[0] += `supply_inflow_wheel`(wa, K, c), [1] += (wb, K, c) |
| 0x081B4A | `supply_inflow_wheel` (s16, int w, s16 K, int c) | med | 0 unless p_w < s = `circuit_supply_pressure`(c); ROM 0xDA5D2[w/2] * k_cross[w/2] * lvl^2 / K * (s - p_w) / s |
| 0x081C46 | `supply_inflow_distribute` (void, int c) | high | splits this frame's pump volume P = `pump_volume_frame`[c] between the circuit's wheels a, b, then equalises them. Common opening m = min(lvl_a, lvl_b): in_a = P * k_a / (k_a + k_b) * m / 10 + P * (lvl_a - m) / 10 (likewise b), k = k_in 0x41B26 (k_cross 0x41B2A when 0x401C10[w] b7). Predicted pressures p'_w = interp(V[w] + in_w, coded volume curve, axis 0x41B4E) (inverse p-V). Cross-flow q = valve_flow(|p'_a - p'_b|, 2 * 0x41ADC[axle][b7] / 7, lvl of the receiving wheel * 8), soft-limited by ROM 0xDA5F4[dir] L: q <= L -> q^2 / 2L, else q - L/2; moved from the higher wheel to the lower. Each result is clamped to +-2000 and to <= 0 when PM[w] >= `circuit_supply_pressure`(c); stored to 0x4016FE[0] (a) and [1] (b) |
| 0x081776 | `wheel_model_flags_clear` (void, int c, int w) | high | clears 0x401C10[w] b7; called for each wheel at the start of `hydraulic_model_step` |
| 0x082BC0 | `wheel_pressure_select` (void, void) | high | detail of the existing entry. (1) Measure: 0x401719 b7/b6 cleared; skipped (no measurements) when 0x402888 b5 or `fault_is_set` of 35/57/59/61/63 << 15; else `wheel_pressure_get` for w = 0..3; b7 = both fronts valid, cleared by an invalid rear; b6 = all four valid. (2) Per wheel w: no b7 (front) / b6 (rear) -> `coa_vol_to_pressure`(w). `valve_cmd`[w] < 0 sets `wheel_dump_latch`[w]; > 0 clears it and sets a dump-ended flag (one stack word, not reset per wheel). `pump_recent`[c] = 5 while `pump_volume_frame`[c] >= 1, else counts down on the circuit's first wheel. Pump-fed path (PM < `circuit_supply_pressure`, `usv_close_level`[c] >= 1, 0x401DCC[c] != 3, `valve_cmd`[w] == 20, `pump_recent`[c] >= 1): PM = min(pV_w^-1(pV_w(PM) + 500), measured), not below the old PM while PM < 500; V re-synced; latch cleared. Else: latch set -> `coa_vol_to_pressure`; otherwise, if dump ended, `lpa_volume`[c] += V - pV_w(measured) clamped 0..0x41B1E[3]; PM = measured (0x82E9C); V re-synced. Both re-sync paths set `wheel_model_flags`[w] b5 = PM <= 500 and 0x401A20[w] <= 500 |
| 0x081722 | `coa_pressure_to_vol_value` (s16, int w, s16 p) | high | pV_w(p) via the coded curve; pure |
| 0x08236C | `circuit_feed_pressure_update` (void, int c) | med | writes `circuit_pressure`[c]. Not `circuit_supply_fed`: max(PM[a], PM[b], `driver_pressure`). Pump-fed: estimate from `circuit_supply_pressure`, `pump_volume_frame` * 17 and ROM tables 0xDA614/0xDA61C/0xDA624/0xDA62C/0xDA634/0xDA63C (indexed by `wheel_model_flags` b7 and inlet levels; not fully traced), floored at `driver_pressure` |
| 0x084D98 | `inlet_current_for_dp` (u16 mA, int w, s16 dp) | high | inlet-valve counterpart of `usv_current_for_dp`: current to hold dp (0.01 bar, wheel side lower) across inlet valve w. 0 when `fault_is_set`(0x150004) (inlet cal invalid). dp <= 14000: `interp_linear_xy`(dp, ROM axis 0xDA158 {0, 2000, 5000, 9000, 14000}, `inlet_cal`.f[w][0..4] at 0x401E72 + 10 * w, n = 5). dp > 14000: f[w][4] + (dp - 14000) / 100 * k / 100 * 90 / 100, k = 207 front (w 0/1) / 133 rear, i.e. ~1.86 / ~1.20 mA per bar; no lower extrapolation. Result zero-extended; no 1800 mA cap here (`inlet_base_current_set` caps). Callers: `coa_wheel_gain_apply` 0x84E82, `inlet_profile_fill` 0x84EE4 (dp = 13000), `valve_pulse_sequencer` 0x854E2 (dp = `supply_pressure`(w) - PM[w]) |
| 0x084ECC | `inlet_profile_fill` (void, int w, u16 mA) | med | fast-loop closed-valve current: writes mA to all 5 steps of `inlet_current_profile`[w]. Rear wheels (w >= 2) with 0x408DA0 b3 set: mA = min(mA, `inlet_current_for_dp`(w, 13000)), i.e. capped at the 130 bar hold current. Sole caller `inlet_fast_current` 0x8519E (0x85256): modes 1 / 4 / 8 pass 1524 / 1532 / 1492 mA for the first two half-frames, then `inlet_holdin_current` (1100) |
| 0x073C2E | `inlet_base_current_set` (void, u16 mA, int w) | high | 0x4009AC[w] = min(mA, 1800) * 51 / 400 |
| 0x08AC10 | `valve_cal_start` (bool, int type) | high | SID 31 routine 0x28 -> type 1 (inlet valves), 0x29 -> type 2 (MCI / USV); sets 0x404970; type 2 clears 0x401E9A[0..3]. See EEPROM_MAP "Block 16" |
| 0x08A906 | `valve_cal_active` (u8, void) | high | returns 0x404970 (0 idle, 1 inlet, 2 MCI) |
| 0x086FA0 | `mci_cal_load` (void, void) | high | EEPROM block 16 +0..+33 -> 0x401D70 / 0x401D90; invalid -> 0x401DB0 b0 |
| 0x08B16C | `inlet_cal_load` (void, void) | high | EEPROM block 16 +34..+76 -> 0x401E70; invalid -> 0x401E9A[4] b0 (fault 0x150004 via 0x8B2D8) |
| 0x08ACD0 | `mci_cal_save` (void, void) | med | builds the 34-byte MCI record in 0x40493D from 0x401D70/0x401D90 and queues the write |
| 0x086724 | `cal_checksum` (u8, u8 *p, int n) | high | XOR of (byte + 1) |
| 0x08673C | `cal_checksum_ok` (bool, u8 *data, int n, u8 *chk) | high | chk[0] == sum and chk[1] == ~sum |
| 0x0871D0 | `usv_current_for_dp` (s16 mA, int c, s16 dp) | high | 0 when 0x401DB0 b0; interp(dp, P[c][8] 0x401D70, I[c][8] 0x401D90); beyond the ends, linear from the end slope, up to P7 + 20 bar; capped at 1800 mA; dp <= -130 bar -> 0x401DD0[c] = -13000. Callers write the USV setpoints 0x401D42[c] (0x768DC) |
| 0x08678A | `mci_cal_fault_check` (void, void) | high | 0x401DB0 b0 -> `fault_set`(0x088000) |
| 0x082108 | `supply_charge_state_update` (void, int c) | high | called for c = 0, 1 after `wheel_pressure_select`. Not `circuit_supply_fed`(c): state = 0. Fed, both inlet levels 0 and `pump_volume_frame`[c] >= 1: state = min(state + 1, 2). Fed, either inlet level >= 1: state = state >= 2 ? state - 1 : 0. Gates `supply_inflow_split` (state >= 2) |
| 0x082B0C | `wheel_dump_step_predict` (void, int w, int c) | high | called per wheel at the end of `hydraulic_model_step`. lvl = interp(PM[w], 0x41986, 0x4198E, n = 4); q = valve_flow(PM[w] - `lpa_pressure`[c], k_out[w/2], lvl * 8); p_after = interp(max(V[w] - q, 0), coded volume curve, axis 0x41B4E, n = 10) (inverse p-V); 0x401D00[w] = PM[w] - p_after, or 0 when `valve_cmd`[w] == -20 |
| 0x081EE0 | `wheel_volume_temp_comp` (void, int c, int w) | low | runs when 0x401A28 b1 is clear and PM[w] == 0; front/rear temp-comp tables 0x41AE4/0x41AFC and 0x41AF0/0x41B08 by coding byte 3/4; not fully traced |

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x004016DA | `wheel_volume` (s16[4]) | high | model volume V per wheel |
| 0x004016E2 | `wheel_pressure_model` (s16[4], 0.01 bar) | high | PM; overwritten with the measured pressure by `wheel_pressure_select` |
| 0x004016F2 | `lpa_volume` (s16[2]) | high | per circuit |
| 0x004016F6 | `lpa_pressure` (s16[2], 0.01 bar) | high | from the LPA curve |
| 0x004016FA | `pump_volume_frame` (s16[2]) | med | pump volume this frame (0x82824) |
| 0x004016FE | `lpa_inflow` (s16[2]) | high | Da + Db; also a 2-entry scratch (wheel a/b) for the supply inflow inside 0x826C0 |
| 0x00404994 | `driver_pressure` (s16, 0.01 bar) | high | driver-side pressure used by every inlet path; committed by `dispatch_slot00_driver_pressure` 0x8CE5E from master 0x401FF8 (the `master_pressure_get` value), else wheel-pressure mean 0x404996, else model 0x40171A |
| 0x00401A16 | `valve_cmd` (s8[4]) | high | > 0 = inlet opening * 2, < 0 = outlet opening * 2 |
| 0x00401A1C | `usv_close_level` (s8[2], 0..20) | med | 20 = isolated from the master side (inferred: USV closed) |
| 0x00401D00 | `dump_step_dp` (s16[4], 0.01 bar) | high | predicted pressure drop from one minimum (4 ms, `coa_dump_predict_level`) dump pulse (0x82B0C; deadband in `outlet_dump_time_calc`); `abs_p_dump_cap` = PM - this |
| 0x41986 | `coa_dump_predict_p_axis` (s16[4], 0.01 bar) | high | 0 / 3000 / 8000 / 12000; same in 335 |
| 0x4198E | `coa_dump_predict_level` (s16[4]) | high | outlet level for the prediction: 4 / 4 / 4 / 4; also the minimum outlet pulse in ms in `outlet_dump_time_calc` (flat 4 ms; the prediction uses open = level * 8 of 80 per frame) |
| 0x00401722 | `supply_charge_state` (u8[2], 0..2) | high | written only by 0x82108; read by `supply_inflow_split` |
| 0x00401C10 | `wheel_model_flags` (u8[4]) | med | b7 selects k_cross / 0x41ADC column 1 in 0x81C46 and the 0x8236C tables; cleared each frame by 0x81776 and no direct setter found (may be written through a pointer, or effectively always 0); b5 set at 0x81AE4 / 0x82EC8 |
| 0x41ADC | `coa_cross_flow_k` (s16[2][2]) | high | [axle][b7]: front 3231 / 673, rear 987 / 987; used as 2 * x / 7; same in 335 |
| 0x0DA5F4 | `cross_flow_soft_limit` (s16[2]) | high | 100 / 100; [0] flow a -> b, [1] b -> a |
| 0x00401715 | `wheel_dump_latch` (u8[4]) | high | 1 from the first dump frame until the inlet opens again; model pressure while set |
| 0x00401719 | `wheel_p_meas_valid` (u8) | high | b7 = fronts (and rears) valid, b6 = all four valid; rebuilt each frame by 0x82BC0 |
| 0x00401724 | `pump_recent` (u8[2]) | high | 5 while the pump delivers to circuit c, then counts down per frame |
| 0x004009AC | `inlet_base_current_dac` (u8[4]) | high | written by `inlet_base_current_set`; per-frame default fill for `inlet_out_dac` steps that nothing staged (`valve_output_frame_merge`). Only non-zero writers are in the manufacturing test protocol (0x76926..50 from frame bytes, `coa_wheel_gain_apply`); 0x770F8 zeroes it. In normal driving it is presumably 0 (RAM init not checked), so unstaged steps leave the inlet de-energised = open |
| 0x00401E70 | `inlet_cal` ({u8 chk, u8 ~chk, s16 f[4][5] mA}) | high | inlet-valve self-calibration (routine 0x28) loaded from EEPROM block 16 +34 (raw copy, no scaling); f[w] at 0x401E72 + 10 * w = hold current at the Δp points of axis 0xDA158; read by `inlet_current_for_dp` |
| 0x00401B98 | `inlet_current_profile` (s16[4][5], mA) | high | fast-loop half-frame inlet profile (5 steps = 5 ms). Written by `inlet_build_profile` 0x84A56 (mode 2) or `inlet_profile_fill` 0x84ECC (modes 1/4/8); uploaded by `inlet_profile_select_upload` 0x844E6 -> `inlet_profile_upload` into steps 0-4 (half 0) or 5-9 (half 1) of `inlet_out_dac` |
| 0x0DA158 | `inlet_cal_dp_axis` (s16[5], 0.01 bar) | high | {0, 2000, 5000, 9000, 14000} = 0 / 20 / 50 / 90 / 140 bar |
| 0x41A38 | `coa_inlet_gain_front` (curve[2], %) | high | COA+0xC0, 28 B per brake code (front code = 0x4031AA +3); `curve_interp_s16` record lo 70, hi 100, xs {100, 250, 500}; read only at x = 500 -> 91 % (both codes identical) |
| 0x41AA4 | `coa_inlet_gain_rear` (curve[2], %) | high | COA+0x12C, 28 B per brake code (rear code = 0x4031AA +4); same shape; at x = 500 -> 92 % |
| 0x00401D70 | `mci_cal_p` (s16[2][8], 0.01 bar) | high | USV characteristic pressure points per circuit |
| 0x00401D90 | `mci_cal_i` (s16[2][8], mA) | high | USV characteristic current points per circuit |
| 0x00404970 | `valve_cal_type` (u8) | high | active calibration routine |
| 0x00401D42 | `usv_current_set` (s16[2], mA) | med | USV current setpoints |
| 0x00401AA8 | `wheel_p_request` (struct[4], 8 bytes) | high | +0 u8 mode (0 none, 1 hold, 2 build, 4 dump; `inlet_mode_select`), +2 s16 rate (0.01 bar per 10 ms frame, copied each frame from the arbitrated request (*0x4019A8[w])+6 by 0x85D64; 9000 = full, unmetered build), +4 s16 outlet dump time owed (ms, <= 0; `outlet_dump_time_calc`), +6 s16 (cleared by `inlet_idle_reset`). Arbitrated request record *0x4019A8[w]: +0 type, +6 rate, +8 s16 target pressure (0.01 bar), +10 flags |
| 0x00401CF4 | `dump_ref_pressure` (s16[4], 0.01 bar) | high | pressure the issued dump time already covers; PM on dump entry / build / mode 0, target after each dump plan (`outlet_dump_time_calc`) |
| 0x00401CEC | `outlet_cmd_last` (s16[4], ms) | high | last outlet step count n (< 0 = outlet open \|n\| ms); 10 at mode 0 |
| 0x00401980 | `abs_active_any` (u8) | med | 1 when any of the control-active flags at 0x84340.. is set; cleared with 0x40199C[0..3] |
| 0x00401DB0 | `supply_mode_flags` (u8) | low | b6 = `supply_mode_active` |

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
| 0x07AEAA | `can_tx_19E_status_flags` (sig39) | high | ST_CLCTR bitfield: b0 ← 0x408DA2 b7 (front in ABS cycle), b1 TCS, b2 AYC, b3 DSC, b4 MSR (user-confirmed), b5 ← 0x408DA0 b1 (rear-only control); see FACTS ST_CLCTR |
| 0x07AD74 / 0x07AF52 / 0x07ACFA / 0x07AD6A / 0x07B05C | `can_tx_19E_abs_status` / `_dsc_status` / `_event_counter` / `_torque_intervention` / `_lvc_flag` | high (code) | 0x19E bytes 1–3; full decode in CAN_TX_TABLE_7846816A.md "Frame 0x19E" |
| 0x07AEFA / 0x07B018 / 0x07ADA2 | `can_tx_19E_bls_state` / `_feature5_status` / `_brake_applied` | high (code) | 0x19E byte 5 |
| 0x07AD2A | `can_tx_19E_driver_pressure` | high | 0x19E byte 6: 0x93F00(2) → 0x401FF8 ÷100, clamp 254, 0xFF on fault |
| 0x06FE92 | `bls_input_get` | high | GPIO 0xDE0018 b0 via 0x4009F4 (latched by 0x6FCAA); −1 when 0x4009F6 b4 clear or inhibit 0x4009BC b5 |
| 0x094538 | `bls_signal_get(sel,out)` | med-high | BLS value + validity (out[2] b7) + fault flags 0x90010/20/40/80 (out[3]) |
| 0x0B7ABC | `bls_plausibility_monitor` | high | BLS on with 0x401FFC > 5 bar / off with < 4 bar |
| 0x08D030 | `wheel_pressure_get(w,out)` | high | 0x40499A[w] value + valid b7 |
| 0x080C46 | `lamp_state_gather` | high | function states → 0x401662[0..7] (ABS 0x4049EC, DSC 0x4049EF, TCS 0xC7818, …) |
| 0x08D8C0 / 0x08D8F6 | `abs_function_state_update` / `_get` | high | 0x4049EC: 1 init/uncoded, 2 OK, 3 warning, 4 off |
| 0x08DA8E / 0x08DA88 | `dsc_function_state_update` / `_get` | med | 0x4049EF state 1–13 (1 failed, 8 init, 10–13 AYC active) |
| 0x0B567E | `fault_reaction_matrix` | high (structure) | rebuilds 0x402880 (u32) / 0x40288E (u16) each cycle from fault latches 0x402838[group] and the sensor words 0x402888 / 0x402890 / 0x40288C (copied to the stack at entry). Group A (0x40284C, DME CAN, & 0x2F) → 0x402880 b2–b5, 0x402882 b4/b6, 0x40288E b0/b2–b5 (FACTS "DSC driver mode"). **Sensor rule** (FACTS "Steering-sensor loss"): 0x402888 & 0x0D (steering / lateral / yaw invalid) → 0x402880 b2 (0xB596C); & 0x0C → 0x402881 b7 (0xB5AF2); the follow-on rule 0xB5BDE → 0xB5BFC then sets 0x402880 b2–b5 and 0x402882 b4. 0x40288E is not touched by this rule. Epilogue 0xB5D0A: stack word → 0x402880, half → 0x40288E, lamp half → `0xB5458` |
| 0x00402880 | `fault_reaction_word` (u32) | med | function-inhibit bits. Byte 0: b2 AYC/active-brake inhibit (aborts AYC 0xB5CD0; ABS hooks 0x46050/0x59BF2 via 0x408DC6 b5), b3–b5 read by AYC code and **inhibit the three TCS channels** (b4 → 0x403004 b7, b5 → 0x403048 b6, b3 → 0x402F84 b1), **b6/b7 ABS** (0x408DC6 b6/b3, 0x19E ABS status). Byte 2 b4 → DSC inhibit 0x400DF4 b6 (0x6A03A). Some bits are set every cycle (0x402880 b0/b1, 0x402881 b1/b2/b4–b6, 0x402882 b3/b5) |
| 0x0040288E | `fault_reaction_word2` (u16) | med | b6 → ABS function state 3/4 (0x8D8C0); b6/b7 → 0x19E ABS status; b2 forces the DSC function state (0x8DA8E) |
| 0x0040284C | `fault_latch[10]` (group A) | high | b3 = fault 0xA0008, reported by all three DME torque timeouts (D354–D356). **b6 = fault 0xA0040**, F-CAN 0x0C9 steering timeout (D373), set by 0xB484A. b8–b10 (& 0x700) and & 0xDF00 invalidate sensors in 0xB4A74 (sources not traced) |
| 0x0B97D4 | `steering_angle_init_monitor` | med | F-CAN 0x0C9 status 0x40164D; 0x40200A = 1 in state 2; faults 0x1200xx |
| 0x0C03EE | `lvc_condition_update` | high (code) | → 0x402BE8 (CAN 0x19E 3.2). LVC ≈ hill-start assist: LVC code reads HSA level f+9 (0xC0D44) and coded_feature(11)=HSA (0xC0D5E) |
| 0x0C3D56 | `lvc_ax_filter` | med | 0x402B5C = filtered long. accel (sensor or CAN) ×9.81 |
| 0x0CB708 | `tcs_torque_intervention_flag` | med | → 0x402F6E b5 |
| 0x0CF478 | `u8 coded_feature(u8 n)` | high | switch on n (≤ 38) over the three feature words 0xF677A / 0xF67DC / 0xF683E [f+6] (f+6 = row chosen by `coding_feature_row_select`); n=3 RPA (coding c3 b3), n=11 hill-start (c13 b6), n=5/13 set when c3 b2 = 0 |
| 0x045808 | `abs_state_aggregate` | high | per-cycle ABS state roll-up: clears then rebuilds 0x408DA2 b0/b5/b6/b7 from rec[0] b0 per wheel (front → b7, rear → b5); sole writer of 0x408DA0 b1 (0x45A62); called from 0x45EC4 |
| 0x04DEC4 | `abs_rear_decel_latch` (code block in `abs_event_classifier`) | high | sets 0x409049[4w] b3 for rears (0x4DF9E), snapshot 0x408EB2 → 0x408E72; released at 0x4ECA0 |
| 0x07B1F2 | `can_tx_1A0_vspeed` | high | **front wheels only** (records 0,1): Σ raw speed /20, or /10 with 1 front faulted, 0xFFF with 2; clamp 3000 (0.1 km/h) → 0x404720. Not vref |
| 0x07B0AC | `can_tx_1A0_ax` | high | 0x9390E(1) → 0x40200E (front-wheel accel mean, 0.01 g) ×4 → 0.0025 g/bit; 0x800 invalid |
| 0x07B06A | `can_tx_1A0_ay` | high | 0x93C96(1) → 0x4020DA (1 mg) ×803/2048 → 0.025 m/s²/bit; 0x800 on out[3] b5/b6 |
| 0x07B104 | `can_tx_1A0_yaw` | high | 0x943E4(1) → 0x4020F4 (1/20000 rad/s) ×939/16384 → 0.05 °/s/bit; 0x800 on out[3] b5/b6 |
| 0x07B172 | `can_tx_1A0_drive_direction` | high (code) | 0 standstill, 1 fwd, 2 rev, 3 unknown, 7 invalid; see CAN_TX_TABLE "Frame 0x1A0" |
| 0x07B0E0 | `can_tx_1A0_alive_counter` | high | 0x4010DC low nibble 0..14, +1 per frame |
| 0x09390E | `ax_signal_get(idx, out)` | med-high | idx0 accelerometer 0x4049FC, idx1 wheel-derived 0x40200E, idx2 0x4049FD (learned ax zero offset, 2 mg; not a filtered accel), idx3 0x404A00 (raw, 1 mg inferred). Callers: idx1 → 0x1A0 AccX; idx3 → 0x1A3 0.0/12 (0x7B906), 0x2B3 1.4/12 (0x7B7F4); idx2 → 0x1A3 1.4/12 (0x7B96E), 0x2B3 3.0/12 (0x7B83C); no caller passes idx0 |
| 0x093C96 | `ay_signal_get(idx, out)` | med | idx0 0x4020D6, idx1 0x4020DA (offset-corrected), idx2 0x402AB6, idx3 0x4020DC, idx4 0x402126, idx5 0x4020A6+2; `out` = `sensor_sig_t`. Copies the status byte of `abs_ay_get` 0x93AC0 into out[2], then out[3]: b5\|b6 ← 0x402890 b2, b4 ← 0x402888 b2 (steering-loss rule, **not** used by the 0x1A0 encoder), b3 ← 0x4029BE b2, plus 0x402884 b5 / cluster status 0x402E50 |
| 0x0943E4 | `yaw_signal_get(idx, out)` | med | idx0 0x4020F0, idx1 0x4020F4 (offset-corrected), idx2 0x402102, idx3 offset 0x4020F8; `out` = `sensor_sig_t`. out[2] copied from `abs_yaw_get` 0x94308; out[3]: b5\|b6 ← 0x402890 b3, b4 ← 0x402888 b3 (ignored by 0x1A0), b3 ← 0x4029BE b3, plus 0x402884 b7 / 0x402E50 |
| 0x08F2B0 | `ax_from_front_wheels` | high | 0x40200E = iir_blend_q8(mean rec+0x20 of unfaulted fronts clamp ±100, prev, 248) (α 1/32), 0x8000 if none; called from 0x8F028 |
| 0x0712FC | `iir_blend_q8(x, y_prev, k)` | high | returns s16 x + (y_prev − x)·k/256 (signed ÷256 toward 0); 1st-order IIR, k = weight on the old value. Callers: 0x8F31E (k 248), 0x65B96/0x65BA6 (k 255), 0x65BBE (k 233) |
| 0x08FEE8 | `ay_offset_apply` | med | 0x4020DA = 0x4020D6 − offset/100 |
| 0x0D381C | `vehicle_standstill_update` | med | 0x40328C b5 valid, b7 standstill (≥3 wheels with rec+0x1A ≤ 72, hard-coded `movi 72` at 0xD386C; the at-rest speed 2K/60000 must stay at or below it) |
| 0x0D3A1C | `vehicle_standstill_get(idx)` | high | idx0: −1 if 0x40328C b5 clear else b7; idx1: b4 → b6 |
| 0x06341A | `ayc_direction_state` | med | sets 0x400B09 b3 (reverse) + state 0x400BFE = 7, clears on forward |
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
| 0x084D42 | `supply_pressure(w)` | med-high | max(driver pressure 0x404994, own PM, partner PM), clamp [0,20000] |
| 0x0819FE | `coa_vol_to_pressure(w)` | high | PM 0x4016E2[w] = Vcurve⁻¹(V 0x4016DA[w]); model path only (dump phase / sensor fault) |
| 0x082BC0 | `wheel_pressure_select` | high | per wheel: PM 0x4016E2[w] = measured 0x402198[w] (store 0x82E9C) + V re-sync; model when 0x401A16[w]<0 or gate closed; sets 0x401719 b7/b6 = measured-valid |
| 0x06FD90 | `wheel_pressure_spi_sample(phase)` | high | fast QSPI CS5 burst (cmd tbl 0xD73C8) → 0x8FA00 |
| 0x08FA00 | `wheel_pressure_condition(phase,raw)` | high | offset 0x40218C[w]/16, ring 0x40202A, 4-avg → 0x402198+4w; fills 0x40206A |
| 0x091A50 | `wheel_pressure_get(w,out)` | high | measured wheel pressure + flags, r2 = valid; 16 control callers |
| 0x091A7C | `wheel_pressure_status_update` | med-high | 10 ms; calls 0x8FBEA/0x8FCE8; builds valid flags 0x40219A+4w |
| 0x08FBEA | `wheel_pressure_tracks_10ms` | med-high | primary 0x40207A/0x40208E, redundant 0x402082/0x402096 |
| 0x08FCE8 | `wheel_pressure_offset_learn` | med-high | zero offsets 0x40218C[w], 0x40209E[w] |
| 0x0946D0 | `wheel_pressure_diag_get(sel,w,out)` | med-high | KWP 0x21: value / redundant track / offsets |
| 0x08CDC4 | `wheel_pressure_mean` | high | mean of valid wheel pressures → 0x404996; master fallback |
| 0x08CFCC | `can_2b2_stage_wheel_pressure` | high | PM → 0x40499A+4w, flags b5 = measured, b7 = valid |
| 0x093E1C | `master_pressure_get(want,out)` | high | (same function as the row above) |
| 0x093F00 | `pressure_signal_get(sel,out)` | high | wrapper in the `*_signal_get` family: calls `master_pressure_get(1)` and copies its st b7..b3, so validity always follows the master sensor whatever `sel`. value: sel0 0x4020DE, sel1 0x4020E4, sel2 0x401FF8 (master, ÷100 bar on 0x19E byte 6), sel3/4 0x4020A6[+4/+6], else 0x8000 + st2 b5. st2 per the sensor_sig_t convention (monitor 0x40288D b3, hard fault 0x402890 b5) |
| 0x08F488 | `master_pressure_offset_learn` | med-high | offsets 0x4020AA/AC → 0x4020E2/E8 |
| 0x08CE8E | (tail of 0x8CE5E) | med | commits 0x404994: master 0x401FF8 → wheel mean 0x404996 → model 0x40171A |
| 0x0955EC | `ddsrpa_value_range_monitor` | med | uses CSW+0x18 (0x41E40=1562); faults 0xC0100.. |
| 0x0B433A | `nvm_fault_slot_commit` | high | FSF descriptor table 0xF57F8; NVM blocks 0x31/0x1B1/0x1C1 |
| 0x0B4140 | `fault_history_push` | high | 14-entry ring at 0x4028E4 |
| 0x0BAD80 | `speed_dependent_accumulator_monitor` | med | FSF 0xF57D6/DA; fault 0x124000 |
| 0x0812FA | `indicator_lamp_output_update` (slot 39) | high | 14-handler table 0xD9FB4 → lamp vector 0x40165E → TX 0x19E |
| 0x08119C | `lamp_vector_read` | high | 3-byte lamp status, read by the 0x19E getters |

Pressure model is **volume-domain** (not a simple integrator): V tracked per wheel via the COA p↔V curves, valve
flow Q = isqrt(dp)·open·k/4096, low-pressure accumulator per circuit. Tunable COA fields (k_in 957/421, k_out
755/465, k_cross, k_back 705, LPA tables, pump supply-store cap/fill rate, pump flow curve/filter, temp-comp) in the XDF. **Pressure unit 0.01 bar**
(pinned by CAN 0x2B2/0x19E: internal value ÷100 = integer bar; LPA 1.3–5.0 bar, pedal 8 bar, clamp 200 bar). **CSW** 0x41E28: only +0x18=1562 is
live (DDS/RPA reference); rest vestigial. **VAR** 0x41D00: empty placeholder (payload 0). **FSF** 0xF57C4: fault-NVM
slot descriptors + a speed monitor + mask tables; body byte-identical to the 1M.

## ABS controller core — pressure pipeline + decision layer (cycle 6)

ABS/vref RAM shifted +0x24; code shift −0x220/−0x200. Full work in `analysis/agents/m3abscore/`, `m3absslip/`.

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0559CC | `abs_pm_snapshot` | high | PM 0x408F2A[w] = wheel pressure 0x4016E2[ch] (measured; model in dump/fault); also `abs_p_dump_cap` 0x40901C[w] = max(0, 0x4016E2[w] − 0x401D00[w]); dispatcher-direct after model step |
| 0x045F54 | `abs_pressure_frame` | high | per-wheel slip update, phase dispatch, dump-stage coord, decision chain |
| 0x04D270 | `abs_event_classifier` | med-high | builds the per-wheel threshold scratch, then → abs_phase_sm |
| 0x0504D0 | `abs_wheel_phase_dispatch` | high | switch on rec[0] → 5 phase handlers |
| 0x050580 | `abs_phase_armed_handler` (0x80) | high | rate 8000; hold request → rate 0. Rear while a wheel cycles: CMD = min(PM + 5 bar, arbiter output 0x408F6E), rate 500, **100 when decision code = 1 or 0x408E5F b7**; front lateral pre-limit on 0x409049 b0 (curve 0x403B4). `agents/abs_full/08_phase_control.md` §5.5 |
| 0x050894 | `abs_phase_precontrol_handler` (0xC0) | high | rate 0, CMD = PM; creep by `abs_precontrol_build_rate` after 2 frames or when re-accelerating (≤ 25000); CMD ≤ arbiter + 5 bar; latch branches use ROM curve 0xD6AFC. §5.5 |
| 0x057DA4 | `abs_precontrol_build_rate` | high | pre-control: curve 0x403E6(PM) 8 → 3 bar/frame, front rec+6 rules (200 / 0), rear code-1 slip rule (150 / 0); else curve 0x409E4 front / 0x40A00 rear |
| 0x059C6C | `abs_mode_update` | high | dispatcher slot 34. Writes `abs_mode_flags` 0x408DA1 bits 7:5 = 1 (standstill counter 0x408EC0 reaches 30), 2, 3 (both fronts' low-speed flag 0x409056 b0); 0x408E68 b0 = counter ≥ 30; limit 0x408EC4 = max(vref − 0x408E5C, 0.65·vref, 15 km/h). `08_phase_control.md` §6.1 |
| 0x045556 | `abs_mode5_check` | med | mode = 5 when 0x408E5C ≥ 1000 and 0x408DA2 b6 clear |
| 0x04AAA8 | `abs_phase_dump_handler` (0x21) | high | → 0x55F06 target; events bit31 re-accel / bit30 |
| 0x04CA3C | `abs_phase_hold_handler` (0x09) | high | entry 0x57200; TGT = PMMIN + headroom·n/16 |
| 0x04B680 | `abs_phase_reapply_handler` (0x11/0x15) | high | step code → 0x581BA; PM+1000 end clamp |
| 0x055F06 | `abs_dump_entry_target` | high | R = pct(LOCKEST)·LOCKEST/100 + A + B (+C rear), scaled; 0x408F94 = max(LOCKEST − R, 0); CMD = min(that, cap); RAMP=−8000. Decode: `agents/abs_full/08_phase_control.md` §5.2 |
| 0x0562DC | `abs_dump_continue` | high | stepped dump: step period vs wait counter 0x408FB4, early/scheduled steps, CMD −= D. `08_phase_control.md` §5.3 |
| 0x056C60 | `abs_dump_step_period` | high | step period 0x408DCC from cal table 0x40BF0 by slip; sets 0x408DD4 b30 on deep slip |
| 0x056728 | `abs_dump_step_amount` | high | step size D → 0x409136[10w]; early (b26) vs scheduled formulas |
| 0x056EDC | `abs_dump_step_scale` | med-high | scales D by slip vs rec+0x32 and decel vs cycle peak; min 2 bar |
| 0x04B160 | `abs_dump_frame_flags` | high | 0x408DD4 b31 re-accel / b30 keep dumping / b28-27 cornering |
| 0x04B012 | `abs_dump_entry_reset` | high | dump entry: zero 0x408FAC/0x408FB4/dump count; 0x40908E = 0x409096 = 1 |
| 0x04ADD4 | `abs_dump_entry_flags` | med | dump entry flag bookkeeping |
| 0x057024 | `abs_dump_forced_target` | high | forced-dump (0x40903A b5) entry target: LOCKEST − F |
| 0x053940 | `abs_dump_hold_stage_ctrl` | med | front-pair controller; applies staged target 0x4091AE to one front |
| 0x055B44 | `abs_dump_r_decel_rate` | high | A term → 0x409130[10w]; thresholds cal 0x40B08..0x40B0E on 0x408DD0 = accel − rec+0x24; −1000..+2·abs(d) |
| 0x055CE8 | `abs_dump_r_wheel_decel` | high | B term → 0x409132[10w]; F·g·s·abs(accel)/50000 clamp 100..1200; curves 0x40BCA/0x40B70/0x40B92/0x40BAE |
| 0x056996 | `abs_dump_r_rear_slip` | high | C term (rears, code ≠ 1): own/partner slip, curve 0xD6C4A(LOCKEST) |
| 0x04B09C | `abs_dump_frame_inputs` | med | 0x408DD0 = rec+0x20 − rec+0x24, 0x408DCE = accel/16 (dump-handler entry) |
| 0x04FB44 | `abs_decel_onset_latch` | med | 0x40909E[w] = rec+0x20 − rec+0x24 (latched outside hold; zeroed in hold) |
| 0x057200 | `abs_hold_entry_sync` | high | PM=CMD=SNAP=X; headroom 0x408FA4 |
| 0x05898C | `abs_slip_and_lockon_update` | high | slip 0x408F84; lock-onset latch 0x408FBC |
| 0x05862C | `abs_lockon_pressure_estimator` | high | writes LOCKEST 0x408FD0 (min-selected with PM, clamp 25000) |
| 0x044502 / 0x0447C4 | `abs_frame_entry_a/b` | high | dispatcher slots 12/13 |
| 0x0443F4 | `abs_apply_ramp` (id 19) | high | CMD +400/frame → 25000; vref gate 0x442AC = 4 km/h |
| 0x046B6… →0x0446B6 | `abs_emit_pressure_request` | high | arbiter id 1 / 11-rear, start SNAP, target UP, rate RAMP |
| 0x0584CC | `abs_cmd_slew_limiter` | med-high | CMD=min(CMD,TGT); RAMP=min(RAMP, CMD−SNAP) |
| 0x05DC08 | `abs_arbiter_output_snapshot` | high | 0x408F6E[w] = arbiter_channel_output 0x836C8(ch) |
| 0x051B54 | `abs_decision_classify` | high | writes code 0x408DDE (1/32/64/128/1024/16). Default 1 if both rears only armed, else 64; straight shortcut → 1 (0x51E46); lateral-curve code 32 / code 1 by driver pressure (0x51C2A, 0x51E6A, 0x51F32) — see `abs_decision_t` |
| 0x05884A | `abs_cycle_ref_update` | high | dump start: `abs_p_ref` = 0x408FE8 = `abs_p_lock`; lateral side-share 0x409008; later frames scale 0x408FE8 |
| 0x058B30 | `abs_decision_resolve` | high | 64→16, 128→256/2, 16→8 |
| 0x058FF4 | `abs_decision_pressure_exec` | high | switch on code 2/8/32/256 |
| 0x054D9A | `abs_pair_logic` | high | partner-in-slip test (curve 0x40DB6); writes 32/1024/16/2 |
| 0x05184C | `abs_rear_lead_select` | med-high | rear select-low; DDE+10 index fields |
| 0x052380 | `abs_gross_slip_threshold` | high | **real arming threshold** curve 0xD6CE2 (≈11 % vref) |
| 0x04FC3C | `abs_phase_sm` | high | 0x80→0x21→0x09→0x11 transitions verified on M3; full table `agents/abs_full/08_phase_control.md` §4 |
| 0x050FF4 | `vref_fall_from_ax` | med-high | vref fall step = max(−44, (d − m)·360/1000), d from ax `0x408E80` (or `0x408DAF` in some non-regime cases), margin m 10–40; maintains shadow 0x408E7E. Called only from `vref_update` 0x451F2 via route 2 (0x45142–0x451F2): needs `0x408E1C` b7, `0x408E6D` b7+b4+b5+b6 (lat, yaw, steering, pressure), \|lat\| < 30, `0x408DA1 & 0xE0` = 0, no `0x400B09` b6, and `0x408DB5` b7 or (ax > −0.3 g, `0x408E6A` ≥ 21, regime). Without the SZL vref never uses ax (`agents/abs_full/10_vref_and_ax.md` §2.5, §3) |
| 0x05D82C | `abs_sensor_gather` | med-high | writes ax 0x408E80 (default = 0x408DAF, else getter 0x93828); sets 0x408E6D b3 from the ax getter and clears it again at 0x5D914 in the same pass; also the lat/yaw latches 0x408ECA/ECC/ECE. Builds `abs_sensor_valid` 0x408E6D; full map in the "Sensor validity" section |
| 0x093828 | `ax_get(valid, out)` | med-high | returns 0x4049FC + status; present flag ROM 0xF6756[9]; faults 0x404A2E b7:6, 0x402888 b1 |
| 0x092B98 / 0x092BBC / 0x092C26 | `ax_raw_scale` / `ax_filter` / `ax_offset_learn` | med | cluster idx5 × cal 0x40F2C → 0x404A00 (1 mg, inferred) → LP 0x404A02 (DC gain 10 → 0.1 mg) → (−offset 0x404A04)/100 clamp ±127 → 0x4049FC; offset learned vs 0x408DAF when no controller active (partly traced). Learner state 0x4049FD (s8, 2 mg, steps of at most ±5, clamp ±119) ×20 → 0x404A04 |

Key ABS RAM: PM 0x408F2A, CMD 0x408F22, LOCKEST 0x408FD0, PMMIN 0x408FC4, dump reduction R 0x409134+10w,
request flags 0x408D9C (bit7 dump/hold → id 1/11, bit4 apply → id 19), decision code 0x408DDE.

Per-wheel ABS pressure arrays. Unit 0.01 bar; index = wheel idx (rec+0x2A, 0..3); every access is
`ld.h`/`st.h` at base + 2·idx with `sexth` on load, so each array is 4 × s16 = 8 bytes.

| Address | Name | Type | Size | Conf | Evidence |
|---|---|---|---|---|---|
| 0x408F22 | `abs_p_cmd` | s16[4] | 8 | high | commanded pressure (CMD); internal, not sent to the arbiter directly |
| 0x408F2A | `abs_p_wheel` | s16[4] | 8 | high | wheel pressure PM (measured; model in dump/fault) via `abs_pm_snapshot` 0x559CC |
| 0x408F4A | `abs_p_start` | s16[4] | 8 | high | arbiter `start` arg (0x446B6); = measured pressure at hold entry (0x57200) |
| 0x408F52 | `abs_p_cmd_max` | s16[4] | 8 | high | CMD ceiling; hold sets PMMIN + headroom·n/16 (0x4CA3C), reapply steps raise it (0x581BA), clamp 0x584CC |
| 0x408F62 | `abs_p_req_target` | s16[4] | 8 | high | arbiter `target` arg (0x446B6) |
| 0x408FC4 | `abs_p_min` | s16[4] | 8 | high | cycle minimum (PMMIN); min(PM) during dump, = PM at hold entry |
| 0x408F5A | `abs_p_req_rate` | s16[4] | 8 | high | arbiter `rate` arg (0x446B6); −8000 (0xE0C0) dump, 0 hold, >0 build, 9000 = full build; valve mode = sign(rate) (0x84460) |
| 0x408FD0 | `abs_p_lock` | s16[4] | 8 | high | lock-onset pressure (LOCKEST); = min(PM, 20000) at reapply step 0x5820E, estimator 0x5862C; dump target reference |
| 0x408FA4 | `abs_p_headroom` | s16[4] | 8 | high | max(500, LOCKEST − PMMIN) at hold entry (0x5732A); scales hold/reapply ceiling steps |
| 0x408F94 | `abs_p_dump_target` | s16[4] | 8 | high | max(0, LOCKEST − R) at dump entry (0x5617A) |
| 0x40901C | `abs_p_dump_cap` | s16[4] | 8 | high | max(0, 0x4016E2[w] − 0x401D00[w]), written every frame by `abs_pm_snapshot` 0x55A22; dump CMD = min(target, cap) (0x56192, 0x4AC1A) |
| 0x408F3A | `abs_p_passthru` | s16[4] | 8 | med | CMD and CMD_max set to this when the wheel has no ABS request (0x408D9C b7 clear, 0x4479C); writer not traced |
| 0x408FF0 | `abs_p_ref` | s16[4] | 8 | high | lock pressure (`abs_p_lock`) snapshotted at the start of each dump (from armed or reapply) by `abs_cycle_ref_update` 0x5884A; also copied to 0x408FE8 |
| 0x408F6A | `abs_p_rear_cmd_prev` | s16[2] | 4 | high | rears only, [0] = wheel 2, [1] = wheel 3; CMD snapshot at `abs_decision_resolve` entry (0x58BDE); read as 0x408F66 + 2·idx in 0x5173C |

Related: 0x408FE8 s16[4] = `abs_p_ref` × (current lateral side-share / share at dump start), both shares from
0x409008[w] = clamp(50 ± lat/2, 10, 90) (50 when lateral is invalid), capped at 25000 (0x5884A). 0x409018[w] b5 =
the new `abs_p_ref` is within max(ref/16, 4 bar) of the previous one (0 on a first cycle). 0x401D00 s16[4] (hydraulic RAM) is the margin subtracted to form `abs_p_dump_cap`;
writer not traced.

### ABS dump parameters

Everything that sizes or paces a dump. Decode: `agents/abs_full/08_phase_control.md` §5.2 (entry), §5.3 (later
frames). Values byte-read from the image; curves evaluated with `curve_interp_s16` (truncate toward zero). Curve
layout `[lo, hi, n, xs(n−1), cs(n), ks(n)]` s16; patching `hi` (address + 2) clamps a curve's output.
Units: pressure 0.01 bar, accel 0.01 g, speed 0.01 km/h, frame 10 ms. "a" = wheel accel `rec+0x20`;
"d" = `rec+0x20` − `rec+0x24` (`0x408DD0`, negative while decel is still building). "Lit" = code literal-pool word
(patchable, but check every `lrw` that shares it).

**Entry dump** (`abs_dump_entry_target` 0x55F06): R = (R0 + A + B [+ C rear]) × low-pressure × onset; target =
`abs_p_lock` − R.

| Address | Name | Type | Unit | Stock | Conf | Role |
|---|---|---|---|---|---|---|
| 0x40994 | `abs_dump_r0_pct_front` | curve n6 | x 0.01 bar (`abs_p_lock`) → % | 16 @10 bar, 11 @17.5–30, 10 @40, 8 @≥50 | high | R0 = pct · `abs_p_lock` / 100, fronts |
| 0x409BC | `abs_dump_r0_pct_rear` | curve n6 | x 0.01 bar → % | 16 @10, 13 @17.5–20, 11 @30, 10 @40–50, 9 @60, 6 @≥66 | high | R0, rears |
| 0x40B08 / 0x40B0A / 0x40B0C / 0x40B0E | `abs_dump_a_d_c1` / `_c2` / `_c3` / `_c4` | s16 | 0.01 g (d) | −140 / −90 / −40 / −210 | high | A-term bands on d; c4 gates the +gain·\|d\| add (XDF "ABS decel ladder" [0..3]) |
| 0x55E68 / 0x55E6C / 0x55E70 | `abs_dump_a_accel_a1` / `_a2` / `_a3` | Lit s32 | 0.01 g (a) | −300 / −220 / −170 | high | A-term accel limits; halved < 60 km/h, quartered < 20 km/h |
| 0x55FA0 / 0x55FA4 / 0x55FA8 | `abs_dump_a_ease_1000` / `_650` / `_400` | Lit s32 | 0.01 bar | −1000 / −650 / −400 | high | A when d ≥ 0 (decel easing): smaller dump for d > 100 / ≤ 100 / ≤ 50 |
| 0x55E7C | `abs_dump_a_mid_150` | Lit s32 | 0.01 bar | −150 | high | A for c1 < d < 0 (−300 / −500 deeper bands are code) |
| 0x40B6E | `abs_dump_a_d_gain` | s16 | ×0.1 bar/g | 20 (= 2 bar per g of d) | high | A += −gain · d / 10 when d < c4 |
| 0x560B0 | `abs_dump_b_divisor` | Lit s32 | – | 50000 | high | B = F·g·s·\|a\| / this, clamp 1–12 bar; stock 1.2 bar/g at F 60. Read only by the three B formulas (0x55E40/0x55E9E/0x55EBE) |
| 0x560B4 | `abs_dump_b_v50` | Lit s32 | 0.01 km/h | 5000 | high | F speed split (50 km/h) |
| 0x55E64 | `abs_dump_v60` | Lit s32 | 0.01 km/h | 6000 | high | 60 km/h split, **shared** by A (0x55B54/0x55C88) and B (0x55DC2) |
| 0x40BE6 / 0x40BE8 | `abs_dump_b_gs_vmax` / `_vmin` | s16 | 0.01 km/h | 6000 / 2000 | high | g and s adjustments only for 20 < vref ≤ 60 km/h |
| 0x40BCA | `abs_dump_b_g_vref` | curve n4 | x 0.01 km/h → % added to g | 90 @0, 30 @20, 10 @40, 1 @≥60 km/h | high | g = 100 + this (low-speed boost) |
| 0x40B70 | `abs_dump_b_g_plock` | curve n5 | x 0.01 bar → % added to g | −40 @0, −21 @40, −2 @80, +40 @≥120 bar | high | added to g with flag P only |
| 0x40B92 | `abs_dump_b_s_slip` | curve n4 | x slip % → 0.1× added to s | 0 @<13 %, 10 @20, 15 @30, 25 @50 | high | s = 10 + this (s/10 = multiplier) |
| 0x40BAE | `abs_dump_b_s_vwheel` | curve n4 | x 0.01 km/h → 0.1× added to s | 40 @0, 16 @20, 10 @≥50 km/h | high | added to s with flag P only |
| 0x55FB0 | `abs_dump_flag_p_decel` | Lit s32 | 0.01 g | −130 | high | flag P: other front `rec+0x24` < this |
| 0xD6C60 | `abs_dump_lowp_scale` | curve n3 (ROM) | x 0.01 bar (PM) → % | 200 @≤10, 167 @12, 134 @14, 100 @≥16 bar | high | R × this/100 under the low-pressure flags |
| 0xD6C4A | `abs_dump_c_plock_permille` | curve n3 (ROM) | x 0.01 bar → ‰ | 600 @0, 799 @40, 998 @≥80 bar | high | rear C term own-slip part × this/1000 |
| 0x40B4C | `abs_dump_onset_k1` | curve n5 | x 0.01 g (−`0x40909E`) → % | 100 @0, 115 @2 g, 139 @3, 152 @6, 169 @10 g | high | R × k1/100 (b1/b4 paths) or k1/143 (default) when a < −2 g |
| 0x40B14 | `abs_dump_onset_k2` | curve n5 | x 0.01 g (−a) → % | 0 @≤4 g, 14 @5, 40 @8, 44 @9.6, 50 @≥12 g | high | R × (1 + k2/100) or (1 + k2/133); hi at 0x40B16 = 150 |

**Later dump frames** (`abs_dump_continue` 0x562DC, `abs_dump_step_period` 0x56C60, `abs_dump_step_amount`
0x56728, `abs_dump_step_scale` 0x56EDC).

| Address | Name | Type | Unit | Stock | Conf | Role |
|---|---|---|---|---|---|---|
| 0x40BF0 | `abs_dump_step_period_tbl` | s16[7] | frames | 178, 5, 3, 2, 2, 1, 0 | high | step period by slip band (178 = no scheduled step, 0 = continuous) |
| 0x40B48 | `abs_dump_early_wait_front` | s16 | frames | 4 | high | early-step wait base W (+m from the ratio bands below) |
| 0x40B4A | `abs_dump_early_wait_rear` | s16 | frames | 4 | high | rear early-step wait |
| 0x40B36 / 0x40B38 / 0x40B3A / 0x40B3C / 0x40B3E / 0x40B40 | `abs_dump_decel_ratio_b1` / `_b2` / `_b3` / `_b4` / `_b5` / `_b6` | s16 | % of release-end decel | 120 / 100 / 90 / 50 / 30 / 20 | high | W adjust −2/−1/−1/+2/+3/+4 |
| 0x40BEA / 0x40BEC / 0x40BEE | `abs_dump_slip_ratio_b1` / `_b2` / `_b3` | s16 | % of release-end slip | 160 / 140 / 120 | high | W adjust −2/−1/−1 when decel ratio is 50–90 % |
| 0x40B10 | `abs_dump_step_d_add1` | s16 | 0.01 g (d) | −350 | high | step D += 2·\|d\| below this (XDF ladder [4]) |
| 0x40B12 | `abs_dump_step_d_add2` | s16 | 0.01 g (d) | −490 | high | step D += \|d\| more below this (XDF ladder [5]) |
| 0xD6C8C | `abs_dump_step_rear_pair_slip` | curve n4 (ROM) | x 0.01 g (vehicle decel) → 0.01 km/h | 200 to −0.4 g, 280 @−0.6, 440 @−0.8, 600 @≤−1.0 g | high | coupled rears: D += partner slip − this |
| 0x40AE4 | `abs_dump_forced_min_ms` | s16 | ms (inferred; value ÷ 10 = frames) | 50 | med | forced-dump flag held ≥ 5 frames |

Step-size constants are code (`movi`/`bseti`), not pool words: early front D = min(2·\|a\|, 12 bar) or
max(1.5·\|a\|, 2s/3), floor 4 bar; scheduled D = max(10 bar, 2s/5) (front `rec+0x16` b7: max(12 bar, s/2)), 8 bar
in the listed slow cases; `abs_dump_step_scale` floor 2 bar.

**Forced dump** (`abs_dump_forced_target` 0x57024) and **front staged dump** (`abs_dump_hold_stage_ctrl` 0x53940,
`abs_dump_stage` 0x5424C, 0x543FC).

| Address | Name | Type | Unit | Stock | Conf | Role |
|---|---|---|---|---|---|---|
| 0xD6C76 | `abs_dump_forced_front_vscale` | curve n3 (ROM) | x 0.01 km/h → % | 130 @0, 92 @50, 68 @100, 42 @≥150 km/h | high | front forced F × this/100 |
| 0x40B46 | `abs_dump_forced_rear_base` | s16 | 0.01 bar | 800 | high | rear forced F base |
| 0x40B04 | `abs_dump_forced_rear_add_max` | s16 | 0.01 bar | 700 | high | cap on the rear pressure-difference add |
| 0x40E9A | `abs_front_stage_enable` | s16 | flag | 1 | high | `abs_dump_hold_stage_ctrl` runs when ≠ 0 |
| 0x40E94 / 0x40E9C | `abs_front_stage_set_a_enable` / `_set_b_enable` | s16 | flag | 1 / 1 | high | threshold sets A / B |
| 0x40E5E / 0x40E60 / 0x40E62 | `abs_front_stage_a_t1` / `_t2` / `_t3` | s16 | peak byte a/16 (×0.16 g) | −62 / −78 / −94 (≈ −9.9 / −12.5 / −15 g) | high | stage thresholds on the dumping front's peak decel |
| 0x40E9E / 0x40EA0 / 0x40EA2 | `abs_front_stage_b_t1` / `_t2` / `_t3` | s16 | a/16 | −25 / −44 / −62 | high | set B thresholds (`0x400A95` b1) |
| 0x40E64 / 0x40E66 / 0x40E68 | `abs_front_stage_r1` / `_r2` / `_r3` | s16 | 0.01 bar | 1000 / 1500 / 2000 | high | other front pulled to lock − R (floor 20 bar) |
| 0x40E96 | `abs_front_stage2_enable` | s16 | flag | 1 | high | 0x543FC runs when ≠ 0 |
| 0xD6D18 | `abs_front_stage2_vref` | curve n3 (ROM) | x 0.01 km/h → ? | 3000 @≤70, 4000 @100, ≈ 7960 @200 km/h | med | 0x543FC second writer of `0x4091AE`; output unit not decoded |
| 0x40E6A / 0x40E6C | `abs_front_stage2_k1` / `_k2` | s16 | ? | 10 / 40 | low | read by 0x543FC; not decoded |

Related, already listed: `dump_step_dp` 0x401D00 (predicted drop from one minimum 4 ms pulse; cap), `coa_dump_predict_p_axis` 0x41986 /
`coa_dump_predict_level` 0x4198E. Reapply parameters: next subsection (0x40D5E / 0x40D60 are build **rates**, not step
sizes).

### ABS reapply

Decode in `agents/abs_full/08_phase_control.md` §5.4. Units as above; "rate" = `abs_p_req_rate`, 0.01 bar per frame.
In one line: each step raises the ceiling `abs_p_cmd_max` by a fraction of the hold headroom, CMD ramps to it at the
build rate, then waits a fixed number of frames; after too many steps without a new lock it switches to a continuous
ramp.

**Functions**

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x04B680 | `abs_phase_reapply_handler` (void) | high | per frame: `abs_reapply_entry_flags`, `abs_reapply_frame_prep`, `abs_reapply_conditions`; counters 0x408F76/7A/7E; `abs_reapply_period_select`; step limit N_max and fast rate (below); `abs_reapply_step(n, fast_rate)`; overspeed (phase b2, 0x15) tail: CMD = CMD_max = PM + 10 bar, rate 9000 |
| 0x04B970 | `abs_reapply_entry_flags` (void) | med | only when the previous phase was not reapply: clears per-wheel flags; rec+9 b1 = slip > 2.5 km/h |
| 0x04B9E2 | `abs_reapply_entry_init` (void) | high | first reapply frame: zero 0x408F7E/76/7A; `abs_reapply_flags_w1_clear`; `ctl` bits 3:0 = 0, `flags` b8 = 1, `ceil_saved` = `abs_p_cmd_max`; arbiter mode bits 0x408EFD; misc flag clears |
| 0x04BB52 | `abs_reapply_frame_prep` (void) | high | scratch.n = `ctl`[15:11]; scratch.period = 0; sub-phase 0x408FCC = 0x80; calls `abs_reapply_entry_init` when rec+1 b4 is clear |
| 0x04BC84 | `abs_reapply_conditions` (void) | med | builds `scratch.cond` / `scratch.cond2` (layout below). b4 "re-decelerating": rec+0x24 < T, T = −1.40 g (−1.30 g at ≤ 70 bar filtered pressure) + 0.04 g·n, capped at −1.30 / −1.25 / −1.20 g, with vref ≤ 30 km/h or rec+6 < 0; or rec+0x24 − vehicle decel < −0.2 g (≤ 30 km/h) / −0.3 g (0x408DEF b5) |
| 0x04C0BC | `abs_reapply_period_select` (void) | high | scratch.period = ROM 0xD6CF8[n] (0, then 7); overrides: 21 (filtered-pressure flag), 0 (several), 2 (cond & 0x21), cap 20, 0xFF when cond b4, min with 0x400A94 (rec+0x18 b2); sets `flags` b11 for a wheel still lagging vref (cal 0x40D4A / 0x40D4C / 0x40D58) |
| 0x0581BA | `abs_reapply_step` (void, u8 n, s16 fast_rate) | high | rate from `abs_reapply_special_rate` or `abs_reapply_rate_select`; fast_rate ≠ 0: `abs_p_lock` = min(PM, 200 bar), no wait; sub-stage 1 (wait): when 0x408F7E ≥ period, start a step (`abs_p_cmd_max` = min(200 bar, max(0x401C14[w], CMD + `abs_reapply_step_amount`(n)))); else, with cond b4, freeze (CMD = min(CMD_max, PM) when n ≥ 3, else CMD_max; rate 0); sub-stage 2 (build): `abs_reapply_ramp_to_ceiling`, stopped by cond b4 or a re-decelerating wheel (n < 2 and rec+0x20 < −2 g, or < −3 g with slip > 1 km/h). Sub-phase bytes 0x81–0x87 |
| 0x057E48 | `abs_reapply_ramp_to_ceiling` (void, s16 fast_rate) | high | CMD += rate (fast: also CMD_max += rate, ≤ 200 bar); on reaching CMD_max: CMD = CMD_max, sub-stage 1, n += 1 (≤ 30; reset to 3 under 0x40905E b0 + 0x408E68 b4) |
| 0x057F62 | `abs_reapply_step_amount` (s16, u8 n) | high | D = H·(16 − m)/32 while n ≤ (m > 8), else H·(16 − m)/(48 − m); H = `abs_p_headroom`, m = `ctl`[7:4]. /24 variant, ½ and /44 for long events (`abs_cycle_count` ≥ 16), ÷3 / ÷4 when `abs_reapply_decel_count` ≥ 2 / ≥ 4 (then ≥ 2 bar), ×2 with cal 0x40D54, + `abs_reapply_step_boost`; fronts ≤ 7 bar in one flagged case. Record 0x40912E[10w] = D, +2 = D + boost |
| 0x04C368 | `abs_reapply_step_boost` (s16) | med | 0 unless n > N0 and `abs_reapply_decel_count` < 2 and one of: CMD > max(1.1 × `abs_p_ref` [cal 0x40D5A], `abs_p_ref` + 3 bar); front, driver pressure > 1.5 × `abs_p_ref`; or a flag set. Boost = (n − N0) × 2.5 bar (front) or 1.7 bar (rear, or front with 0x408E1A b1). N0 = cal 0x40D52 (5) − wheels not in ABS (floor 3), −3 when slow/hard braking, − (peak − 75)/30, + ax terms |
| 0x04B3C8 | `abs_reapply_special_rate` (u16) | med | non-zero → continuous build at that rate instead of steps: 200 (partner forced-dump flags), 250 (+70 below −0.6 g) after a long rear coupling, 800 (n ≥ 12, < −0.5 g), 100; may set scratch.period from ROM 0xD6B6E; rear cornering branch with curve 0x403B4(\|lat\|) |
| 0x057952 | `abs_reapply_rate_select` (void, s16 fast_rate) | high | rate = cal 0x40D5E (front 300) / 0x40D60 (rear 500); front ≤ 200 when `abs_p_ref` < 30 bar and rec+0x10 [7:5] < 3; fast_rate ≠ 0 overrides; first-step tweaks (H/20 or H/30, peak byte), clamp 150..500; rate ≥ 0x401C24[w] unless `flags` b9; 100 with 0x409060 b4 and a small peak |
| 0x058550 | `abs_reapply_flags_w1_clear` (void) | high | `flags` &= ~(b10 \| b11) |
| 0x04CF76 | `abs_hold_set_reapply_frac` (void) | high | hold: `ctl`[7:4] = cal 0x40D62 (front) / 0x40D64 (rear) & 15 |
| 0x0584CC | `abs_cmd_slew_limiter` | high | rate > 0 and CMD ≠ start: CMD ≥ CMD_max → CMD = CMD_max; rate = min(rate, CMD − start) |

**RAM**

| Address | Name | Type | Conf | Evidence |
|---|---|---|---|---|
| 0x408F02 | `abs_reapply_state` | `abs_reapply_state_t[4]`, 6 B each (index ·6) | high | layout below |
| 0x408DD8 | `abs_reapply_scratch` | `abs_reapply_scratch_t`, current wheel only | high | rebuilt every reapply frame |
| 0x408F76 | `abs_reapply_frames` | u8[4] | high | +1 per reapply frame; 0 at entry |
| 0x408F7A | `abs_reapply_step_frames` | u8[4] | high | +1 per frame; 0 at each step start; > 100 clears arbiter mode b4 |
| 0x408F7E | `abs_reapply_wait_frames` | u8[4] | high | frames since the last step (compared with scratch.period); 0xFF = do not count |
| 0x409014 | `abs_reapply_decel_count` | u8[4] | med | +1 per frame with rec+6 < 0 (wheel decelerating) in armed / reapply, −2 or −10 decay; 0 at hold entry (0x4CCC0) |
| 0x408EF7 | `abs_cycle_count` | u8[4] | low | gates on ≥ 15 / ≥ 16 in dump and reapply; 0 after ≥ 50 dump frames (0x4AD26) and at 0x51216 |
| 0x401C14 | – | s16[4] | low | floor for a new reapply ceiling; written in the valve stage (0x8465A, 0x85642, 0x85872); role open |
| 0x401C24 | – | s16[4] | low | floor for the reapply rate; written in the valve stage (0x8583C, 0x85D3C) |

```c
typedef struct {            /* 0x408F02 + 6*w */
    u16 ctl;                /* [15:11] n, steps taken (0..31)
                               [10:8]  sub-stage: 1 wait, 2 build
                               [7:4]   m, hold fraction /16 (cal 0x40D62/0x40D64 = 10)
                               [3]     freeze done this step
                               [2:0]   cleared at entry and at each step */
    u16 flags;              /* b11 wheel still lagging vref (0x4C0BC); b10,b11 cleared by 0x58550;
                               b9 skip rate floor 0x401C24; b8 set at entry, cleared once n >= 4;
                               b6/b7 set in 0x4C368; b5 partner flag (0x57952) */
    s16 ceil_saved;         /* abs_p_cmd_max at entry and at each step start, 0.01 bar */
} abs_reapply_state_t;

typedef struct {            /* 0x408DD8, current wheel */
    u8  period;             /* frames to wait before the next step; 0xFF = no scheduled step */
    u8  _1;
    u8  n;                  /* copy of ctl[15:11] */
    u8  cond;               /* b0 count an extra step / fast rate; b1 ABS master state; b2 rear-latch flags;
                               b3 a wheel on the other axle has 0x40902E b5; b4 wheel re-decelerating: stop building,
                               freeze, no further scheduled step (period 0xFF);
                               b5 front-pair condition */
    u8  cond2;              /* b0 special rate active; b1 set in 0x4C368; b4/b5/b6 ratio of the two filtered
                               pressures (0x408E20 + 14w, +6 vs +8) above 99/97/94 %; b7 slip > 1 km/h and wheel
                               decel lags vehicle decel by > 0.15 g */
} abs_reapply_scratch_t;
```

**Calibration and constants**

| Address | Name | Tag | Unit | Stock | Role |
|---|---|---|---|---|---|
| 0x40D5E | `abs_reapply_rate_front` | CAL | 0.01 bar / frame | 300 | build rate toward each new ceiling; also the fast rate above 80 bar |
| 0x40D60 | `abs_reapply_rate_rear` | CAL | 0.01 bar / frame | 500 | rear build rate |
| 0x40D62 | `abs_reapply_frac_front` | CAL | /16 | 10 | m: step = H·(16 − m)/32, later H·(16 − m)/(48 − m); also the hold ceiling P_min + H·m/16 |
| 0x40D64 | `abs_reapply_frac_rear` | CAL | /16 | 10 | m, rears |
| 0x40D52 | `abs_reapply_boost_n0` | CAL | steps | 5 | N0 base for `abs_reapply_step_boost` |
| 0x40D5A | `abs_reapply_boost_ref_pct` | CAL | % of `abs_p_ref` | 110 | boost when CMD is past this (and 3 bar past `abs_p_ref`) |
| 0x40D54 | `abs_reapply_step_x2_enable` | CAL | flag | 0 | doubles the step when 0x408E7A > 105 or 0x408DEC b2 |
| 0x40D4A / 0x40D4C | `abs_reapply_lag_slip_min` / `_decel` | CAL | 0.01 km/h / 0.01 g | 100 / −10 | lagging-wheel flag (`flags` b11): slip > max(this, 0.3·vref) and wheel decel − vehicle decel < this |
| 0x40D58 | `abs_reapply_lag_rear_clear` | CAL | flag | 0 | clears `flags` b11 on rears with 0x408DEB b5 |
| 0x40D50 | `abs_reapply_cond_k` | CAL | ? | 172 | compared with byte 0x408E7A in `abs_reapply_conditions` |
| 0x40D56 | `abs_reapply_entry_opt` | CAL | flag | 0 | entry init clears rec+0x0D b5 when 0 |
| 0x40C94 | `abs_rear_precontrol_ax` (ABS+0x8F8) | CAL | 0.01 g | 70 | rear decel-gate latch `0x409049[4w]` b3 in `abs_event_classifier`: set (0x4DED2…0x4DF9E) needs trusted ax (`0x408E1C` b7) beyond −cal / −(cal − 15) with `0x40902E` & 0x12 (or the `0x408E94` < −700 path), rec+6 < 0, driver pressure > 0; released (0x4EC34) when trusted ax > −(cal − 15) = −0.55 g, or driver pressure falls 4 bar and below 80 % of the snapshot `0x408E72`. b3 arms rear pre-control (EV0.b6, 0x4ECBC) and drives 0x19E ST_CLCTR bit 32. Never active without ax trust (no SZL) |
| 0xD6CF8 | `abs_reapply_period_tbl` | ROM s16[] | frames | 0, 7, 7, … | wait after each completed step, by n |
| 0xD6B6E | `abs_reapply_special_period_tbl` | ROM s16[] | frames | 0, 1, 2, 2, 3, 3, 3, 4, 4, 5, 6, 7, 8, 9 | period in the special-rate (250) case, index max(1, n − 3) |
| 0x403B4 | `abs_reapply_rear_lat_dp` | CAL curve n7 | x \|lat\| byte → 0.01 bar | lo 0, hi 200 | rear cornering branch of `abs_reapply_special_rate` |
| 0x4B74C… | step limit N_max | CODE | steps | 12 if the axle partner is in ABS, else 9; −3 if the diagonal is not, −2 if the same-side wheel on the other axle is not; 12 for rears and under 0x40903C b7 / 0x408DEF b7 | past it, fast_rate = 600 |
| 0x4B87A | fast rate | CODE | 0.01 bar / frame | 600 (3 bar/frame via 0x40D5E when PM > 80 bar on a front) | continuous ramp with lock re-capture |
| 0x58204 | ceiling cap | CODE | 0.01 bar | 20000 | |

## Inter-ECU inputs (cycle 6)

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x06ACC6 | `fcan_peer_exchange_task` | med | external torque-limit exchange; gated by cal 0x4182A (=0, disabled) |
| 0x06AF8A | `fcan_rx_78F_78E_parse` | high | parses the aux torque-limit frame → 0x404634/36 |
| 0x0C56D0 | `fcan_rx_queue_push` | med | F-CAN→PT-CAN gateway queue 0x402E84 |
| 0x07A172 | `fcan_to_can_gateway_drain` | med | re-sends 0x0C8/0x194/0x1D6/0x2A6/0x1D9 on PT-CAN |
| 0x07FB8A | `nm_rx_frame_process` | med | network-management, node 0x29; RX 0x480 |
| 0x07F9A6… | `can_rx_dead_stubs` | high | bare `jmp r15` setters for 0x0AC/0x0B4/0x1B4/0x0D5/0x388 and F-CAN 0x118/0x11F |

F-CAN 0x118/0x11F are dead (all signals discarded); they are not AFS frames.

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

**ABS sensor-gather RAM:** 0x408EB2 = **driver brake pressure** (not yaw); 0x408ECA = lateral accel
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

## Sensor validity, steering-loss reaction, TCS inhibit (FACTS "Steering-sensor loss")

**Signal getter convention.** Every `*_get(want, out)` below fills a 4-byte `sensor_sig_t` and returns 1 if the
value is valid (and `want` = 1), else 0:

```c
typedef struct {
    int16_t value;   /* +0  raw RAM value; lateral 0x93AC0 substitutes ay_wheel_estimate when invalid */
    uint8_t st;      /* +2  b7 valid · b6 sensor fitted (sensor_fitted(n) == 1) · b5 checked (always set)
                            b4 invalid · b3 invalid because of sensor_reaction_word (b4 set too)        */
    uint8_t st2;     /* +3  only the *_signal_get(idx) wrappers (n = sensor bit in the reaction words: ax 1, lat 2, yaw 3,
                            pressure 5): b7 valid (st b6&b5 set and (st2 & 0x7C) == 4) · b6 fault (hard fault, or aux bit
                            0x402884) · b5 hard fault 0x402890 bit n (also out-of-range idx, value 0x8000) · b4 reaction
                            word 0x402888 bit n · b3 per-sensor monitor bit (ax 0x402009 b4, lat 0x4029BE b2, yaw
                            0x4029BE b3, pressure 0x40288D b3) · b2 always set. CAN encoders send "invalid" when
                            st2 & 0x60                                                                   */
} sensor_sig_t;
/* valid  <=>  (st & 0x78) == 0x60  &&  want == 1 */
```

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x0CF5C2 | `sensor_fitted(n)` | high | returns ROM byte 0xF6756[n] (n ≤ 35, else 0xFF). n = 5 pressure, 6 lateral, 7 yaw, 8 steering, 9 ax |
| 0x093AC0 | `abs_ay_get(want, out)` | high | value s8 0x402AB6 (sign-extended) when valid, else `ay_wheel_estimate_get()`; invalid on 0x402888 b2 or 0x402884 b5 |
| 0x093B3A | `abs_ay_aux1_get(want, out)` | med | s8 0x402124 = front-axle lateral accel estimate (0.01 g, `ay_axle_est_update`), same validity bits as `abs_ay_get` |
| 0x093C22 | `abs_ay_aux2_get(want, out)` | med | s8 0x402126, same validity bits. Meaning not decoded |
| 0x094308 | `abs_yaw_get(want, out)` | high | s16 0x402100 (1/20000 rad/s); invalid on 0x402888 b3 or 0x402884 b7 |
| 0x094376 | `abs_yaw_accel_get(want, out)` | med-high | s16 0x402102; same validity bits as `abs_yaw_get` |
| 0x09403C | `steer_roadwheel_angle_get(want, out)` | med | s16 0x40212E (= angle·29360/ratio, `steer_ratio_convert`); invalid on 0x402888 b0 or 0x402884 b3 |
| 0x094120 | `steer_angle_get(want, out)` | med | s16 0x402132 = **offset-corrected steering-wheel angle** (`steer_offset_learn` output); same validity bits |
| 0x0940AE | `steer_rate_get(want, out)` | med | s16 0x402130; same validity bits |
| 0x093E8E | `pressure_aux_get(want, out)` | med | s16 0x402000; validity as `master_pressure_get` (0x402888 b5 / 0x402884 b4) |
| 0x0B5D74 | `cluster_fault_any` | med | 1 if fault 0x90020, 0x90010 or 0x90080 is latched (`fault_is_set`). ABS: 0x408E6D b2 = NOT this |
| 0x0D21C4 | `ay_wheel_estimate_update` | low-med | called from 0xD0410. Lateral substitute from the front-wheel record difference (rec+0x35, rec+0x1C of wheels 0/1) and vref, slewed ±1/±2 per call → 0x408D64. Formula not fully decoded |
| 0x0D240A | `ay_wheel_estimate_get` | high | returns s8 0x408D64 |
| 0x0D21BC | `ay_wheel_estimate_reset` | high | 0x408D64 = 0 |
| 0x0B4A74 | `sensor_reaction_build` | high | runs each cycle; zeroes 0x402888/0x40288A/0x402890/0x402892/0x402894/0x402896, then sets them from fault latches 0x402838[g] and status flags (rules below). Calls 0xB7F0C first |
| 0x0B481E | `fcan_fault_flag_set(id)` | high | id 0xA1000 → 0x4028B1 b6, 0xA0040 → b7, 0xA0800 → b5 |
| 0x0B484A | `fcan_fault_commit` | med-high | 0x4028B1 b7 → 0x402893 b6 and hold counter 0x4028BC = 255 (b6 clears when it runs out). 0x4028B1 b5\|b7 → `fault_set(0xA0040)` (b7) or `fault_set(0xA0800)`; when 0x400956 b3 the path waits for a value > 2000 and calls 0xB5DF2(2) instead. Clears 0x4028B1 b7 |
| 0x0530E4 | `abs_yaw_stable_update` | med | (called from 0x447EE) counter 0x408EF4 → 0x408E5F b4 = low yaw for ≥ 63 frames; forced 0 unless 0x408E6D b7, b4 and b5; zeroed when \|steering\| > cal 0x4040E. Cals: calm yaw 0x40404 = 1047, set at 0x4040C = 63 frames, hysteresis 0x40406 = 28, decay 0x40408 = 1571 / 0x4040A = 3002, steering 0x4040E = 2971 counts (≈ 130°); `agents/abs_full/09_chassis_sensor_use.md` §7.2 |
| 0x0C7794 | `tcs_mode_set(m)` | high | 0x4030A2 = m |
| 0x0C779A | `tcs_state_a` | med-high | **brake TCS** (channel A) state. Fault word u32 0x403004 (byte 3 b2 masked out), active flag 0x402FC0 b4 (= 0x19E TCS bit). 2 if 0x4030A4 = 2; 3 if 0x4030A3 = 5; **6 (5 if 0x402F6A b0) = inhibited**: fault word ≠ 0 and not active; **7 = DSC off**: masked bit (DSC-off latch) set and not active; mode 0x4030A2 = 3: 8 idle / 10 active (12 with a fault); else 4 idle / 9 active (11 with a fault) |
| 0x0C7818 | `tcs_state_b` | med-high | **engine ASR** (channel B) state; same state scheme; fault word u16 0x402F84 (byte 1 b2 masked), active 0x402F6C b7, alt state when 0x402F6A & 2. Read by `lamp_state_gather` as "TCS" |
| 0x0C789C | `tcs_state_c` | med-high | **MSR** (channel C) state; same state scheme; fault word u16 0x403048 (byte 1 b2 masked), active 0x40303C b7 (`msr_pid` flag), alt state when 0x402F6A & 4 |
| 0x0CE3D0 | `tcs_a_inhibit_update` | high | 0x403004 b7 = 1 while 0x402880 b4; cleared only when 0x402880 b4 is clear and 0x402F86 b2 is set (latched otherwise) |
| 0x0CE638 | `tcs_c_inhibit_update` | high | 0x403048 b6 from 0x402880 b5, same latch/release on 0x402F86 b2 |
| 0x0CE7A4 | `tcs_b_inhibit_update` | high | 0x402F84 b1 = 0x402880 b3 (not latched); 0x402F84 b7 = 0x40288C b5 |
| 0x0CE848 | `tcs_inhibit_summary_7e` | med | 0x402F7E b1 = OR of 0x403004 b7/b0, 0x403005 b3/b4/b6, 0x403007 b0 (b0 or b1 picked by 0x402F7E b6) |
| 0x0CE8A0 / 0x0CE8D4 / 0x0CE8FA / 0x0CE920 | `tcs_inhibit_sum_b0` / `tcs_inhibit_sum_a` / `tcs_inhibit_sum_c` / `tcs_inhibit_sum_b` | high | build 0x402F6A b0 (0x402F84 b1, 0x402F85 b0/b2), b6 (0x403004 b7, 0x403007 b0), b5 (0x403048 b6, 0x403049 b0), b4 (0x402F84 b1, 0x402F85 b0) |
| 0x00402888 | `sensor_reaction_word` (u16, rebuilt each cycle) | high | byte 0: **b0 steering invalid** (also clears ABS lat-valid), **b1 ax**, **b2 lateral**, **b3 yaw**, b4/b6 set every cycle (0xB4B50), **b5 brake pressure**. Byte 1 b0–b3 from group 8 & 0x1C / 0x4028D9 b4. Main rules in `sensor_reaction_build`: steering timeout (group A b6 = 0xA0040 latched **and** 0x402E6D b5) → b0\|b2\|b3 (0xB4C66); 0x402893 b6 (0xA0040 pending, held 255 cycles) → b0\|b2\|b3; group 18 & 0x931F, group A & 0x700, group 8 b11/b12, group 11 & 0xE00, 0x402009 b3, 0x402009 b6+b7, 0x4028B6 b1, 0x402A11 b3, group 18 b7 → b0\|b2\|b3; group A & 0xDF00, group 15 & 0x3F7F, group 8 b5, 0x402893 b4 → b1\|b2\|b3; group 16 & 0x7F / b7 / & 0x3F00 / b14 → b2\|b3 |
| 0x00402890 | `sensor_hardfault_word` (u16, rebuilt each cycle) | med-high | same bit positions as 0x402888, set by a subset of the rules (not by the steering-timeout rule). b2/b3 make 0x1A0 ay/yaw = 0x800 |
| 0x00402884 | `sensor_reaction_aux` (u8) | med | b3 steering, b4 brake pressure (= 0x402952 b2, 0xB4B80), b5 lateral, b7 yaw invalid. Other writers 0xB7F2C, 0xB80CC–0xB8F12 not traced |
| 0x0040288A | `sensor_reaction_flags` (u8) | med | b7 set every cycle by `sensor_reaction_build` (0xB4C8A); rest not decoded |
| 0x00402893 | `sensor_reaction_req` (u8) | med | b4 → 0x402888 b1–b3; b6 = F-CAN fault 0xA0040 pending/held (0xB484A) → 0x402888 b0/b2/b3 |
| 0x004028B1 | `fcan_fault_pending` (u8) | high | b5 0xA0800, b6 0xA1000, b7 0xA0040 (set by `fcan_fault_flag_set`, b7 consumed by 0xB484A) |
| 0x004028BC | `fcan_fault_hold_cnt` (u8) | med | 255 on each pending 0xA0040, −1 per cycle; keeps 0x402893 b6 |
| 0x00402E6D | `fcan_0C9_status` (u8) | med-high | b7 set on 0x0C9 timeout, b5 = copy of b7 (0xC6EA4); b5 is the "frame missing now" term of the steering rule. Also written by the 0x0C9 alive handler |
| 0x0040164E | `steer_0C9_status` (u8) | med | b1–b3 set on 0x0C9 timeout |
| 0x00402F35 | `fcan_monitor_flags` (u8) | med | **b4 = F-CAN fault reporting enabled** (`fcan_comm_state_update` 0xC4F0E); b6 (0xC7470) and b7 (0xC7480) set from request bytes; b3/b7 block b4 |
| 0x00408D64 | `ay_wheel_estimate` (s8, ≈ 0.01 g) | low-med | written only by 0xD21C4 / 0xD21BC |
| 0x00408E6D | `abs_sensor_valid` (u8 bitfield) | high | built by `abs_sensor_gather` each cycle: **b0** 0x408EC8 valid, **b2** no cluster fault (`cluster_fault_any` = 0), **b3** set from the ax getter at 0x5D868 but **cleared again at 0x5D914 in the same pass** (no other writer of 0x408E6D found, so consumers such as vref 0x4513E always see 0; ax validity survives only in 0x408E1B b4 and 0x408DEC b2 = ax invalid), **b4** yaw, **b5** steering (both angle getters valid), **b6** brake pressure (0x408EB2; zero-pressure plausibility counter 0x408EBA < 50), **b7** lateral (getter valid and 0x402888 & 0x09 = 0). Lateral users test b7 (rear select-low 0x5197E, classifier 0x51BF2 with b6, many others); the straight latch 0x521EC needs b7+b5+b4 (mask 0xB0); the rear cornering latch 0x4E8B6, vref route 2 and `abs_chassis_frame_init` need b7+b6+b5+b4 (0xF0) |
| 0x00408ECA | `abs_ay` (s8, ≈ 0.01 g) | high | positive = left-hand turn (ISO 8855); from `abs_ay_get`, written **every cycle even when invalid** (then = `ay_wheel_estimate`) |
| 0x00408ECB | `abs_ay_aux1` (s8) | med | from 0x93B3A, written only when b7 |
| 0x00408EC8 | `abs_ay_aux2` (s16) | med | from 0x93C22, valid b0 |
| 0x00408ECC | `abs_yaw` (s16, 1/20000 rad/s) | high | positive = left-hand turn (ISO 8855); from `abs_yaw_get`; **0 when invalid** |
| 0x00408ECE | `abs_yaw_accel` (s16) | high | from 0x94376; 0 when invalid (no valid bit) |
| 0x00408EDE / 0x00408EE4 / 0x00408EE6 | `abs_steer_angle` / `abs_steer_roadwheel` / `abs_steer_rate` (s16) | med | positive = left (ISO 8855); offset-corrected steering-wheel angle / road-wheel angle / steering rate, from 0x94120 / 0x9403C / 0x940AE; 0 unless b5. Consumers: angle → `abs_yaw_stable_update` 0x530E4 (cal 0x4040E), `abs_gma_hold_frames` 0x54BE8, front staged dump peak `0x400A92`; road-wheel → `abs_countersteer_check`, peak 0x408EE2; rate → `abs_gma_hold_frames`. Front µ-split outputs 0x400A90 / 0x400A97 b0 have no readers |
| 0x00408EB4 | `abs_pressure_aux` (s16) | med | from 0x93E8E (0x402000) |
| 0x00408E5F | `abs_cornering_flags` (u8) | med | b6:5 pair-gate state S (`abs_pair_gate` 0x54B70); b2 used with b4 by `abs_pair_gate_split_yaw` (writer not traced); b1 gates the direction-selective rear dump 0x4EF72; b4 yaw-stable (0x530E4); b4 gates the straight/homogeneous latch b7 (0x521D4), classifier shortcut 0x51E46, pair-gate predicate 0x547D8, one ax plausibility route in 0x49572 |
| 0x00408EF4 | `abs_yaw_stable_cnt` (u8) | med | frames of low yaw for 0x408E5F b4 |
| 0x0040200C | `dsc_sensor_cal_flags` (u8 bitfield) | high (read side) / low (setter) | DSC chassis-sensor "ready to calibrate" flags / `31`-routine precondition gate. **Bits read by `kwp_31` 0xB2D08–0xB2D44 (verified): b0 long-accel, b5 steering, b6 lateral, b7 pressure** — clear bit → the matching cal routine returns NRC `0x22`. The bits are maintained by the chassis-sensor conditioning task (`~0x089E00`–`0x08A5xx`), a register-heavy per-sensor state machine **not reliably linearised from static analysis** — do NOT trust a specific numeric guard here without a bench check. Each bit means roughly "that sensor is coded-fitted (`sensor_fitted(n)`, ROM `0xF6756[n]`: 5 pressure, 6 lateral, 8 steering, 9 ax) AND currently reading valid/plausible with no active fault and no competing valve/sensor cal owning the state (`valve_cal_type 0x404970`)". `0x089EC0` is a *getter* of b7 (returns a status code 3/16), not the setter. Routine-body completion bits (separate from these ready bits): b2 (`0xB2E50`), b3/b4 (`0xB2E46`), `0x40200D` b7 (`31 24` body `0xB2E82`). **[cap] the exact per-bit set conditions need a bench capture of `0x40200C` across sensor states.** |
| 0x00402132 | `steer_angle_corr` (s16) | high | positive = left (ISO 8855); offset-corrected steering-wheel angle (raw 0x4020D0 − offset 0x4020A6/64), ≈ 0.044°/count [unverified] |
| 0x004020A6 | `steer_offset` (s16, Q6 counts) | high | learned steering zero offset (`steer_offset_learn`); clamp ±29257 (457 counts ≈ 20°), fault 0x120001 above 14628 (≈ 10°); saved in EEPROM record 0x4020AE |
| 0x0040212E | `steer_roadwheel_angle` (s16, LSB = steering LSB / 28.67) | high | 29360·angle / ratio (`steer_ratio_convert`) |
| 0x00401644 | `steer_angle_can` (s16 counts) | med | 0x0C9 sig 43 ·1029/1024 |
| 0x0040164D | `steer_can_status` (u8) | med | b7:6 0x0C9 angle status (0xC5E20) |
| 0x004020D0 / 0x004020D2 | `steer_angle_raw` / `steer_angle_iir` (s16 counts) | high | raw angle / IIR k 241/256 (learner target) |
| 0x004020D4 | `steer_roadwheel_prev` (s16) | high | previous 0x40212E |
| 0x004020AE | `sensor_offset_record` (u16[17]) | med | EEPROM block 8 at 0x160. +0 checksum over +2..+33; +2 → 0x4020FA; +4..+10 → 0x4020A6 steer, 0x4020A8 lateral, 0x4020AA / AC master pressure offsets; +16.. → 0x4049FD / 0x404A04 (not decoded) |
| 0x00402134 | `steer_learn_div` (u8) | high | reload 100; learner runs at 0 |
| 0x00402136 | `steer_learn_distance` (u16) | med | += vref/360 per learn, cap 60000; zeroed while 0x4020FC b7 |
| 0x004020FC | `steer_offset_flags` (u8[2]) | med | +0 b7 resets 0x402136; +1 b7 learner enable, b6 fault-monitor enable, b5 set by 0x92104, b4 alt learner curve 0xDA902. Writers 0x92104, 0x90660 |
| 0x00402142 | `sensor_offset_record_state` (u8) | med | state of 0x92104 (0–5) |
| 0x00402144 | `chassis_state_flags` (u8[5]) | low | 0x91070; +3 b7 gates the steering learner (writer not traced), +3 b2 the master-pressure learner |
| 0x004020DC | `ay_idx3` (s16) | low | `ay_signal_get` idx3; learner curve-A input; scale not decoded |
| 0x0040211C | `steer_yaw_residual` (s16) | low | 0x90BC0; learner curve-B input |
| 0x00400B2C | (s16) | low | learner divisor, also read by the yaw observer; init 1 at 0x647A0; role not traced |
| 0x00402130 | `steer_rate` (s16) | low-med | `steer_rate_update` 0x90408 |
| 0x00403004 | `tcs_a_fault_word` (u32) | med-high | b7 (byte 0) = fault-reaction inhibit (0xCE3D0); byte 3 b6 = DME "torque not adjustable" (0x40114F b5, 0xCE55A); **byte 3 b2 = DSC-off latch** (set while `tcs_mode` = 2, cleared when mode ≠ 2 and 0x402F86 b2; 0xCE584) → state 7 |
| 0x00402F84 | `tcs_b_fault_word` (u16) | med-high | b1 = 0x402880 b3, b7 = 0x40288C b5; byte 1 b7 = 0x40114F b5; **byte 1 b2 = DSC-off latch** (same rule, 0xCE7F0) → state 7 |
| 0x00403048 | `tcs_c_fault_word` (u16) | med-high | (0xCE638) b7 = 0x40288C b5; b6 = 0x402880 b5 (latched); b5 = channel A or B or AYC active (0x402FC0 b4 \| 0x402F6C b7 \| 0x400B0A b6); b4 = 0x403056 ≥ 15; b3 = 0x403047 b7 or 0x6FF0E() = 1; **b2 = pedal > 13 %** (`pedal_at_most(13)` = 0, only when 0x401150 b4 clear); b1 = 0x403046 b2; byte 1 b0 = 0x4030A4 = 3. **No DSC-off bit** (byte 1 b2 has no writer found) |
| 0x00402F6A | `tcs_inhibit_summary` (u8) | med | b0 / b4 channel B, b5 channel C, b6 channel A inhibited; b1 (0xCE812), b2 (0xCE748) not decoded; b7 needed for DSC off → on (`mode_transition_valid`), writer not identified |
| 0x004030A2 | `tcs_mode` (u8) | high | 1 normal, 2 driver DSC off, 3 MDM (`tcs_mode_from_driver_mode`); read by the channel state functions |

## ABS and TCS use of the chassis sensors (FACTS "ABS with and without the SZL", `agents/abs_full/09_chassis_sensor_use.md`)

Who reads lateral / yaw / steering inside ABS and TCS, what each needs valid, and the DSC-off behaviour of the
traction channels. Validity bits are `abs_sensor_valid` 0x408E6D (b7 lat, b6 pressure, b5 steering, b4 yaw).

**ABS decision word.** `abs_decision_classify` writes a small struct at 0x408DDE:

```c
typedef struct {
    uint16_t code;      /* +0  0x408DDE: 1 rears independent / not in control, 64 rear select-low, 32 cornering
                                 (lateral-g) build, 128 special (0x40493A b5), 16/1024/2 from abs_pair_logic      */
    uint8_t  pct;       /* +2  0x408DE0: code-32 position of driver pressure between the two lateral-g curves, % */
    uint8_t  _pad[7];
    uint16_t idx;       /* +10 0x408DE8: b9 lead rear is the inside rear (abs_rear_lead_select); b13:12 lead rear s, b11:10 and b15:14 the other rear t (code-32 exec) */
} abs_decision_t;
```

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x054B70 | `abs_pair_gate` | high | state machine S = `0x408E5F` b6:5, returns S. S0 → 1 when `abs_pair_gate_split_yaw`; S1 → 2 when (split_yaw or 0x54954) and not `abs_pair_gate_hold`, S1 → 3 when neither; S2 → 3 unless split_yaw / 0x54954; S3 → 0 when 0x54AF8 returns 0. `abs_pair_logic` jumps to its exit (0x553BE) while S = 0 |
| 0x0547D8 | `abs_pair_gate_split_yaw` | med-high | per axle pair: pressure-split tests (PM `0x408F2A` vs 30 % of `0x408FF0`, curve 0x40E74 of `0x408FF0`), \|yaw\| > cal 0x40DD4 with the sign of the side, `0x408E5F & 0x14` = 0x14 (yaw-stable + b2), and vref / 0x40DC8 / 0x40D84 conditions. Never true without yaw |
| 0x054A80 | `abs_pair_gate_hold` | med | returns 0 (release) when the partner is dumping with rec+1 b4 and not rec+22 b7, or has dumped > 40 frames with yaw and yaw accel of the same sign and \|yaw\| < cal 0x40DD4 |
| 0x053D3C | `abs_front_split_detect` | low-med | writes front-pair state `0x400A95`; cal enables 0x40E92 / 0x40E9C; uses raw lat byte thresholds (16 / −15 / 6 / −5 / 21 / −20) with side flags `0x408DF0` b7/b6, and lat valid (b7) as one release path; calls 0x599BC |
| 0x0540D4 | `abs_front_stage_cancel` | med | clears `0x400A96` b7 when `0x400A95` b6 and vref > 40 km/h; clears `0x400A96` b6 when `0x400A95` b5 and (\|lat\| > 35 with b7, or `0x400A95` b1) — a corner cancels the front staged dump only with valid lat |
| 0x05A0DC | `abs_chassis_frame` | med | tail of the ABS frame; builds a 96-byte stack context, calls 0x5A21C, 0x5AE66, 0x5AEEE, 0x5A2E0, 0x5AC0C, 0x5CFDC, 0x5D264, 0x5CAF4, 0x5D290, 0x5A4E4, then copies context fields to 0x40915E–0x409188 (no direct readers found) |
| 0x05A21C | `abs_chassis_frame_init(ctx)` | med-high | ctx+33 b4 = all of lat, pressure, steering, yaw valid (`0x408E6D & 0xF0` = 0xF0); otherwise clears `0x40903C[3w]` b4 for every wheel. ctx+32 b0 = `0x408DF0 & 0xC0` ≠ 0. Clears `0x40903A[3w]` b7/b6/b2 and `0x40903B[3w]` b6/b1 each frame |
| 0x05AEEE | `abs_side_select(ctx)` | low-med | first part decoded: picks the inside/outside side (ctx+1 b2 or b3, record offset 0 / 0x40) from the lateral sign when \|lat\| ≥ 11 and b7, else from the rear wheel-speed difference (RR vs RL rec+0x1C) with lat thresholds −5 / −15. Rest (≈ 3.5 k lines) not decoded |
| 0x05CAF4 | `abs_countersteer_check(ctx)` | low-med | lat, yaw and 2nd lateral of the same sign, steering valid (b5) with road-wheel angle `0x408EE4` of the opposite sign, yaw accel opposite, \|yaw\| below half `0x408ED0` → rear-control branch writing `0x408DA0` b4/b5/b7. Without steering the countersteer condition is skipped. Uses only the sign of the road-wheel angle and peak `0x408EE2` > 0 (no magnitude cal) |
| 0x054BE8 | `abs_gma_hold_frames(pred_yaw)` | med-high | (`09_chassis_sensor_use.md` §7.3) GMA rebuild pacing score for the record in `0x400978`, called at 0x55200 in `abs_pair_logic`: the caller steps the command +0x40DB0·100 (3 bar) once `0x408EEF` ≥ score + 0x40D8E (7). Terms: +7 slip (curve 0x40974) or rec+6 < 0; (vref − 0x40DC6)/0x40D8C/100; −decel/14 below 0x40DCA km/h; rears (\|pred yaw\| − 0x40DD6)/0x40DCC by yaw sign (− RR, + RL); rears \|steer rate\|/0x40D86 when rate > 0x40D88 (RR) / < −0x40D88 (RL); 0x40D92·(\|angle\| − min)/(0x40D8A − min) with min `0x408EF2`; 248 when \|angle\| > 0x40D8A and own PM − partner PM > 5 bar |
| 0x05A4E4 | `abs_corner_peak_track` | low-med | peak road-wheel angle `0x408EE2`, peak lat `0x408EDB`, peak yaw `0x408ED0` / `0x408ED2` in the current turn direction (for `abs_countersteer_check`) |
| 0x0538E8 | `abs_decel_est_clamp_ax` | high | in the ABS regime (`0x408DA1` b4) with ax < 0.3 g: clamps the wheel-derived vehicle decel `0x408DAF` to ax ± 0.2 g (±127). Called from 0x53512 when `0x408E6D` b3 (dead) or `0x408E1C` b7 (ax trusted) |
| 0x049572 | `abs_ax_decel_estimator` | low-med | called from 0x4629E; also the **ax plausibility / trust logic** for `0x408E1C` b7 (0x49586–0x49CB8: compares ax with `0x408DAF` while braking, deviation `0x408E8E`, alive counter `0x408E8C`). Initial trust needs lateral + pressure valid, yaw-stable and \|lat\| < 0.20 g, so it is never set without the SZL; see `agents/abs_full/10_vref_and_ax.md` §1.1. Writes 0x408E82–0x408E90, 0x408E98, 0x408EA7/A8/AA. Straight-line updates need lat + pressure valid, yaw-stable, \|lat\| < cal 0x40C9A, or lat + yaw valid with \|lat\| < half that and \|yaw\| < 700. Outputs only partly traced (0x408E98 gates one rear pre-control dump) |
| 0x0CC89C | `tcs_sensor_latch` | high | copies the chassis signals for the traction code: ax (0x93828) → 0x40306C, lateral (`abs_ay_aux2_get` 0x93C22) → 0x40306E, brake pressure (0x93E1C) → 0x403070, road-wheel angle (0x9403C) → 0x403072, yaw (0x94308) → 0x403074; valid bits in `tcs_sensor_valid` |
| 0x0CB43E | `tcs_straight_detect` | med | straight = \|yaw\| < 2792 below 25 km/h, else 27265 / (vref / 256), \|lat\| < 15, \|road-wheel angle\| < 1310 counts; reads the latched values without the valid bits |
| 0x0C9450 | `tcs_yaw_slip_term` | low-med | with `tcs_sensor_valid` b3: \|yaw\|/75, else `0x4030A8`·2; then curves 0xF6158/0xF6168 and 0xF6178/0xF618A scaled by vref |
| 0x0D03F8 | `vehicle_estimators_frame` | med | via 0x8F29C (T3 0x7101C). When 0xD3A88() (= `state_nibble_get(18, 1)` after its update) ∈ {2, 3, 4, 5}: 0xD2A2E, `ay_wheel_estimate_update`, 0xD24F6, `tyre_tol_learn` 0xD144A, `wheel_accel_lp_peak` 0xD210C (rec+0x22 / rec+0x38), `vehicle_standstill_update`, 0xD37B6 |
| 0x00408DE0 | `abs_decision_pct` (u8, %) | high | `abs_decision_t.pct`; written only at 0x51F42: pct = 100·(P_drv − P_lo)/(P_hi − P_lo), P_lo = 100·curve 0x40E26(\|lat\|), P_hi = 100·curve 0x40E0A(\|lat\|) (+500 above \|lat\| 80). Not clamped: above P_hi it exceeds 100 and wraps modulo 256 (`st.b` / `ld.b`). Read by `abs_decision_pressure_exec` code 32 (0x59272) |
| 0x00409024 | `abs_yaw_corner_flags` (u8) | med | b0+b6 set when \|yaw\| > curve 0x40E42(−decel) during ABS (0x51BB8); b0 cleared when \|yaw\| < half the curve. b0 blocks the classifier straight shortcut and the straight latch. Never set without yaw |
| 0x00409049 | `abs_rear_latch` (u8 per wheel at 0x409049 + 4·w) | med-high | b2+b5 rear cornering latch (0x4E908; needs `0x408E6D & 0xF0` = 0xF0 and 0x408DC6 b2), b3 rear decel-gate latch (0x4DF9E). b5 enables the code-32 / code-1 lateral branch of the classifier. Latch triggers, threshold T (`0x409132` + 10·w, cals 0x40B06 / 0x403E4 floor) and release: 09 §2.2 |
| 0x00408DA1 | `abs_mode_flags` (u8) | med | b4 braking / ABS regime (gates `abs_decel_est_clamp_ax` 0x538E8, blocks ax-trust set at 0x49A9E, selects the `vref_update` rise/fall regime); bits 7:5 controller mode (0 = normal ABS); non-zero blocks the slip-triggered events; writers and values in `agents/abs_full/08_phase_control.md` §6.1 |
| 0x00408EC0 | `abs_standstill_count` (u8) | high | frames at rest, saturates at 30 → mode 1 (`abs_mode_update`) |
| 0x00409056 | per-wheel flags (u8, stride 2) | high | b0 low speed (< 4 km/h and counter ≥ 30; read by `abs_mode_update` for mode 3), b1 / b2 classifier gross-slip bits |
| 0x00409026 | `abs_dump_entry_rec6` (s16[4]) | high | rec+6 latched at each EV0.b5 / EV0.b0; while dumping the decel flag is rec+6 < half of it |
| 0x00408DAF | `abs_decel_est` (s8, 0.01 g) | med-high | wheel-derived vehicle decel (`0x408EE8`/21, writer 0x534E6); clamped to `abs_ax` ± 0.2 g during ABS when ax is trusted (0x538E8); feeds the vref fall limiter 0x45104 and the decel-threshold g-term |
| 0x00408E80 | `abs_ax` (s16, 0.01 g) | med-high | longitudinal accel used by ABS, written by `abs_sensor_gather` 0x5D82C: ax getter 0x93828 (byte 0x4049FC, ±1.27 g) when valid, else `abs_decel_est` |
| 0x00408E8C | `abs_ax_alive_count` (u8) | med | (0x495C4–0x4961C) held at ≥ 25 while the ax-type signal 0x408E94 differs from its copy 0x408E8A; counts down above 10 km/h (with 0x40095C b0) when it stops changing; at 0 `abs_ax_flags` b7 is dropped. Trust set needs ≥ 16 (0x49AAC) |
| 0x00408E1B | `abs_estim_flags` (u8) | med | b1 = a rear cornering latch is active (gates classifier block 14, yaw-limited E+37 b7); b4 = ax valid copy |
| 0x00408E1C | `abs_ax_flags` (u8) | med-high | **b7 = ax trusted** (plausibility-checked), set by `abs_ax_decel_estimator` on two paths: initial trust (0x49AE0–0x49CB8) after 5 agreeing braking frames with driver pressure > 5 bar, not in ABS, lateral + pressure valid, yaw-stable, \|lat\| < 0.20 g and deviation `0x408E8E` < 20; re-trust (0x49AA8–0x49AD8) only after a stale-signal drop (b2), with ax valid, not in ABS, alive counter `0x408E8C` ≥ 16 and deviation < 50. Cleared at 0x49A76 (deviation > 500) and 0x4961C (counter 0). Never set without the SZL. b7 selects ax over `0x408DAF` in the classifier and the decel-threshold g-term (0x47BE0), enables the rear decel-gate latch and `abs_decel_est_clamp_ax`, and is required by vref route 2. b5 = ax disagrees with wheel decel (cal 0x40D46, 0x495C2); b4 = hold after 0x400E9A (gather, 20 cycles); b3/b2 trust bookkeeping |
| 0x0040903A | `abs_wheel_flags3` (3 × u8 per wheel at 0x40903A + 3·w) | med | +0 b5 forced dump, +0 b7/b6/b2 and +1 b6/b1 cleared each frame by 0x5A21C; **+2 (0x40903C) b7** = alternative enable of the classifier lateral branch (writer not traced), +2 b4 cleared when a chassis sensor is invalid |
| 0x00408DF0 | `abs_side_flags` (u8) | low-med | b7 / b6 = which front is the selected (outside?) wheel; read by the dump cornering flags b27/b28, the yaw-deviation flag, `abs_front_split_detect`. Writer not traced |
| 0x00400A95 / 0x00400A96 | `abs_front_stage_state` / `abs_front_stage_ctl` (u8) | med | front staged-dump pair state (`abs_front_split_detect`, `abs_dump_hold_stage_ctrl`); 0x400A96 b3/b2 apply the staged target, b6/b7 cancelled by `abs_front_stage_cancel` |
| 0x00400A92 | `abs_front_stage_steer_peak` (s16) | med | peak \|steering angle\| while `0x400A95` b7 (0x53D3C); read by 0x540D4 (→ `0x400A97` b0) and 0x5971C (→ `0x400A90`), both outputs without readers |
| 0x00408EF2 | `abs_gma_steer_min` (s16) | med-high | minimum \|steering angle\| since the pair logic engaged; 32000 at reset (0x553BE, 0x5528A), lowered at 0x54E16 |
| 0x00408EEF | `abs_gma_rebuild_cnt` (u8) | med | frames since the last GMA rebuild step; 0 after a step (0x55238), 255 at reset; compared with `abs_gma_hold_frames` + 7 |
| 0x00408EE2 | `abs_steer_rwa_peak` (s16) | low-med | peak road-wheel angle in the turn direction (0x5A4E4) |
| 0x00403064 | `tcs_sensor_valid` (u8) | high | b7 ax, b6 lateral, b5 brake pressure, b4 road-wheel angle, b3 yaw (`tcs_sensor_latch`) |
| 0x0040306C / 0x0040306E / 0x00403070 / 0x00403072 / 0x00403074 | `tcs_ax` / `tcs_ay` / `tcs_brake_pressure` / `tcs_roadwheel_angle` / `tcs_yaw` (s16) | high | latched by `tcs_sensor_latch`. Readers: ax 0xC76A4; lat 0xCB474, `tcs_reduction_floor` 0xCD804 (needs b6); road-wheel angle 0xCB49E; yaw 0xC948E (needs b3), 0xCB484 |
| 0x0040114F | `dme_0A8_flags` (u8) | med | b4 = 0x0A8 byte 5 bits 0–1 = 1 (`can_rx_0A8_flag`; meaning unknown); b5/b6 = 0x0A8 state 3 / 2 (b5 = "torque not adjustable", 5E19). b4 + valid DME frames: `msr_pid` caps its output at 6·S and, in DSC off, forces it to 0 (0xCD33A–0xCD350) |

**Traction channel C is MSR (confirmed 2026-10-26: the arbiter 0xCC2C2 turns its flag into the torque-increase request 0x402F6D b2 = 0x19E bit 4 "MSR"; `TCS_7846816A.md` §6).** `msr_pid` (was `tcs_torque_pi`) only produces a positive request (the integrator
0x40304A is floored at 0), and only while the wheel-derived decel `0x408DAF` is negative. Its channel is blocked
by `tcs_c_fault_word` b2 when the pedal is above 13 %, and by b5 while channel A, B or AYC is active. It has no
DSC-off bit, so it stays enabled in `tcs_mode` = 2 (channels A and B go to state 7).

## CAN RX handlers — full table in `analysis/CAN_RX_TABLE_7846816A.md`

| Address | Name | Conf | Evidence |
|---|---|---|---|
| 0x079D3A | `can_rx_dispatch` | high | PT RX walk in the 10 ms CAN task 0x793F0: DLC check (short → 0x40163C bit, frame dropped), then signals until 0x401174[i] b7 clears |
| 0x079CC8 | `can_rx_signal(sig, payload)` | high | type 0 → handler(unpacked), type 2 → handler(payload), type 4 → reload timeout 0x40161C[var] |
| 0x079FE0 | `can_unpack_bits(p, bit, len, mode)` | high | mask table 0xD7F36; Intel reads p[0] \| p[1]<<8 (Motorola p[−1]) |
| 0x0796CC | `can_rx_timeout_task` | high | PT vars 0..10: counter 0x40161C[v] −1 per 10 ms; at 0 calls the handler every cycle; 0xFF = disabled |
| 0x0C5284 | `fcan_rx_signal` | high | F-CAN equivalent; type 1 = direct RAM store via 0xC54DA (width/pos in var +1) |
| 0x0BF994 | `can_fault_report(mask, …)` | med | PT CAN DTCs: internal id 0x2000 + 16·(mask>>16) + bit(mask) |
| 0x0BFA2A | `fcan_fault_report(mask, id)` | med | F-CAN CAN DTCs: internal id 0x3000 + … (queued in 0x4028C0[], count 0x4028BE). r3 = an associated fault id, passed to `fcan_fault_flag_set` 0xB481E first (0xA1000 takes a separate path via 0xBF8DC) |
| 0x00401174 | `can_rx_frame_status` (u8[47]) | high | per RX frame; b7 = frame accepted this cycle (cleared by checksum/alive failure) |
| 0x0040161C | `can_rx_timeout_cnt` (u8[11]) | high | PT type-4 timeout counters, 10 ms units |
| 0x00402F05 | `fcan_rx_timeout_cnt` (u8[]) | med | F-CAN type-4 counters |
| 0x0040114D | `gearbox_type` (u8) | high | from coding f+2 (0xCF42C): 0 manual → 0, 1 → 1, 2 DCT → 6, 3 → 5. Gates 0x0BA (≠ 0) and 0x3B0 (= 0) |
| 0x004010F7 | `gear_current` (u8) | high | from 0x0BA: 0 N, 1..7, 8 R, 11 P, 0xFF invalid |
| 0x00401146 / 0x00401148 / 0x00401144 | `dme_torque_indicated` / `dme_torque_drag` / `dme_torque_demand` | high (arith) | 0x0A8 / 0x0A9 (negated) / 0x0AA, sext12 ×5 |
| 0x00401142 | `accel_pedal` (u8) | med | 0x0AA byte 3 |
| 0x0040113E / 0x0040113C | `engine_rpm` / `engine_rpm_gradient` | med | 0x0AA bytes 4–5 >> 1; low-passed gradient |
| 0x00401130 | `terminal_state` (u8) | med | from 0x130: 4 / 3 / 0 (inferred KL15 / KL_R / off) |
| 0x004046E0 | `outside_temp_raw` (u8) | med | 0x310 byte 0 |
| 0x00401128 | `relative_time` (u32) | med | 0x310 bytes 1–4 |
| 0x004046DC | `odometer` (u32) | med | 0x330 bytes 0–2 |
| 0x004047F6 / 0x004047FD | `vin_rx` / `vin_stored` (u8[7]) | med | 0x380; mismatch → 0x4046D5 b0 |
| 0x00402F1C / 0x00402F24 / 0x00402F26 | `cluster_yaw_raw` / `cluster_ay_raw` / `cluster_ax_raw` | high | F-CAN 0x0CD b0–1 / 0x0CD b4–5 / 0x0D1 b4–5 (`cluster_sensor_get` 0 / 2 / 5) |
| 0x00402E50 | `cluster_status` (u8) | high | 0x0D4 byte 6 bits 0/1/3 → b7/b2/b3; b2\|b3 makes yaw/ay invalid |
| 0x07D6CE | `can_rx_0A8_checksum` | med-high | checksum: byte = low8(Σ payload + id) as `can_tx_checksum8` (byte zeroed first). Mismatch → frame dropped (0x401174[i] b7 cleared), error counter +1 (sat 3), signals mark |
| 0x07BA42 | `can_rx_0A8_alive` | med-high | 4-bit alive counter: 15 or unchanged → frame dropped, error counter +1 (sat 3); else step (mod 15, max 3) saved; last 0x4046CC hi nibble, counter 0x4046C8 b7:6 |
| 0x07BB5A | `can_rx_0A8_state` | med-high | 0/1 → 0x40114F b6:5 = 00, 2 → 10, 3 → 01 (+ timer 0x4046EB = 50); ≥ 4 invalid (0x401151/54 b5:4) |
| 0x07BBDE | `can_rx_0A8_flag` | med-high | 0/1 → 0x40114F b4; 2/3 invalid (0x401151/54 b2) |
| 0x07BC1A | `can_rx_0A8_event` | med-high | ≠ 0 starts 50-cycle timer 0x4046EC; 0 clears it (0xFF) |
| 0x07CEE8 | `can_rx_0A8_timeout` | med-high | after 50 × 10 ms: DTC D354 via 0xBF994: checksum errors ≥ 3 → 0x2002, alive errors ≥ 3 → 0x2001, else (unless PT bus-off 0xA0002) 0x2000 timeout. Reported only if 0x40116 |
| 0x07CC58 / 0x07CCAE | `dme_pedal_fault_report` / `dme_rpm_fault_report` | high | 5E1A (id 0x201A, mask 0x10400, fault 0xA0020); called from 0x7E7A4 when timers 0x4046EA / 0x4046ED expire |
| 0x07CC7A | `dme_torque_not_adjustable_report` | high | 5E19 (id 0x2018, fault 0xB0040); timer 0x4046EB, started by 0x0A8 3.0–3.3 = 3 |
| 0x07CC94 | `dme_msg_implausible_report` | high | 5E18 (id 0x201B, fault 0xB0010); timer 0x4046EC, started by 0x0A8 6.4–6.5 ≠ 0 |
| 0x07D16A | `pedal_at_most(thr)` | high | 1 if pedal 0x401142 ≤ thr (thr = 0xFF: pedal = 0); no validity check. Callers: ABS 0x4EDD6 (only when 0x408DC6 b6 clear), LVC 0xC3FE0, TCS 0xCE02E/0xCE50A/0xCE6EA |
| 0x0C2CB8 | `lvc_driveoff_torque_model` | med | hill-start: rpm 0x40113E × 50/100 vs table 0x422F8[f+9], engine torque 0x401146 × 10 → 0x402C80/0x402D30. Release logic not traced |
| 0x0C0DAE | `lvc_param_init` | low | copies f+0 → 0x402DAA (never read), f+9 → 0x402DAC, f+2 → 0x402DAE and the f+9-indexed rows of 0x422F8 / 0x4233A / 0x4237A → 0x402DB0… (called from 0xC23E8) |
| 0x0C27E6 | `lvc_condition_eval` | med | sets LVC condition bits 32–42 via `lvc_condition_set`; bit 40 = `engine_rpm` × 50/100 ≥ 0xF587E[f+10] (5000 / 5500 / 6000 / 6500, also sets 0x402BF8 = 500). Called from 0xC1784 |
| 0x0C2450 | `void lvc_condition_set(s16 n)` | high | sets bit n of the 48-bit LVC condition field 0x402D50 / 0x402D52 / 0x402D54 |
| 0x004028A5 | `engine_running` (b7) | med | b7 = rpm 0x40113E ≥ 720 (0xB5E3C; ≈ 360 rpm if 0.25 rpm/bit raw); read by the supervisor / lamp code 0xB5E3C–0xB61D8 |
| 0x07D656 | `can_rx_0A9_checksum` | med-high | checksum: byte = low8(Σ payload + id) as `can_tx_checksum8` (byte zeroed first). Mismatch → frame dropped (0x401174[i] b7 cleared), error counter +1 (sat 3), signals mark |
| 0x07BC32 | `can_rx_0A9_alive` | med-high | 4-bit alive counter: 15 or unchanged → frame dropped, error counter +1 (sat 3); else step (mod 15, max 3) saved; counter 0x4046C8 b3:2 |
| 0x07CF3E | `can_rx_0A9_timeout` | med-high | after 500 ms: D355 (0x2005 checksum / 0x2004 alive / 0x2003 timeout) |
| 0x07D562 | `can_rx_0AA_checksum` | med-high | checksum: byte = low8(Σ payload + id) as `can_tx_checksum8` (byte zeroed first). Mismatch → frame dropped (0x401174[i] b7 cleared), error counter +1 (sat 3), signals mark |
| 0x07BD44 | `can_rx_0AA_alive` | med-high | 4-bit alive counter: 15 or unchanged → frame dropped, error counter +1 (sat 3); else step (mod 15, max 3) saved; counter 0x4046C9 b7:6 |
| 0x07BEEA | `can_rx_0AA_rpm_error` | med-high | 0x4046D8 b4 = (value ≠ 0); when set, the rpm signal is treated as invalid |
| 0x07BFD8 | `can_rx_0AA_nibble` | med-high | 4-bit value → u32 0x40470C (15 → stored as 8) |
| 0x07CF94 | `can_rx_0AA_timeout` | med-high | after 500 ms: D356 (0x2008 / 0x2007 / 0x2006) |
| 0x07D4A6 | `can_rx_0BA_checksum` | med-high | checksum in byte 5 (same scheme). Only when 0x40114D ≠ 0 (automatic/DCT coded) and 0x401151 b7 clear |
| 0x07BFF8 | `can_rx_0BA_alive` | med-high | 4-bit alive counter: 15 or unchanged → frame dropped, error counter +1 (sat 3); else step (mod 15, max 3) saved |
| 0x07C08A | `can_rx_0BA_flag` | med-high | value < 2 → 0x4010FA b7; else invalid (0x4010FB/FC b5). Gated like the gear |
| 0x07C226 | `can_rx_0BA_flag2` | med-high | value < 2 → 0x4046D9 b2; else 0x4046D9 b1 (invalid) |
| 0x07CDD8 | `can_rx_0BA_timeout` | med-high | after 500 ms: D357 (0x200B / 0x200A / 0x2009) |
| 0x07C24C | `can_rx_130_gateway` | med-high | copies the 8 payload bytes and passes them to 0x7A3A8 (re-sent; F-CAN TX 0x130 exists) |
| 0x07D404 | `can_rx_130_checksum` | med-high | checksum compared with byte 4 high nibble (0x7D24C over 4 bytes; byte 4 low nibble kept). Mismatch → frame dropped, counter 0x4046CA b5:4, 0x4046D4 b2/b0 (terminals inval |
| 0x07C282 | `can_rx_130_alive` | med-high | 4-bit alive counter: 15 or unchanged → frame dropped, error counter +1 (sat 3); else step (mod 15, max 3) saved |
| 0x07C2F6 | `can_rx_130_kl_a` | med-high | 2-bit: 1 → 0x4046D4 b1 = 1, 0 → 0; 2/3 → 0x4046D4 b0 (invalid). Used by 0x19E byte 5 (BLS state valid only when this = 1). Probably terminal R (inferred) |
| 0x07C328 | `can_rx_130_kl_b` | med-high | 2-bit: 1 → 0x4046D4 b3, 2/3 → b2 invalid. Then 0x401130 = 4 if this is on, 3 if sig 164 is on, else 0; 0x401134 b7 = invalid. Probably terminal 15 (inferred) |
| 0x07C38E | `can_rx_130_kl_c` | med-high | 2-bit: 1 → 0x40114F b2; ≥ 2 → invalid (0x401152/55 b3). Probably terminal 50 / crank (inferred) |
| 0x07CE44 | `can_rx_130_timeout` | med-high | after 500 ms: D35A (0x2010 checksum / 0x200F alive / 0x200E timeout); terminal state invalid |
| 0x07CFFC | `can_rx_1A3_timeout` | med-high | after 100 ms: sets 0x4046D8 b3 only. The signal itself is a stub (ACC not used) |
| 0x07C904 | `can_rx_226_nibble` | med-high | 4-bit → 0x404709 (15 = invalid → 0x4046D8 b7). Reloads the software timeout 0x4046F8 = 4000 |
| 0x07C932 | `can_rx_226_state` | med-high | u16 combined with 0x404709 into 0x401111 b7:5: 0 if either is 0, 2 if 0x404709 < 5, else 3; b1 = invalid |
| 0x07C974 | `can_rx_226_byte0` | med-high | u8 → u32 0x404714; 0xFF → invalid (0x404718 b5) |
| 0x07C85A | `can_rx_2E4_trailer` | med-high | 2-bit trailer status (D377 text: "Status_Anhaenger"): 3 = invalid (0x401116/18 b7); else 0x401115 b7 = bit 0. Reloads software timeout 0x4046F4 = 2500; on expiry 0x7D0D4 |
| 0x07D2B4 | `can_rx_308_checksum` | med-high | 4-bit checksum in byte 0 low nibble. Status MSA (D379) |
| 0x07C99C | `can_rx_308_alive` | med-high | 4-bit alive counter: 15 or unchanged → frame dropped, error counter +1 (sat 3); else step (mod 15, max 3) saved |
| 0x07CB26 | `can_rx_308_s1_0` | med-high | 2-bit; stored only if 0xCFD8C ≠ 0 (coding flag word 0x4031F6 bit 7, likely MSA coded): 1/2 → u32 0x404744; else invalid (0x404748 b5) |
| 0x07CAD6 | `can_rx_308_s1_2` | med-high | 2-bit, MSA-gated: 0..2 → 0x40473C; 3 invalid |
| 0x07CAAC | `can_rx_308_s1_4` | med-high | 2-bit, MSA-gated: 1/2 → 0x404734; else invalid |
| 0x07CA7E | `can_rx_308_s1_6` | med-high | 2-bit, MSA-gated: 0..2 → 0x40472C; 3 invalid |
| 0x07CA5A | `can_rx_308_s2_0` | med-high | 2-bit: 1 → 0x404724 = 0, 2 → 1; else invalid (0x404728 b5) |
| 0x07CB50 | `can_rx_308_s2_2` | med-high | 2-bit, MSA-gated: 0..2 → 0x40474C; 3 invalid |
| 0x07CB7E | `can_rx_308_s2_4` | med-high | 4-bit, MSA-gated: → 0x404754; 15 invalid |
| 0x07D006 | `can_rx_308_timeout` | med-high | after 2.5 s: D379 (0x2033 timeout / 0x2034 / 0x2035) plus resets of the MSA records; large handler, not fully traced |
| 0x07C824 | `can_rx_310_outside_temp` | med-high | u8 → 0x4046E0 (outside temperature, raw); 0xFF invalid (0x4046D8 b1, 0x401137 b6) |
| 0x07C7C8 | `can_rx_310_rel_time` | med-high | bytes 1–4 → u32 0x401128 (relative time); all 0xFF invalid (0x40112C b7). Reloads software timeout 0x4046F2 = 500; on expiry 0x7D09C raises D358 (0x200C) |
| 0x07C75E | `can_rx_316_state` | med-high | 2-bit → 0x401108 b7:5: 0 → 000, 1 → 001, else 011 + b1 invalid (same encoding as 0x3B0) |
| 0x07C79A | `can_rx_319_state` | med-high | 2-bit → 0x404830 b7:6, also passed through the 0x398 handler |
| 0x07C89A | `can_rx_330_mileage` | med-high | bytes 0–2 (24-bit) → 0x4046DC (odometer); 0xFFFFFF invalid (0x4046D4 b7, 0x401137 b7). Reloads software timeout 0x4046F6 = 5000; on expiry 0x7D0E6 raises D359 (0x200D) |
| 0x07C636 | `can_rx_380_vin` | med-high | 7 VIN bytes: all 0xFF → invalid (0x4046D6 b3, 0x4046D7 b7). Else compared with the stored copy 0x4047FD[7] (mismatch → 0x4046D5 b0) and copied to 0x4047F6[7]. VIN DTCs D3 |
| 0x07C450 | `can_rx_398_s0_4` | med-high | 2-bit request for driver-mode slot 1: 1 → 0x401139 b3:2 = 2 + received flag 0x40113B b3:2 → slot-1 state 10; other non-zero → invalid (0x40113A b5). Slot meaning not identified |
| 0x07C3DC | `can_rx_398_dsc_mode` | high (code) | **DSC driver-mode request**, 0x398 byte 1 bits 2–4: 0 → DSC on, 1 → DSC off, 4 → MDM (via 0x401139 b5:4 and `can_mode_request_apply` 0x8D70A); other values invalid (0x40113A b6) |
| 0x07D3BE | `can_rx_399_checksum` | med-high | 4-bit checksum (byte 0 low nibble) |
| 0x07C4E6 | `can_rx_399_alive` | med-high | 4-bit alive counter: 15 or unchanged → frame dropped, error counter +1 (sat 3); else step (mod 15, max 3) saved |
| 0x07C51E | `can_rx_399_s1_0` | med-high | 2-bit → 0x40483B |
| 0x07C524 | `can_rx_399_s1_2` | med | 3-bit; only with terminal 15 on 0x130 (0x4046D4 & 0x0C = 8). With 0x40483B and toggle state 0x4046BC, writes the same driver-mode request bytes 0x401139–0x40113B as 0x398. Toggle logic not fully traced |
| 0x07AB08 | `can_rx_797_payload` | med-high | DLC 1. 0x401164 = 0xFFFF; if 0xAF78C(1,0,0) = 4 → 0x7A686(payload). Not traced further |
| 0x07CBE4 | `can_rx_480_nm` | med-high | OSEK NM (id 0x480 + node, mask 0x780). Ignores its own 0x4A9; stores the sender node in 0x404841 and runs 0x7FB8A |
| 0x07E4D6 | `can_rx_580_nm` | med-high | NM / node messages 0x580–0x5FF (mask 0x780); large handler 0x7E4D6, not traced |
| 0x0C5948 | `fcan_rx_cluster_checksum` | med-high | checksum in byte 7 (0xC72B8). Mismatch → frame invalid (0x402EE5[i] b7), per-frame error counter in 0x402F39/0x402F3A, sat 3. Shared by 0x0CD / 0x0D1 / 0x0D4 |
| 0x0C59FE | `fcan_rx_0CD_alive` | med-high | 4-bit alive; unchanged → invalid + counter 0x402F39 b5:4. Ignored during start-up (0x400966 b6). Last value 0x402F28 |
| 0x0C5A5E | `fcan_rx_0CD_q1` | med-high | 2-bit → 0x402E4E b5:4 (qualifier) |
| 0x0C5A4C | `fcan_rx_0CD_q0` | med-high | 2-bit → 0x402E4E b7:6 (qualifier) |
| 0x0C6D8E | `fcan_rx_0CD_timeout` | med-high | after 100 ms: D370 via 0xBFA2A(reason, 0xA1000): 4 checksum → 0x3002, 2 alive → 0x3001, 1 timeout → 0x3000 |
| 0x0C5A72 | `fcan_rx_0D1_alive` | med-high | 4-bit alive, counter 0x402F39 b1:0; last 0x402F29 |
| 0x0C5AD0 | `fcan_rx_0D1_q1` | med-high | 2-bit → 0x402E4E b1:0 |
| 0x0C5ABC | `fcan_rx_0D1_q0` | med-high | 2-bit → 0x402E4E b3:2 |
| 0x0C6DBA | `fcan_rx_0D1_timeout` | med-high | after 100 ms: D371 (0x3005 / 0x3004 / 0x3003) |
| 0x0C5B9C | `fcan_rx_0C9_alive` | med-high | 4-bit alive (15 invalid) with error counter; status into 0x402E6D / 0x40164E |
| 0x0C5E4A | `fcan_rx_0C9_q5` | med-high | 2-bit → 0x402F36 b5:4 |
| 0x0C5E74 | `fcan_rx_0C9_mux` | med-high | 4-bit multiplexer index → 0x402F3D; selects how sig 41 is read |
| 0x0C5E7A | `fcan_rx_0C9_mux_data` | med-high | 16-bit multiplexed payload; 13-way jump table 0xC5EC8 on the mux index. Includes the steering-sensor error codes that map to DTCs 94B0–94C9; not traced further |
| 0x0C5C18 | `fcan_rx_0C9_angle_rate` | med-high | 16-bit: bits 13..0 sign-folded and scaled → u32 0x402E70 (steering angle rate, inferred); bits 15:14 → 0x402F54 b4:3 (status) |
| 0x0C5E20 | `fcan_rx_0C9_angle_status` | med-high | 2-bit: 0/1 mapped through table 0xF58C0, ≥ 2 → 3; → 0x40164D b7:6 (angle status read by `steering_angle_init_monitor`) |
| 0x0C62EC | `fcan_rx_0C9_q2` | med-high | 2-bit → 0x402F53 b3:2 |
| 0x0C6E18 | `fcan_rx_0C9_timeout` | med-high | after 100 ms: D373 ("SWA-Top-Sensor 200 or 201"; 0x300B / 0x300A / 0x3009). Sets 0x40164E b1–b3, 0x402E6D b7 (→ b5), 0x402E6E b7. Reports only while 0x402F35 b4; the D373 report carries fault id **0xA0040** (→ `fault_set` via 0xB484A). Second report from 0x402F53 b3:2 = 1/2 → mask 0x40400 / 0x40800 (not traced). Effect: steering, lateral and yaw all invalid (FACTS "Steering-sensor loss") |
| 0x0C5AE2 | `fcan_rx_0D4_alive` | med-high | 4-bit alive, counter 0x402F3A; last 0x402F2A |
| 0x0C5B30 | `fcan_rx_0D4_status` | med-high | 4-bit cluster status → 0x402E50: b7 = bit 0, b3 = bit 3, b2 = bit 1. 0x402E50 & 0x0C ≠ 0 makes yaw / lateral accel invalid (see 0x1A0 decode) |
| 0x0C6DEC | `fcan_rx_0D4_timeout` | med-high | after 100 ms: D372 (0x3008 / 0x3007 / 0x3006) |
| 0x0C5B60 | `fcan_rx_140` | med-high | u16 → 0x402E52; sets 0x402EDE b4 and 0x402E51 b6. Read by the cluster identity check 0xC70A0 |
| 0x0C5B82 | `fcan_rx_0C8_gateway` | med-high | when 0x402F49 b2 is set (one-shot): push to the F→PT gateway 0xC56D0 |
| 0x0C630A | `fcan_rx_2A6_byte0` | med-high | u8 with a large state machine (0xC630A, 3-bit field, faults incl. 0xB0400); not traced |
| 0x0C6D78 | `fcan_rx_78x_7Dx_flag` | med-high | sets 0x408D2C[frame index − 26] = 1 ("received" flag). Same handler for 0x78F/0x78E/0x7DC–0x7DF |
| 0x0794FC | `can_comm_state_update` | high | PT comm state 0x4015E4; sets/clears `can_dtc_enable` 0x401163 b4 (see CAN_RX_TABLE "ignition gate"); 0x4015E4 b3 = timeout counting enabled |
| 0x00401163 | `can_dtc_flags` (u8) | high | b4 = PT CAN DTC reporting enabled; b6/b7 set from diag routines (0x78FAC/0x78FCA), b7 = monitoring disabled by tester |
| 0x004015E8 | `can_rx_flags` (u8) | med | b4 = reporting suppressed: 0x40471C ≠ 0 or uptime 0x4046C0 ≤ 178 (written in 0x7E7A4) |
| 0x0040471C | `ign_on_delay_cnt` (u8) | high | reloaded to 75 while `ignition_on` is clear, then −1 per 10 ms |
| 0x004046C0 | `can_uptime_cnt` (u32) | high | +1 per 0x7E7A4 call (10 ms) |
| 0x00400956 | `power_flags` (u8) | med | b6 = ignition on (from 0x72020; set at start-up), b5 = 0x4009BC & 0x60 (supply inhibit, inferred), b2–b4 other supply bits |
| 0x072020 | `power_state_update` | high (code) | state 0x4009C0 (1/2 → 4 on, 5 off), counter 0x4009BE. Source by 0x4009FF b0: clear → `terminal_state` ∈ {4,5}; set → `hw_ign_input` 0x400958 b5 (counter +1 to 7 while on, −1 to 0 then off). Rewrites 0x4009FF b0 at the end of each pass |
| 0x004009FF | `ign_source_hw` (b0) | high | 1 = take ignition from the hardware input: 0x401134 b7 (`terminal_state` invalid: CAN init, 0x130 timeout) or (0x401162 b7 and previous b0) |
| 0x00400958 | `power_flags2` (u8) | med | **b5 = `hw_ign_input`** = NOT bit 8 of 0x4009C8 (0x72224). Bench: reads on with power only |
| 0x004009C8 | `wss_asic_status_rx`[1] (u16) | med | QSPI CS5 status word 1. b8 (inverted) → hardware ignition input; b3–b7 → supply flags 0x4009BC (0x72224) |
| 0x072224 | `power_inputs_update` | med | from 0x6FD7E (after the CS5 poll). 0x4009C8 bits → 0x4009BC b0/b1/b5/b6/b7, 0x400957 b0/b7, 0x400958 b5; fault 0x80002 on b7 |
| 0x0C4DD0 | `fcan_comm_state_update` | med | F-CAN gate flags 0x402EE0; 75-cycle delay 0x402EDD on 0x400956 & 0xA0. Writes **0x402F35 b4 = F-CAN fault reporting enabled** (0xC4F0E): 0x400956 b5/b7 clear, delay expired, 0x400966 b0 clear, 0x402F35 b3/b7 clear. No ignition term |
| 0x08E144 | `diag_routine_dispatch_a` | med | 20-way jump table on a command byte; among others toggles 0x401163 b7 (CAN monitoring off/on) and 0x401FE6 |

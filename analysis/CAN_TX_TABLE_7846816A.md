# CAN TX frame table — 7846816A (M3)

Decoded from the config tables (image `flash/bin/7846816A_00000000.bin`, CPU = file − 0x8000) and checked
against the packer code. PT-CAN header 0xD7F45 (20 TX), F-CAN header 0xF59C3 (14 TX).

## Record layout (as read by the TX code)

- **Message** (23 B, PT 0xD7F65 / F 0xF59DD): +2 u16 CAN id · +4 low nibble DLC · +5 b6 = send via the shared
  mailbox-3 software queue (0x40157C → 0x40146C) · +6 period ×10 ms (0xFF = event) · +10 n_signals ·
  +11 u16 first signal · +13 mailbox.
- **Signal** (5 B, PT 0xD839E / F 0xF5CBD; base = hdr+0x0D + u16 hdr+0x0C, index ×5):
  +0 b0..4 length · b5 flag (not read by the TX packer; not a sign flag) · **b6 pack mode** ·
  +1 low nibble start byte, high nibble start bit · +3 u16 variable id.
- **Variable** (8 B, PT 0xD88C0 / F 0xF5ED0): +0 b0..2 type · +1 default · +4 u32 handler.

## How a signal is packed

`can_tx_signal` 0x79798 (PT) / 0xC5070 (F) switches on variable type:

- **type 0**: `v = handler()`, then `can_pack_bits` 0x7A006 / 0xC548E(v, &payload[byte], bit, len, mode).
  The masks come from the table at 0xD7F16 / 0xF5892 (u16[len]). The routine shifts v and the mask left by
  `bit` and merges the low 8 bits into `payload[byte]`. The high 8 bits go to `payload[byte+1]` when
  mode = 0 (**Intel / little-endian**) and to `payload[byte−1]` when mode = 1 (**Motorola / big-endian**).
  Length is at most 16 bits. The mask table starts **0x400** (then 0x1, 0x3, …, 0xFFFF), so a length-0 signal is
  not a no-op: it copies value bit 10 into `payload[byte+1]` bit (bit+2), and writes nothing only when bit ≥ 6
  (the shifted mask leaves 16 bits). Every Intel signal also rewrites `payload[byte+1]` (unchanged when the mask
  fits one byte), so a signal at byte 7 touches the byte after the payload.
- **type 2**: `handler(payload)`. The handler writes raw bytes itself, so position, length and pack mode are
  not used (checksums, diag/raw frames).
  Signals are processed in table order, so a type-2 handler on a frame's last signal sees the fully packed
  payload and can overwrite any byte (how the stock checksums work, and the simplest way to repurpose a frame).
- **type 4** (PT and F): no call. The default value is latched into 0x40161C / 0x402F05 once the message
  is TX-confirmed. F-CAN also has **type 1** (direct RAM read through +4) and **type 3** (+4 is a constant).
  No TX signal uses types 1, 3 or 4 in this image.

## Frames suppressed at run time [C, bench-confirmed for 0x0BF / 0x0E1]

A frame is sent when its counter `0x4015F8[i]` reaches the period (+6). `0x7E7A4`, called every CAN cycle from
`can_stack_cycle` 0x793FC **before** the scheduler, zeroes some counters, so those frames never come due:

| frame (index) | store | condition |
|---|---|---|
| 0x0E1 (2) | 0x7E85E `st.b r6,(r7,2)` | `coded_feature(2)` ≠ 1, which is **always** in this image (jump-table case 0xCF548 returns 0) |
| 0x0BF (4) | 0x7E8C6 `st.b r6,(r7,4)` | **unconditional** |
| 0x1A3 (8) | 0x7E912 `st.b r6,(r7,8)` | 0x4046D4 b3 clear |
| 0x2B3 (11) | 0x7E906 `st.b r6,(r7,11)` | ax getter `0x9390E(3)` status b6 clear |

So 7846816A never transmits 0x0BF or 0x0E1 (confirmed on a bench unit; 0x1A3 and 0x2B3 were present there). The
patcher's 0x0BF / 0x0E1 patches replace those stores with `mov r6,r6` (0x1266).

The payload is pre-filled with 0xFF before packing. Every TX signal that uses the packer is Intel; the only
two signals with the Motorola bit set are type-2 frames on 0x798, where the bit has no effect.
F-CAN 0x797/0x798/0x790/0x791/0x7D4–0x7D8 have 0 signals (payload comes from elsewhere).

Handler column = the function the TX path calls. Symbol/notes come from `7846816A_symbols.md`, the ghidra
symbol file and `agents/m3cansig/cb_summary.txt`. "const"/"reads" notes are only given for trivial getters.

#### PT-CAN 0x0C4  DLC 7  10 ms  mbox 0

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.0 | 16 | Intel (LE) | 0x052 | 0 value getter | 0x07B6D4 | can_tx_0C4_steer_angle |  |
| 1 | 2.0 | 2 | Intel (LE) | 0x053 | 0 value getter | 0x07B6E8 |  |  |
| 2 | 3.0 | 16 | Intel (LE) | 0x054 | 0 value getter | 0x07B714 |  |  |
| 3 | 5.0 | 8 | Intel (LE) | 0x02E | 0 value getter | 0x07B728 |  |  |
| 4 | 6.0 | 2 | Intel (LE) | 0x05E | 0 value getter | 0x07B72C |  | const 1 |
| 5 | 6.2 | 2 | Intel (LE) | 0x02F | 0 value getter | 0x07B730 |  | const 0 |

#### PT-CAN 0x0CE  DLC 8  20 ms  mbox 1

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 6 | 0.0 | 16 | Intel (LE) · b5 | 0x061 | 0 value getter | 0x07AB8C | can_tx_0CE_wheelspeed_0 | FL wheel speed (wheel 0, 0x40BF1A) ×4/25 → s16, 1/16 km/h; negative in reverse; 0x8000 invalid — see 0x0CE section |
| 7 | 2.0 | 16 | Intel (LE) · b5 | 0x062 | 0 value getter | 0x07ABE8 | can_tx_0CE_wheelspeed_1 | FR wheel speed (wheel 1, 0x40BF5A) ×4/25 → s16, 1/16 km/h; negative in reverse; 0x8000 invalid — see 0x0CE section |
| 8 | 4.0 | 16 | Intel (LE) · b5 | 0x063 | 0 value getter | 0x07AC42 | can_tx_0CE_wheelspeed_2 | RL wheel speed (wheel 2, 0x40BF9A) ×4/25 → s16, 1/16 km/h; negative in reverse; 0x8000 invalid — see 0x0CE section |
| 9 | 6.0 | 16 | Intel (LE) · b5 | 0x064 | 0 value getter | 0x07AC9E | can_tx_0CE_wheelspeed_3 | RR wheel speed (wheel 3, 0x40BFDA) ×4/25 → s16, 1/16 km/h; negative in reverse; 0x8000 invalid — see 0x0CE section |

#### PT-CAN 0x0E1  DLC 6  20 ms  mbox 2

DBC name: brake wheel torque ("Radmoment Bremse"). This image sends only the alive counter and checksum; every value field is all-ones (not available).

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 10 | 1.0 | 4 | Intel (LE) | 0x016 | 0 value getter | 0x07B734 |  | alive counter 0x4010DF low nibble, 0..14 wrap |
| 11 | 1.4 | 12 | Intel (LE) | 0x066 | 0 value getter | 0x07B75C |  | const 0xFFF (not available) |
| 12 | 3.0 | 16 | Intel (LE) | 0x065 | 0 value getter | 0x07B758 |  | const 0xFFFF (not available) |
| 13 | 5.0 | 2 | Intel (LE) | 0x03B | 0 value getter | 0x07B760 |  | const 3 |
| 14 | 5.2 | 3 | Intel (LE) | 0x040 | 0 value getter | 0x07B764 |  | const 7 |
| 15 | 5.5 | 3 | Intel (LE) | 0x044 | 0 value getter | 0x07B768 |  | const 7 |
| 16 | 0.0 | 8 | raw | 0x072 | 2 payload writer | 0x07D802 |  | checksum: can_tx_checksum8(DLC, id) 0x7D24C |

#### PT-CAN 0x0B6  DLC 5  20 ms  mbox 3 · via TX queue (+5 b6)

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 17 | 1.0 | 4 | Intel (LE) | 0x014 | 0 value getter | 0x07AB5E |  |  |
| 18 | 1.4 | 12 | Intel (LE) · b5 | 0x05D | 0 value getter | 0x07AB58 | can_tx_0B6_sig18 | reads 0x4046E6 |
| 19 | 3.0 | 12 | Intel (LE) · b5 | 0x05C | 0 value getter | 0x07AB52 | can_tx_0B6_sig19 | reads 0x4046E8 |
| 20 | 4.4 | 2 | Intel (LE) | 0x04F | 0 value getter | 0x07AB48 | can_tx_0B6_sig20 | reads 0x4046D4 (lsri r2,5; andi r2,3) |
| 21 | 4.6 | 2 | Intel (LE) | 0x02B | 0 value getter | 0x07AB82 |  | reads 0x408DB5 (lsri r2,2; andi r2,3) |
| 22 | 0.0 | 8 | raw | 0x070 | 2 payload writer | 0x07D886 |  | checksum: can_tx_checksum8 0x7D24C |

#### PT-CAN 0x0BF  DLC 5  20 ms  mbox 3 · via TX queue (+5 b6)

DBC name: drivetrain wheel torque (`torq_wheel_drivetrain`). This image sends only the alive counter and checksum; every value field is all-ones (not available).

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 23 | 1.0 | 4 | Intel (LE) | 0x013 | 0 value getter | 0x07F948 |  | alive counter 0x4010E1 low nibble, 0..14 wrap |
| 24 | 1.4 | 4 | Intel (LE) | 0x021 | 0 value getter | 0x07F96C |  | const 0xFFFF → 0xF (not available) |
| 25 | 2.0 | 16 | Intel (LE) | 0x068 | 0 value getter | 0x07F970 |  | const 0xFFFF (not available) |
| 26 | 4.0 | 4 | Intel (LE) | 0x03C | 0 value getter | 0x07F974 |  | const 0xFFFF → 0xF |
| 27 | 4.4 | 2 | Intel (LE) | 0x067 | 0 value getter | 0x07F978 |  | const 0xFFFF → 3 |
| 28 | 0.0 | 8 | raw | 0x06F | 2 payload writer | 0x07F97C |  | checksum: can_tx_checksum8 0x7D24C |

#### PT-CAN 0x193  DLC 8  event  mbox 3 · via TX queue (+5 b6)

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 29 | 0.4 | 4 | Intel (LE) | 0x011 | 0 value getter | 0x07F8D0 |  |  |
| 30 | 1.0 | 8 | Intel (LE) | 0x020 | 0 value getter | 0x07F8F4 |  |  |
| 31 | 2.0 | 2 | Intel (LE) | 0x05F | 0 value getter | 0x07F8F8 |  |  |
| 32 | 3.0 | 8 | Intel (LE) | 0x031 | 0 value getter | 0x07F8FC |  |  |
| 33 | 4.0 | 3 | Intel (LE) | 0x03F | 0 value getter | 0x07F900 |  |  |
| 34 | 5.0 | 3 | Intel (LE) | 0x022 | 0 value getter | 0x07F904 |  |  |
| 35 | 5.3 | 3 | Intel (LE) | 0x032 | 0 value getter | 0x07F908 |  |  |
| 36 | 6.0 | 8 | Intel (LE) | 0x028 | 0 value getter | 0x07F90C |  |  |
| 37 | 7.0 | 8 | Intel (LE) | 0x019 | 0 value getter | 0x07F910 |  |  |
| 38 | 0.0 | 4 | raw | 0x06B | 2 payload writer | 0x07F914 |  | checksum + alive (0x4010E1): can_tx_checksum8 0x7D24C |

#### PT-CAN 0x19E  DLC 8  20 ms  mbox 3 · via TX queue (+5 b6)

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 39 | 0.0 | 8 | Intel (LE) | 0x037 | 0 value getter | 0x07AEAA | can_tx_19E_status_flags | ST_CLCTR: 0x01 front in ABS cycle (0x408DA2 b7), 0x20 rear-only control (0x408DA0 b1) |
| 40 | 1.0 | 2 | Intel (LE) | 0x030 | 0 value getter | 0x07AD74 | can_tx_19E_abs_status | ABS status: 2 if ABS off (0x40288E b6) or (ABS lamp lamp0.b7 and ABS degraded 0x402880 b6), else 0 |
| 41 | 1.2 | 3 | Intel (LE) | 0x03E | 0 value getter | 0x07AF52 | can_tx_19E_dsc_status | DSC status enum: 2 failed, 6 init/sensor-system, 3 limited (steering-angle not valid/latched), 1 DSC-off lamp, 4 lamp0.b0 mode, 0 normal — see 0x19E section |
| 42 | 1.6 | 2 | Intel (LE) | 0x043 | 0 value getter | 0x07B050 |  | const 3 (2-bit 3 = not available) |
| 43 | 2.0 | 2 | Intel (LE) | 0x041 | 0 value getter | 0x07B014 |  | const 3 |
| 44 | 2.2 | 2 | Intel (LE) | 0x029 | 0 value getter | 0x07AD66 |  | const 3 |
| 45 | 2.4 | 4 | Intel (LE) | 0x012 | 0 value getter | 0x07ACFA | can_tx_19E_event_counter | 4-bit counter 0x4010DE, +1 (wraps 0..14) only when 0x4046D4 b4 is set; no setter of that bit found → appears frozen |
| 46 | 3.0 | 2 | Intel (LE) | 0x02C | 0 value getter | 0x07AD6A | can_tx_19E_torque_intervention | 0x402F6E b5 (tcs_torque_intervention_flag 0xCB708): AYC torque request or TCS active with large torque cut (latched) |
| 47 | 3.2 | 2 | Intel (LE) | 0x051 | 0 value getter | 0x07B05C | can_tx_19E_lvc_flag | 0x402BE8 == 1: hill-start-assist (LVC) condition from 0xC03EE: HSA state 1, driver pressure above threshold, abs(filtered ax) below gearbox limit |
| 48 | 3.4 | 2 | Intel (LE) | 0x03A | 0 value getter | 0x07AF4E |  | const 3 |
| 49 | 3.6 | 2 | Intel (LE) | 0x057 | 0 value getter | 0x07B066 |  | const 3 |
| 50 | 4.0 | 4 | Intel (LE) | 0x039 | 0 value getter | 0x07AF4A |  | const 14 |
| 51 | 4.4 | 2 | Intel (LE) | 0x046 | 0 value getter | 0x07B054 |  | const 3 |
| 52 | 4.6 | 2 | Intel (LE) | 0x047 | 0 value getter | 0x07B058 |  | const 3 |
| 53 | 5.0 | 2 | Intel (LE) | 0x038 | 0 value getter | 0x07AEFA | can_tx_19E_bls_state | brake-light switch: 0 off, 1 on, 2 BLS fault (0x90010), 3 invalid/not available; 3 unless CAN 0x130 byte0 bits0-1 = 1 |
| 54 | 5.2 | 2 | Intel (LE) | 0x01F | 0 value getter | 0x07AD62 |  | const 0 |
| 55 | 5.4 | 2 | Intel (LE) | 0x042 | 0 value getter | 0x07B018 | can_tx_19E_feature5_status | coded feature 5 (0xCF478(5)): 3 not coded, 2 unavailable (0x40288F b5, or lamp2.b3 & 0x402882 b4), else 0 |
| 56 | 5.6 | 2 | Intel (LE) | 0x036 | 0 value getter | 0x07ADA2 | can_tx_19E_brake_applied | 1 BLS on or any valid wheel pressure > 6 bar; 0 BLS off & pressures valid & none > 6 bar; 2 BLS invalid; 3 BLS off but no wheel pressure valid |
| 57 | 6.0 | 8 | Intel (LE) | 0x01A | 0 value getter | 0x07AD2A | can_tx_19E_driver_pressure | driver/master pressure 0x93F00(2) → 0x401FF8, ÷100 = bar, clamp 0..254, 0xFF on sensor fault |
| 58 | 7.0 | 8 | raw | 0x06E | 2 payload writer | 0x07D85C |  | checksum: can_tx_checksum8 0x7D24C |

#### PT-CAN 0x1A0  DLC 8  20 ms  mbox 3 · via TX queue (+5 b6)

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 59 | 1.4 | 3 | Intel (LE) | 0x050 | 0 value getter | 0x07B172 | can_tx_1A0_drive_direction | 0 standstill, 1 forward, 2 reverse, 3 moving/direction unknown, 7 invalid — see 0x1A0 section |
| 60 | 0.0 | 12 | Intel (LE) | 0x060 | 0 value getter | 0x07B1F2 | can_tx_1A0_vspeed | 0.1 km/h, mean of the two FRONT wheels (not vref), clamp 3000, 0xFFF when both fronts faulted |
| 61 | 2.0 | 12 | Intel (LE) · b5 | 0x00E | 0 value getter | 0x07B0AC | can_tx_1A0_ax | long. accel = filtered mean of FRONT wheel accelerations 0x40200E (0.01 g) ×4 → 0.0025 g ≈ 0.025 m/s² per bit; 0x800 when both fronts faulted. Not the accelerometer |
| 62 | 3.4 | 12 | Intel (LE) · b5 | 0x00D | 0 value getter | 0x07B06A | can_tx_1A0_ay | lateral accel 0x4020DA (1 mg, offset-corrected) ×803/2048 → 0.0250 m/s² per bit, clamp ±2047; 0x800 on sensor/cluster fault |
| 63 | 5.0 | 12 | Intel (LE) · b5 | 0x017 | 0 value getter | 0x07B104 | can_tx_1A0_yaw | yaw rate 0x4020F4 (1/20000 rad/s, offset-corrected, ±90 °/s) ×939/16384 → 0.0500 °/s per bit; 0x800 on sensor/cluster fault |
| 64 | 6.4 | 4 | Intel (LE) | 0x015 | 0 value getter | 0x07B0E0 | can_tx_1A0_alive_counter | 0x4010DC low nibble +1 per frame, 0..14 wrap |
| 65 | 7.0 | 8 | raw | 0x071 | 2 payload writer | 0x07D82C |  | checksum: can_tx_checksum8 0x7D24C |

#### PT-CAN 0x1A3  DLC 5  20 ms  mbox 3 · via TX queue (+5 b6)

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 66 | 0.0 | 12 | Intel (LE) | 0x02D | 0 value getter | 0x07B906 | can_tx_1A3_ax_raw | accelerometer (cluster sig 5) RAW 0x404A00 (`ax_signal_get(3)`; unfiltered, no offset correction; 1 mg inferred) ×251/256 → 0.01 m/s²/bit, signed, clamp ±2047; 0x800 invalid |
| 67 | 1.4 | 12 | Intel (LE) | 0x027 | 0 value getter | 0x07B96E | can_tx_1A3_ax_offset | learned ax zero offset 0x4049FD (`ax_signal_get(2)`; s8, 2 mg, ±119) ×251/128 → 0.01 m/s²/bit, same scale as sig 66 (corrected ax = sig 66 − sig 67), signed, clamp ±2047; 0x800 invalid. Not a low-passed accel |
| 68 | 3.0 | 2 | Intel (LE) | 0x049 | 0 value getter | 0x07B9B2 |  |  |
| 69 | 3.2 | 2 | Intel (LE) | 0x045 | 0 value getter | 0x07B9F0 |  |  |
| 70 | 3.4 | 4 | Intel (LE) | 0x010 | 0 value getter | 0x07BA1C |  |  |
| 71 | 4.0 | 8 | raw | 0x06D | 2 payload writer | 0x07D7AE |  | checksum: can_tx_checksum8 0x7D24C |

#### PT-CAN 0x1A6  DLC 8  100 ms  mbox 3 · via TX queue (+5 b6)

Wheel-tick odometry. `0x7F22C` adds per-wheel tick deltas into u16 accumulators 0x4046FE (a rear wheel, by
0x400952 status), 0x404700 (wheel 0) and 0x404702 (wheel 1) while 0x4046D7 b6 is set, and counts u8 0x404704 up to 255;
`0x7F88C` zeroes them. Each getter returns 0xFFFF when its wheel's 0x400952 b0 or 0x40288C b2 is set. The getters
have side effects: sig 75 sets 0x4046D7 b6 (enables the accumulation) and sig 72 resets 0x4046FE on a 0x4046D7 b6 /
0x4046D9 b0 handshake. The 0x1A6 getters are the only readers of the accumulators found.

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 72 | 0.0 | 16 | Intel (LE) | 0x023 | 0 value getter | 0x07B2B4 |  | rear tick accumulator 0x4046FE (reset handshake, see above) |
| 73 | 2.0 | 16 | Intel (LE) | 0x024 | 0 value getter | 0x07B2FA |  | wheel-0 tick accumulator 0x404700 |
| 74 | 4.0 | 16 | Intel (LE) | 0x025 | 0 value getter | 0x07B32C |  | wheel-1 tick accumulator 0x404702 |
| 75 | 6.0 | 12 | Intel (LE) | 0x026 | 0 value getter | 0x07B34E |  | sets 0x4046D7 b6; 12-bit value from 0x404704 × 40 and 0x404706 (time base, not fully decoded) |

#### PT-CAN 0x2B2  DLC 8  20 ms  mbox 3 · via TX queue (+5 b6)

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 76 | 0.0 | 8 | Intel (LE) | 0x01B | 0 value getter | 0x07B490 |  |  |
| 77 | 1.0 | 8 | Intel (LE) | 0x01C | 0 value getter | 0x07B4DE |  |  |
| 78 | 2.0 | 8 | Intel (LE) | 0x01D | 0 value getter | 0x07B51C |  |  |
| 79 | 3.0 | 8 | Intel (LE) | 0x01E | 0 value getter | 0x07B566 |  |  |
| 80 | 4.0 | 2 | Intel (LE) | 0x056 | 0 value getter | 0x07B5A4 |  |  |
| 81 | 4.2 | 2 | Intel (LE) | 0x055 | 0 value getter | 0x07B5E0 |  |  |
| 82 | 4.4 | 12 | Intel (LE) · b5 | 0x018 | 0 value getter | 0x07B692 |  |  |
| 83 | 6.0 | 2 | Intel (LE) | 0x04A | 0 value getter | 0x07B610 |  | const 0 |
| 84 | 6.2 | 3 | Intel (LE) | 0x04B | 0 value getter | 0x07B614 |  |  |
| 85 | 6.5 | 3 | Intel (LE) | 0x035 | 0 value getter | 0x07B63E |  | const 0 |
| 86 | 7.0 | 2 | Intel (LE) | 0x048 | 0 value getter | 0x07B642 |  |  |
| 87 | 7.3 | 2 | Intel (LE) | 0x03D | 0 value getter | 0x07B668 |  |  |
| 88 | 7.5 | 3 | Intel (LE) | 0x04D | 0 value getter | 0x07B68E |  | const 0 |

#### PT-CAN 0x2B3  DLC 5  50 ms  mbox 3 · via TX queue (+5 b6)

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 89 | 1.4 | 12 | Intel (LE) | 0x00C | 0 value getter | 0x07B7F4 | can_tx_2B3_ax_raw | same source as 0x1A3 sig 66 (raw 0x404A00) ×201/512 **+2048** (offset binary) → 0.025 m/s²/bit, clamp 0..4095; 0xFFF invalid |
| 90 | 3.0 | 12 | Intel (LE) | 0x00B | 0 value getter | 0x07B83C | can_tx_2B3_ax_offset | same source as 0x1A3 sig 67 (learned ax offset 0x4049FD) ×201/256 +2048 → 0.025 m/s²/bit, same scale as sig 89; clamp 0..4095; 0xFFF invalid |
| 91 | 4.4 | 2 | Intel (LE) | 0x033 | 0 value getter | 0x07B8B6 | can_tx_2B3_ax_status | `ax_signal_get(3)` out[3]: b5 or b6 → 2 (invalid), else 0. 1 needs b2 clear, which this path never produces |
| 92 | 1.0 | 4 | Intel (LE) | 0x00F | 0 value getter | 0x07B8E2 | can_tx_2B3_alive | alive counter 0..14, 0x40471D low nibble |
| 93 | 0.0 | 8 | raw | 0x06C | 2 payload writer | 0x07D7D8 |  | checksum: can_tx_checksum8 0x7D24C |

#### PT-CAN 0x31D  DLC 2  event  mbox 3 · via TX queue (+5 b6)

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 94 | 0.0 | 3 | Intel (LE) | 0x04C | 0 value getter | 0x07B76C |  | reads 0x40482E (lsri r2,5; andi r2,7) |
| 95 | 0.3 | 5 | Intel (LE) | 0x034 | 0 value getter | 0x07B776 |  | reads 0x40482E (andi r2,31) |
| 96 | 1.0 | 2 | Intel (LE) | 0x02A | 0 value getter | 0x07B77E |  | reads 0x40482E (lsri r2,2; andi r2,3) |

#### PT-CAN 0x374  DLC 5  1000 ms  mbox 3 · via TX queue (+5 b6)

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 97 | 0.0 | 8 | Intel (LE) · b5 | 0x058 | 0 value getter | 0x07B3B8 |  |  |
| 98 | 1.0 | 8 | Intel (LE) · b5 | 0x059 | 0 value getter | 0x07B3E4 |  |  |
| 99 | 2.0 | 8 | Intel (LE) · b5 | 0x05A | 0 value getter | 0x07B438 |  |  |
| 100 | 3.0 | 8 | Intel (LE) · b5 | 0x05B | 0 value getter | 0x07B464 |  |  |
| 101 | 4.0 | 2 | Intel (LE) | 0x04E | 0 value getter | 0x07B3A0 |  |  |

#### PT-CAN 0x4A9  DLC 8  event  mbox 3 · via TX queue (+5 b6)

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 102 | 0.0 | 1 | raw | 0x074 | 2 payload writer | 0x07B788 |  | copies 8 B from 0x404854 |

#### PT-CAN 0x5A9  DLC 8  event  mbox 3 · via TX queue (+5 b6)

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 103 | 0.0 | 1 | raw | 0x076 | 2 payload writer | 0x07B7D0 |  | copies 8 B from 0x40475C+1 |

#### PT-CAN 0x629  DLC 8  event  mbox 3 · via TX queue (+5 b6)

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 104 | 0.0 | 1 | raw | 0x073 | 2 payload writer | 0x07B7AC | can_tx_629_diagresp_cb | copies 8 B from 0x404849 (diag response, addr 0x29) |

#### PT-CAN 0x798  DLC 8  event  mbox 3 · via TX queue (+5 b6)

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 105 | 0.0 | 0 | raw (Motorola bit set, unused) | 0x069 | 2 payload writer | 0x07AAA8 |  | copies 8 B from 0x4046A8+6 |
| 106 | 0.0 | 0 | raw (Motorola bit set, unused) | 0x06A | 2 payload writer | 0x07AACC |  | tail-calls 0x7A9FC(0, payload) |

#### PT-CAN 0x111  DLC 8  event  mbox 4 · via TX queue (+5 b6)

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 107 | 0.0 | 1 | raw | 0x075 | 2 payload writer | 0x07BA40 |  | stub (bare return) — payload stays 0xFF |

#### F-CAN 0x080  DLC 5  event  mbox 0

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.0 | 16 | Intel (LE) | 0x00C | 0 value getter | 0x0C6A14 |  | const 0 |
| 1 | 2.0 | 1 | Intel (LE) | 0x00D | 0 value getter | 0x0C6A18 |  | const 0 |

#### F-CAN 0x0CE  DLC 8  10 ms  mbox 1

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 2 | 0.0 | 16 | Intel (LE) | 0x008 | 0 value getter | 0x0C6A1C |  |  |
| 3 | 2.0 | 16 | Intel (LE) | 0x009 | 0 value getter | 0x0C6A78 |  |  |
| 4 | 4.0 | 16 | Intel (LE) | 0x00A | 0 value getter | 0x0C6B00 |  |  |
| 5 | 6.0 | 16 | Intel (LE) | 0x00B | 0 value getter | 0x0C6B5C |  |  |

#### F-CAN 0x11E  DLC 8  10 ms  mbox 2

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 6 | 0.0 | 5 | Intel (LE) | 0x013 | 0 value getter | 0x0C6CA0 |  |  |
| 7 | 1.0 | 5 | Intel (LE) | 0x014 | 0 value getter | 0x0C6D30 |  |  |
| 8 | 0.6 | 2 | Intel (LE) | 0x007 | 0 value getter | 0x0C6D5A |  | const 0 |
| 9 | 2.0 | 2 | Intel (LE) | 0x01C | 0 value getter | 0x0C6D68 |  | const 0 |
| 10 | 2.2 | 2 | Intel (LE) | 0x01B | 0 value getter | 0x0C6D6C |  | const 0 |
| 11 | 2.4 | 2 | Intel (LE) | 0x01A | 0 value getter | 0x0C6D70 |  | const 0 |
| 12 | 2.6 | 2 | Intel (LE) | 0x019 | 0 value getter | 0x0C6D74 |  | const 0 |
| 13 | 3.0 | 4 | Intel (LE) | 0x016 | 0 value getter | 0x0C6D5E |  | const 0 |
| 14 | 4.0 | 16 | Intel (LE) | 0x017 | 0 value getter | 0x0C6D62 |  | const 0 |
| 15 | 0.15 | 0 | raw | 0x018 | 2 payload writer | 0x0C6D66 |  | stub (bare return) |

#### F-CAN 0x130  DLC 5  event  mbox 3

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 16 | 0.15 | 0 | raw | 0x015 | 2 payload writer | 0x0C5766 |  | copies queued frame (desc 0x402ED8, idx 0x402F1B); 0x6D9CE |

#### F-CAN 0x374  DLC 5  1000 ms  mbox 4

| sig | pos (byte.bit) | len | pack mode | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 17 | 0.0 | 8 | Intel (LE) | 0x00E | 0 value getter | 0x0C6BB8 |  |  |
| 18 | 1.0 | 8 | Intel (LE) | 0x00F | 0 value getter | 0x0C6BE4 |  |  |
| 19 | 2.0 | 8 | Intel (LE) | 0x010 | 0 value getter | 0x0C6C10 |  |  |
| 20 | 3.0 | 8 | Intel (LE) | 0x011 | 0 value getter | 0x0C6C5C |  |  |
| 21 | 4.0 | 2 | Intel (LE) | 0x012 | 0 value getter | 0x0C6C88 |  |  |

## Frame 0x19E (StatusDSC) — signal decode

All positions Intel. Values are what the getter returns. Sources were traced to their writers. Names marked
(inferred) come from how a value is used, not from a BMW name.

| Byte.bit | Len | Getter | Value |
|---|---|---|---|
| 0.0 | 8 | `can_tx_19E_status_flags` 0x7AEAA | ST_CLCTR bitfield; see FACTS "ST_CLCTR". 0x01 front in ABS cycle, 0x02 TCS (0x402FC0 b4, or 0x402F6C b7 & 0x402F6D b3), 0x04 AYC torque (0x400B0A & 0xC0), 0x08 0x400DF4 b7, 0x10 0x402F6D b2, 0x20 rear-only control |
| 1.0 | 2 | `can_tx_19E_abs_status` 0x7AD74 | 2 = ABS off (fault-reaction 0x40288E b6), or ABS lamp on (lamp0.b7) with ABS degraded (0x402880 b6); else 0 |
| 1.2 | 3 | `can_tx_19E_dsc_status` 0x7AF52 | enum, first match wins: **2** DSC failed (0x40288E b2, or lamp0.b6 & 0x402880 b2) · **6** start-up / sensor system (0x400957 b5/b6/b7 or 0x400966 b6) · **3** steering angle not valid (0x40200A = 0) or the steering latch is set · **1** DSC-off lamp (lamp0.b5) · **4** lamp0.b0 (mode lamp, inferred DTC/M-mode) · **0** normal |
| 1.6 | 2 | 0x7B050 | const 3 |
| 2.0 | 2 | 0x7B014 | const 3 |
| 2.2 | 2 | 0x7AD66 | const 3 |
| 2.4 | 4 | `can_tx_19E_event_counter` 0x7ACFA | counter 0x4010DE, stepped (wraps 0..14) only when 0x4046D4 b4 is set; the getter clears the bit. No code sets b4, so the field likely stays at its start-up value (0x6FA66 restores it). Needs a bus capture |
| 3.0 | 2 | `can_tx_19E_torque_intervention` 0x7AD6A | 0x402F6E b5 from 0xCB708. Set when AYC requests torque (0x400B0A & 0xC0), or when TCS is active (0x402F6C b7) with a large torque cut: (0x402F7A − 0x402F7C) < ¾·0x402F72, or < ⅞·0x402F72 with 0x402FA0 ≥ 21 and 0x402F6C b6. Held while 0x402F6C b5 or its own previous value is set |
| 3.2 | 2 | `can_tx_19E_lvc_flag` 0x7B05C | 1 when 0x402BE8 = 1, else 0. 0x402BE8 comes from the LVC function 0xC03EE (cal in the LVC block). LVC is very likely the **hill-start assist**: its code reads the HSA-level coding f+9 (0xC0D44) and gates on coded feature 11 = hill-start (0xC0D5E). Conditions: cal 0x4213A ≠ 0, 0x402D24 b8, LVC state (0x402D1B b5:4) = 1, 0x402BB8 b2 clear, abs(0x402B5C) < cal 0x42140[gearbox f+2]·0.981 (150 → 147), and driver pressure 0x402BA8 above 0x402BEA = cal 0x4213C + 300·0x402BEE. 0x402B5C is filtered long. accel (0xC3D56: ax sensor or CAN, ×9.81, i.e. road slope at standstill). What the flag means within HSA (armed / holding) is unconfirmed |
| 3.4 | 2 | 0x7AF4E | const 3 |
| 3.6 | 2 | 0x7B066 | const 3 |
| 4.0 | 4 | 0x7AF4A | const 14 |
| 4.4 | 2 | 0x7B054 | const 3 |
| 4.6 | 2 | 0x7B058 | const 3 |
| 5.0 | 2 | `can_tx_19E_bls_state` 0x7AEFA | brake-light switch: 0 off, 1 on, 2 BLS fault (0x90010 latched), 3 invalid. Always 3 unless 0x4046D4 & 3 = 2 (CAN RX 0x130 byte 0 bits 0–1 = 1, setter 0x7C2F6) |
| 5.2 | 2 | 0x7AD62 | const 0 |
| 5.4 | 2 | `can_tx_19E_feature5_status` 0x7B018 | 3 when coded feature 5 is absent (0xCF478(5) ≠ 1). Otherwise 2 if 0x40288F b5, or lamp2.b3 & 0x402882 b4; else 0. Feature 5 = feature-word bit 4, set by the validator when coding byte 3 bit 2 = 0 (the bit the coding tool calls "brake fan control?"). Function not identified |
| 5.6 | 2 | `can_tx_19E_brake_applied` 0x7ADA2 | 1 when the BLS is on, or any valid wheel pressure (0x40499A[w], `wheel_pressure_get` 0x8D030) is > 6 bar. 0 when the BLS is valid and off and at least one wheel pressure is valid. 3 when the BLS is valid and off but no wheel pressure is valid. 2 when the BLS is invalid and no wheel is > 6 bar |
| 6.0 | 8 | `can_tx_19E_driver_pressure` 0x7AD2A | driver/master pressure 0x93F00(2) → 0x401FF8, ÷100 = bar, clamped 0..254, 0xFF when the getter's fault bits (out[3] & 0x60) are set |
| 7.0 | 8 | 0x7D85C | checksum, `can_tx_checksum8` 0x7D24C (Σ payload + id) |

**Inputs behind these signals**
- **Brake-light switch.** `bls_input_get` 0x6FE92 reads GPIO 0xDE0018 b0, latched into 0x4009F4 by 0x6FCAA. It
  returns −1 if 0x4009F6 b4 is clear or the global inhibit 0x4009BC b5 is set, otherwise 0/1. `bls_signal_get`
  0x94538 wraps it with validity bits and fault flags (ids 0x90010/20/40/80). It is a BLS because
  `bls_plausibility_monitor` 0xB7ABC latches "seen on with pressure 0x401FFC > 5 bar" and "seen off with < 4 bar".
- **Lamp vector.** 0x40165E is three bytes, built by `indicator_lamp_output_update` 0x812FA. While
  0x401661 b7:6 = 1 or b5 is set, `lamp_vector_read` returns the alternate vector 0x401658 (start-up lamp check).
  Function states are gathered by 0x80C46 into 0x401662+: [0] ABS state 0x4049EC, [1] DSC state 0x4049EF,
  [2] TCS 0xC7818, [3] 0xBEE54, [4] 0x9BDA6, [5] 0xAF78C(2), [6] 0x8D950, [7] 0x95FA6.
  - lamp0.b7 = ABS lamp: ABS state 3 or 4, or 0x400948 b1.
  - lamp0.b6 = DSC state 1, the failed state (0x400B37 b7:5 = 1 with 0x40287A b4 and 0x40288E b2).
  - lamp0.b5 = DSC-off lamp (handler 0x80CFE): DSC state 2/9 (or TCS state 7, or DSC state 4 with mode switch
    0x4049B4[0] = 0), and mode switch 0x4049B4[0] or 0x4049BC[0] ≠ 0.
  - lamp1.b7 = DSC intervening: DSC state 10–13 (AYC active, 0x64EB0) or 0x402FC1 b3.
  - lamp0.b0 (0x81020) = mode lamp, set from TCS state 8/10 or DSC state 6/12 with mode switch value 4.
  - lamp2.b3 (0x8115A) = feature 5 coded & 0x40287A b0 & 0x400956 b6.
- **ABS function state** 0x4049EC (`abs_function_state_update` 0x8D8C0): 1 initialising or coding invalid
  (0x400966 b6, 0x8E3FE), 2 OK, 3 warning (0x40287A b6), 4 off (0x40288E b6).
- **Fault-reaction masks.** 0x402880 (u32) and 0x40288E (u16) are rebuilt each cycle by
  `fault_reaction_matrix` 0xB567E from the fault latches and status flags. 0x402880 b6 is set where 0x40288E b6 is
  set, and on more conditions.
- **Steering.** 0x40200A = 1 only in state 2 of `steering_angle_init_monitor` 0xB97D4. That monitor uses F-CAN
  0x0C9 status 0x40164D and fault ids 0x1200xx. 0x402009 b6 is set in its fault state. The DSC-status latch
  0x4046D9 b3 = 0x402009 b6 && (vref 0x408DA8 > 18 km/h, or already latched).

## Frame 0x1A0 (Speed) — signal decode

All positions Intel. Bit 1.7 is not packed, so it stays 1 (the payload is pre-filled with 0xFF). The 12-bit
signed fields use 0x800 (−2048) as the invalid value. Internal LSBs are from FACTS "Cycle 7": yaw 1/20000 rad/s,
lateral 1 mg, wheel accel 0.01 g. CAN LSBs follow from the getter scale factors.

| Byte.bit | Len | Getter | Value |
|---|---|---|---|
| 0.0 | 12 | `can_tx_1A0_vspeed` 0x7B1F2 | vehicle speed, 0.1 km/h = mean of the two **front** wheels (FACTS "CAN 0x1A0 vehicle speed"). 0xFFF and 0x4015E8 b7 when both fronts are faulted; clamp 3000 (300.0 km/h); copy in 0x404720 |
| 1.4 | 3 | `can_tx_1A0_drive_direction` 0x7B172 | first match wins: **7** standstill detector invalid (`vehicle_standstill_get` 0xD3A1C(0) < 0) · **0** standstill (0x40328C b7) · if both fronts are direction-capable (0x4046D7 b3/b2), not faulted (0x400952[0/1] b0) and `wheel_direction_valid` 0xB973C(0/1): **1** both fronts report forward, **2** both report reverse, **3** they disagree · otherwise **2** if AYC's reverse flag 0x400B09 b3 is set, else **3** |
| 2.0 | 12 | `can_tx_1A0_ax` 0x7B0AC | longitudinal accel = 0x9390E(1) → 0x40200E × 4, clamp ±2047. 0x40200E (writer 0x8F2B0) = mean of the **front** wheel accelerations (rec+0x20, 0.01 g) over the unfaulted fronts, clamped ±1.00 g, then low-passed by `iir_blend_q8` 0x712FC: y = x + (y_prev − x)·248/256, i.e. a 1st-order IIR with α = 1/32 (time constant ≈ 32 calls). The filter is skipped (raw value stored) when the previous value was 0x8000. So 1 bit = 0.0025 g = 0.0245 m/s² (BMW's 0.025). 0x800 when both fronts are faulted (0x40200E = 0x8000). The accelerometer path (0x9390E(0) → 0x4049FC) is **not** used |
| 3.4 | 12 | `can_tx_1A0_ay` 0x7B06A | lateral accel = 0x93C96(1) → 0x4020DA × 803/2048 (truncated toward 0), clamp ±2047. 0x4020DA (writer 0x8FEE8) = conditioned ay 0x4020D6 minus the learned offset ÷100. 1 bit = 2.550 mg = 0.02502 m/s². 0x800 when the getter sets out[3] b5 or b6 (below) |
| 5.0 | 12 | `can_tx_1A0_yaw` 0x7B104 | yaw rate = 0x943E4(1) → 0x4020F4 × 939/16384, clamp ±2047. 0x4020F4 (writer 0x90982 @0x90AEE; zeroed at init by 0x9486E) = 0x4020F0 minus offset 0x4020F8 ÷10, clipped ±31415 (±90 °/s). 1 bit = 0.0500 °/s. 0x800 on b5/b6 as for ay |
| 6.4 | 4 | `can_tx_1A0_alive_counter` 0x7B0E0 | 0x4010DC low nibble +1 each frame, 14 → 0 (15 is skipped). Start value restored by 0x6F8BA (0x6FA5C). Unlike the 0x19E counter it is not gated |
| 7.0 | 8 | 0x7D82C | checksum, `can_tx_checksum8` 0x7D24C (Σ payload + id) |

**Validity of ay / yaw (getters 0x93C96 / 0x943E4, index 1).** out[3] b5|b6 (→ 0x800) is set when any of:
- the fault-reaction mask 0x402890 b2 (ay) / b3 (yaw) is set (sets b5 and b6);
- 0x402884 b5 (ay) / b7 (yaw) is set while 0x4029BE b2 (ay) / b3 (yaw) is clear;
- sensor-cluster status not OK: 0x402E50 & 0x0C ≠ 0, or 0x4009B9 b1 = 0 (0x70066), or 0x402E51 b7 = 0.
  0x402E50/51 are written by the F-CAN code (0xC5948 / 0xC6354 / 0xC70A0); the cluster sends on F-CAN 0x0CD/0x0D1.
- **Not** on `sensor_reaction_word` 0x402888 b2/b3: that only sets out[3] b4, which the encoders ignore. A missing
  steering frame (0x0C9) sets exactly those bits, so 0x1A0 keeps sending live ay/yaw while the ABS has them invalid
  (FACTS "Steering-sensor loss").

**Drive-direction inputs**
- **Standstill detector** `vehicle_standstill_update` 0xD381C → 0x40328C. b5 = valid: fewer than 2 wheels faulted,
  0x40288C b2 clear, and 0x408DA1 b7:5 ≠ 3. b7 = standstill: set when at least 3 healthy wheels are ≤ 0.72 km/h
  (rec+0x1A ≤ 72), vref 0x408DA8 ≤ 0x4E20, and |value| from the yaw-family getter 0x94308(1) ≤ 0x7AED (not decoded further). Cleared when 2 wheels are above
  0.72 km/h (or 1 above with 1 faulted) or vref exceeds the limit. `vehicle_standstill_get` 0xD3A1C(0) returns
  −1 if b5 is clear, else b7.
- **Wheel direction.** `wheel_dir_forward(w)` 0xB96F4 = 0x4029D9 bit (4+w): 1 forward, 0 reverse. This polarity
  matches the 0x0CE getters, which negate the wheel speed when the result is 0. `wheel_direction_valid`
  returns 1 outright above 70 km/h, and the bits only update below 55 km/h (see symbols "Wheel direction").
  0x4046D7 b3..b0 = wheel 0..3 is direction-capable (`validate_dir_cfg`
  0x75A5E(w) = 15), latched once by `can_dme_iface_update` 0x7E7A4 (b4 = done).
- **Fallback.** 0x400B09 b3 is set by the AYC direction state machine 0x6341A. It sets b3 and enters state 7
  (0x400BFE) when its direction decision says reverse, and clears b3 on forward. That decision is
  `vehicle_dir_get` 0xB96C2 (0x4029DA b7:6: 1 forward, else reverse; −2 when unavailable) when available,
  otherwise an estimator 0x632AC / 0x633AC (not decoded; selected by 0x4010FB b7 and the coding table 0xD710A).

**Not confirmed:** the absolute sign of ay and yaw, the BMW names of the enum values in 1.4, and the meaning of
0x402884 / 0x4029BE bits beyond their role here.

## Frame 0x0CE (wheel speeds) — signal decode

Four identical getters, one per wheel. Order = wheel index 0..3 = **FL, FR, RL, RR** (same as 0x2B2; FL confirmed on
the bench, FACTS "Results"). Each is a signed 16-bit Intel field at bytes 0/2/4/6 with 1 bit = **1/16 km/h**.

Per wheel w (`can_tx_0CE_wheelspeed_w` 0x7AB8C / 0x7ABE8 / 0x7AC42 / 0x7AC9E):
1. **0x8000** (invalid) if the wheel's sensor fault latch 0x400952[w] b0 is set, or the fault reaction 0x40288C b2 is
   set (the same two checks the 0x1A0 speed uses).
2. v = filtered wheel speed rec+0x1A (0x40BF1A + 0x40·w, 0.01 km/h). This is the raw wheel speed: no tyre-size
   compensation and not vref.
3. **0** if v ≤ the standstill floor 0x4032D0. The floor is min(2·900·C/60000) over the coded circumferences
   (`wheel_cal_prepare` 0x751A8), ≈ 0.6 km/h at C = 2073 mm.
4. Otherwise |v·4/25| (signed ÷, toward 0), clamped to **4800** (300 km/h).
5. **Negated** when `wheel_direction_valid` 0xB973C(w) = 1 and `wheel_dir_forward` 0xB96F4(w) = 0 (latched
   reverse). Below 70 km/h, valid needs the wheel's direction info and no direction fault. Above 70 km/h valid is 1
   outright, and the sign is the direction latched below 55 km/h (normally forward; a latched reverse above
   120 km/h raises a direction fault). If the direction function is disabled or ≥ 2 wheels are direction-faulted,
   the value is always positive. Detail: `analysis/7846816A_symbols.md`, "Wheel direction".

So the range is −4800..+4800 (±300 km/h), with 0x8000 as the invalid marker. There's no counter or checksum in
0x0CE (DLC 8, 20 ms, mailbox 1).

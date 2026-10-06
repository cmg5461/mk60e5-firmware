# Wheel-speed sensor chain: 1M 7846411A

> **Update 2026-10-06:** Conclusions here that non-VDA/E46 sensors need hardware are **superseded**. ASIC register 0x28C is a
> per-channel VDA/2-level mode mask, and with both-edge timer capture (mode 0xA1) E46 sensors read on all four
> wheels. See `docs/E46_SENSOR_FIRMWARE_PATCH.md` and FACTS.md.


Source: a Sonnet subagent report, saved by the main session (subagents cannot write files). The
agent's scratch scanners are in this folder. Condensed but faithful. CPU addresses throughout;
file offset = CPU + 0x8000.

**Verified by the main session against the binary:**
- `movi r2,15` at 0x0B91AC (60F2) → jsri 0x075ABA → store to 0x4029D6.
- BFU block at 0x41F04 (`BFU\x01`, u16s 100, 72, 2073, 2073, 48, 48 at 0x41F10..0x41F1A).
- 0xD79F8 = `00 01 02 03 05 09`.
- ASIC read commands at 0xD7792.
- 0x0B9524 needs 0x4029D6 != 0.
- 0x0D5CDC called for ch 0..3 with 0x91 (17 | 0x80) at 0x06F5D4..0x06F5EE.
- B9118 literal pools (values in section 6) are used only inside B9118.

Everything else is the agent's reading.

## Summary
- **VDA bits are not decoded in the MCU.** The four edge ISRs only timestamp speed edges. Direction, direction-valid, a 3-bit air gap and other flags come pre-decoded in 16-bit words that an external sensor-interface ASIC returns over QSPI (0x00DB0000, chip select 5).
- **Path:** the reader is 0x0D52E8, the poll is 0x06FD70, and the post-processing is 0x075CC8 / 0x075BD0.
- **No firmware sensor-type switch was found.** The capture mode is hard-coded (0x91, mode 3, on all channels). The ASIC init tables are constant flash data.
- **"Direction expected" comes from a literal in code.** 0x0B91AC `movi r2,15` feeds 0x075ABA (returns 15 for input {0,1,2,3,15}, else 0), and the result goes to 0x4029D6, the wheel mask.
- **Without direction-capable sensors the stock code logs a fault.**
  - Every wheel reads direction-invalid.
  - After 175 cycles at 4.01–55 km/h, 0x0B4064 logs a per-wheel fault (ids 0x00020040..0x00050040 from 0xF5A74).
  - It also sets 0x4029DA bit4.
- **Candidate patch for E46 sensors (agent inference, UNTESTED).** Change 0xB91AC `60F2` to `6042` (`movi r2,4`), so 0x4029D6 = 0. B9118 then returns early and B9524 returns 0, so there are no negative speeds and no direction fault.
  - Not verified on hardware.
  - It does not address the probable application signature.
  - The authoritative check is to diff the owner's E46-configured flash at 0xB91AC, 0xD79FC, 0xD75A0..0xD7620 and 0x41F10..0x41F1C.
- **Calibration (BFU block, tag 0x41F04):**
  - circumference 2073 front (0x41F14) and rear (0x41F16);
  - tooth count 48 (0x41F18 / 0x41F1A);
  - standstill threshold 72 (0x41F12).
- **Speed formula (0x0752B8):** v[0.01 km/h] = 100·n·(900·C/100)/T. n = edges, T = stamp delta. Floor 62 (0x4032D0 = 2·900·2073/60000), cap 30000.

## 1. Data flow
```
sensor -> ext. ASIC --speed pulse--> D8/F8 capture -> edge ISRs
ASIC <-QSPI CS5 (0x0D52E8)- 0x06FD70 (when 0x07772C(3)==0):
  rx 0x4009C6 <- 02D0,0290,0248 ; rx 0x400F1C <- 02A0,02C0,02B0,02C0,02B8,02C0,02A8,02C0,0000 ; rx 0x4009CE <- diag
0x075D1E -> 0x075CC8: per wheel A=0x400F1C[1+2i], B=[2+2i]
  A bit4 ^ invert mask (0xD79FC[bit8 of 0x4031F4] = 05 or 09); B bit4 (dir-valid) cleared unless A bit3 & B bit3
  -> 0x400A34+2w = {b0 = A low, b1 = B low}; then 0x075BD0 (quality 0x400A3C/44/48)
  accessors 0x075AF0 dir (-2/+1/-1), 0x075B50 airgap = (b0>>5)&7, 0x075B10/B30/B6C other flags
0x0B9118 (from 0x0B3DA8 main cycle) -> 0x4029D2..DE
ISR w: count 0x40339A+w (cap 57), stamp>>2 at 0x40338A+4w, 32-bit stamps 0x409318/28,
  interval -> *(0x4091A8)+44w+2idx (idx<22)
0x073B78 (slot 0): snapshot 0x40338A -> 0x40339E; swap buffers 0x4091A4/0x4091A8 (0x4091AC / 0x40925C)
  -> 0x0A9F7E tooth/encoder monitor (0xA6xxx-0xAAxxx, hard-coded 48)
0x071040 wss_main_job -> 0x0752B8 (w=0..3): n=0x4033AE+w, T=last-first, C=0x41F14 (w0,w1) / 0x41F16 (w2,w3)
  -> 0x40094A[w] (s16, 0.01 km/h)
0x08EE30 -> 0x0B65DC (struct 0x40BF00+0x40k, slew/validity filter) -> 0x40BF1A+0x40k
CAN 0x0CE callbacks: sign from 0x0B9524 + 0x0B94DC
```

## 2. Functions
| Addr | Name | Conf | Evidence |
|---|---|---|---|
| 0x0B9118 | wheel_direction_update | high | sole writer of 0x4029D2..DE |
| 0x0B9524 | wheel_direction_valid(w) | high | DA bit5, D8<2, D6 != 0, fault clear, speed <= 7000, D9 bit w, D7 bit w clear |
| 0x0B94DC | wheel_direction(w) | high | D9 bit 4+w |
| 0x0B94AA | vehicle_direction | med | DA bits 6-7 vote |
| 0x075AF0 | asic_wheel_dir(w) | high | -2 invalid, +1/-1 |
| 0x075B50 | asic_wheel_airgap(w) | high | (b0>>5)&7 when b1 bit5 |
| 0x075B10/B30/B6C | asic_flag1/0/2 | med | |
| 0x075ABA | validate_dir_cfg | high | 15 for {0,1,2,3,15}, else 0 |
| 0x075ADE | dir_invert_mask | high | 0xD79FC[(0x4031F4>>8)&1] |
| 0x075CC8 | asic_decode_post | high | writes 0x400A34[w] |
| 0x075BD0 | asic_wheel_quality | med | |
| 0x06FD70 | asic_sensor_poll | high | QSPI reads |
| 0x0D52E8 | qspi_xfer_cs(cs,n,tx,rx) | high | 0xDB0008/0C/14/0400/0440/0480 |
| 0x0D5400 | qspi_xfer_bytes | med | CS2 = EEPROM-like (cmds 1/2/3/5) |
| 0x06F78A..0x06F900 | asic_init | med | tables 0xD75A0 / 0xD75D2 / 0xD7607 to CS5 |
| 0x073B78 | wss_window_rollover | high | |
| 0x071040 | wss_main_job | high | |
| 0x0752B8 | wheel_speed_update | high | speed formula |
| 0x075204 | wheel_cal_prepare | high | 900·C, min speed |
| 0x08EE30 | wheel_post_loop | high | |
| 0x0B65DC | wheel_speed_filter | med | |
| 0x08F000 | wheel_struct_init | high | |
| 0x071D1C | count_standstill_wheels | med | |
| 0x0A9F7E | wss_interval_task | med | |
| 0x0AA338 | tooth_correction_update | low | |
| 0x0AAB00 | wss_plausibility_monitor | low | |
| 0x0B3DA8 | esp_cycle_a | high | calls B9118 |
| 0x0B4064 | dtc_report(id) | med | fault logging |

## 3. 0x0B9118 algorithm
**Inputs:**
- vref 0x408D84;
- 0x400966 bit6 (init phase);
- 0x402904 bit7 (controller active);
- asic_wheel_dir;
- 0x40094A[w];
- struct0 speed;
- 0xF5A74.

**Steps:**
1. Clear D3/D4/D5/D8.
2. If vref < 5500, DA bit5 is clear and init is done, **set DA bit5**. DA bit5 is a run-time enable; it is not coding data.
3. **Reset path** (taken during init or while a controller is active):
   - clear DA bits 2..7 and DB..DE, D2..D9;
   - then D6 = validate_dir_cfg(15) = 15 and DA |= 4.
4. **Main path** (returns if D6 == 0). For each wheel, with the direction from the ASIC:
   - invalid, DA bit5 set and 401 ≤ speed < 5500: counter DB+w++ (otherwise it decrements);
   - counter ≥ 175: DA bit4 = 1, fault 0xF5A74[w], D7 |= 1<<w;
   - speed < 5500: D9 bit w = valid, D9 bit 4+w = forward;
   - in [2501, 5500) with DA bit3 set: a direction mismatch gives the same fault;
   - above 12000 with struct0 speed > 2500: direction must be forward.
5. All wheels valid: DA bit3 is set. DA bits 6-7 hold the vehicle direction vote.

## 4. Sensor type / direction selection
- **Capture mode:** constant 0x91 (mode 3).
- **ASIC init tables:** constant. Whether any bit in them selects sensor type is unknown.
- **Direction expectation:** only the code literal at 0x0B91AC was found.
- **Per-wheel polarity:** 0x4031F4 bit8 (source unresolved).
- **No pulse-width, Manchester or parity decoding in the MCU.**

## 5. RAM
| Addr | Meaning | Conf |
|---|---|---|
| 0x40BF00+0x40k | wheel[k]: +0x1A final speed, +0x2A index | high |
| 0x40094A+2w | raw speed (0.01 km/h) | high |
| 0x400952+w | fault (bit0), valid sample (bit7) | med |
| 0x40339A..9D | edge count | high |
| 0x40338A+4w | stamp (+2 previous) | high |
| 0x4091A8 / 0x4091A4 | ISR buffer active / done | high |
| 0x4033CC / 0x4033D0 | 900·C front / rear | high |
| 0x4032D0 | min speed (62) | high |
| 0x400F1C[0..8] | ASIC wheel rx | high |
| 0x4009C6 / 0x4009CE | ASIC status / diag rx | med / low |
| 0x400A34+2w | decoded ASIC wheel bits | high |
| 0x4029D6 | direction wheel mask | high |
| 0x4029D7 / D8 | direction fault mask / count | high |
| 0x4029D9 | direction bits | high |
| 0x4029DA | b2 reset done, b3 available, b4 fault, b5 enable, b6-7 vote | high |
| 0x4029DB..DE | invalid counters | high |
| 0x408D84 | vref | med |
| 0x4031F4 | variant word | low |

## 6. Calibration / tables
| CPU addr | Value | Meaning | Conf |
|---|---|---|---|
| 0x41F04 | "BFU",01 / 00000003 / 12B873A1 | block tag / count? / id? | med |
| 0x41F10 | 100 | no reader found | low |
| 0x41F12 | 72 | standstill threshold (0.01 km/h) | med |
| 0x41F14 / 0x41F16 | 2073 / 2073 | circumference front / rear (mm assumed) | high / med unit |
| 0x41F18 / 0x41F1A | 48 / 48 | tooth count front / rear | med |
| 0xF5A74 | 4 × u32 0x000n0040 | direction fault ids per wheel | med |
| 0xD79F8 | 00 01 02 03 | ASIC reply index → wheel | high |
| 0xD79FC | 05 09 | direction invert masks | high use |
| 0xD75A0 | 12 × u32 (count 0xD75D0) | ASIC init words | med |
| 0xD75D2 | 13 × (u16,u16) (count 0xD7606) | ASIC init pairs | med |
| 0xD7607 | 24 B | ASIC block write | low |
| 0xD7792 | 9 × u16 | ASIC wheel read cmds | high |
| 0xD7764 | 4 × u16 | ASIC status reads | med |
| 0xB9450 | 5500 | direction logic upper speed (used 3x in B9118) | high |
| 0xB9484 / 0xB9488 | 401 / 5099 | invalid-counter speed window (offset / span) | high |
| 0xB9504 / 0xB9508 | 2501 / 2999 | mismatch-check window (offset / span) | high |
| 0xB950C / 0xB9510 | 12000 / 2500 | high-speed forward check | high |
| 0xB95B4 | 7000 | direction-sign speed limit | high |
| 0x75584 / 0x75588 / 0x75590 | 60000 / 5536 / 30000 | timeout / init offset / speed cap | high |

## 7. ISR/channel → wheel (index → FL/FR/RL/RR only via the CAN 0x0CE hint)
| w | ISR | ctrl | ASIC cmd | 0x0CE bytes | axle |
|---|---|---|---|---|---|
| 0 | 0x070D2C | 0xF8008E | 02A0 | 0-1 | front |
| 1 | 0x070E3C | 0xD8008E | 02B0 | 2-3 | front |
| 2 | 0x070EC6 | 0xD8009E | 02B8 | 4-5 | rear |
| 3 | 0x070DB2 | 0xF8009E | 02A8 | 6-7 | rear |

## 8. Open questions
1. 0x4031F4: who writes it? Bit8 selects the invert mask; bit4 is read at about 60 sites.
2. Diff an E46-configured flash at the sites in section 6 and at 0xB91AC.
3. Other ASIC word bits (field strength, calibration, parity) are unidentified.
4. The capture clock is unknown, and it is unknown whether tooth correction alters 0x40BF1A.
5. Meaning of 0x402904 bit7 and 0x400966 bit5.
6. 0x0B65DC filter law.
7. Do the ASIC init tables contain a sensor-type bit?

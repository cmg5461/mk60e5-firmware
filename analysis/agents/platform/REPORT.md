# Platform: clocks, timers, INTC, system modules, integrity (1M 7846411A)

Source: a Sonnet subagent report, saved by the main session. Condensed but faithful.
[C] = read from code/data, [I] = inferred, [G] = guess. CPU addresses throughout.

**Verified by the main session:**
- Prescaler argument 79 passed to 0xD6C80 for both timer modules (0x6F5BE / 0x6F5C6).
- First arm 0x3A98 = 15000.
- ROM-test range table 0xD7584 = [0x40000, 0x402F8), [0x40300, 0x426BC), [0x426C0, 0xF6684), with stored words 0xB6EFCB77, 0x03B09CDC and 0xD719D58D at the range ends.
- 0xF59E0 = "0182H200020A".
- 0xF6664 = 0x0C "AZ2RAB00039".
- 0x40200 = "LOCK"; 0x402F4 → 0xF668C.
- Block directory at 0x40300 (12 entries; table in FACTS.md).

## Q1. Clock and timers
- **PLL 0x06C784 (module 0xDC0000) [C]:** multiplier field 6 (MFD + 4 = 10), post-divider stepped 1 → 0 after lock, tables 0xD752E / 0xD756E. The crystal is unknown.
- **System clock: 80 MHz [I].** Evidence: the serial divider table at 0xD78E0 matches 5 MHz/N exactly for standard baud rates (9600, 19200, 38400, 57600, 115200, 10400 K-line, 31250, 62500, 200).
- **Timer tick: 1 µs [C+I].** Timer prescaler is 79 (reload 0xFF−79), i.e. ÷80, so a D8/F8 count = 1 µs.
  - Counter +0x0, compare +0x100, ack +0x380, prescale reload +0x0F.
- **Frame confirmed: exactly 10000 counts = 10 ms.**
  - Slot deltas: 1000, 1000, 500, 300, 200(rel), 1000−lat, 1000, 1000, 1000, 500, 500, 1000, 1000.
  - T2 runs every 1 ms (slots 0,1,2,5,6,7,8,9,11,12), T1 every 2.5 ms (0,3,7,10), T3 every 10 ms, T0 at 8 ms.
  - First tick 15 ms after init.
- **vec61:** +624 counts (0.624 ms). It only increments 0x400838, which has no reader.
- **Wheel tick inconsistency (open):** stamps are counter>>2 = 4 µs if capture uses the same counter. The formula constant 900 then implies 100 edges/rev, versus BFU 48 teeth (×2 = 96, which gives 937.5).

## Q2. INTC 0xE10000
- **Priority table [C]:** 15 words at 0xE10040, one byte per source. Non-default: 0,1,3 = 10; 8,9,11 = 8; 16 = 3; 18 = 12; **19 = 0**; 25 = 27; 26 = 25; 27 = 23; **29 = 29 (unique)**; 30 = 21; 31 = 11; 34 = 18; 35 = 17; 40 = 26; 41 = 24; 42 = 22; 44 = 28; 45 = 20; 50 = 16; 51 = 7. All others are 1.
- **Self-check 0x042B68 [C]:** byte19 == 0, byte29 == 29, every other byte non-zero and != 29, else error 0xA601.
- **ICR:** u16 0xE10000, low 5 bits = level. OS critical sections set level 29 [C].
- **Index → vector [I, med-low]:** vec = 32 + index. Under that mapping vec61 is priority 29 and vec57/58/59 are 27/25/23, but vec32 and vec56 are inconsistent. Not proven.

## Q3. System modules
| Module | Identity | Conf | Detail |
|---|---|---|---|
| 0xFFF00000 | MPU | med-high | descriptors at +0x200+8i via 0xD5654; table 0xD7648 (17 entries); violation status +4 & 7 → handler 0x077BEA (errors 0xA004/05/23/24/25/26); IRQ stubs save/clear/restore bits 12:8 |
| 0xFFF80000 | flash cache | med | +0x2000 4 KiB tags?, +0x4000 16 KiB data?; cache bits 0xF000 cleared during the ROM test |
| 0xDC0000 | PLL | | |
| 0xFB0000 | reset control | high | bit7 = software reset (0x06CF86); 0xFB0001 = reset cause |
| 0xFF0000 | system status | low | written only at startup; 0xFF0006 read by 0x0D58B0; bit2 gates the bootloader jump |
| 0xD50200/04 | hardware signature unit | med | |
| 0xFA0000 + 0xDD0000 | **two CAN modules**, identical init | | |
| 0xFC0000 | serial unit | | |
| 0xF60000 | flash controller | | |

- **No periodic watchdog service found [C].** T0's worker 0x078B20 sets fixed output levels via 0xF50200/04 while 0x400966 bit5 is set; it is not a toggle.
- **Bootloader jump 0x0D5684 [C]:** requires u32 0x4010 == 'SBL!', 0x4000 != 0xFFFFFFFF, and 0xFF0006 bit2. It then quiesces peripherals and does jsr [0x4000] (secondary bootloader at CPU 0x4000, not in the .0pa).

## Q4. Integrity checks in the application [C]
- **Background ROM test:**
  - Init 0x06DEFE; per-frame step 0x06DDE4 from T3.
  - Uses the hardware signature unit 0xD50200 over three ranges (table 0xD7584), compared with the u32 stored at each range end.
  - About 2684 words per frame, so about 0.7 s per full pass.
  - Mismatch → set_error(0x10004) and fault latch 0x40288C.
  - The algorithm is a hardware MISR/CRC; standard CRC32 variants and sums do not match.
  - Range B is exactly the calibration block area (0x40300–0x426BC).
- **ID record check (0x6F8C4):** 0xF6664 = "AZ2RAB00039"; else error 0x12000.
- **Other checks:** CAN mailbox RAM pattern test 0x0D4434; stack canaries; INTC self-check; runtime supervision. There is no general RAM test.
- **BMY block:** u32 0x000F59E0 points to the reference string "0182H200020A" (the .0pa header says 0182H200030A). The M3 equivalent is 0x000F56D8. The following 0x10 is probably the signature length in words (16 × 4 = 64 bytes). The app never reads the BMY block, so the bootloader presumably checks it [I].

## Q5. 0xFFFF00 / 0xDF8xxx
Not referenced by the application. They belong to the boot/programming layer (identification and a fixed 8-byte pattern).

## Q6. ecu_mode = test-protocol level (0x400A11 bits 7:5) [C]
- **Writers:** only the ASCII manufacturing/test protocol state machine 0x076092 (state 0x400A28, 13 states, jump table 0x76134). It is fed from the serial buffer 0x40331D. The protocol window opens at power-up for 179 frames (about 1.8 s).
- **Levels [I]:** 0 normal, 1 handshake, 2, 3 (code "16"), 4 (code "33"), 7 abort.
- **Mode ≥ 3 → reduced cycle 0x071012:** skips control (0x8EE30 / 0x8CAD8), monitoring, diagnostics and NVM. Mode ≥ 4 also stops CAN.
- 0x076092 is the test protocol, not a general ECU state switch. T3 calls it only while the protocol is active; otherwise 0xAFEDC (KWP2000).

## Functions
| Address | Name | Conf |
|---|---|---|
| 0x06C784 | pll_init | high flow / low names |
| 0x042B68 | intc_prio_selfcheck | high |
| 0x0D6C80 | timer_prescale_cfg(mod,flags,val) | high |
| 0x0D6C70 | timer_counter_read | high |
| 0x0D6D28 | arm_D8_from_counter | high |
| 0x0D5654 | mpu_set_region | med-high |
| 0x077BEA | mpu_violation_handler | med-high |
| 0x0D5684 | jump_to_bootloader | high |
| 0x06CF86 | sw_reset | high |
| 0x06CFA6 | ecu_reset_dispatcher | med |
| 0x0D58B0 | sys_status_read | med |
| 0x06DEFE / 0x06DDE4 | rom_test_init / rom_test_step | high |
| 0x06CF30 / 0x06CF54 | hw_sig_run | med-high |
| 0x0D4434 | can_ram_test | high |
| 0x070F94 | startup_window_and_counters | med-high |
| 0x076092 | test_protocol_state_machine | med |
| 0x076030 / 56 / 74 | protocol_enter / normal / exit | med |
| 0x078B20 | t0_set_output_levels | med |

## Open questions
1. The crystal (80 MHz is inferred).
2. The INTC index → vector mapping.
3. Wheel capture tick vs the 900 constant.
4. The hardware signature algorithm.
5. 0xFF0000 identity; external watchdog?
6. Who drives the ASCII test protocol.
7. Cache bit meanings.

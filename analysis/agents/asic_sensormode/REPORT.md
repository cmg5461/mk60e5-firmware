# Wheel-speed ASIC config + mode-2 data path (M3 7846816A) — why mode-2 read nothing

> **Update 2026-10-06:** Conclusions here that non-VDA/E46 sensors need hardware are **superseded**. ASIC register 0x28C is a
> per-channel VDA/2-level mode mask, and with both-edge timer capture (mode 0xA1) E46 sensors read on all four
> wheels. See `docs/E46_SENSOR_FIRMWARE_PATCH.md` and FACTS.md.


Two Sonnet deep-dives (ASIC front-end; mode-2 edge path), **key claims re-verified byte-exact by the main
session** against `flash/bin/7846816A_00000000.bin` and `analysis/7846816A_main.lst`. CPU addrs; file = CPU+0x8000.

## Bottom line
Flipping the mode byte 4→2 was **never going to produce a wheel-speed reading by itself.** The mode value
only selects which *presence/fault* check runs; the speed **magnitude** pipeline reads captured edges with
**no mode dependence**, and those edges reach the MCU **through the ASIC**. The ASIC is hard-configured for
VDA active (current-mode 7/14/28 mA) sensors, so a non-VDA stimulus yields no pulses → no edges → no speed.
The real lever is the **ASIC input-stage configuration (QSPI registers)**, whose field meanings are **not
determinable from firmware** — needs the ASIC datasheet (part number off the opened board) or a reference
flash (motorsport bin, which is NLA).

## Corrections to the older sensortype report [verified]
- `sub_075A44` (0x75A44, file 0x7DA44) is NOT a mode dispatch. Its arg r2 is the **wheel index**; for 0..3 it
  returns 4 (the shared `movi r3,4` at 0x75A56 = file 0x7DA56, the toggle), else 0. The 4/2/else split is in
  the CALLER, the presence loop `sub_075E38` (`cmpnei r2,4` at 0x75E9E = `2a 42`).
- The prior ASIC table addresses 0xD75A0/0xD75D2/0xD7607 were **1M (7846411A)** addresses. The **M3** tables
  are at **0xD7210 / 0xD7242 / 0xD7276** (file 0xDF210/0xDF242/0xDF276) — M3 = 1M − 0x390.
- `0x075AA0` is inside a direction decoder, not a routine returning 4; `0x075F1C` is live (`cmplti r7,3`).

## Mode-2 presence vs speed [verified]
- Caller `sub_075E38`: per wheel calls `sub_075A44`, then on the returned value: **4**→ASIC-frame popcount≥3
  presence (`0x400F20+4*ch`); **2**→period-pair presence at `0x40339E` (window: (cur−prev) in [6..25],
  `subi r2,6`/`movi r6,19`) + edge-count≥2 + ASIC-status counter; **else**→immediate fault.
- Mode-2 presence PASSES trivially with no pulses (counters stay 0 ⇒ `0x4010CE[w]=1`). It only faults if the
  ASIC status bit is set persistently (≥3 cycles) or pulses are glitchy.
- **Speed magnitude** `sub_07525C` loads `0x40339E` and computes speed from cur/prev + edge count, clamps,
  stores `0x40094A+2w`. **No mode check anywhere in it.**

## Edge-capture path [verified]
- 4 input-capture ISRs (`sub_070CD0/070DE0/070E6A/070D56`) on two mirrored timer modules (0xF8xxxx / 0xD8xxxx,
  regs 0x8E/0x9E) write live counters 0x40339A–0x40339D and interval buffer 0x4091CC; each self-disables at
  57 edges. `sub_073B1C` snapshots 20 bytes from 0x40338A → 0x40339E (snapshot counters 0x4033AE–0x4033B1).
  Re-enable in `sub_07525C`. Power-on init `sub_06EEB0` clears the enables. **Mode-independent; this is the
  same path stock mode-4 speed uses.**
- [likely] The ASIC conditions the sensor signal and drives the digital pulse into the capture pin — a raw
  signal at the sensor input does NOT bypass the ASIC. So capture is still gated by ASIC input mode.

## ASIC access + register map [verified code]
- Hardware **QSPI base 0xDB0000, chip-select PCS5**. Driver `asic_reg_xfer32` @ 0xD4A30 (irq-bracketed; TX
  word0=(reg>>? )&0x3FF, word1=val&0x3FF → **10-bit reg id + 10-bit data**; returns RX0<<16|RX1). Generic
  `qspi_xfer(cs,n,tx,rx)` @ 0xD4CA8. Init runs ~0x06F4xx–0x074092; all constants, **no coding/NVM/variant read**.
- Global 12-word table @ 0xD7210: regs 0x2F4=000,0x26C=1AA,0x274=0C0,0x264=00E,0x23C=006,0x2CC=010,0x284=0FF,
  0x28C=00F,0x24C=090,0x2D4=001,0x2E4=0E2,0x00C=002.
- Global 13-pair table @ 0xD7242: **0x154/0x15C/0x164/0x16C = 0x1B** (identical across the 4 channels — top
  suspect for a per-channel sensor-type/mode field), 0x174=200,0x17C=000,0x21C=1FF,0x104=00F,0x10C=0FF,
  0x2FC/0x304=0E5,0x30C/0x314=1FB.
- Per-channel `sub_073F74` (0x73F74): channel table @ 0xD75E4, input table @ 0xD75A4, row table @ 0xD7614.
  Writes per-channel regs 0x184/18C/194 (ch0) etc. with row values, reg 0x224=0x322 (bits 8/9 set for ch2/ch3),
  and input-level regs 0x114–0x14C = 0xBF/0xC4/0xF2. ch0↔inputs{1,4}, ch1{0,5}, ch2{2,3}, ch3{6,7}.
- Runtime `sub_07452A` retunes 0x114/0x13C and ORs bits 6/7 into reg 0x15C (literal 0x015C001B @ file 0x7C6FE).

## Candidate patch sites to ATTEMPT a passive/VR mode (file = CPU+0x8000) — meanings UNKNOWN, guesses
- Reg 0x154/15C/164/16C `0x1B`: files 0xDF244,0xDF248,0xDF24C,0xDF250 (+ row copies 0xDF61A/622/62A/632; runtime 0x7C6FE).
- Input levels 0xBF/0xC4/0xF2: 0xDF5A6,0xDF5AE,0xDF5B6,0xDF5BE,0xDF5C6,0xDF5CE,0xDF5D6,0xDF5DE.
- Per-channel flag (reg 0x224 / 0x4033DE): h3 halfwords 0xDF5AA,0xDF5B2,0xDF5BA,0xDF5C2,0xDF5CA,0xDF5D2,0xDF5DA,0xDF5E2.
- Plus the already-known: direction mask `movi r2,15` @ 0xC13C4 (CPU 0xB93C4); presence-defeat `bt`→`br` @ file 0x7DF2C (`e0 1a`→`f0 1a`).

## Decisive bench diagnostic (no datasheet, no flash) [from mode-2 agent]
Stimulate FL and read RAM live: **0x40339A–0x40339D** (live edge counters) and **0x4033AE–0x4033B1** (snapshot).
- Stay 0 ⇒ no pulses reach the MCU ⇒ ASIC gating confirmed (the fundamental blocker).
- Go >0 while CAN speed stays 0 ⇒ edges arrive but speed is nulled downstream (fault/CAN gate), a different fix.

## Needs the ASIC datasheet
Part number + register map; meaning of the low 3 bits of the 10-bit reg id; the 0x1B field bits and the
runtime bits 6/7 of reg 0x15C; whether reg 0x224 bit8/9 is a mode flag; what 0xBF/0xC4/0xF2 (and runtime
0xD4/0xE9/0x35) are; channel→wheel mapping; meaning of the 0x1A5 loopback test @ 0x06F58A.

## [verified 2026-10-05] Live ASIC-reconfiguration campaign (E46 on FL, bench) — NEGATIVE
Using the patched-0x23 peek/poke instrument (see PATCH_PLAN.md), with the observable
validated by an E90 (VDA) positive control (0x40339E-A1 interval words change rapidly
+ FL counter 0x40339A[0] ticks while spinning; E46/at-rest = all zero):
- Per-channel mode field 0x154/15C/164/16C: swept full range (0x00,0x3F, single-bit
  flips of 0x1B, 0x1FF, 0x3FF, 0xDB) -> no captured edges.
- Input-threshold regs 0x114-0x14C (all 8 set together): swept 0x000..0x3FF -> nothing,
  AND extremes produced NO comparator free-run/noise (=> capture is gated upstream of
  the analog threshold, in the digital VDA-decode stage).
- Per-channel flag 0x224: 0x000/0x0FF/0x100/0x300/0x322/0x3FF -> nothing.
Conclusion: the non-VDA decode mode is NOT reachable via the per-channel config
registers this firmware programs. Reinforces the hardware-gate finding with active
evidence. Untested (riskier/speculative): the global 0xD7210-table regs as a possible
global protocol selector. Residual caveat: firmware re-writes 0x114/0x13C/0x15C each
cycle (mitigated by re-writing every poll; a definitive single-channel test needs an
init-table patch + flash). Scripts: scratchpad/asic_modesweep.py, asic_thresh_sweep.py.

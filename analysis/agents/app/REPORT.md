# Application layer: 1M 7846411A

Source: a Sonnet subagent report, saved by the main session. The agent's call-graph scripts were
in the session scratchpad and are not kept. Condensed but faithful. [V] = read from code/data by
the agent, [I] = inferred.

**Verified by the main session:**
- The OS object graph: 0xD7F14 → class 0xD81F4 → object table 0xD81D0 → per-object class
  +40 = task body.
- Object → task map 0xD7F08 = {3,4,2,1,0}.
- Runs-per-frame: byte 2 of the per-object class's first word (stored inline, not via a pointer).
- The full call order of T3 body 0x071040.
- The four 0xDB2D8.. tables are Q12 sine/cosine values (18° and 22.5° steps).

## 0. Tasks are thin wrappers
| OS task | Object | Class +40 body | Runs per 13-slot frame |
|---|---|---|---|
| T3 | obj0 0xD80AC | **0x071040 main cycle** | 1 (slot 0) |
| T1 | obj3 0xD810C | 0x070C58 | 4 (slots 0, 3, 7, 10) |
| T2 | obj2 0xD816C | 0x070CB4 | 10 |
| T0 | obj4 0xD8008 | – (0x0785DA → 0x78B20) | event, slot 11 |
| T4 | obj1 0xD7FA8 | – (0x0785BE stack monitor) | background |

**Wrapper per task:** 0x783F8(root, i) → 0x78256 (pending++) → 0x78268 (calls class +40) → TerminateTask.

**Supervision:** 0x786FC (slot 0) checks each object's pending count against runs-per-frame. On mismatch it raises error 0xA010.

**Frame period:** 10 ms, inferred [I] from CAN 0x0C4/0x0CE periods with T3 running the CAN stack once per frame. That makes T2 about 1 ms and T1 about 2.5 ms.

**ISR slot extras (vec60 0x70A86):**
- slot 0: 0x73B78 (T3 overrun check via 0x4009B4 bit2 → error 0x10001; wheel buffer swap), 0x786FC;
- slot 4: SPI command 0x74364;
- slot 5: 0x75690;
- slot 6: 0xD5070 read → 0x400A06, 0xD47B4 (CAN module);
- slot 7: 0x7154A(1).

## 1. T3 main cycle 0x071040 (verified call order)
`0x7772C(3)` = ecu_mode_ge(3) (0x400A11 bits 5-7). If the mode is ≥ 3, the reduced path 0x71012 runs instead.

| # | Call | Role | Conf |
|---|---|---|---|
| 1 | 0xD597C | irq enable | high |
| 2 | 0x70F94 | frame counters 0x40095C/60, power-up state 0x400964/66 | med |
| 3 | 0x6FB72 → 0x7861A | shutdown/error path check | med |
| 4 | 0x6FD70 | GPIO + ASIC sample (QSPI CS5) | high |
| 5 | 0x75774 | ASIC write sequence | med |
| 6 | 0x74586 | SPI read sequence (→ 0x88ACA) | med |
| 7 | 0x71B56 | ECU state machine | low-med |
| 8 | 0xBF950 (stub), 0x82EC2 | clear 4 channel structs 0x401728 (stride 0x38) | med |
| 9 | 0xC4B4C | communication state machine #2 (0x402EE0) | med |
| 10 | 0xCFA00 → 0xD0080 | coding/config NVM block | med |
| 11 | 0x78B3E(1) … 0x78B40(1) | empty measurement hooks | high |
| 12 | 0x752B8 | wheel_speed_update | high |
| 13 | 0x8EE30 | per-wheel pass (0xB65DC filter + about 12 more) | med |
| 14 | 0x8F0A4 | coding/limit lookup | low |
| 15 | 0x78B3E(2) … 0x78B40(2) around **0x8CAD8** | **vehicle-level control dispatcher** (about 40 direct calls, about 620 reachable functions) | high (structure) |
| 16 | 0xB3DA8 | **monitoring pass** (plausibility, wheel direction 0xB9118, fault bookkeeping) | high (structure) |
| 17 | 0x71F2E | IO/ASIC housekeeping (DE0000 port) | low |
| 18 | 0x7944C | **CAN stack** (rx 0x79D96, tx 0x79874; state 0x4015E4 bits 5-7: init / normal / bus-off / off) | high |
| 19 | 0x6D084 | serial FC0000 helper | low |
| 20 | 0x76092 or 0xAFEDC | ECU-state giant switch / **diagnostics main** | med |
| 21 | 0x6DFCC, 0x6DDE4, 0x737F0 | NVM management, error flags | low |
| 22 | set 0x4009B4 bit2 | "T3 done" for the overrun check | high |

## 2. T1 0x070C58 (4×/frame) and T2 0x070CB4 (10×/frame)
**T1** runs, in order:
1. 0x7437C (output bit images 0x4009B0/84/98)
2. 0x6FE74 (SPI 0xD5070, filter 0x6992C)
3. 0x6FE40 (SPI 0xD52E8, 0x8F808)
4. per channel 0..3: **0x850A2(ch, phase)** (state 0x4019-0x401E)
5. 0x74DBC → 0x86FB0, then the output image 0x40106C/6E

The 4 channels are wheels or valve groups (unknown).

**T2** runs 0x74250 (0x71C10, 0x74BB2, 0x73E18) and 0x7427C (0x74F42 ×3 = an SPI job engine with 11 jobs at 0x401070..0x4010B8). [I] T2 is the ~1 ms SPI/ASIC comms engine. The valve and pump drive probably goes out through these SPI images (not confirmed).

## 3. Helpers
| Addr | Name | Conf |
|---|---|---|
| 0x6D17C | abs16_sat (534 callers) | high |
| 0x6D190 | abs32_sat | high |
| 0x6D1A4 / 0x6D1AC | sign16 / sign32 | high |
| 0x6D1B2 | sat16 | high |
| 0x6D1C6 / 0x6D1CE | divs16 / divu16 | high |
| 0x711FA | interp1d(x[], y[], n) | high |
| 0x71158 | interp1d_limited (126-139 callers) | med |
| 0xB4064 / 0xB40FA | set_error(group<<16 \| mask) / is_error | high |
| 0xB4122 | error-group NVM store | med |
| 0x7772C | ecu_mode_ge(n) | high |
| 0x6E21C / 0x6E338 / 0x6E492 / 0x6E4CE / 0x6E5FC | NVM queue / request / sync read / read / write | med |

## 4. Module map (address clustering + call/RAM evidence)
| Module | Code range | RAM | Conf |
|---|---|---|---|
| OS kernel | 0x42000-0x44000 | 0x400320-0x400870 | high |
| Wheel-state conditioning (wheel structs 0x40BF00) | 0x44000-0x5E000 | 0x408D-0x4091, 0x40BF00 | med |
| Vehicle model / signal bus (guess) | 0x5E000-0x6C000 | 0x400A-0x400F, 0x4046 | low |
| System / HW support (reset, irq, SPI jobs, ISRs, ECU state, wheel edge, NVM, CAN abstraction) | 0x6C000-0x78000 | 0x4009-0x4010, 0x4028, 0x4033, 0x4093 | high |
| OS application wrapper | 0x77C00-0x78B60 | 0x4008xx | high |
| CAN comms + signal callbacks | 0x78D00-0x7F800 | 0x4011-0x4016, 0x4046-0x4048 | high |
| Control: per-channel logic (probably ABS/valves) | 0x80000-0x94000 | 0x4016-0x4022 | low-med |
| Control II: large state machines (ESP/yaw? unknown) | 0x94000-0xAC000 | 0x4034, 0x404A-0x404E, 0x4059 | low |
| Per-wheel spectral module (Q12 sin/cos tables; **RPA indirect tyre-deflation, hypothesis**) | 0xA3000-0xAE000 | 0x405D78 + w·0x7AC, 0x408B94.., 0x4023-0x4027 | med (tables verified; RPA label inferred) |
| Diagnostics (KWP2000) | 0xAE000-0xB4000 | 0x4093-0x4095 | high |
| Monitoring + fault manager | 0xB4000-0xC4000 | 0x4028-0x402D, 0x408C98 | high / med |
| Coding/config + comms #2 + parameter access | 0xC4000-0xD4000 | 0x402E-0x4032 | med |
| HW drivers (CAN 0xDD0000, serial 0xFC0000, QSPI 0xDB0000, timers D8/F8, irq) | 0xD4000-0xD7000 | – | high |
| Const data / calibration | 0xD7000-0xF678B | – | high |

**Peripherals:**
- 0xDD0000: CAN
- 0xDB0000: QSPI
- 0xDE0000: byte GPIO (+0x18/1A/1B/27)
- 0xD50000 / 0xF50000: port/pin config
- 0xFC0000: serial unit (vec44/52)
- 0xE10000: INTC
- 0xD80000 / 0xF80000: timers

## 5. Data / calibration regions
| Range | Content | Conf |
|---|---|---|
| 0xD7D00-0xD7EFF | id/code lookup pairs | low |
| 0xD7F00-0xD8250 | OS object graph | high |
| 0xD82D5-0xD92E4 | CAN config | high |
| 0xD9000-0xD9FFF | callback/descriptor list (16 B: fn ptr, 0xFF, 0) | med |
| 0xDA2F0-0xDB2FF | **main scalar calibration block (probable)**: fn-ptr table, then s16/u16 limits (1000, 1500, 2000, 2500, 30000, negatives); about 290 literal refs from about 160 functions; layout follows caller address order | med |
| 0xDB2C0-0xDB2D7 | breakpoint table | low |
| 0xDB2D8 / 0xDF158 / 0xE6E58 / 0xEACD8 | **Q12 sin/cos tables** (8000 / 16000 / 8000 / 16000 × s16) | high (values) |
| 0xF3000-0xF38xx | 1-D maps (axis 1200..15000) + thresholds, used by 0xAA852-0xAFF3C | med |
| 0xF33A8 / 0xF34BC | KWP tables | high |
| 0xF3800-0xF5900 | NVM block descriptors / defaults | med |
| 0xF5900-0xF5CFF | error-group tables (0xF5B00 pointer table) | med |
| 0xF6100, 0xF64E0/0xF6542, 0xF6600-0xF662C | coding limits, NVM defaults | med |

## 6. Open questions
1. Which module is the ESP/yaw controller (0x94000-0xAC000)? How do yaw-rate, lateral-accel and steering inputs arrive (CAN callbacks → 0x4046xx images, or comms #2 0xC4B4C)?
2. Comms state machine #2 (0xC4B4C): a second bus or another layer?
3. Valve/pump outputs: are the SPI images 0x40106C..0x4010B8 the valve driver? Which ASIC commands?
4. T1's 4 channels: wheels or valve groups?
5. DE0000 GPIO pin roles (pump relay, lamps, watchdog)?
6. Timer clock / frame period (10 ms inferred).
7. Meaning of the ecu_mode values (0x400A11 bits 5-7).

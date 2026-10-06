# ABS calibration block (1M 7846411A) — field decode

Agent-derived (Sonnet), **verified by the main session**: all scalar/ladder values below
were re-read byte-exact from `flash/bin/7846411A_00000000.bin`, and the curve-reader format
was confirmed by disassembling `sub_071158`. Data tables on disk: `_curves.txt`, `_scalars.txt`
(regen with `gen.py`; annotations `annot.py`). Offsets are from block base **CPU 0x4039C**.

## Header [verified]
`ABS\x01`, version 3, id 0x12B71411, body from +0x0C.

## Structure [verified]
Body = **39 piecewise-linear curves + scalar gaps**, not a flat list.
- Curve record (reader `sub_071158`, 0x7115C–0x711C6): `s16 lo, hi, n; x[n-1]; c[n] intercept; k[n] slope (Q10)`.
  Output = `clamp(c[i] + (x*k[i])>>10, lo, hi)`. Slope multiplies x itself, not (x − breakpoint).
  Confirmed in disasm: `mult r3,r1; asri r1,9; lsri r1,22; addu r3,r1; asri r3,10; addu r14,r3` then clamp to (r2,0)/(r2,2).
- Adjacent segments agree at each breakpoint to rounding.
- Almost all refs are `lrw` + disp-0 `ld.h`, one literal per scalar/curve.

## What this block actually calibrates [agent, med]
Readers sit almost entirely in **0x44000–0x5E000 (the wheel-state conditioning layer)**; **no reads
from the 0x8xxxx control code**. So this is the calibration of the **wheel acceleration / speed / slip
*estimation* layer**, not the valve hold/dump logic. No hold/dump timing, no per-axle pressure target,
no jerk threshold, and **no explicit slip-percent target** was found in this block. Those presumably
live in the control code (dispatcher 0x8CAD8) or its own cal — a follow-up target.

## Slip / deceleration fields (all values verified)
1. **Per-wheel deceleration-threshold builder, fn 0x47DFC** [agent, med]:
   - Base +0xCC = **−116**; floor +0xCA = **−240**.
   - Low-speed floors +0xF0 = **−120** (vref < 20 km/h), +0xF2 = **−132** (vref < 60 km/h).
   - Speed-term curves +0x76 (front) / +0x9E (rear): ≈10 @100 km/h, ≈74 @300 km/h, subtracted from base.
   - Second term curve +0xF4: input a signed byte from 0x408D94/0x408D8B, output ≈0..+125, also subtracted.
   - Accumulator gains +0xC6 = **40** (front), +0xC8 = **25** (rear) [agent, low].
   - Unit guess [agent, low]: ≈0.01 g (0.1 m/s²) → base ≈ −1.2 g, floor ≈ −2.4 g. **Not proven**: the unit
     of the wheel acceleration at struct+0x20 was not derived.
2. **Deceleration ladder** [agent, low-med]: +0x2C8..0x2D2 = **−140, −90, −40, −210, −350, −490**
   (fn 0x55D44, 0x56B96). fn 0x55D44 writes targets −150/−300/−400/−650/−1000 into `0x40910C[]`;
   its 50/100 compares weakly fit the same 0.01 g unit.
3. **Three-stage thresholds on signed byte struct+0x39, fn 0x5444C** [agent, low-med]:
   - Set A +0x61E/620/622 = **−62, −78, −94**; Set B +0x65E/660/662 = **−25, −44, −62** (choice via flag +0x65C).
   - Stage outputs +0x624/626/628 = **1000, 1500, 2000**. Slip-like staged threshold; unit unknown.
4. **Speed gates** [agent, med]: +0x458 = 7000, +0x502 = 7000, +0x508 = 10000 (70/70/100 km/h on per-wheel
   speed words); +0x3A6 = 6000, +0x3A8 = 2000 (60/20 km/h on a vref-like value).
5. **Score detector, fn 0x5587C** (likely rough-road/disturbance) [agent, low-med]: +0x526/528/52A = 24/14/19,
   weights +0x538..53E = 3/4/5/1, speed thresholds +0x52C/52E/530 = 1000/100/3000.
6. Curves +0x242 (15..45) and +0x264 (20..40) write wheel-struct +0x46/+0x48 as fn(vref) [agent, low-med] —
   counters/limits, not slip targets.

## Enable flags [agent, med]
+0x652..0x65C = 0,1,1,1,1,1; also +0x456 = 1, +0x514/516/518 = 0, +0x540/542 = 1.

## Open / unknown
- Unit of struct+0x20; sources of vehicle-level signed bytes 0x408D94, 0x408D8B, 0x408DA4+8.
- Consumers of `0x4090C2[]`, `0x40910C[]`, `0x409188`.
- Transform in `sub_06D17C` ahead of curves +0x18, +0x200, +0x41A, +0x5CA, +0x5E6.
- No direct reader found for curves +0x144, +0x3CA, +0x598, +0x5AE; nor scalars +0x0E–0x16, +0x3FE,
  +0x45C, +0x504, +0x50E, +0x630, +0x650, +0x658, +0x666.
- **Where the actual ABS slip/pressure *targets* live** (control code 0x8xxxx), since this block is
  estimation-layer cal only.

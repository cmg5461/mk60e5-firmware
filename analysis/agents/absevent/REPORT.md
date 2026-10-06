# ABS event/accel decode (1M 7846411A): +0x20 source, rec[0] state machine, decision codes

Agent-derived (Sonnet), **key claims verified by main session**: `sub_0D271C` conversion literal 0xE287
(58023, ×2.833), writes +0x1E (disp 30) and +0x20 (via addi r4,32); `0x752B8` ±5714 clamp + call to
0xD271C at 0x754DE; `sub_0465B0` ±2032 clamp — all byte-exact. Machine files in `analysis/agents/absevent/`.

## RESOLVED: the dump stages ARE reachable
Normal-mode wheel accel `+0x20` is written by **`sub_0D271C`**, called from the wheel-speed update
`sub_0752B8` (0x754DE), once per wheel per 10 ms frame (the earlier scans missed it because `st.h` reaches
only disp 30, so the code does `addi r,32` then `st.h (r,0)`):
```
Δv = v_new - v_prev            ; 0.01 km/h/frame, clamped ±5714 in 0x752B8
+0x1E = Δv·58023/2048/10        ≈ Δv·2.833   (0.01 g per 10 ms)
+0x20 = (new +0x1E + old +0x1E)/2            ; two-frame mean
```
Range ±16189 raw (~±162 g). `sub_0B65DC` only switches to its ±158 slew-limited **recovery** path when
|+0x1E| > 10000/12000 (glitch) or sample count ≥57 — that recovery path was what earlier agents mistook for
the normal source. `sub_0465B0` clamps +0x20 to ±2032 (±20 g) and `w.39 = a/16` spans ±127.
- **Verdict [agent, med-high]:** set A (−62/−78/−94) = wheel decel ≈ −9.9/−12.5/−15 g; set B (−25/−44/−62) =
  ≈ −4/−7/−9.9 g. Both well inside the ±20 g clamp and below the glitch cutoff → **the staged dump logic is
  live**. [needs-hw] the real −10 g crossing frequency and low-speed quantisation.
- Units cross-check: ×2.833 = the 0.01 g ↔ 0.01 km/h-per-10 ms conversion; the vref +44/frame = 1.25 g agrees.

## rec[0] per-wheel state machine [verified from sub_04FE3C]
Prev state copied to rec[1] each frame. Bits: b7 armed, b0 in-ABS-cycle (sets 0x408D7D bit4 = vehicle ABS
active), b5 dump (gate for sub_05444C), b3 hold, b4 reapply, b2 reapply-hold/overspeed, b6 pre-control.

| State | Name [agent, med] | Transitions |
|---|---|---|
| 0x80 | armed idle | EV0.5→0x21; EV0.6→0xC0; EV0.7→0x84 |
| 0xC0 | pre-control | EV0.5→0x21; else→0x80 |
| 0x84 | rear overspeed hold | EV1.5→0x80 |
| 0x21 | **DUMP** | EV0.3→0x09 |
| 0x09 | **HOLD** (low-pressure) | EV0.0→0x21; EV1.7→0x11; EV1.6→0x15 |
| 0x11 | **REAPPLY** (build) | EV0.0→0x21; EV0.1→0x15 |
| 0x15 | reapply-hold | EV1.4→0x11 |

Suppress (→forces 0x21→0x09, 0xC0→0x80): `(0x400952[w] bit3 and (b0 or front))` or rec[0x19] bit5 (glitch).
`0x408D7D` bits 7:5 = mode (sub_045776/045A28); ≥5 with 0x401FF2&0xA0==0x80 resets all wheels to 0x80.

## sub_04D470 event classifier [structure verified; predicates partial]
144-byte frame; scratch struct E@sp+104 filled by helpers: sub_04FA5A (slips E+28/30/32), sub_04F7D4
(low-speed margin E+20), sub_052E54 (E+10 = phase threshold: −100 if rec[0] b2, −1000 if b3, else −400),
sub_052ED0 (E+12 = 7% vref), sub_052580 (E+6 = curve(0xD7322,vref)+terms). Second reference speed vref2 =
0x408D86 (sub_045884); rec+28 = tyre-compensated speed. Event word = 2 bytes (EV0=sp+28, EV1=sp+29) → to
sub_04FE3C, also stored 0x4090F2[2w].
- **EV1:** b7 sensor-quality ≥3; b6 rear & slipB<E+10 & 0x408D7D&0xE0==0; b5 slipB≥E+10 or (front & 0x408D7D b4);
  b4 slipB≥E+10; b3 pressure/lateral gate.
- **EV0 [med-low]:** b0 persistent slip (slipA≥E+6+E+16+E+18, or persistence counter); b1 →0x11→0x15 gate;
  b3 recovery-from-dump; b5 **main trigger** (slipA vs thr + decel +0x20<−100 + vehicle-decel gate); b6 entry
  candidate (decel < −1 g & 0x408D8B<0 & 0x408DA2 b6); b7 rear overspeed.

## sub_051D54 → global decision code 0x408DBA [agent, high-med]
Block: +0 code, +2 pct byte, +8 word (cleared when code 1), +10 (0x408DC4) wheel-index fields.

| Code | Meaning |
|---|---|
| 1 | no axle control / "build" (most readers skip when code 1) [verified readers] |
| 64 | a rear wheel in control → pair logic active (baseline when not 1) |
| 128 | signature invalid / special |
| 32 | yaw/lateral-limited (byte+2 = 0..100%); also sub_054F9A S1 partner-b5 & CMD<SAV |
| 1024 | reapply nudge (S1, partner b5, CMD≥SAV, SAV<0.60·X; UP=SAV+80) |
| 16 | stepped reapply by 80 (S1, partner not b5) |
| 2 | pair-hold complete (writes RAMP 0x408F36 = −8000) |

Stores: sub_051930/051D54 (1/32/64/128), sub_054F9A (32/1024/16/2). Init: 1 if both rear records are
state 0x80/0x84, else 64; forced to 1 on lateral/pressure gate, vref<15 km/h with 0x408D91 b4, etc.

## Open / needs-hw
- Full EV0/EV1 predicate set (~3000 more instr of sub_04D470); state names inferred not proven (confirm
  0x21=dump vs valve outputs needs a trace). Real +0x20 distribution in braking [needs-hw]. Meaning of the
  sub_0D271C mode gate (0x400A10 byte1 bits7:5 < 3).

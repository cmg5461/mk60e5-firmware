# ABS input / estimation side (1M 7846411A): vref, slip, wheel accel, decel targets

Agent-derived (Sonnet), **key curves/constants verified by main session** (front/rear pct +0x154/+0x17C,
decel speed curves +0x76/+0x9E, 2nd curve +0xF4, ladder +0x2C8 all byte-exact; slip curve +0x576 matches).
Machine files: `analysis/agents/absvref/evalcurves.py`, `curves_eval.txt`. CPU addresses; 10 ms frame.

## vref (0x408D84, s16, 0.01 km/h) — a rate-limited integrator [verified writer]
Sole writer `sub_044BF0`, once/frame after the per-wheel ABS loop (0x463E0, call 0x464B6). Each cycle:
`vref += delta`, then `vref = max(vref, 0x4032D0)` (floor 62 = 0.62 km/h; = min(circ_f,circ_r)·1800/60000).
Inputs = 4 filtered wheel speeds (struct+0x1A) × per-wheel tyre factor (Q10): Cmax (fastest compensated),
Fmax (fastest front), Vmin (slowest valid), Vmax (raw max). It is NOT a pure max-select.
- **Rise** (per 10 ms frame, 0.01 km/h): +44 if vref<Fmax; +22 while ABS active and vref<Vmin; up to +282
  in init/controller modes 1/2/4. (+44/frame = 1.25 g, +22 = 0.62 g, +282 ≈ 8 g "snap".)
- **Fall:** −22/−23/−32/−44 normal; −90 when mode field A[7:5]≠0 and Vmin<vref. In ABS, `sub_0511F4` sets
  the fall to `−(|vehicle-decel est| + 20…30)·0.36`, capped at −44.
- Resync to shadow integrator 0x408E5A on invalid-wheel flag; forced to a selected wheel when 0x408DC9 bit1;
  init to the floor. A wheel is skipped if struct+0x19 & 0xC0, fault bit 0x400952+w bit0, or (vmin) 0x40903A bit7.
- No separate standstill handling beyond the floor. Mode sequencer `sub_045776` writes A[7:5] (end-of-ABS/resync).

## Wheel acceleration (struct+0x20, 0.01 g) [writer verified; normal source OPEN]
Writer `sub_0B65DC` (pass 0x8EE30): normal mode `y=raw`; on trigger (|+0x1E|>12000/10000 or sample count≥57)
enters slew-limited recovery (bit7): `y += clamp((raw−y)/8, ±56)`, `+0x20 = step·283/100` → ±158 (±1.58 g).
Low-passes: +0x24 = a_lp (decay 0.82/cyc), +0x26 = |a| LP (0..500), 0x408DAC = a−a_lp (ladder input "X").
- **CONFLICT / open:** 0xB65DC writes +0x20 only in recovery mode. In recovery range ±158, the peak-decel
  byte `w.39 = a/16` (sub_0465B0, smoothed) spans only ±9 — which would make the dump stages (−62/−78/−94)
  unreachable. So there is almost certainly a **normal-mode writer of +0x20 not yet found** (several scans
  missed it) OR +0x20 has a wider normal-mode source. Needs resolution (follow-up).

## Slip & threshold [verified; corrects earlier docs]
slip = vref − struct+0x1A. **ABS entry threshold `curve(ABS+0x576)` takes x = vref** (NOT slip): 150−4·vref/1024
(vref<50 km/h), 115+3·vref/1024 (≥50); lo0/hi900. Eval 150/130/144/158/173/202 @ vref 0/50/100/150/200/300 km/h.
Entry when `thr < slip`. Slip ratio 0x408F60 = (vref−wheel)·10000/vref (1e-4). w.32 = peak slip (vref−spd)/32
clamped 0..250. 0x408DAE = slip% (only 20<vref≤60 km/h).

## Decel threshold builder `fn 0x47DFC` → 0x4090C2[2·idx] [constants verified]
Bidirectional per-wheel accel threshold. Base ABS+0xCC=−116, floor ABS+0xCA=−240; low-speed floors
−120(<20)/−132(<60); front speed curve +0x76 (lo0/hi500: 0→74 over vref 0→300 km/h), rear +0x9E
(lo−110/hi150), 2nd curve +0xF4 (x=decel: 0→60). Pressure-imbalance relaxation for fronts; result −99 when
|a|<15. Positive side r11 = 63 (285/130 in control). Units 0.01 g (−116 = −1.16 g). **0x4090C2 is the decel
threshold; it is distinct from 0x409110 (pressure-reduction amount).**

## Ladder / dump-amount summation → 0x40910A+10·idx (R) [curves verified]
Per-wheel record R (5×s16): R+0 (sub_056106, pressure-proportional dump %), R+2 (sub_055D44, ladder), R+4
(sub_055EE8, decel×slip dump, clamp 100..1200), R+6 (sub_056106, total). L = pressure level 0x408FAC+2·idx.
- **R+0 pct curves (verified):** front +0x154 = 20/17/15/10/9/8 %; rear +0x17C = 30/22/15/12/9/6 % vs L.
- **R+2 ladder (sub_055D44):** input X=0x408DAC (a−a_lp); cal −140/−90/−40/−210 (+0x2C8..) scaled /1,/2,/4 by
  vref (≥60 / <60 / <20 km/h); stage thresholds give −150/−300/−500; positive branch −400/−650/−1000 for jerk.
- **R+4:** decel×slip dump, only 20<vref≤60 km/h; gain G by speed/flags; clamp 100..1200.
- **R+6 total** = R+0 + R+2 + R+4, ×curve(0xD72A0) if pressure<2500, + rear slip-sum (sub_056B96).
  Application: `new = L − R+6` floored 0; if new<commanded 0x408EFE → level reduced. **So 0x409110 = pressure
  REDUCTION amount, not a decel target.**

## Units
speeds/vref 0.01 km/h [verified]; +0x20 0.01 g (×2.83 conv) [high unit / med normal source]; 0x47DFC thr
0.01 g [med]; delta 0.01 km/h per 10 ms [verified]; 0x408D8B ≈0.01 g signed [med], = 0x408EC4/21; pressure
level 0.01 bar [unproven].

## Corrections to earlier docs
1. ABS+0x576 curve input = **vref**, not slip (both this and the phase agent agree).
2. w.39 = a/16 clamp ±127 in code but actual range ±9 given +0x20∈±158 → dump stages look unreachable (open).
3. **0x409110 = pressure-reduction amount**, not decel target; decel threshold is **0x4090C2**.

## Open (→ follow-up)
- **Normal-mode writer of +0x20/+0x22** (only recovery-mode 0xB65DC found). Biggest gap; may need dynamic trace.
- Meaning of +0x1E, struct+0x19 bit7, the w.0 / 0x408E49 / 0x408DC6 bit fields.
- sub_045776 mode counter; 0x408E5C / 0x408D94 / 0x408E46; pressure-level scale.

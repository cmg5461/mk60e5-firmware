# Does lateral acceleration (and yaw rate / steering) change ABS braking? — 7846816A (E9x M3)

Scope: whether **lateral g / yaw rate / steering** alter the **ABS** pressure/slip/decel loop (the user runs
"ABS only"), as opposed to only the **DSC/ASC yaw-control (AYC)** function. CPU addresses; file offset =
CPU + 0x8000. Confidence tags: **CONFIRMED** (read from bytes/opcodes), **INFERRED** (reasoned from code),
**UNCONFIRMED**. Per-mechanism sensor requirements and the no-SZL case: `09_chassis_sensor_use.md`.

## TL;DR

**Yes — lateral g, yaw rate and steering angle all modify ABS braking, through mechanisms inside the ABS
controller itself (0x44xxx–0x5Dxxx) that run regardless of DSC state.** They need valid chassis sensors: a
missing steering frame (F-CAN 0x0C9) also marks lateral and yaw invalid for ABS and switches all of them off
(FACTS.md "Steering-sensor loss"). The **vehicle model** (mass/l_f/l_r/Cf/Cr/Jz) does **not** feed ABS
pressure/EBD — only the DSC yaw observer/reference/AYC. A yaw-*deviation* link (measured − DSC-model target)
reaches the ABS region but is gated by AYC being active, so for a DSC-off / "ABS-only" car it is inert.

---

## 1. Where the sensors enter

`abs_sensor_gather` **0x5D82C** fills these every frame; validity bits are in `abs_sensor_valid` 0x408E6D
(b7 lateral, b6 brake pressure, b5 steering, b4 yaw):

| ABS RAM | Signal | Source |
|---|---|---|
| **0x408ECA** | lateral accel (signed **byte**, ≈ 0.01 g/count) | `abs_ay_get` 0x93AC0 (cluster ay); written every cycle, = `ay_wheel_estimate` when invalid |
| 0x408ECB | 2nd lateral channel (byte) | getter 0x93B3A, written only when valid |
| **0x408ECC** | yaw rate (s16, 1/20000 rad/s; 0 if invalid) | `abs_yaw_get` 0x94308 |
| **0x408ECE** | yaw accel (s16; 0 if invalid) | getter 0x94376 |
| 0x408EDE / 0x408EE4 / 0x408EE6 | steering-wheel angle (offset-corrected) / road-wheel angle / steering rate | getters 0x94120 / 0x9403C / 0x940AE |

[CONFIRMED]

**Steering in ABS:** the yaw-stable flag `0x408E5F` b4 (`abs_yaw_stable_update` 0x530E4) needs steering valid
and resets above ≈ 130° steering-wheel angle; the GMA rebuild pacing uses steering angle and rate; the
countersteer test uses the road-wheel angle sign; and steering validity gates the rear cornering latch and the
ax-based vref fall. Details in `09_chassis_sensor_use.md` §7. [CONFIRMED]

## 2. Cornering-dependent modification of ABS

### (a) Rear-axle strategy — `abs_decision_classify` 0x51B54 [CONFIRMED]
Writes the decision code 0x408DDE and the `pct` byte 0x408DE0 (`09_chassis_sensor_use.md` §2.1):
- **Yaw cornering flag:** |yaw| > curve **0x40E42**(−decel) while braking sets `0x409024` b0+b6.
- **Lateral-g thresholds:** with lateral + pressure valid and a rear cornering latch (or `0x40903C` b7),
  P_lo = 100·curve **0x40E26**(|lat|) and P_hi = 100·curve **0x40E0A**(|lat|) (+5 bar when |lat| > 80) are
  driver-pressure thresholds.
- Driver pressure below P_lo → **code 1** (rears handled independently, no select-low).
- A dumping wheel with P_lo < P_drv (and P_drv < P_hi or latch b5) → **code 32** with
  `pct = 100·(P_drv − P_lo)/(P_hi − P_lo)` (0x51F42).
- A straight-line shortcut (|lat| < 9, yaw-stable, balanced front pressures) → code 1.

`abs_decision_pressure_exec` **0x58FF4**, code-32 arm **0x59222**, then sets
`CMD(0x408F22) = PM − pct·(LOCKEST 0x408FD0 − CMD)/100`: the knock-down grows as the driver's pressure moves
from the light-braking curve toward the upper one.

### (b) Lateral-g build step — decision code 256 [CONFIRMED]
`abs_decision_resolve` 0x58B30 maps code 128 to **256** or 2; on the path at 0x58C4E–0x58C5E the choice is
the signed lateral byte ≥ 40 → 256, else 2 (the preceding wheel test was not fully reduced). Exec arm
**0x59064**: nothing for a wheel in dump or hold (`rec[0] & 0x28`) or with |lat| < 40; for |lat| > 80 with
wheel pressure PM < 40 bar, or 65 < |lat| ≤ 80 with PM < 30 bar, the command is set to
`min(0x408F42[w] + 80, 25000)`, a +0.8 bar step. The 40 ≤ |lat| ≤ 65 and higher-pressure paths (0x5910C,
0x59114) were not decoded. Step size, cap and the 40/65/80 gates are code literals.

### (c) µ-split yaw-moment limiting — `abs_pair_logic` 0x54D9A [CONFIRMED]
Runs only once `abs_pair_gate` 0x54B70 has seen an axle pressure split with |yaw| > cal 0x40DD4 on the
matching side and the yaw-stable flag. It then writes codes 32 / 1024 / 16 / 2 and paces the high-grip
wheel's +3 bar rebuild steps with `abs_gma_hold_frames` 0x54BE8 (slip, speed, decel, predicted yaw =
yaw + yaw accel/2, steering rate, steering added since the event began). `09_chassis_sensor_use.md` §2.4, §7.3.

### (d) Inside/outside rear-wheel lead [CONFIRMED]
`abs_rear_lead_select` **0x5184C** uses the **sign and magnitude of lateral accel 0x408ECA** — thresholds +6,
−5, −10 and 0x408ECB vs ±11 (0x5199A–0x519DA) — to decide which rear leads the select-low and to set bit9 in
the decision word (0x408DDE+10). Needs lateral valid (b7, 0x5197E).

### (e) Rear cornering latch and dump step size [CONFIRMED]
- The event classifier's rear cornering latch (0x4E908, needs lateral, pressure, steering and yaw valid)
  enables (a) and the yaw-limited flag in classifier block 14.
- `abs_dump_frame_flags` 0x4B160 halves / thirds the dump release steps on the selected front when
  |lat| > 50 / > 80 (`08_phase_control.md` §5.3).

> Note on magnitude: 0x408ECA is a signed **byte**; breakpoints (30/50/60/100/115) and thresholds (40/65/80)
> fit **~0.01 g/count** (±127 ≈ ±1.27 g). [byte CONFIRMED; 0.01 g/count INFERRED]

## 3. The vehicle model (0x5E424 / 0x5DE44) — feeds DSC only, not ABS [CONFIRMED]

`vehmodel_load_axle_derived` **0x5E424** writes RAM **0x400AE8..0x400AF8**;
`vehmodel_load_singletrack_coeffs` **0x5DE44** writes **0x400AA4..0x400AD8**.
Exhaustive consumer search:
- 0x400AE8..AF8 read only at **0x5E4xx** (loader), **0x900xx/0x905xx/0x90Exx** (CSI `yawref` / `yaw_ref_closedform`
  0x90D10/0x90E5C) and **0xBB8A8** (a monitor).
- 0x400AA4..AD8 read only at **0x5DExx** (loader), **0x5EBC4/0x5ECxx/0x5EDxx/0x5EFxx/0x5F0xx/0x5F9xx**
  (yaw observer + yaw PD) and **0x63Cxx** (AYC).
- **No read anywhere in the ABS controller region 0x44xxx–0x5Dxxx.**

⇒ mass/l_f/l_r/Cf/Cr/Jz influence **only** the DSC yaw target/observer and AYC brake intervention.
They have **no path into ABS front/rear distribution, EBD, slip targets, or pressure**. [CONFIRMED]

**Variant-0 (M3 sedan) model values** (first s16 of each table, byte-read from the bin):
l_f = l_r = 1413 (Q10) = **1.380 m each** (wheelbase 2.76 m, modeled ~50/50); mass **1787 kg**;
Jz **2999** kg·m²; track_f/r 1575/1573 Q10 m (1.538 / 1.536 m); **Cf = 7527, Cr = 10596**.
Understeer term **Cr·l_r − Cf·l_f = 10596·1413 − 7527·1413 = +4,336,497** (raw). **Sign is positive**
(Cr·l_r > Cf·l_f because rear cornering stiffness Cr > front Cf at equal l): the modeled car is
**static-understeer / yaw-stable**, the normal factory DSC reference. This number sets the DSC yaw
reference/observer only. [CONFIRMED values; physical LSBs of Cf/Cr UNCONFIRMED]

## 4. Axle-load transfer: longitudinal EBD vs lateral left/right

- **Longitudinal (front/rear EBD): present, and it is decel-based, not model-based.** The decel-threshold
  builder `abs_decel_threshold_builder` **0x47BDC** uses **separate front vs rear speed-term curves**
  (front family 0x40412+0x28·variant, rear 0x405F2) plus a g-term family 0x40674, and the rear wheel's
  pressure reference is the **same-side front wheel's pressure PM** (rear select-low / rear
  request id 11). That is the EBD-equivalent and it responds to deceleration, always active. It does
  **not** consult the vehicle model. [CONFIRMED structure]
- **Lateral left/right bias touching ABS** = the rear lead choice in §2(d) and the cornering knock-down in
  §2(a). There is **no** separate lateral axle-load lookup that re-splits left/right apply pressure.
  [INFERRED — no such table found in the ABS block]

## 5. Yaw-*deviation* (measured − DSC model target) link — gated by AYC [INFERRED inert for ABS-only]

`abs_yaw_deviation_monitor` **0x4A254**: computes **e = yaw_rate(0x408ECC) − AYC target B1A(0x400B1A)**
and a lateral-dependent threshold (ABS-block curve **0x40C5A**), storing e into ABS RAM
0x408EA2 / 0x408E9C / 0x408EA0. Those are consumed in the ABS region at 0x4E6AC/0x4E6D0, 0x4EB58,
0x50B94. **But** the useful branch is gated by AYC-active flags (0x408DEA bits6/7 and 0x401FF2 @0x4A270–
0x4A290); the target B1A is produced by the yaw observer, which runs the vehicle model only when DSC/AYC
is active. ⇒ For a DSC-off / "ABS-only" configuration this monitor is effectively **inert** (gate closed).
**Correction (2026-10-23):** it is *not* the only way the vehicle model reaches ABS. 13 other ABS literals load
0x400B1A (event classifier, `abs_side_select` 0x5AEEE, `abs_corner_peak_track` 0x5A4E4, 0x50894, 0x57024), plus
0x55420 → 0x4020EC. These are gated on yaw-valid only (FACTS "ABS reads the steering-based yaw target").

## 6. Net answer for a track user braking near the lateral limit

With working chassis sensors (SZL + yaw/lateral cluster), mid-corner ABS behaves differently from
straight-line, even in "ABS only":
1. **Rear strategy follows pedal pressure against lateral-g curves** (0x40E26 / 0x40E0A): light pedal →
   rears independent (code 1); firmer pedal on a dumping wheel → code-32 knock-down scaled by `pct`. [CONFIRMED]
2. **Rear inside/outside lead** follows the lateral-accel sign. [CONFIRMED]
3. **Dump release steps** are halved / thirded on the selected front above 0.5 / 0.8 g. [CONFIRMED]
4. **µ-split rebuild** of the high-grip wheel is paced by yaw and steering once a yaw kick opens the pair
   gate. [CONFIRMED]
5. Longitudinal **EBD** (decel-driven) is active throughout but is not cornering-specific. [CONFIRMED]

Without the SZL none of 1–4 run (rears stay select-low, full-size dump steps). In neither case is there
vehicle-model (Cf/Cr/mass) influence on ABS pressure or a model-based yaw-target intervention — those belong
to DSC/AYC. The cornering behaviour is cal-resident in the ABS block (0x40E0A/0x40E26/0x40E42, the GMA and
yaw-stable cals) plus code literals (40/65/80 lateral gates, +5 bar boost), so it is tunable, subject to the
ROM MISR re-sign.

### Key addresses
- ABS sensor-gather 0x5D82C → lateral 0x408ECA, yaw 0x408ECC, yaw-accel 0x408ECE, steering 0x408EDE/EE4/EE6.
- `abs_decision_classify` 0x51B54 (pct at 0x51F42); `abs_decision_resolve` 0x58B30;
  `abs_decision_pressure_exec` 0x58FF4 (code 32 @0x59222, code 256 @0x59064, code 8 @0x5932A).
- `abs_pair_logic` 0x54D9A + gate `abs_pair_gate` 0x54B70; pacing `abs_gma_hold_frames` 0x54BE8.
- `abs_rear_lead_select` 0x5184C.
- `abs_decel_threshold_builder` 0x47BDC (front 0x40412 / rear 0x405F2 / g-term 0x40674).
- `abs_yaw_deviation_monitor` 0x4A254 (gated).
- Vehicle model loaders 0x5E424 / 0x5DE44 → RAM 0x400AE8..AF8 / 0x400AA4..AD8 (DSC-only consumers).
- ABS-block lateral/yaw cal curves: 0x40E26, 0x40E0A, 0x40E42, 0x40C5A (all inside ABS block 0x4039C..0x40EA6).
- Variant model tables (file offsets): l_f 0xDEF42, l_r 0xDEF5A, mass 0xDEF72, Jz 0xDEF8A, Cf 0xDEECA, Cr 0xDEEE2.

## Lateral-g curves 0x40E0A / 0x40E26 — inputs, scaling, use

**1. X-axis input [CONFIRMED addr / INFERRED LSB].** Both curves take x = **|lateral accel|**, the signed byte
at **0x408ECA** (`ld.b;sextb;abs()` at 0x51C2C, 0x51C40, 0x51C54). **Neither is yaw rate.** Yaw rate
(0x408ECC) is used separately at 0x51B88 against curve **0x40E42** (x = decel) to latch the cornering flag
0x409024. With ~0.01 g/count the breakpoints are xs = 0.3/0.5/0.6/1.0/1.15 g. The CAN 0x1A0 AccY scaling
(`can_tx_1A0_ay` ×803/2048) is a separate outbound scaling — label plots in g, not CAN counts.

**2. Output [CONFIRMED scaling].** classify multiplies each curve by 100 (0x51C3A, 0x51C4E) → **0.01 bar**:
0x40E0A = **26→49 bar** over 0→1.27 g, **+5 bar** when |ay| > 0.8 g (0x51C60 r6=500, addu r8) = P_hi;
0x40E26 = **14→40 bar** = P_lo. Both rise with lateral g. They are compared with the driver's brake pressure
`0x408EB2`, not with wheel pressure.

**3. Use [CONFIRMED].** P_lo alone decides code 1 (P_drv < P_lo); P_lo and P_hi together give `pct` for
code 32 (§2(a)). 0x40E26 also releases the rear cornering latch (driver pressure < 100·curve(|lat|)).
**0x40C5A does not factor in**: it belongs to the AYC-gated `abs_yaw_deviation_monitor` 0x4A254.

**4. Tuning direction [INFERRED].** Raising P_lo widens the light-pedal band where the rears run independent
with no knock-down. For a given pedal pressure between the curves, raising P_hi lowers `pct` and so the
knock-down. The +5 bar high-g boost is a code literal (500 at 0x51C62), not in the curve. Re-sign ROM MISR at
0x4249C after any cal edit.

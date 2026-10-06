# Does lateral acceleration (and yaw rate / steering) change ABS braking? — 7846816A (E9x M3)

Scope: the headline question is whether **lateral g / yaw-rate / steering** alter the **ABS**
pressure/slip/decel loop (the user runs "ABS only"), as opposed to only the **DSC/ASC yaw-control
(AYC)** function. CPU addresses; file offset = CPU + 0x8000. Confidence tags: **CONFIRMED** (read from
bytes/opcodes here), **INFERRED** (reasoned from code), **UNCONFIRMED**.

## TL;DR

**YES — lateral g and yaw rate directly modify ABS braking, through three mechanisms that live inside
the ABS controller itself (0x44xxx–0x5Dxxx) and run during ABS regulation regardless of DSC state.**
Steering angle does **not** reach ABS (it feeds only CSI/DSC yaw reference). The **vehicle model**
(mass/l_f/l_r/Cf/Cr/Jz) does **NOT** feed ABS pressure/EBD at all — it feeds only the DSC yaw
observer/reference/AYC. There is additionally a yaw-*deviation* link (measured − DSC-model target) that
is consumed in the ABS region but is gated by AYC being active, so for a DSC-off / "ABS-only" car it is
effectively inert.

---

## 1. Where the sensors enter, and who consumes them (ABS vs DSC)

**The ABS controller has its own per-frame sensor-gather** (~0x5D8xx, in the ABS region), distinct from
the DSC yaw observer. At 0x05D93C–0x05D9BC it writes, each behind a validity getter:

| ABS RAM | Signal | Store | Source getter |
|---|---|---|---|
| **0x408ECA** | lateral accel (signed **byte**, ±127) | `st.b` @0x5D942 | cluster ay (F-CAN 0x0CD/0x0D1 → `csi_cond_sensor2` 0x8FE70) |
| 0x408ECB | 2nd lateral channel (byte) | `st.b` @0x5D97E | getter 0x93B3A |
| **0x408ECC** | yaw rate (s16, 0 if invalid) | `st.h` @0x5D9A4 | getter 0x94308 (`csi_cond_sensor0` 0x905E4) |
| **0x408ECE** | yaw accel (s16) | `st.h` @0x5D9BC | getter 0x94376 |

So lateral accel + yaw rate + yaw accel are ingested by ABS **every frame, independent of the DSC
yaw-control path**. [CONFIRMED]

- **Steering angle** (`steer_capture` 0x901D4 → 0x4020D0, `steer_ratio_convert` 0x9032E): consumed only
  by CSI/`yawref_stage_main` 0x90D10 and TX relay 0x0C4. **No reference from the ABS region 0x44xxx–0x5Dxxx.**
  Steering does **not** affect ABS. [CONFIRMED]

Consumers of 0x408ECA (lateral) and 0x408ECC (yaw) are **pervasive across the ABS controller**
(dozens of sites in 0x45xxx–0x5Dxxx). The load-bearing ones are below.

## 2. Cornering-dependent modification of ABS — the three mechanisms

### (a) Decision code 32 — lateral/yaw "build-percentage" limiter [CONFIRMED]
`abs_decision_classify` **0x51B54** (writes the ABS decision code 0x408DDE; called from the ABS
decision dispatcher `sub_05173C` @0x51748):
- Reads yaw rate 0x408ECC; if |yaw| > **1047** counts (= 23 + 1<<10; ≈3 deg/s at 1/20000 rad/s LSB) it
  sets cornering flag 0x409024 (bits 6,0). (0x51B88–0x51BC0)
- Reads lateral accel 0x408ECA, |ay|, and evaluates **ABS-cal-block curves 0x40E26 and 0x40E0A** (both
  < 0x40EA6 ⇒ inside the ABS cal block), scaling ×100 → a build percentage; branch at |ay|>80.
  (0x51C2A–0x51C66) It also uses peak-decel curve 0x40E42.
- This is gated by the wheel being in an active ABS control phase (flag 0x408E6D bits 0xC0; else build% = 0).

`abs_decision_pressure_exec` **0x58FF4**, code-32 branch @0x59222 (and its resolved code-8 branch
@0x59064, which re-reads 0x408ECA and tests |ay| vs 40/65/80): takes the percentage byte, multiplies the
pressure headroom `(CMD 0x408F22 − PM 0x408F42)` or `(LOCKEST 0x408FD0 − …)` by %/100, and writes a
**reduced/limited commanded pressure back to 0x408F22**. Net effect: **during cornering the ABS
re-apply/build is throttled** — pressure is allowed to rise less aggressively as |ay| and |yaw| grow.
This is classic cornering-brake-control behavior built into ABS. [CONFIRMED mechanism; exact %-shape per
curves above]

### (b) Pair-logic cornering gate [CONFIRMED]
`abs_pair_logic` **0x54D9A** (ABS axle-pair S0..S3 machine; called @0x51FA0): at entry it forms a
**short-horizon predicted yaw = yaw_rate(0x408ECC) + yaw_accel(0x408ECE)/2** (0x54DA0–0x54DB8), then
calls gate `sub_054B70`; if the gate returns 0 the pair path is skipped (jmp to exit). It writes ABS
decision codes 32 / 16 (0x54E48, 0x54F08). So the axle-pair hold/reapply cycle is steered by yaw
rate + yaw accel. [CONFIRMED]

### (c) Inside/outside rear-wheel selection (select-low bias) [CONFIRMED]
`abs_rear_lead_select` **0x5184C** (rear select-low; called @0x51744): uses the **sign and magnitude of
lateral accel 0x408ECA** — thresholds |ay| vs +6, −5, −10 and 0x408ECB vs ±11 (0x5199A–0x519DA) — to
decide which rear wheel leads and to set bit9 in the decision word (0x408DDE+10). This is directional,
cornering-aware rear-wheel handling (inside vs outside). [CONFIRMED]

> Note on magnitude: 0x408ECA is a signed **byte**, so the lateral term the ABS loop sees is coarse
> (≈ few % g per count); the thresholds (6, 40, 65, 80) are in those byte units. [CONFIRMED it is a byte;
> absolute g/count UNCONFIRMED]

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

**Variant-0 model values** (first s16 of each table, byte-read from the bin):
l_f = l_r = 1413 (Q10) = **1.380 m each** (wheelbase 2.76 m, modeled ~50/50); mass **1787 kg**;
Jz **2999** kg·m²; track_f/r 1575/1573 mm; **Cf = 7527, Cr = 10596**.
Understeer term **Cr·l_r − Cf·l_f = 10596·1413 − 7527·1413 = +4,336,497** (raw). **Sign is positive**
(Cr·l_r > Cf·l_f because rear cornering stiffness Cr > front Cf at equal l): the modeled car is
**static-understeer / yaw-stable**, the normal factory DSC reference. This number sets the DSC yaw
reference/observer only. [CONFIRMED values; physical LSBs of Cf/Cr UNCONFIRMED]

## 4. Axle-load transfer: longitudinal EBD vs lateral left/right

- **Longitudinal (front/rear EBD): present, and it is decel-based, not model-based.** The decel-threshold
  builder `abs_decel_threshold_builder` **0x47BDC** uses **separate front vs rear speed-term curves**
  (front family 0x40412+0x28·variant, rear 0x405F2) plus a g-term family 0x40674, and the rear wheel's
  pressure reference is the **same-side front wheel's modelled pressure** (rear select-low / rear
  request id 11). That is the EBD-equivalent and it responds to deceleration, always active. It does
  **not** consult the vehicle model. [CONFIRMED structure]
- **Lateral left/right bias touching ABS = the inside/outside rear-wheel select-low bias in §2(c)**,
  keyed on lateral-accel sign. There is **no** separate lateral axle-load lookup that re-splits
  left/right apply pressure beyond that select-low handling. [INFERRED — no such table found in the ABS block]

## 5. Yaw-*deviation* (measured − DSC model target) link — gated by AYC [INFERRED inert for ABS-only]

`abs_yaw_deviation_monitor` **0x4A254**: computes **e = yaw_rate(0x408ECC) − AYC target B1A(0x400B1A)**
and a lateral-dependent threshold (ABS-block curve **0x40C5A**), storing e into ABS RAM
0x408EA2 / 0x408E9C / 0x408EA0. Those are consumed in the ABS region at 0x4E6AC/0x4E6D0, 0x4EB58,
0x50B94. **But** the useful branch is gated by AYC-active flags (0x408DEA bits6/7 and 0x401FF2 @0x4A270–
0x4A290); the target B1A is produced by the yaw observer, which runs the vehicle model only when DSC/AYC
is active. ⇒ For a DSC-off / "ABS-only" configuration this is the **one** way the vehicle model could
touch ABS, and it is effectively **inert** (B1A stale/zero, gate closed). The §2 direct lateral/yaw
mechanisms do **not** depend on it. [INFERRED]

## 6. Net answer for a track user braking near the lateral limit

Mid-corner at high |ay| and |yaw|, **ABS will behave differently than straight-line, even in "ABS only":**
1. The **re-apply/build pressure is throttled** by the lateral/yaw build-percentage (decision code 32,
   curves 0x40E26/0x40E0A) — ABS holds a lower/slower-rising pressure the harder you corner. [CONFIRMED]
2. The **axle-pair hold/reapply cycle is modulated** by predicted yaw (yaw + yaw-accel) in pair-logic. [CONFIRMED]
3. **Rear inside/outside wheel lead changes** with the lateral-accel sign (select-low bias). [CONFIRMED]
4. Longitudinal **EBD** (front-biased, decel-driven) is active throughout but is not cornering-specific. [CONFIRMED]

What does **not** happen in ABS-only: no steering-angle input, no vehicle-model (Cf/Cr/mass) influence on
ABS pressure, and no yaw-target (model-based) intervention — those belong to DSC/AYC, which is off.
Practically: the stock firmware deliberately **softens/limits ABS brake build when it senses cornering**
(a conservative, understeer-safe bias), so a track driver trail-braking at the limit gets less brake
pressure than the tyre could take; this is cal-resident in the ABS block (0x40E0A/0x40E26/0x40C5A, the
|yaw|>~3 deg/s and |ay| byte thresholds) and is therefore **tunable**, subject to the ROM MISR re-sign.

### Key addresses
- ABS sensor-gather ~0x5D8xx → lateral 0x408ECA, yaw 0x408ECC, yaw-accel 0x408ECE.
- `abs_decision_classify` 0x51B54; `abs_decision_pressure_exec` 0x58FF4 (code-32 @0x59222, code-8 @0x59064).
- `abs_pair_logic` 0x54D9A + gate `sub_054B70` 0x54B70.
- `abs_rear_lead_select` 0x5184C.
- `abs_decel_threshold_builder` 0x47BDC (front 0x40412 / rear 0x405F2 / g-term 0x40674).
- `abs_yaw_deviation_monitor` 0x4A254 (gated).
- Vehicle model loaders 0x5E424 / 0x5DE44 → RAM 0x400AE8..AF8 / 0x400AA4..AD8 (DSC-only consumers).
- ABS-block lateral/yaw cal curves: 0x40E26, 0x40E0A, 0x40E42, 0x40C5A (all inside ABS block 0x4039C..0x40EA6).
- Variant model tables (file offsets): l_f 0xDEF42, l_r 0xDEF5A, mass 0xDEF72, Jz 0xDEF8A, Cf 0xDEECA, Cr 0xDEEE2.

## Cornering-limiter curves 0x40E0A/0x40E26 — inputs, scaling, apply

**Correction to §2(a):** closer reading of `abs_decision_classify` 0x51B54 shows these two curves
produce a **pressure-domain** term (×100 → 0.01 bar), not a 0–100 % factor. Details:

**1. X-axis input & scaling [CONFIRMED addr / INFERRED LSB].** BOTH curves take x = **|lateral accel|**,
read from the signed byte at **0x408ECA** (`ld.b;sextb;abs()` at 0x51C2C, 0x51C40, 0x51C54). **Neither is
yaw rate.** Yaw rate (0x408ECC) is used *separately* at 0x51B88: curve **0x40E42** (x = peak-decel byte)
yields a threshold that |yaw| is compared against to latch the cornering flag 0x409024 (bits 6,0).
The ABS lateral byte is a coarse copy (gather truncates the cluster halfword at 0x5D942). Breakpoints
(xs 30/50/60/100/115) and thresholds (40/65/80) map cleanly to **~0.01 g/count** (byte ±127 ≈ ±1.27 g),
so xs = 0.3/0.5/0.6/1.0/1.15 g. [addr CONFIRMED; 0.01 g/count INFERRED from breakpoint plausibility;
cycle-7 raw cluster ay = 1 mg but that is re-scaled before this byte]. Relation to CAN 0x1A0 AccY
(`can_tx_1A0_ay` ×803/2048) is a separate outbound scaling — label the plot x in g, not CAN counts.

**2. Output semantics [CONFIRMED scaling; bar unit INFERRED].** classify multiplies each curve by 100
(0x51C3A, 0x51C4E) → values in **0.01 bar**: 0x40E0A = **26→49 bar** over 0→1.27 g, **+5 bar** added when
|ay|>0.8 g (0x51C60 r6=500, addu r8); 0x40E26 = **14→40 bar**. Both **rise with lateral g** — they are a
lateral-load (outside-wheel) **pressure term that increases with cornering load**, NOT a blanket
knockdown. The ×100/+500 prove these are pressures (the exec's separate % byte is a `ld.b` ≤255, so these
feed a pressure reference, not that byte).

Separately, `abs_decision_pressure_exec` 0x58FF4 code-32 (0x59222) computes
**new CMD(0x408F22) = PM − pct·(LOCKEST − CMD)/100**, floored (0x59272–0x5930A) — a headroom-limited
command using a small % byte at 0x408DE0 (producer not yet traced).

**3. Combination [CONFIRMED separate / role UNCONFIRMED].** The two curves land in separate registers
(0x40E26→r11, 0x40E0A→r8+boost); they are **not** multiplied/min'd together here. 0x40E0A is the primary
term (wider range + the high-g +5 bar boost); 0x40E26 is a smaller companion (likely the other wheel of
the pair or a lower stage). Exact store destination (ceiling via min vs reference/offset) **not fully
traced** — do not commit a tuning sign until confirmed with a dynamic trace.
**0x40C5A does NOT factor into code-32**: it belongs to `abs_yaw_deviation_monitor` 0x4A254 (AYC-gated,
measured − model yaw target) — a separate DSC-dependent path [CONFIRMED].

**4. Tuning direction [INFERRED, pending role confirmation].** These curves make the lateral-g pressure
term grow with g. If they act as per-wheel pressure **ceilings/references**, then to give a track driver
MORE brake authority while cornering you RAISE the outputs: lift `cs[]` (offsets) and `ks[]` (slopes),
most impactfully on **0x40E0A** in the 0.3–0.8 g band (segments at xs 50 and 100) plus the **+5 bar
high-g boost** (hard-coded 500 at 0x51C62 — a code patch, not in the curve), and similarly 0x40E26.
If instead they feed the headroom knockdown, LOWER them. The scaling evidence favors the ceiling/reference
reading. Re-sign ROM MISR at 0x4249C after any cal edit.

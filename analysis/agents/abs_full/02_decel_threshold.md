# ABS wheel-deceleration-rate trigger path — 7846816A (E9x M3)

Scope: the wheel-**deceleration-rate** trigger of ABS (complement to the gross-slip trigger at
`abs_gross_slip_threshold` 0x052380 / curve 0xD6CE2). All addresses CPU; **file offset = CPU + 0x8000 =
XDF addr**. s16 big-endian. Curve evaluator (verified): layout `[lo,hi,n, xs(n-1), cs(n), ks(n)]`;
`i = #{xs[j] : x>=xs[j]}`, `y = clamp(cs[i] + ((x*ks[i])>>10), lo, hi)`.
Confidence tags: **[C]** confirmed from bytes/code here · **[I]** inferred · **[U]** unconfirmed.

---

## 1. `wheel_accel_update` 0x0D20DC — how wheel accel/decel is computed  [C]

Disassembly (file 0x0D20DC, 15 insns):
```
r6 = 0xE287 = 58023                       ; scale numerator
r2 = Δv * 58023                           ; Δv = input (clamped wheel-speed delta, see caller)
r2 = trunc(r2 / 2^11)   (signed, round-toward-zero idiom asri10/lsri21/add/asri11)
r2 = trunc(r2 / 10)     (divs)            ; => r2 = trunc(Δv * 58023 / 20480) = Δv * 2.83315
r4 = *(0x400978)                          ; current wheel struct ptr (loop var, stride 0x40)
r3 = [struct+0x1E] (prev raw accel)
     [struct+0x1E] = r2                   ; store new raw accel
r2 = (r2 + r3) >> 1                        ; TWO-FRAME MEAN
     [struct+0x20] = r2                    ; <-- wheel acceleration, 0.01 g
```
- **Scale factor 2.8332 = 58023 / 20480** (= 58023/2^11/10). Literal 0xE287 byte-verified; identical to 1M
  0xD271C. **[C]**
- **Input Δv**: from the caller `wheel_speed_update` 0x07525C at the `jsri` 0x075482. Before the call r10
  (=Δv) is clamped to **±5714 (0x1652 / 0xFFFFE9AE)** — the glitch clamp — then `mov r2,r10`. Δv is the
  per-frame change of the filtered wheel speed in 0.01 km/h. **[C]**
- **Unit proof (0.01 g, 10 ms frame)**: 1 count of Δv (0.01 km/h) over one frame →
  output = 2.8332 counts = 0.028332 g. Physically 0.01 km/h / 10 ms = 0.27778 m/s² = 0.028326 g. Match to
  4 sig-figs ⇒ **output unit = 0.01 g and the frame is 10 ms, CONFIRMED.** **[C]**
- struct+0x1E = single-frame raw accel; **struct+0x20 = two-frame mean**, the value every threshold path
  consumes. A further ±20 g clamp and the peak byte `w.39 = a/16` live in `wheel_peak_decel_byte` 0x046390
  (not here). **[C]**

---

## 2. The decel THRESHOLD builder `abs_decel_threshold_builder` 0x047BDC → 0x4090E6[wheel]  [C bytes / I unit]

Produces a **bidirectional** per-wheel accel threshold (0.01 g). Called per wheel from the event path at
0x0472D8; the return value (r2) is compared against the wheel's `struct+0x20` accel at 0x0472F0–0x047316
(`cmplt r9,r2`: accel below threshold ⇒ decel event; struct+6 integrates the exceedance). Result also
stored to the array `0x4090E6 + 2*wheel_idx`. **Front = wheels 0,1 / rear = 2,3**, distinguished by
`btsti ptr,7` on the struct pointer (base aligned so +0x80/+0xC0 set bit7). **[C]**

Cal inputs (literal pool of 0x047BDC, byte-verified values):

| Role | CPU | file | var-0 value |
|---|---|---|---|
| decel_base | 0x40620 | 0x48620 | **−116** (−1.16 g) |
| decel_floor (abs min) | 0x4061E | 0x4861E | **−240** (−2.40 g) |
| floor<20 table (12×) | 0x40644 | 0x48644 | **−127** (v0); −120 (v1..11) |
| floor<60 table (12×) | 0x4065C | 0x4865C | **−132** (v0..9); −140 (v10,11) |
| speed-term front family (stride 0x28) | 0x40412 | 0x48412 | curve, see §3 |
| speed-term rear (single) | 0x405F2 | 0x45DF2 | curve, see §3 |
| g-term family (stride 0x40) | 0x40674 | 0x48674 | curve, see §4 |

Core build sequence:
```
thr = base (−116)
thr -= speed_term(vref)      ; front curve 0x40412+0x28*var (by coding var 0x4031AA+1) or rear 0x405F2
thr -= g_term(|decel|)       ; curve 0x40674+0x40*var, x = |vehicle decel estimate|
thr  = max(thr, decel_floor = −240)                 ; absolute deepest
if vref < 6000 (60 km/h):  thr = max(thr, floor60[var] = −132)
if vref < 2000 (20 km/h):  thr = max(thr, floor20[var] = −127)
```
- Both curve terms are **subtracted** from base ⇒ the threshold **deepens** (more negative) with speed and
  with current deceleration, trending toward the −2.40 g floor. **[C]**
- Low-speed floors are **max()** clamps ⇒ they **cap how deep** the threshold may go at low speed (relax it):
  ≤ −1.32 g below 60 km/h, ≤ −1.27 g below 20 km/h. They bind only when the g-term has already driven the
  threshold past those limits (at low speed the speed-term is ~0). **[C]**
- **Floor selection = coding variant** `[0x4031AA+1]` (0..11), `ld.b` + `ixh` into each 12-entry table. The
  `<20` gate is `vref<2000`, the `<60` gate `vref<6000`. **[C]**
- **Above 60 km/h** neither low-speed floor applies: the only lower bound is the absolute floor −240, so the
  threshold is free to deepen with speed/decel from −1.16 g toward −2.40 g. **[C]**

Secondary adjustments in the same function:
- **|wheel accel| < 15 (±0.15 g) ⇒ thr forced to −99** (−0.99 g), a shallow default (also taken for a rear
  wheel when `[0x408DEB]` bit5 set). 0x047DE6–0x047E00. **[C]**
- **Front split-μ / pressure-imbalance term** (front only, 0x047D44–0x047DA0): when own wheel pressure
  `PM 0x408F2A` far exceeds the same-axle partner's, `thr -= clamp(ΔPM/300, ≥8)` (deepens). Conditional,
  bytes read; physical intent inferred. **[I]**
- **Special fixed override −130 / −135** (0x047CE0–0x047CE8) when a wheel phase byte (`[0x40902E+…]` bit1)
  is set. **[C bytes] / [I meaning]**
- A gated rough-road speed trim (−25/−21/−15/−8 at >160/120/80/60 km/h) applies only when `[0x408DEB]`
  bit0 set with specific wheel-valid conditions; skipped in the normal path. **[C bytes]/[I]**

g-term x-input source (default path): `r12 = min([0x408DAF], −[0x408DB8])`, signed bytes = a **vehicle
longitudinal decel estimate**; x = −r12 = |decel|. Curve breakpoints 0.30–1.83 g strongly imply the x-axis
unit is 0.01 g. **[I unit]**

---

## 3. Speed-term curve family 0x40412 (front, stride 0x28) — variant 0  [C]

Stored bytes (CPU 0x40412): `lo=0, hi=500, n=6, xs=[10000,15000,20000,25000,30000],
cs=[0,−10,−10,−50,−95,−277], ks=[1,2,2,4,6,12]`. x = vref (0.01 km/h). Decoded output (0.01 g), **subtracted
from base** (so it *deepens* the decel threshold as speed rises):

| vref km/h | 0 | 20 | 40 | 60 | 80 | 100 | 120 | 150 | 200 | 250 | 300 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| speed_term | 0 | 1 | 3 | 5 | 7 | 9 | 13 | 19 | 28 | 51 | 74 |
| g equiv | 0 | .01 | .03 | .05 | .07 | .09 | .13 | .19 | .28 | .51 | .74 |

So the threshold goes from −1.16 g (standstill) to about −1.16−0.74 = **−1.90 g at 300 km/h** before the
g-term. **Rear** curve 0x405F2 has identical cs/ks but `lo=−110, hi=150` (allows a small negative/relaxing
value); output is the same 0..74 in practice. Variants 0–9 identical; 10/11 more permissive (per symbols).

---

## 4. g-term curve family 0x40674 (stride 0x40) — variant 0  [C bytes / I x-unit]

Stored bytes (CPU 0x40674): `lo=0, hi=250, n=10, xs=[30,50,70,100,110,120,130,155,183],
cs=[0,−8,−22,−31,−54,−65,−41,−77,−104,−121], ks=[0,256,563,683,922,1024,819,1106,1280,1376]`.
x = |vehicle decel estimate| (0.01 g, from signed byte ⇒ reachable 0..127). Decoded output (0.01 g),
**subtracted from base** (deepens the threshold as the car brakes harder):

| |decel| g | 0.00 | 0.30 | 0.50 | 0.60 | 0.80 | 1.00 | 1.27 |
|---|---|---|---|---|---|---|---|
| g_term | 0 | 0 | 5 | 10 | 22 | 36 | 60 |

Flat (0) below ~0.3 g, rising to +0.60 g of extra depth at the ±1.27 g byte limit (breakpoints 155/183
unreachable from a signed byte).

### Effective decel-threshold formula (function of vref and current decel)
```
thr(vref, decel) [0.01 g, negative] =
    base − speed_term(vref) − g_term(|decel|)
    with base = −116
         speed_term = curve 0x40412+0x28*var  (front)  or 0x405F2 (rear),  x = vref
         g_term     = curve 0x40674+0x40*var,  x = |decel|
    thr = max(thr, −240)                       # absolute floor
    if vref < 60 km/h: thr = max(thr, floor60[var] = −132)
    if vref < 20 km/h: thr = max(thr, floor20[var] = −127)
    if |wheel_accel| < 15 (0.15 g): thr = −99  # shallow override
    (front only) thr −= clamp(ΔPM/300, ≥8)     # split-μ imbalance, conditional
```
A wheel triggers a pressure dump when its `struct+0x20` (two-frame-mean wheel accel, 0.01 g) falls **below**
`thr`. Worked points (front var 0, ignoring the split-μ/override terms):
- 100 km/h, light vehicle decel (<0.3 g): thr = −116 − 9 − 0 = **−1.25 g**
- 100 km/h, 1.0 g vehicle decel: thr = −116 − 9 − 36 = **−1.61 g**
- 300 km/h, 1.0 g: −116 − 74 − 36 = −226 → **−2.26 g**
- 50 km/h, 1.0 g: −116 − ~4 − 36 = −156 → clamped by floor60 to **−1.32 g**
- 15 km/h, 1.0 g: → clamped by floor20 to **−1.27 g**

---

## 5. Acceleration (spin-up / re-apply) threshold ending a dump  [C]

The same builder emits a **positive** threshold when the wheel is recovering, selected at the output
(0x047E02–0x047E30) by the sign of `struct+6` (the decel-exceedance integrator) and the sign of the wheel
accel:
- `r13 = 63` default (+0.63 g) — not in an active control cycle;
- in-cycle (rec[0] bit0 set): `r13 = 285` (+2.85 g) if `struct+16` bit2 clear, else `r13 = 130` (+1.30 g).

When `struct+6 > 0` (reapply side) and wheel accel ≥ 0, the stored threshold is this positive value; the
phase machine ends the dump / begins rebuild once the wheel's spin-up acceleration crosses it. So the
re-apply acceleration threshold is **+0.63 g (idle) / +2.85 g / +1.30 g (in-cycle)**. (`−99` shallow decel
threshold and `−130/−135` overrides from §2 also participate.) **[C bytes] / [I phase semantics]**

---

## Distinctness from EBD/DSC
This path is the **ABS controller's** per-wheel accel threshold (code 0x44000–0x4E000, reading the ABS cal
block 0x4039C). It is independent of: the TCS drive-slip thresholds (0xF61F6/0xF625C, engine side), the AYC
yaw thresholds, and the EBD/brake-force logic. The vehicle-decel byte feeding the g-term is a shared signal
but the curves/floors above are ABS-cal only. **[I]**

## Residual unknowns
- Exact unit/source of the g-term x bytes `[0x408DAF]/[0x408DB8]` (inferred 0.01 g vehicle decel). **[U]**
- Physical meaning of the `struct+6` integrator scaling at the caller (0x47318, ×104|256 /(1024−23)). **[U]**
- The `[0x40902E]`-indexed phase byte selecting the −130/−135 override. **[U]**

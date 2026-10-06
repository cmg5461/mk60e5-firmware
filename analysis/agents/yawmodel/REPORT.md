# Yaw / single-track reference model + DSC mode (1M 7846411A; M3 compared)

Agent-derived (Sonnet), **key claims verified by main session**: vehicle-model scalars (l_f 1331, l_r 1393,
mass 1739, Jz 3039, Cf 7186, Cr 12857, tracks 1575/1573), AE8=675·(l_f+l_r)/1024=1795, AYC mode tables
(+0x230=1396, +0x232=2792, clamps [10471,10471,8028]/[9773,9773,7330], +0x62=[200,200,100], +0xF2=[1,0,0],
+0x294=698) — all byte-exact. Scripts in `analysis/agents/yawmodel/` (`sim.py` integer observer replica, etc.).

## 1. Vehicle-model parameters [verified values; roles agent high]
1M scalars at 0xD7468+ (M3 = coding-indexed rows, geom REPORT). l_f/l_r settled by three independent uses
(front slip angle, front axle load m·l_r/L = 51.1% front, torque balance ṙ=(l_f·F_f−l_r·F_r)/Jz):
l_f=1331 (1.30 m), l_r=1393 (1.36 m), **mass 1739 kg**, **Jz 3039 kg·m²** (Jz/m=1.75 m²≈l_f·l_r → consistent),
Cf 7186 / Cr 12857 (cornering stiffness, ~16 N/rad per LSB [med-low]), tracks 1575/1573.

## 2. There is a real single-track (bicycle) model [verified]
- **Closed-form reference** (CSI fn 0x90C44 → 0x4020EC): `r_ref = δ·v / (L·(1+v²/v_ch²))`, **v_ch = 97.65 km/h**
  (v_ch² = 32·AEA·AE8). Plus redundant yaw estimates from wheel-speed diff, lateral accel (r=a_y·k/v), and the
  validated measured yaw rate; cross-checked in fn 0xBB15E.
- **Dynamic observer** (AYC fn 0x5ECB0, once/10 ms): states β=0x400C42, r=0x400C44; nonlinear tyre with a
  friction clip; trapezoidal integration. Output **B1A = 0x400B1A = reference (target) yaw rate**, friction-
  limited by `r_lim ≈ μ·g/v`. Numerically validated (sim.py): gain peaks ~80–100 km/h, best-fit v_ch 97.0 km/h,
  step time ≈10 ms. Also computes a steering-deviation/understeer measure (δ = L·r/v + K_us·a_y).
- Measured yaw rate from F-CAN 0x0CD (redundant 0x0D1) → LPF → 0x402100 (B46); lateral accel 0x0CD word2.

## 3. Yaw error → intervention [verified code; semantics med]
```
e = B46(measured) − B1A(model target)            ; fn 0x60D68
entry: |e| > B6C ;  hold: |e| > B70 while active ;  persistence ≥79 → controller active
u = B76·max(0,|e|−B70)·sgn(e)/16384 + B78·(yaw-error rate)/16384    ; PD yaw-moment demand
```
Threshold base: AYC+0x230 = 1396 (set A), +0x232 = 2792 (set B); B6C = base·f(v,m)/128; B70 = B6C − 698.
Output → brake (request ids 3/20) and engine-torque (fn 0x6514C) sides.

## 4. DSC mode = 3-state index (the permissiveness thread) [verified tables]
Mode `m ∈ {0,1,2}` written by 0xCF92A (from TCS cycle): `m=0 if 0x4030A4∈{1,4,5} or 0x4030A2≠3; else m=2 if
coding bit set, else 1`. The **coding bit = record byte 10 bit 5** (EEPROM, getter 0xD02D8). So the mode is
(TCS state) × (one coding bit).

Mode-indexed AYC entry threshold B6C (set A, by speed):

| m | 20 | 50 | 80 | 120 | 160 | 200 km/h |
|---|---|---|---|---|---|---|
| 0, 1 (identical) | 3490 | 3490 | 3013 | 2378 | 1952 | 1396 |
| 2 | 2420 | 1861 | 1396 | 1396 | 1396 | 1396 |

P-gain: m0/m1 = 30/30/43/60 %, m2 = 73/77/84/100 %. Torque curve @0.8 g: m0=400, m1=2000, m2=330.
Feature-enable AYC+0xF2 = [1,0,0] (a feature active only for m0).

**Direction:** **m=1 is the most permissive** (loose yaw thresholds + largest TCS slip + highest torque-
intervention ceiling); **m=2 is the tightest yaw control**; m=0 pairs tight traction with loose yaw (reads
like a differential-brake off-state [agent, low]). The physical car picks m=1 vs m=2 via the coding bit, only
while TCS state is 2/3. **M3 AYC block is byte-identical to the 1M** except three per-variant arrays
(+0x46A/+0x482) — so the yaw/mode tables themselves are not M-specific.

## 5. Open / needs-hw
- **[needs-hw]** Which driver-visible mode (DSC-on / DTC / MDM / OFF) each m runs in — needs the live values
  of 0x4030A4/A3, 0x400DF2, 0x4031B1 while cycling the DSC button, plus coding byte 10 bit 5.
- **[needs-hw]** Absolute sensor LSB scales (yaw 15.7k vs 20.4k per rad/s; steering; lat-accel) — bench/CAN capture.
- **[agent, med-low]** Stiffness unit (~16 N/rad). **[partial]** 2nd half of 0x5ECB0 (re-sync flags), path
  B1C → valve/torque arbiter (ids 3/20) not fully followed.

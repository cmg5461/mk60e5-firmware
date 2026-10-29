# vref, the decel estimate and the longitudinal accelerometer — 7846816A (E9x M3)

Read from `analysis/7846816A_main.lst`. **Not bench-verified** except where noted. CPU addresses. Tags: **[C]** read
from code, **[I]** inferred, **[U]** unknown.

Units: speeds 0.01 km/h; accel 0.01 g; frame 10 ms. One vref count per frame = 1 km/h/s = **0.0283 g**, so
44/frame = 1.25 g and 0.36 count/frame ≈ 0.01 g (the `×360/1000` in the code converts 0.01 g to counts, ×1.02).

| step/frame | g | | step/frame | g |
|---|---|---|---|---|
| 11 | 0.31 | | 44 | 1.25 |
| 22 | 0.62 | | 49 | 1.39 |
| 32 | 0.91 | | 63 | 1.78 |
| 40 | 1.13 | | 71 | 2.01 |

Related: `01_core_slip_loop.md` §1 (summary), `09_chassis_sensor_use.md` §2.6 /
§2.10, `02_decel_threshold.md`, FACTS "[disasm 2026-10-06]".

---

## 1. Signals [C]

| RAM | type | what |
|---|---|---|
| `vref` 0x408DA8 | s16 | reference speed; sole writer `vref_update` 0x449D0 |
| 0x408E7E | s16 | shadow integrator; written only in `vref_update` and `vref_fall_from_ax`; kept ≤ vref, ≥ floor. No literal-pool reader found [U] |
| 0x4032D0 | s16 | speed floor (~0.6 km/h, from tyre circumference at init) |
| `abs_decel_est` 0x408DAF | s8 | "DAF", vehicle decel estimate. Writer 0x534E6 = `0x408EE8 / 21`; 0x408EE8 is written by `sub_053720` (below). Wheel/speed-derived, so self-referential once all four wheels slip [I] |
| `abs_ax` 0x408E80 | s16 | ax used by ABS. Gather 0x5D82C: = DAF by default, overwritten by the cluster ax (`0x4049FC`, s8, ±1.27 g) when the getter is valid |
| `abs_ax_flags` 0x408E1C | u8 | b7 = **ax trusted** |
| `abs_estim_flags` 0x408E1B | u8 | b4 = ax valid |
| `abs_mode_flags` 0x408DA1 | u8 | b4 = braking / ABS regime; bits 7:5 controller mode |
| `abs_sensor_valid` 0x408E6D | u8 | b7 lat, b6 pressure, b5 steering, b4 yaw |

### 1.1 ax trust (`abs_ax_decel_estimator` 0x49572) [C]
Two paths write b7 of `0x408E1C`:
- **Initial trust, 0x49AE0–0x49CB8.** All of: driver pressure `0x408EB2` > cal 0x40CC6 (5 bar), `0x401FF2` b7, not in
  the ABS regime (0x408DA1 b4 clear), `0x408E68` b7 clear, **`0x408E6D` b7 and b6 (lateral and pressure valid)**,
  **`0x408E5F` b4 (yaw-stable)**, DAF < 0 (and ax the same sign, unless b5), **\|lat\| `0x408ECA` < cal 0x40C9A (0.20 g)**.
  Each passing frame updates the agreement counter `0x408EA7`; b7 is set once it reaches 5, with b3 set and the
  deviation `0x408E8E` < 20. Any failed condition goes to 0x49CDA, which clears b6 only.
- **Re-trust, 0x49AA8–0x49AD8.** Needs b2, which 0x49614 sets only when ax was trusted (b7) and then went stale
  (alive counter `0x408E8C` reached 0). Then: ax valid, not in the regime, counter ≥ 16, deviation < 50.
- So **trust is never established without lateral and yaw**, i.e. without the SZL (bench-confirmed on the MR2:
  lat/yaw/steering invalid, b7 and b2 0 for a whole 740 s drive, b3 1). Only the re-trust path lacks a
  lateral / yaw / steering input, and it needs prior trust.
- Cleared when the deviation exceeds 500, or when the alive counter reaches 0. The counter is held ≥ 25 while
  the ax signal changes (0x408E94 ≠ 0x408E8A) and counts down above 10 km/h while it is frozen.
- **Deviation integrator 0x408E8E (0x49632–0x49A26) [C, 2026-10-23].** Runs while braking (0x401FF2 b7), vref > 5 km/h,
  DAF < 0 and ax valid (ax invalid → 1000 at once). e = \|DAF − ax\|, T = cal 0x40D46 = 20 (0.20 g). Outside the ABS
  regime: +5 / +4 / +3 / +2 per frame for e > T+30 / T+20 / T+10 / T; inside the regime: +3 / +2 / +1 / +1. Small e
  decays it (−1 / −5 / −10 / −30 for e > 0.75T / T/2 / T/3 / less; −50 on one path). Capped at 1000. Above 500 it
  clears b7 and b2 and steps the agreement counter 0x408EA7 down. b5 (0x495B0) = e > T, informational.
- **Blind during ABS.** With trust set, `abs_decel_est_clamp_ax` holds DAF within ax ± T in the regime, so e ≤ T
  (± one frame of ax change) and the regime branch can only decay the integrator. Once ABS is running, a trusted ax
  that is wrong by a constant amount is not caught by this integrator; see the next item for the one in-ABS check.
  MR2 log 2026-10-23: DAF − ax stayed in [−0.20, +0.11] g through a 1.0 g ABS stop.
- **In-ABS ax invalidation, `sub_0935E8` / `sub_093234` [C structure, I meaning].** Above 10 km/h with 0x408DB5 b6
  set: b6 = sp+40 ≥ ¼ of gross-slip curve 0xD6CE2(vref), computed in the event classifier (0x4F0C4) for the wheel
  0x400980 points at; inferred: the reference wheel still shows slip. In the ABS regime, counter 0x404A2D counts
  +1 per frame while both rears decelerate past 0.10 g within 0.30 g of each other (rec+0x22) and the left/right
  speed differences stay below min(vref/25, 300); otherwise −2. At ≥ 30 it sets 0x404A2E b7: ax invalid (getter
  0x93828), so deviation = 1000 and trust is lost. b7 latches until ax ≥ +0.11 g outside the regime. Outside ABS
  (0x408DA1 b3 only) the twin test sets b6 after 40 frames when both fronts decelerate uniformly while \|ax\| < 0.15 g
  (ax stuck near zero). Net: a vref held above the wheels for about 0.3 s of uniform rear decel invalidates ax.
- **No overflow path [C].** 0x408EE8 (`sub_053720`, IIR 20/21 of the mean wheel accel rec+0x22, slew ±200 per
  frame) is clamped to ±2667 before `DAF = 0x408EE8 / 21`, so DAF saturates at ±127 and never wraps. ax is the
  clamped byte 0x4049FC. Both peg at −1.27 g together, so the deviation reads 0 in a > 1.27 g stop. The alive
  counter compares 0x408E94 = 0x404A00 − 0x404A04/10 (1 mg, s16, clamp ±32767), which does not stop at 1.27 g; it
  freezes only if the cluster output itself flat-lines.

### 1.2 DAF clamp to ax (`abs_decel_est_clamp_ax` 0x538E8) [C]
Called from the DAF writer (0x53512) when 0x408E6D b3 (dead, cleared in the gather) **or 0x408E1C b7**. In the
ABS regime with ax < +0.30 g: `DAF = clamp(DAF, ax − 20, ax + 20)`, then ±127. Because ax itself saturates at
−127, a trusted DAF can reach −127 only with ax ≤ −1.07 g.

---

## 2. `vref_update` 0x449D0 [C]

`sp+8` = old vref. Wheel loops run first, then one step `s` is chosen, then applied.

### 2.1 Wheel picks
- **Cmax** (r12): fastest tyre-compensated wheel speed (`rec+0x1A × (0x301 + byte)/1024`; byte = the smaller of
  0x403214[w] and `rec+53` for fronts, the larger for rears, or always the table with 0x40320F b3; 0x44AF0–0x44B54).
  The bytes are learned tyre-tolerance factors normalised to the slowest wheel: `../../TYRE_TOLERANCE_LEARNING_7846816A.md`.
  Excludes faulted wheels (0x400952[w] b0,
  `rec+0x19 & 0xC0`) and wheels with `rec[0]` b2. **A rear is also excluded** while 0x408DA2 b7 (front in an ABS
  cycle) is set, 0x408DB5 b5 is clear and 0x408DC4 b5 is set, unless an invalid wheel was already seen.
- **Fmax** (r4): fastest compensated front, excluding `rec[0]` b2.
- **Vmin** (sp+16): slowest valid raw wheel (also skips 0x40905E[2w] b7). **Vmax** (sp+12): fastest raw wheel.
- Fallbacks (0x44CFA–0x44D2C): no valid wheel → all picks = floor 0x4032D0; Cmax = 0 → Cmax = Fmax = old vref;
  Cmax < Vmin → Cmax = Fmax = Vmin.

Per-frame flags gathered in the same loops (names are mine):

| flag | set when |
|---|---|
| `F_dh` (sp+40) | **both** fronts have `rec[0] & 0x28` (dump or hold) |
| `F_b2` (sp+72) | both fronts have `rec+0x10` b2 |
| `R_dh` (sp+32) | **a** rear has `rec[0] & 0x28` |
| `R_ctl` (sp+60) | a rear has `rec[0]` b0 (in control) |
| `R_b2` (sp+64) | both rears have `rec[0]` b2 |
| `R_b5` (sp+28) | a rear has `rec[0]` b5 (also sets 0x403291 b2) |
| `inval` (r8) | a wheel was skipped as faulted |
| `hiP` (r2) | a wheel in control with `rec+0x39` (peak accel byte, a/16) ≥ 45, or ≥ 1 with PM 0x408F2A[w] > 40 bar, 0x408DC6 b2 and pressure valid |

### 2.2 Rise (vref ≤ Cmax side) — 0x44D82–0x44DE2
```
if not regime (0x408DA1 & 0xF0 != 0x10):
    s = +22 if vref < Vmin            (+282 in controller modes 1/2/4 or with 0x400966 b6)
else:
    s = +44 if vref < Fmax
        or (vref < Cmax and (0x408E5A != 0 or (R_b5 and 0x408DA2 b7)))
```
So outside the regime vref creeps up only when **every** wheel is above it (spinning wheels can't drag it up);
in the regime it follows the fastest front at up to 1.25 g. vref is a slew-limited tracker: there is no clamp to
Cmax, so a step may overshoot by up to one step and is corrected next frame.

### 2.3 Fall step selection — 0x44DE4–0x45040
Taken only with controller mode 0 and **vref > Cmax** (above every counted wheel). Mode ≠ 0: `s = −90` while
Vmin < vref, nothing else (no limiter, no helper).

First a `hold` condition (0x44DE4–0x44EB4; also sets the limiter-skip r8) when (0x408DA1 & 3) = 0, `hiP` is
clear, and any of:
- 0x408DEE & 12 = 12;
- `R_b5`, a rear with `rec+0x17` b7, and DAF > −0.50 g;
- a wheel with `rec+0x17` b3 whose axle partner has 1 ≤ `rec+0x39` < 16, DAF > −0.75 g, and (0x408DEF b0 or `R_b5`);
- a wheel with `rec+0x17` b7 and 0x408DF0 & 0xC0 = 0;
- sp+48 clear (the last wheel written in loop 1 is in control with 1 ≤ `rec+0x39` < 25), DAF > −0.75 g, and a
  rear with `rec+6` < −150.

```
if 0x408DEE b6, or (0x408DEB b5 and both fronts rec+0x3A < 16 and 0x409048[4w] hi-nibble >= 6):
    if 0x408E7A < 140 and 0x408DF0 & 0xC0 == 0:  s = -11, skip limiter          -> 0.31 g
if s not chosen:
    if 0x408DEB b5 or hold
       or (F_b2 and F_dh and (R_dh or R_b2 or (!R_ctl and Fmax == Cmax))):  goto SLOW
    if a front has rec+12 b2:                                                 goto FAST
    if vref < 100 km/h and regime and 0x408DA2 b5 clear:                      goto SLOW
    goto FAST
SLOW:
    regime:  s = -22; if F_dh and R_dh: s = -23 + DAF_adj                       -> 0.62-1.13 g
    else:    s = -32                                                            -> 0.91 g
FAST:
    s = -44
    if (0x408DEE & 12) != 0 and DAF > -0.75 g:  s = -32, skip limiter
    elif both fronts reapply flags b11 (0x408F04/0x408F0A) and (R_dh or a rear b11):
         s = -32 + DAF_adj, skip limiter                                        -> 0.91-1.39 g
DAF_adj = (75 + DAF)/3 when DAF < -0.80 g, else 0   (reaches -17 at DAF = -127)
```
So −44 is not an absolute cap: the reapply-flag branch reaches **−49 (1.39 g)** with DAF pegged, and it skips the
limiter.

### 2.4 Decel limiter — 0x45040–0x45138
Skipped when any of:
- r8 is set (`inval`, `hold`, or the −11 / −32 branches);
- `hiP`;
- either front has `rec+0x10` b2;
- 0x400966 b6, or controller code 0x408EF6 & 15 ∈ {1, 2, 4};
- outside the regime, unless pressure is valid, 0x40493A bits 3:2 = 2 and driver pressure 0x408EB2 < 60 bar;
- 0x408DED & 0x18 = 0x18 (both fronts' deep-slip flags, `08_phase_control.md` block 19), the wheels at
  *0x400980 / *0x40097C within 3 km/h, and the rears' `rec+0x24` within 30.

```
m  = 30 if either front has rec+12 b2, else 50
lim = min((DAF - m) * 360/1000, -m * 360/1000)
s   = max(s, lim)
```
vref may fall at most ≈ m·0.01 g faster than DAF, and the limiter never forces the fall below 0.51 g (m 50) /
0.28 g (m 30). With an honest DAF the limiter, not the −44, sets the rate below ~0.72 g:

| DAF | lim (m 50) | fall |
|---|---|---|
| −0.30 g | −28 | 0.79 g |
| −0.60 g | −39 | 1.10 g |
| −0.72 g | −44 | 1.25 g (fixed step takes over) |
| −1.27 g | −63 | (1.78 g, unreachable with the −44 fixed step) |

**Note `hiP`:** a wheel in control spinning up at > 40 bar skips the limiter, so during a high-µ ABS stop many
frames take the raw fixed step. [I: those are exactly the high-grip frames.]

### 2.5 Route into `vref_fall_from_ax` — 0x4513A–0x451F6
```
if 0x408E6D b3:  goto JOIN                          # route 1; b3 is cleared in the gather -> dead
route 2 requires all of:
    0x408E1C b7                                      # ax trusted
    0x408DB5 b7, or (ax > -0.30 g and 0x408E6A >= 21 and regime)
    0x400B09 b6 clear
    0x408E6D & 0x90 == 0x90                          # lat + yaw valid
    |lat 0x408ECA| < 30
    0x408E6D & 0x60 == 0x60                          # steering + pressure valid
JOIN:
    0x408DA1 & 0xE0 == 0
    if FL or FR rec+0x10 b2: ax >= 0
    if lat valid: |lat| <= 70
    s = vref_fall_from_ax(s, old vref, Cmax)         # replaces s; helper also updates the shadow
otherwise:
    shadow 0x408E7E += s
```
(The code is `cmplti r7,21; bt skip`, so the counter must be **≥ 21**.) 0x408E6A is a
frame counter (0x471A4) that runs while 0x401FF2 b5 is set; 21 frames = 210 ms. Meaning of 0x408DB5 b7 [U]; it
also selects the slower ax IIR `(10x+23y)/24` in `sub_092B98`.

### 2.6 Apply — 0x451F8–0x4523C
```
shadow = max(shadow, floor)
0x408DEE b0 = (s >= 1)
vref += s ; call 0x45556 (controller-mode bookkeeping, no clamp) ; vref = max(vref, floor)
```
The rest of the function (0x4523E on) maintains 0x408DEE b1 and related flags; it does not change vref.

---

## 3. `vref_fall_from_ax` 0x50FF4 (s_in, vref, Cmax) [C]

1. Wheel loop: `bothF` = both fronts `rec[0] & 0x28`; `anyR` = a rear `rec[0] & 0x28`; `allRb2` = both rears
   `rec[0]` b2.
2. Decel input d (negative = braking), from ax = 0x408E80 and DAF:
   - regime: `d = −|ax|`;
   - not regime, ax ≤ 0: `d = ax`, except `d = DAF` when ax > −0.30 g, 0x408DB5 b6 and 16 ≤ ax − DAF < 50;
   - not regime, ax > 0: `d = −ax`, except `d = DAF` when ax < 0.30 g, 0x408DB5 b6 and −50 < DAF + ax < −15.
3. Margin m: 20 if d > −0.50 g else 30. Not regime and |d| > 0.30 g: +10 and done. Otherwise, if `bothF` and
   (`anyR` or `allRb2`): −10. Minimum 10.
4. If Cmax < vref: `s = max(−44, (d − m)·360/1000)` (clamp literal at **0x51100**); shadow = Cmax if
   Cmax ≥ shadow, else shadow + s.
   Otherwise: s = s_in (the rise step) and shadow += s_in.
5. shadow = min(shadow, vref). Return s.

| \|ax\| | m | s | fall |
|---|---|---|---|
| 0.20 g | 20 | −14 | 0.40 g |
| 0.50 g | 30 | −28 | 0.79 g |
| ≥ 0.93 g | 30 | −44 | 1.25 g |

The result **replaces** every selection in §2.3–2.4, including the −11 / −49 branches and the limiter-skip cases.

---

## 4. Behaviour by ax state [C mechanism / I effect]

| | vref fall during all-wheel slip | low-µ protection | high-µ ceiling |
|---|---|---|---|
| **A. ax invalid** (no cluster) | fixed step, bounded by limiter on DAF | DAF only; self-referential | 1.25 g (1.39 g branch) |
| **B. ax valid, not trusted** | same as A: vref_update reads ax only behind the trust gate | as A | as A |
| **C. ax trusted, SZL missing** (only if trust was set before the SZL was lost: initial trust needs lat + yaw, §1.1; a car without the SZL is in B) | fixed step, limiter on DAF held to ax ± 0.2 g | **ax-anchored**: fall ≤ 1.02·(\|ax\| + 0.2 + m/100) g | as A |
| **D. ax trusted, all chassis sensors valid** (stock M3) | route 2 replaces the step with the helper | tightest: fall ≈ \|ax\| + 0.1…0.4 g | 1.25 g (−44 clamp) |

- **A/B:** once all four wheels slip, vref is open-loop and DAF is derived from the same speeds. A faster fall
  makes DAF more negative, which loosens the limiter. The fixed steps are the backstop against runaway.
- **C** (only if trust survived from before the SZL was lost): the clamp breaks that loop. On 0.3 g ice DAF ≥ −0.50 g, so the fall is at most 1.02 g (m 50) /
  0.79 g (m 30) instead of drifting to 1.25 g.
- **D:** route 2 needs ax > −0.30 g unless 0x408DB5 b7 is set, so in a hard stop it usually falls back to C. Its
  job is low-grip, all-wheel-ABS coast-down. It never raises the ceiling.
- **High grip in every case:** DAF and ax are s8 and saturate at 1.27 g, the slope byte 0x408DB8 clamps at ±127,
  and the step tops out at 1.25 g (1.39 g on one branch). A car that really decelerates harder outruns vref;
  apparent slip grows at about (a − 1.25 g)·35 km/h per second.

---

## 5. Raising the fall ceiling (motorsport) [I]

- Changing only the fixed −44 (0x44FEA) to e.g. −71 gives about **1.6–1.8 g**, not 2.0 g, wherever the limiter
  runs: with DAF pegged at −127 the limiter allows −63 (m 50) / −56 (m 30). It changes nothing below ~0.72 g
  DAF. In the limiter-skip frames (`hiP`, front `rec+0x10` b2, `hold`, …) the raw −71 applies.
- 2.0 g through the limiter needs m ≈ 72 (0x450FC / 0x45102). Raising m globally also speeds the low-µ fall
  (0.3 g ice with trust: 1.25 g instead of 1.02 g).
- Without ax trust (A/B) a larger fixed step removes the runaway backstop: on ice vref could fall at the new
  cap and collapse onto the wheels.
- Safer shape: keep the stock steps, and only when ax is trusted **and** pegged (ax ≤ ~−1.20 g) use a larger
  margin and let the limiter result go below −44. Low-µ behaviour and the runaway backstop then stay stock.
- Route 2 / the helper is not the place: it is dead without the SZL, gated to ax > −0.3 g, and clamped at −44
  (0x51100).
- Other 1.27 g saturations to handle alongside: the decel-trigger threshold g-term input (threshold tops out
  near −1.8 to −1.95 g at 60–150 km/h, so wheels tracking a 2 g stop would cross it) and the 20 km/h floor
  (−1.27 g). The 60 km/h floor is already skipped when ax is pegged and trusted (`02_decel_threshold.md`).

---

## 6. Observing on CAN (patcher repo) [I]

- `data/track/can_0e1_ax_trust` (0x0E1, 10 ms): byte 0 = 0x408E1C (b7 trusted), byte 1 = 0x408E1B (b4 ax valid), byte 2 =
  alive counter, byte 3 = DAF (s8), bytes 4–5 = 0x408E80 (s16 LE), byte 6 = 0x408E6D, byte 7 = 0x408DA1 (b4
  regime). The former `can_0e1_abs_pressure` is gone (pressures are in `data/track/can_2b2_abs_state` and `data/study/can_reapply`).
- `data/track/can_2b2_abs_state` (0x2B2): vref, whole-bar pressures and per-wheel phase; the per-frame vref change is the step `s`.
- Which case applies: B vs C is byte 0 b7. In C, byte 3 should stay within ±20 of bytes 4–5 while byte 7 b4 is set.
- 60 km/h decel-threshold floor skipped ⇔ bytes 4–5 ≤ −127, byte 3 < −110, byte 0 b7.

---

## Open
- Meaning of 0x408DB5 b7/b6, 0x408DC6 b2, 0x401FF2 b5, 0x408E5A, 0x408DEE b6,
  `rec+12` b2, `rec+0x10` b2, reapply flags b11, `rec+0x17` b3/b7.
- Readers of the shadow 0x408E7E.
- Frame order of the DAF writer/clamp relative to `vref_update`.

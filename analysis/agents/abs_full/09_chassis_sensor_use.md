# ABS with and without the steering-angle sensor (SZL) — 7846816A (E9x M3)

Question behind it: in a swap with the yaw/lateral cluster on F-CAN, what does the ABS do differently
when the steering-angle frame 0x0C9 (SZL) is present, compared with a dead SZL? Read from the disassembly
(`analysis/7846816A_main.lst`), not bench-tested. CPU addresses; file = CPU + 0x8000. Tags: **[C]** read from code,
**[I]** inferred behaviour, **[open]** not traced. Symbols: `analysis/7846816A_symbols.md`, "ABS and TCS use of
the chassis sensors". Why a dead SZL also kills lateral and yaw: FACTS.md "Steering-sensor loss".

## 1. What the ABS sees

`abs_sensor_gather` 0x5D82C fills these every frame. Valid bits are in `abs_sensor_valid` 0x408E6D
(b7 lateral, b6 brake pressure, b5 steering, b4 yaw).

| Signal | SZL + cluster | SZL dead |
|---|---|---|
| `abs_ay` 0x408ECA (s8) | cluster lateral, b7 = 1 | `ay_wheel_estimate` 0x408D64, b7 = 0 |
| `abs_ay_aux1` 0x408ECB (s8) | updated | not updated (stale; 0 if never valid) |
| `abs_yaw` 0x408ECC, `abs_yaw_accel` 0x408ECE | live, b4 = 1 | 0, b4 = 0 |
| `abs_steer_angle` / `abs_steer_roadwheel` / `abs_steer_rate` 0x408EDE / EE4 / EE6 (offset-corrected steering-wheel angle, road-wheel angle, steering rate) | live, b5 = 1 | 0, b5 = 0 |
| yaw-stable `0x408E5F` b4 (`abs_yaw_stable_update` 0x530E4) | set after ≥ 63 low-yaw frames, \|steering\| < cal 0x4040E | never |
| ax `0x408E80` | live | live |
| brake pressure `0x408EB2`, b6 | live | live |

The lateral substitute (`ay_wheel_estimate_update` 0xD21C4) is built from the front left/right wheel-speed
difference and vref. Its instantaneous term is forced to 0 while a front is in an ABS cycle (`0x408DA2` b7), and the
output slews 1–2 counts per call, so it follows steady cornering before braking and decays during front ABS.
**[C structure, I detail]**

Most lateral readers test b7 first and take their "no lateral" branch. Yaw and steering readers see 0. A few
readers use the raw lateral byte without b7 and so see the estimate (§3).

## 2. Mechanisms that need the SZL

### 2.1 Rear-axle strategy — `abs_decision_classify` 0x51B54 [C]

Writes `abs_decision_t` at 0x408DDE (code, pct at 0x408DE0).

1. **Default** (0x51C6C): code **1** if both rears are only armed (`rec[0] & 0xC0` = 0x80 for 0x40BF80 and
   0x40BFC0), else **64** (rear select-low).
2. **Yaw cornering flag** (0x51B76–0x51BF0, only with `0x408DA1` b4): \|yaw\| > curve **0x40E42**(−decel) with the
   vehicle decelerating sets `abs_yaw_corner_flags` 0x409024 b0+b6; b0 clears when \|yaw\| drops below half the
   curve. Decel = ax `0x408E80` when `0x408E1C` b7, else `0x408DAF`. **SZL dead: yaw = 0, never set.**
3. **Lateral-g thresholds** (0x51BF2–0x51C66): only with `0x408E6D & 0xC0` = 0xC0 (lat + pressure valid), the wheel's
   `0x40903C` b7 **or** rear cornering latch `0x409049` b5, and `0x408DC4` b4 clear:
   - P_lo = 100 · curve **0x40E26**(\|lat\|), P_hi = 100 · curve **0x40E0A**(\|lat\|), + 500 (5 bar) when \|lat\| > 80.
   - Otherwise P_lo = P_hi = 0.
4. **Straight-line shortcut → code 1** (0x51E00–0x51E94): \|lat\| < 9 (< 15 if the last code was 1), front
   pressures `0x408FF0` / `0x408FF2` within 50 % of each other, yaw-stable flag, 0x409024 b0 clear, yaw valid,
   `0x408DBE` b7 clear, plus the rear condition r9 (0x51CB8–0x51DA2). Rears are handled independently instead of
   select-low. **SZL dead: never taken.**
5. **Code 1 at light pedal in a corner** (0x51E6A): driver pressure `0x408EB2` < P_lo with `0x40903C` b7 or latch b5.
6. **Code 32 with pct** (0x51EF4–0x51F42): the current wheel is dumping (`rec[0]` b5), P_lo < P_drv, and (P_drv < P_hi
   or latch b5), with `0x40903C` b7 or latch b5:

   `pct = 100 · (P_drv − P_lo) / (P_hi − P_lo)` → 0x408DE0.

   **pct is not clamped and wraps [C].** The quotient is stored with `st.b` (0x51F42) and read back zero-extended
   (`ld.b`, 0x59272). With latch b5 the branch also runs above P_hi, where pct exceeds 100. From
   P_drv = P_lo + 2.56·(P_hi − P_lo) it wraps modulo 256 back toward 0. At 0.4 g lateral (P_lo 18, P_hi 29 bar) that is
   about 46 bar of pedal; at 1.0 g (30 / 45 bar) about 68 bar. What the wrap does to the rears is [I].
   **SZL dead: P_lo = P_hi = 0 and no latch, so no code 32 from here.**
7. **Code 32 in the exec** (`abs_decision_pressure_exec` 0x58FF4, arm 0x59222–0x59328) [C formula, open wheel roles].
   The half-word at 0x408DE8 (decision word +10) holds two 2-bit wheel indexes: s = bits 12–13, t = bits 14–15.
   - G = `LOCKEST[s] − CMD[s]` (0x408FD0 − 0x408F22, floored at 0) when the partner of the current record
     (`0x400978` xor 0x40) is dumping or holding (`rec[1] & 0x28`); otherwise G = `0x408F42[s] − CMD[s]`.
   - K = pct · G / 100.
   - Normal path: `CMD[t]` (0x408F22) and 0x408F62[t] = max(1 bar, PM[t] − K); rate 0x408F5A[t] = rate[s].
   - With 0x408F80[t] set the base is the hold pressure 0x408F42[t] instead of PM[t]. With 0x408D9C[t] b7 as well, a
     wheel already at the full-dump rate (−8000) keeps a command that is lower than that, and a wheel with a negative
     rate is left alone while rate[s] = 0.
   - **Which rear is s and which is t on the cornering path is open.** Bits 12–13 come from `abs_rear_lead_select`
     0x5184C (the lead rear, index 2 or 3), and every write read there copies bits 12–13 into 14–15
     (0x51A04–0x51A14, 0x51A2E–0x51A3C; also 0x51CA0 for code 128). The classifier's code-32 branch does not write
     them. So t is probably the lead rear itself [I], and code 32 then holds the lead rear's command pct % of its
     dump depth below its own pressure. `abs_pair_logic` also writes code 32 (the partner dump on split-µ) with its
     own fields.

### 2.2 Rear cornering latch — event classifier 0x4E908 [C]

Read 2026-10-26 (0x4E59E–0x4EC1E, pools 0x4E8D8 / 0x4EA28 / 0x4EB30 / 0x4EC40 / 0x4ED5C). The latch enables the
lateral branch of §2.1 (items 3, 5, 6) for one rear. The RL record (sp+88) is tested when lateral ≥ 1 count, the RR
record (sp+64) when lateral < 0; which of them is the inside wheel depends on the sensor sign [open].

- **Enable** (0x4E8B6): `0x408E6D & 0xF0` = 0xF0 (lat, pressure, steering, yaw) and `0x408DC6` b2.
  `abs_cluster_without_szl` drops the steering bit (0xD0).
- **Pre-gate** (0x4E912–0x4E94A): yaw-deviation counter `0x408EA6` above a bound, or \|lat\| > T, or E+37 b7, or the
  recovery flag sp+68; otherwise the wheel's `0x409049` b0 must already be set.
- **Common conditions** (0x4E94C–0x4EA12): the rear not in a cycle (rec b0); `0x409049` b2 and b3 clear;
  `0x401FF2` b7; `0x408E6A` ≥ 3; with sp+68 = 0 and no driver pressure, both front PM > 1 bar and `0x408DC6` b2;
  `0x408DB5` b4 clear; at \|lat\| ≥ 40, the wheel's PM `0x408F2A` > 100 · curve **0x40CC8**(vref km/h) (35 bar at
  standstill, 8 bar at 50–60 km/h, 6 bar above 80 km/h) unless sp+68 is set.
- **Trigger** (0x4EA44–0x4EAC0), any one of:
  1. e = yaw − `0x400B1A` ≥ 1 count in the turn direction (e ≥ 1 for RL, e < 0 for RR);
  2. E+37 b7 (classifier block 14, yaw-limited);
  3. \|lat\| > T;
  4. sp+68 (classifier block 12, yaw-error recovery).

  Triggers 1, 2 and 4 compare yaw with the DSC yaw target, so they are the only parts of the latch that depend on
  the steering angle. With `abs_cluster_without_szl` e = 0 and only trigger 3 is left.
- **Final checks** (0x4EAC2–0x4EAEE): rear not in a cycle, `0x408DA2` b5 clear, no wheel fault `0x400952`, coding
  `0xCFC18` = 0 and `0xCFC56` ≠ 0.
- **Set** (0x4EAF0–0x4EB5E): `abs_rear_latch` 0x409049 b2+b5 (b0 cleared), lat → 0x408EDA, driver pressure →
  0x408ED6, `0x408E1B` b1, yaw → 0x408EA0, e → 0x408EA2.
- **Release** (0x4EB60–0x4EC1E): a latched wheel releases when driver pressure is 0, the lateral sign no longer
  matches its side, or driver pressure < P_lo = 100 · curve 0x40E26(\|lat\|). Release clears b2 and zeroes 0x408EDA /
  0x408ED6. b5 and b0 are cleared only when neither rear is in a cycle, so b5 (the classifier's enable) holds for
  the rest of a rear cycle. That is how the light-pedal code 1 (§2.1 item 5) is reached while P_drv < P_lo.

**Lateral threshold T** (0x4E5F6–0x4E8B4), stored per wheel at `0x409132` + 10·w:
- T = cal **0x40B06** = 80 (0.80 g).
- When yaw accel has the sign of yaw and \|yaw accel\| exceeds curve **0xD6CA8**(vref / 10) (4363 at standstill, 1013
  at 60 km/h, 409 at 100 km/h), T is lowered in proportion to the excess, with gain curve **0x40C9E**(vref km/h) (0
  up to 20 km/h, 23 at 100 km/h); the gain is 6 below 60 km/h when \|e\| > 233 [C structure, I exact term].
- Above 30 km/h with \|yaw accel\| > 2500 and the target of yaw's sign: T −= T · (\|yaw accel\| − 2500) / 12000.
- **T = max(T, cal 0x403E4 = 40)** (0x4E890). Lowering 0x40B06 below 0x403E4 has no effect unless 0x403E4 is
  lowered too. Each of the four cals has a single reader.

Meaning [I]: with an SZL the latch picks up any braked corner in which the car rotates at least as much as the model
asks (trigger 1), and otherwise only above about 0.8 g. The latch also feeds classifier block 14 and the pre-control
handler 0x50894 through the yaw / e snapshots (§7.6). **SZL dead: never latches.**

### 2.3 Which rear leads [C]

- `abs_rear_lead_select` 0x5184C picks the lead rear from the lateral sign (thresholds +6 / −5 / −10, aux ±11) and
  needs b7 (0x5197E). **SZL dead: skipped.**
- `abs_side_select` 0x5AEEE (inside `abs_chassis_frame` 0x5A0DC) uses the lateral sign when \|lat\| ≥ 11 and valid,
  **otherwise the rear wheel-speed difference** (RR vs RL rec+0x1C). This one degrades gracefully.

### 2.4 µ-split yaw-moment limiting (GMA) — `abs_pair_logic` 0x54D9A [C]

- At entry it calls `abs_pair_gate` 0x54B70 and jumps to its exit (0x553BE) while the gate state
  S (`0x408E5F` b6:5) is 0. Everything else in the function — partner-dump code **32**, rebuild codes **1024 / 16**,
  the steering-angle minimum 0x408EF2 and the rebuild pacing (§7.3) — runs only with S ≥ 1.
- S 0 → 1 needs `abs_pair_gate_split_yaw` 0x547D8: a pressure split on the axle, **\|yaw\| > cal 0x40DD4 with the
  sign that matches the side**, and `0x408E5F & 0x14` = 0x14 (yaw-stable flag + b2).
- **SZL dead: yaw = 0 and no yaw-stable flag, so S stays 0 and the pair logic never runs.** [I] on split-µ the
  yaw-triggered limiting of the high-grip wheel is gone; expect more pull and possibly a shorter stop.
- Still active without the SZL: the front staged dump (`abs_dump_hold_stage_ctrl` 0x53940, pressure / decel based,
  `08_phase_control.md` §5.3) and the low-µ pair coupling in 0x48EB0. `abs_front_stage_cancel` 0x540D4 cancels the
  staged dump in a corner (\|lat\| > 35) only with b7, so without the SZL it is not cancelled in corners.
  `abs_front_split_detect` 0x53D3C uses the raw lateral byte (the estimate) in some branches.

### 2.5 Dump step size in corners [C]

`abs_dump_frame_flags` 0x4B160 sets `0x408DD4` b28 / b27 when \|lat\| > 50 / > 80 on the front selected by
`0x408DF0` b7 / b6 (rear on that side not in a cycle, b7 valid). `abs_dump_step_amount` 0x56728 then uses D/2 or
D/3. **SZL dead: full-size release steps mid-corner.**

### 2.6 vref during ABS [C]

`vref_fall_from_ax` 0x50FF4 (step = max(−44, (−\|ax\| − margin)·0.36)) is called only from 0x451F2. Route 1
(`0x408E6D` b3) is dead because b3 is cleared in the gather. Route 2 (0x45142–0x451F2) needs:

- `0x408E1C` b7;
- `0x408DB5` b7, or (ax > −0.3 g, `0x408E6A` ≥ 21, regime 0x408DA1 b4) (full decode in `10_vref_and_ax.md`);
- `0x400B09` b6 clear;
- `0x408E6D` b7 + b4 (lat, yaw) **and** b5 + b6 (steering, pressure);
- \|lat\| < 30 (≈ 0.3 g); `0x408DA1 & 0xE0` = 0; a front with `rec+16` b2 also needs ax ≥ 0;
- with b7, \|lat\| ≤ 70 (redundant here).

**SZL dead: vref never takes the ax-based step;** it falls on the fixed per-frame steps (normally −22 / −32 /
−44) bounded by the wheel-derived vehicle decel `0x408DAF` (`10_vref_and_ax.md` §2.3–2.4). The clamp that pulls
`0x408DAF` to within ±0.2 g of measured ax (`abs_decel_est_clamp_ax` 0x538E8) needs ax trust, which also needs
the SZL (§2.10), so without the SZL the accelerometer does not reach vref at all. The −44/frame (≈ 1.25 g)
ceiling is the same either way. With the SZL, route 2 uses ax only with every chassis sensor valid and
near-straight driving.

### 2.7 Straight-line ax / decel estimator — `abs_ax_decel_estimator` 0x49572 [C structure]

Updates `0x408E82`–`0x408E90`, `0x408E98`, `0x408EA7`/`A8`/`AA` only when lat + pressure are valid with the yaw-stable
flag and \|lat\| < cal 0x40C9A, or lat + yaw valid with \|lat\| < half of that and \|yaw\| < 700. **SZL dead: frozen.**
**[open]** consumers; `0x408E98` > 80 gates one rear pre-control dump start (`08_phase_control.md` block 11).

### 2.8 Countersteer test — `abs_countersteer_check` 0x5CAF4 [C structure, I meaning]

Lateral, yaw and the aux lateral of one sign, steering valid with road-wheel angle `0x408EE4` of the opposite sign,
yaw accel opposite, \|yaw\| below half `0x408ED0` → a rear-control branch that writes `0x408DA0` b4/b5/b7.
**SZL dead: the countersteer condition is skipped.**

### 2.9 All-sensors flag for the end-of-frame block [C]

`abs_chassis_frame_init` 0x5A21C sets context b4 (ctx+33) only when lat, pressure, steering and yaw are all valid;
otherwise it clears `0x40903C[3w]` b4 for every wheel. The rest of `abs_chassis_frame` (≈ 7 k lines) was not
decoded.

### 2.10 What the cluster still does without the SZL [C]

Only the longitudinal accel, and only untrusted. Lateral and yaw are invalid (§1), but ax is not:

- **Trust: not reachable without the SZL** (`10_vref_and_ax.md` §1.1). The initial set of `0x408E1C` b7
  (0x49AE0–0x49CB8) needs lateral + pressure valid, yaw-stable and \|lat\| < 0.20 g. The re-trust path
  (0x49AC6) has no lateral / yaw / steering input but only runs after ax was trusted and went stale. So
  everything under "With trust" below is off on a car without the SZL; only the "Without trust" readers use
  ax (bench-confirmed on the MR2: b7 stayed 0 for a whole drive).
- **With trust:**
  - decel-threshold builder g-term uses measured decel `0x408E92` instead of the wheel-derived terms (0x47BE0);
  - `abs_decel_est_clamp_ax` 0x538E8 holds `0x408DAF` within ±0.2 g of ax during ABS, which bounds the vref fall
    and feeds every decel test that reads `0x408DAF`;
  - the classifier uses ax as its decel input; the rear decel-gate latch (ax < −0.55 g → `0x409049` b3, rear
    pre-control) can fire;
  - further b7-gated sites not decoded: 0x45F7C, 0x477E8, 0x489B4, 0x4C368, 0x57578.
- **Without trust, ax still reaches** the readers of `0x408E80` that do not test b7 (`0x408E80` = ax whenever the
  ax getter is valid): decel-threshold builder branch 0x47CEA, 0x48584 (−0.3 / −0.5 g), axle coupling 0x492F6
  (> −1.0 g), 0x4A530 (0.44 g), classifier EV1.b3 (coding variant 10 only, 0x4D94E), rear-latch release 0x4EC36,
  pre-control handler 0x50E14, 0x532FA, 0x57A34.
- **CAN:** 0x1A0 keeps sending live AccY / YawRate (FACTS "Steering-sensor loss"); 0x1A3 / 0x2B3 carry the raw
  accelerometer and its learned zero offset (FACTS "The accelerometer IS broadcast").
- **Fault side:** a present cluster avoids D370–D372 and their reactions (ax invalid, `cluster_fault_any`).

## 3. Readers that use the raw lateral byte

These do not test b7, so without the SZL they use the wheel-speed estimate:

- classifier block 14 lateral term (0x4E59E–0x4E5D8: factor from \|lat\| 50–60);
- the direction-selective rear dump 0x4EF72 (lat ≥ 6 on RR / < −5 on RL), gated by `0x408E5F` b1 or `0x400B09` b6;
- `abs_front_split_detect` 0x53D3C (some branches);
- the classifier straight shortcut (\|lat\| < 9), which needs yaw-stable anyway.

## 4. Not affected

Slip and decel thresholds, the phase machine, dump-entry target, hold / reapply, EBD (decel-driven), the front
staged dump, the low-µ flag and coupling. (The rear decel-gate latch `0x409049` b3 needs ax trust, so it is off
without the SZL; §2.10.)

## 5. Behaviour summary [I]

| Situation | SZL + cluster | SZL dead |
|---|---|---|
| Straight, uneven rear grip | rears may go independent (code 1) once calm | rears stay select-low (code 64) |
| Trail-braking in ABS | cornering latch → code 1 at light pedal, code 32 knockdown by pct; dump steps ½ / ⅓ | none: select-low, full dump steps |
| Split-µ | pair-logic GMA starts on a yaw kick | only front staging and low-µ coupling |
| Hard braking, all wheels slipping | vref step from measured ax (straight only), else fixed steps bounded by the ax-clamped decel estimate | fixed steps bounded by the wheel-derived decel estimate only |
| Oversteer with countersteer | countersteer rear branch | not detected |

## 6. Traction code use (for comparison)

`tcs_sensor_latch` 0xCC89C copies ax, lateral (`abs_ay_aux2_get`), pressure, road-wheel angle and yaw to
0x40306C–0x403074 (valid bits `tcs_sensor_valid` 0x403064). Users: `tcs_straight_detect` 0xCB43E (\|yaw\|,
\|lat\| < 15, \|road-wheel angle\| < 1310, no valid-bit test), `tcs_yaw_slip_term` 0xC9450 (yaw if valid, else
`0x4030A8`), `tcs_reduction_floor` 0xCD7FE (needs lat valid). Without the SZL the traction channels are
fault-inhibited anyway (FACTS "Steering-sensor loss").

## 7. Steering calibrations that matter when the SZL works

Question behind it: with a working SZL, which calibrations decide how the steering angle changes ABS behaviour, how
sensitive are they, and which are physical properties of the car versus tuning choices? Short answer: the SZL acts
on ABS mainly as a **validity switch** (b5 enables the whole cornering suite, §2), plus a few magnitude thresholds in
the yaw-stable flag and the GMA rebuild pacing. Those thresholds are tuning values. What has to be physically right
is the signal chain upstream: valid status, sign, zero offset, and to a lesser degree the scale. The steering-ratio
curve, the obviously physical calibration, has almost no effect on ABS. Cal values below are read from the
listing; the steering LSB (≈ 0.044° steering wheel per count) is **unverified**, so all degree figures are [I].

### 7.1 Signal chain (shared with DSC) [C]

| Step | Code | RAM | Calibration |
|---|---|---|---|
| CAN 0x0C9 sig 43 | `canrx_steer_angle_0C9` 0xC5C78 | 0x401644 | ·1029/1024 (code literal) on the sensor LSB |
| capture, IIR | `steer_capture` 0x901D4 | raw 0x4020D0, IIR 0x4020D2 (k 241/256) | — |
| zero offset | `steer_offset_learn` 0x9020C | offset 0x4020A6 (Q6); **corrected angle 0x402132 = 0x4020D0 − offset/64** | learns every 100 calls (0x402134) when 0x4020FC+1 b7 and 0x402144+3 b7, not when 0x402884 b3. Gain = min(curve 0xDA8FA/0xDA8FE (alt 0xDA902 when 0x4020FD b4) over \|0x4020DC\|, curve 0xDA906/0xDA90A over \|0x40211C\|)·1200 / 0x400B2C. The target (IIR 0x4020D2) is clamped to offset ± 228 counts, a step clamp, not a window; hard clamp ±0x7249 (457 counts ≈ 20°); \|offset\| > 14628 Q6 (≈ 10°) sets fault 0x120001 (0xBF868); saved in EEPROM block 8 (record 0x4020AE). Detail `DSC_STEERING_AND_VEHICLE_MODEL_7846816A.md` §2. Distance counter 0x402136 += vref/360 up to 60000 |
| road-wheel angle | `steer_ratio_convert` 0x9032E | 0x40212E = 29360·x / ratio | ratio curve x 0x40EB4 / y 0x40ECC (3 sets, coding 0x4031AA+5, ≈ 15.9 → 12.6 : 1); x = corrected angle clipped to ±xs[3]. The CSI sign tables 0x40EE4 / 0x40F14 are not applied on this path |
| steering rate | `steer_rate_update` 0x90408 | 0x402130 | differentiator on raw 0x4020D0 (so offset-free), hold / dwell counters 0x4049F2–0x4049F8, thresholds 68 / 32, 0x91986 with 2285, then IIR (k ≈ 204/256). Units [I] ≈ counts/s, not confirmed |
| ABS copies | getters 0x94120 / 0x9403C / 0x940AE | 0x408EDE angle / 0x408EE4 road-wheel / 0x408EE6 rate | valid `0x408E6D` b5 |

### 7.2 Yaw-stable flag — `abs_yaw_stable_update` 0x530E4 [C]

Counter `0x408EF4`, flag `0x408E5F` b4 = counter ≥ 0x4040C. 10 ms frame (called from 0x447EE). Needs lat, steering and
yaw valid (`0x408E6D & 0xB0`). Yaw LSB 1/20000 rad/s.

| Cal | Stock | Meaning |
|---|---|---|
| 0x40404 | 1047 (3.0 °/s) | \|yaw\| below this: counter +1 |
| 0x4040C | 63 | flag set at ≥ 63 frames (0.63 s) |
| 0x40406 | 28 | hysteresis: at the cap the counter jumps to 63 + 28 |
| 0x40408 / 0x4040A | 1571 (4.5 °/s) / 3002 (8.6 °/s) | counter −1 above the first, −2 above the second; only with \|lat\| ≥ 16 (plus conditions) or `0x40095C` b0 |
| **0x4040E** | **2971 counts (≈ 130° SW)** | **\|corrected angle 0x408EDE\| above this zeroes the counter** |

The flag gates GMA start, the straight latch, the classifier straight shortcut and one ax-estimator route.

### 7.3 GMA rebuild pacing — `abs_gma_hold_frames` 0x54BE8 [C]

Called at 0x55200 in `abs_pair_logic` (so only with the pair gate S ≥ 1, §2.4) for the wheel record in
`0x400978`, with r2 = predicted yaw (yaw + yaw accel / 2). It returns a hold score; the caller raises the wheel's
command (`0x408F22` / `0x408F62` = `0x408F42[w]` + 0x40DB0·100, i.e. +3 bar) once the shared counter `0x408EEF` reaches
score + 0x40D8E, then resets the counter; otherwise it holds at `0x408F42[w]`. A larger score means a slower
high-µ rebuild. Score terms (u8 sum):

| Term | Cals (stock) | Wheels |
|---|---|---|
| +7 if vref − wheel speed > curve 0x40974(vref), or rec+6 < 0 | — | all |
| + (vref − 0x40DC6) / 0x40D8C / 100 above 40 km/h | 4000, 7 → +1 per 7 km/h | all |
| + (−decel 0x408DAF) / 14 below 0x40DCA·100 | 40 km/h | all |
| + (\|pred yaw\| − 0x40DD6) / 0x40DCC; negative yaw → RR only, positive → RL only | 1047 (3 °/s), 63 | rears |
| **+ \|rate 0x408EE6\| / 0x40D86 when rate > 0x40D88 (RR) or < −0x40D88 (RL)** | **1143, 457** (≈ 50 °/s, 20 °/s per frame, units [I]) | rears |
| **+ 0x40D92·(\|angle\| − min) / (0x40D8A − min)**, min = `0x408EF2` while min < 0x40D8A | **14, 2286 counts (≈ 100° SW)** | all |
| **score = 248 if \|angle\| > 0x40D8A and own PM − partner PM (`0x408F2A`) > 5 bar** | 2286 | all |

`0x408EF2` is the minimum \|corrected angle\| since the pair logic engaged: reset to 32000 at the function exit while
S = 0 (0x553BE) and at 0x5528A, lowered to \|angle\| each pass (0x54E16). So the angle term counts **steering added
since the event started**, not absolute lock, and is not capped at 14 once \|angle\| passes 2286. Score 248 + 7 = 255
fills the u8 counter, which stops the rebuild. This is the driver-feedback channel in split-µ: the more the
driver steers or countersteers, the slower the grippy side builds. The rate term is the only one that uses the
steering sign.

Not steering: the pair gate itself (`abs_pair_gate_split_yaw` 0x547D8) uses yaw cal 0x40DD4 = 1399 (4.0 °/s) and the
yaw-stable flag.

### 7.4 Other steering users [C]

- **Countersteer** (`abs_countersteer_check` 0x5CAF4, §2.8): road-wheel angle `0x408EE4` opposite in sign to lat /
  yaw, and peak road-wheel angle `0x408EE2` > 0. The peak is kept by 0x5A4E4 in the current turn direction,
  together with peak lat `0x408EDB` and peak yaw `0x408ED0` / `0x408ED2`. **Sign and zero only, no magnitude cal**,
  so the ratio curve hardly matters.
- **Front staged dump:** `0x400A92` = peak \|angle\| while `0x400A95` b7 (0x53D3C), used by 0x540D4 (90 % test →
  `0x400A97` b0) and 0x5971C (→ `0x400A90`). Neither output has a reader, so no effect.
- **Validity only:** cornering latch (0x4E8B6, mask 0xF0), straight latch, vref route 2, `abs_chassis_frame_init`.
- **Through DSC:** the observer yaw target 0x400B1A and the closed-form reference 0x4020EC, built from the steering
  angle. ABS reads them at the sites in §7.6.

### 7.6 Yaw-target users in ABS [C sites, I meaning]

Read 2026-10-24 from the listing. e = measured yaw `0x408ECC` − target. The thresholds are given in °/s assuming
ABS yaw uses the cluster LSB of 1/20000 rad/s; the constants are round numbers on that scale (349 = 1°/s,
698 = 2°/s, 1047 = 3°/s, 3490 = 10°/s). Every load is `lrw` followed by `ld.h (rN,0)`. None of these sites is gated
on steering-valid or AYC: they need yaw valid (0x408E6D b4), `0x40493A` b5 (always set) or other ABS state. Without
an SZL the target means "wheel straight", so e = the full measured yaw.

| Pool word (loads) | Function | Use |
|---|---|---|
| 0x4E444 (4, 0x4E134–0x4E1B6) | event classifier `sub_04D270`, 08 §12 | yaw-deviation flag sp+68: e against the filtered error `0x408ED8` in ±1400 / ±700 bands, only with `0x408DF0` b7/b6 and \|lat\| ≥ 40 |
| 0x4E900 (5, 0x4E69A–0x4E85C) | event classifier, 08 §14 | yaw and yaw accel in the same direction past `0x408EA0` / `0x408EA2` → E+37 b7 (yaw-limited dump) |
| 0x4ED60 (3, 0x4EA50–0x4EB16) | event classifier, 08 §15 | rear cornering latch: snapshots e into `0x408EA2` when it sets |
| 0x50E88 (1, 0x50B92) | pre-control handler 0x50894 | per rear (record compare against `wheel_rec` + 0x80 / + 0xC0): flag when e has grown past the latched `0x408EA2` in the same direction |
| 0x571E0 (1, 0x570EE) | `abs_dump_forced_target` 0x57024 | with yaw valid: e > 1°/s in the same direction as yaw → forced-dump amount `0x408DC8` halved |
| 0x59980 (1, 0x597E2) | 0x5971C | caps a value at 50 or zeroes it from e; output `0x400A90` has no reader |
| 0x5ABF0 (1, 0x5AA8E) | `abs_corner_peak_track` 0x5A4E4 | `0x408ED8 += (e − 0x408ED8) / 35`: the filtered yaw error |
| 0x5B828, 0x5BEAC, 0x5C594, 0x5C8B8 (9) | `abs_side_select` 0x5AEEE | e in the same direction as yaw against ±3°/s (0x5B572), a ctx threshold of at least cal 0x40A3E (0x5BC60 / 0x5BD66), −500 ≈ 1.4°/s (0x5C352 / 0x5C3D2), ±(2°/s + ctx) (0x5C610), curve 0x40A66(vref) × ctx / 100 (0x5C800 / 0x5C82C) and ⅔ ctx (0x5C88C). Feeds the inside / outside rear handling; downstream not decoded |
| 0x5BBAC (2), 0x5C2CC (1) | `abs_side_select` | the target alone: sign and comparison with a ctx yaw quantity offset by 2°/s and capped at 10°/s (0x5B90E / 0x5BAFA); comparison with a ctx value under the AYC-active flags `0x408DEA+6` b7/b6 (0x5C028) |
| 0x55560 (1, 0x5543E) | `sub_055420`, every ABS frame from 0x4629C | at start-up (`0x400966` b6) or controller modes 1/2/4: seeds 0x409194–0x4091A6 with r_ref 0x4020EC and `0x40919E` = yaw − r_ref. No literal reader of that block found |
| 0x4A450 (2, 0x4A294 / 0x4A2BC) | `abs_yaw_deviation_monitor` 0x4A254, the tail call of every ABS frame | not AYC-gated. Its snapshot branch needs the side flags `0x408DF0` b7/b6, `0x408E6D & 0xF0` = 0xF0 and `0x401FF2 & 0xA0` = 0x80 (ABS enabled, not engaged). Its oversteer state runs ungated: when \|yaw\| exceeds \|target\| by curve 0x40C5A(\|lat\|) (2024 at 0 g, 857 at 0.5 g, 576 at 1.2 g) with yaw accel the same way, it sets `0x408DF1` b6 and counts `0x408EA6` up (+1 per growing frame, −4 otherwise, cap 20). Reset below 10 km/h, with trusted ax ≥ 0, or when \|yaw\| < \|target\|. Readers: cornering-latch pre-gate, `abs_side_select`, 0x4B3C8, 0x4B970, 0x5AC0C, 0x5CAF4, 0x5CFDC |

`abs_cluster_without_szl` points all of these at `abs_yaw`, so e = 0. The target-alone loads then
see measured yaw, which is "the driver wants what the car is doing", not the same as e = 0. Whether they end up
neutral depends on the undecoded ctx quantities.

### 7.5 Physical versus to-taste, and sensitivity [I]

| Calibration | Physical / to-taste | ABS sensitivity |
|---|---|---|
| steering valid (0x0C9 frame, alive, status; `steering_angle_init_monitor` 0xB97D4, faults 0x1200xx) | physical (sensor health) | **very high**: invalid turns off lat, yaw and the whole cornering suite (§2) |
| sign convention (raw 0x0C9 sign) | physical (sensor, install) | **high** for the GMA rate term and the countersteer test; reversed sign makes them act on the wrong side. Also critical for DSC |
| zero offset (learner 0x9020C, its gain curves 0xDA8FA–0xDA90A, ±228 step clamp, fault above ≈ 10°) | estimator tuning that corrects a physical error | low–medium: matters near centre (countersteer sign); too small to matter for the 100–130° thresholds. The GMA angle term is relative to its own minimum, so a static offset barely affects it |
| scale (sensor LSB, ·1029/1024) | physical (sensor) | medium: every ABS steering threshold is in counts, so a 2× scale error halves or doubles the GMA steering terms and moves the 130° / 100° / 50 °/s points |
| ratio curve 0x40EB4 / 0x40ECC | physical (rack ratio) | **almost none** for ABS (only the road-wheel sign and peak in the countersteer test). Critical for the DSC yaw reference |
| rate filter (0x90408) | signal processing | low |
| 0x4040E (130°) | to-taste | low: generous, yaw does most of the work |
| 0x40D8A / 0x40D92 (100°, 14 frames) | to-taste | medium: directly sets the split-µ rebuild speed (stopping distance against pull) |
| 0x40D88 / 0x40D86 (50 °/s, 20 °/s per frame) | to-taste | medium: 200 °/s countersteer adds ≈ 10 frames on a base of 7 |
| yaw-stable yaw thresholds 0x40404–0x4040C | to-taste, but must sit above yaw-sensor noise and offset | medium for whether the flag ever sets |

Order of what "correct" needs: valid status > sign > offset > scale > ratio (≈ none for ABS).

Editing scope [C]: each ABS cal in §7.2–7.3 has direct literal-pool references only from the functions named
there (0x40DD4 also from `abs_pair_gate_hold` 0x54A80), so changing one does not move other logic. All 18 are in the
XDF (ABS category, "ABS yaw-stable: …" / "ABS GMA: …").

## Open

- Writer of `0x40903C` b7 (the other enable of the classifier's lateral branch). `0x408DF0` b7/b6 are set at
  0x5CCBA–0x5CCC0 in the first part of 0x5CAF4 from a wheel-speed side counter (not steering); no clear found.
- Which rear the code-32 exec acts on (§2.1 item 7), and the effect of the pct wrap.
- The remainder of `abs_chassis_frame` 0x5A0DC (0x5AEEE after the side pick, 0x5A2E0, 0x5AC0C, 0x5CFDC, 0x5D264,
  0x5D290, 0x5A4E4); outputs 0x40915E–0x409188 have no direct readers.
- `abs_pair_gate` helpers 0x54954 / 0x54AF8.
- Consumers of the `abs_ax_decel_estimator` outputs.
- Steering LSB (≈ 0.044°/count) and the units of the steering rate 0x402130; the GMA rate cals 0x40D88 / 0x40D86
  depend on them.
- What `steering_angle_init_monitor` 0xB97D4 needs before steering is valid (for example, an un-initialised SZL).
- Whether the CSI sign tables 0x40EE4 / 0x40F14 reach anything ABS reads.
- Writer and meaning of `0x408F42[w]` (the GMA hold pressure) and the increment of `0x408EEF`.

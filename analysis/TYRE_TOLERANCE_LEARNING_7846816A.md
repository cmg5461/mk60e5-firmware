# Tyre-tolerance learning and wheel-ratio plausibility, 7846816A

How the M3 image learns per-wheel speed corrections for tyre-size differences, where the corrected speeds are
used, and which wheel-speed DTCs a large mismatch raises. Written for the swap question "what does stagger or a
tooth-count mismatch do?". Read from `analysis/7846816A_main.lst`, not bench-tested. CPU addresses. Tags: **[C]**
read from code, **[I]** inferred, **[open]** not traced. The non-M image (6862873A) was not checked.

Before this, the docs only said that vref uses "a per-wheel tyre-circumference factor (Q10)"
(`ABS_ALGORITHM.md`, `agents/abs_full/01_core_slip_loop.md`, `10_vref_and_ax.md` §2.1). The learner that
produces the factor, and the second wheel-speed field `rec+0x1C`, were not decoded.

## What it is, and what it is not

- **It is not a tyre-size calibration.** Tyre size is set by the BFU circumference (K = 900·C,
  `WHEEL_SPEED_CHAIN_7846816A.md` §4.4). The learner only sees the ratios between wheels. If C is wrong by the same
  factor on all four, every ratio is 1 and nothing is learned. vref, every speed and slip threshold in km/h, the
  CAN speeds and every wheel acceleration (Δv · 2.83) stay off by that factor.
- **It is a tolerance trim.** It absorbs small differences between wheels: tread wear, pressure, a space-saver
  spare (§4), and the M3's factory stagger, which has its own switch (§3.1).
- **It only reaches part of the chain.** vref and the corrected speed `rec+0x1C` use it. The main ABS slip, the wheel
  accelerations, the excess speed loss and the CAN speeds do not (§6). A learned mismatch therefore shifts ABS
  entry on the faster-reading axle instead of removing the error.
- **Standalone installations:** for ABS control with the wrong tyre sizes it is functionally useless, and with a
  front/rear mismatch it is mildly harmful (§6, "Effect of a front/rear mismatch"). Set the real rolling
  circumference per axle in the BFU block (patcher `basic/wheel_size`) and let the learner absorb only the last
  percent or so.

## Summary

- Each wheel has a learned factor byte `b`, factor = (745 + b)/1000 ≈ (769 + b)/1024. b = 255 is 1.0. The bytes
  are renormalised so that the **slowest-turning wheel is 1.0** and faster wheels are scaled **down** to it. The
  range is 0.746–1.0, so at most about a 25 % difference can be learned. [C]
- Learning runs only with vref > 5 km/h, every wheel valid, not in the braking regime (`0x408DA1` b4), and with the
  rear wheel accels close to the vehicle decel. The slow table steps every 11th pass. [C]
- The table is saved to EEPROM (block 22). **At start-up each axle gets the larger factor of its two wheels,
  floored at 225 (0.970)**, so at most about 3 % is applied straight away; the rest is relearned while driving. [C]
- **Users:** vref's wheel picks, and the corrected speed `rec+0x1C` (overspeed / "faster than reference" tests,
  front main slip when the factory-stagger switch is set (§3.1), left/right comparisons, TCS/MSR/AYC readers). **Not corrected:** the main ABS slip (vref − `rec+0x1A`),
  the wheel acceleration `rec+0x20`, the excess speed loss `rec+6`, and the CAN wheel/vehicle speeds. [C]
- Consequence [I]: the learner moves vref onto the slowest wheel's scale but leaves slip on raw speeds. Before it
  has learned, the slower-reading axle shows phantom slip equal to the mismatch. After it has learned, the
  faster-reading axle reads that much **negative** slip, so it needs extra real slip before ABS enters.
- A wheel ratio ≥ 1.25 above 40 km/h (≥ 1.50 below 20 km/h, interpolated in between) held long enough raises
  **5Dx5 "double tone-ring frequency"** on the fast wheel(s), or **5Dx3** on a single slow wheel (§7). [C]

## 1. Data

| Item | Meaning | Tag |
|---|---|---|
| `0x403214[4]` | slow (stored) factor table, u8 per wheel | C |
| wheel `rec+0x35` (rec+53) | active factor byte | C |
| wheel `rec+0x1C` | corrected speed = `rec+0x1A` × (769 + rec+0x35)/1024, written at 0xD15FA | C |
| wheel `rec+0x2E` / `rec+0x36` | 1/16 IIR of `rec+0x1A` (0.01 km/h) / its fraction byte (0xD1516–0xD1546) | C |
| `0x403255` | EEPROM copy of the factors, block 22 (EEPROM 0x269, 6 bytes); load 0xD26AC, save 0xD24F6; valid flags in `0x403254` b2/b4 | C (I for the exact layout) |
| `0x40320E` b1 | single-wheel large-deviation ("spare tyre") mode, set by 0xD10EC (§4) | C, I meaning |
| `0x40320F` b3 | when set, the slow table is overwritten with rec+0x35 (0xD178A) and vref uses the table only | C, writer [open] |
| `0x403225` b6 | pause: a rear wheel accel outside the band around the vehicle decel `0x408DAF` (0xD14E6 loop) | C |
| `0x403227` b2 | set on every 11th pass (`0x40095C` mod 11 = 0, 0xD1498); gates the slow table step | C |

Helpers: `0xD0444` = clamp(x, lo, hi); `0xD0480` = renormalise four bytes so the largest is 255 (adds 255 − max
to each). [C]

## 2. Per-pass learner `tyre_tol_learn` 0xD144A

Called from `vehicle_estimators_frame` 0xD03F8 (via 0x8F29C from the 0x7101C job), assumed every 10 ms [I].

1. Updates the 1/16 IIR of each wheel speed. It also forms the corrected filtered speeds
   rec+0x2E·(745 + rec+0x35)/1000 and the minimum filtered speed `vmin` (start 30000). [C]
2. Writes `rec+0x1C` for all four wheels (0xD15FA). [C]
3. Target per wheel (0xD167E–0xD1712), only when vref > 500, wheel 0 speed > 500, `0x408DA1` b4 clear and no wheel
   has `0x400952` b0:
   `t = 1000·vmin / rec+0x2E − 745`, or **1** when that is ≤ 0 (wheel more than 25 % fast; also clears `0x403224`
   b6). [C]
4. **Slow table step** (0xD171A–0xD1788), when `0x40320F` b3 is clear, `0x403227` b2 and `0x403225` b6 clear:
   - fronts with b ≥ 205: b += clamp(t − b, −15, +1);
   - rears, and fronts with b < 205: b += clamp(t − b, −1, +15).

   One count is 0.1 %, so a front correction up to 5 % builds at 1.5 % per step and a rear correction at 0.1 % per
   step (about 1 %/s at 110 ms per step [I]). Corrections relax back toward 1.0 at the opposite rate. [C]
5. With `0x40320F` b3 set, the slow table is copied from rec+0x35 instead (0xD178A). [C]
6. Renormalise the slow table (0xD17BE → 0xD0480). [C]
7. With `0x403224` b6 and `0x403227` b2, calls 0xD10EC with the targets (0xD180A). [C; what sets 0x403224 b6 is
   [open]]

## 3. vref use (0x44AF0–0x44B54)

The wheel picks in `vref_update` compute rec+0x1A × (0x301 + byte)/1024 inline. Fronts use the smaller of
`0x403214[w]` and rec+0x35 (the stronger correction), and rears the larger. With `0x40320F` b3 set, both use the
table. Cmax / Fmax are therefore on the slowest wheel's scale. [C]

## 3.1 Factory-stagger switch: front main slip on the corrected speed

The stock M3 runs staggered tyres on a matched calibration. 245/40R18 front is about 2052 mm and 265/40R18 rear about
2102 mm (unloaded, geometric), while the BFU has 2073 mm on both axles, about their mean. Each axle is about 1.2 %
off in opposite directions, so the fronts read about 2.4 % faster than the rears. (Loaded rolling circumferences
are a few percent smaller. The ratio is what matters here.) The learner settles at rears ≈ 255 and fronts ≈ 231.
[C for the cal, I for the tyre figures]

`abs_wheel_signal_frame` 0x461C0 (each frame, before the ABS per-wheel signals) decides **0x408DF1 b7**, the flag that
makes the event classifier use `rec+0x1C` instead of `rec+0x1A` for the **front** main slip [C]:

- b7 = 0 unless |FL.b − FR.b| < 5 and |RL.b − RR.b| < 5 (each axle matched within 0.5 %);
- D = (RL.b + RR.b) − (FL.b + FR.b) must satisfy 2·cal − 20 < D < 2·cal + 10, with cal = ABS+0x66 (0x40402) =
  **25** in this image. That is 30 < D < 60. With both fronts equal, D = 2c where c = 255 − front byte, so
  c = 16…29. The learner's target is t = trunc(1000·vmin/v) − 745, so that window is a front-faster mismatch m of
  about **1.5–3.0 %** (c = 16 ↔ m ∈ (1.52, 1.63] %, c = 29 ↔ m ∈ (2.88, 2.99] %). Otherwise b7 = 0;
- if those pass, b7 = 1 only when tyre-learning status 0x403210 b0 is set and the 5-bit counter
  0x403212 & 31 ≥ 9. If either is not met, b7 keeps its previous value. Both are maintained by the learner's
  bookkeeping (0xD0BE2 …) and their exact meaning is not decoded. [C structure, open meaning]

Stock M3 numbers: D = 2·255 − 2·231 = 48, in the window. So once the learner has converged, the fronts' main slip is
taken on the rear (slowest-wheel) scale and the 2.4 % deadband described in §6 disappears for the fronts.
The start-up restore floor of 225 (2.9 %) also covers this stagger, so the correction is back at once after a
restart. [C/I] BMW therefore designed the calibration around the factory stagger.

Consequences [I]:

- **Square tyres with correct per-axle C:** all factors ≈ 255, D ≈ 0, b7 = 0. The fronts use raw speed, which is
  now correct.
- **Staggered tyres with correct per-axle C** (`basic/wheel_size`): same, D ≈ 0. Nothing depends on the switch.
- **Matched C with a different front-faster stagger:** b7 only engages for about 1.5–3 %. A larger or reversed
  (rear-faster) mismatch leaves it off and gives the §6 deadband or phantom slip.

Behaviour by size of a **rear-larger** stagger m (fronts read m faster; matched C; each axle matched left/right).
The rears are the slowest-turning wheels, so their factor is 1.0 and raw = corrected for them. [C/I]

| m | vref | Rear main slip | Front main slip | Net effect |
|---|---|---|---|---|
| < 1.5 % | rear scale (learned) | raw = corrected | raw: reads up to −1.5 % slip | small front deadband, which the calibration accepts |
| ≈ 1.5–3 %, learner converged | rear scale | raw = corrected | **corrected** (b7) | all four effectively corrected |
| ≈ 3 % to 25 % | rear scale, **still learned** | raw = corrected | raw: reads −m slip | fronts need m extra real slip before ABS entry; worse than no learning at all for the fronts |
| ≥ 25 % (≥ 50 % below 20 km/h) | — | — | — | 5Dx5 / 5Dx3, wheel dropped (§7) |

Timing and conditions:

- **After power-up** b7 is 0 (RAM) until the learner reports converged (0x403210 b0, counter ≥ 9). The duration is
  not decoded. Until then the fronts run on raw slip even inside the window.
- **After a restart** only 2.9 % (floor 225) is restored, which covers the whole window. Above it the remainder is
  relearned: fronts step at up to 1.5 % per slow-table step (every 11th pass, outside the braking regime). Until
  then vref still follows the fronts partly, so the rears show phantom slip of (m − 2.9 %).
- **Left/right mismatch** over 0.5 % on either axle (uneven wear or pressure) clears b7.
- **Front-larger stagger** gives D < 0 and b7 = 0. The fronts are then the 1.0 reference, and the rears read
  −m slip through raw main slip.
- **Non-M (6862873A):** the equivalent function 0x462F4 has no stagger block, and nothing sets the non-M copy of the
  flag (0x403F11 b7, ABS RAM shift −0x4EE0). Front main slip is always raw there. [C]

## 4. Large single-wheel deviation 0xD10EC

Per wheel, d = 255 − t (deviation from the slowest wheel, 0.1 %). d < 15 counts as matched (+1). 81 ≤ d < 200
(8.1–20 %) counts as large (+4, with a nibble state in `0x40322A`). [C]

Only the total 7 (three matched wheels and one large one) advances the counter (high nibble of `0x40322A`). At 13
passes the routine:

- sets `0x40320E` b1;
- loads the targets into `0x403214`;
- copies the renormalised targets into rec+0x35 (0xD10CA);
- writes rec+0x2C = t·100 for t < 175. [C]

This is a space-saver-spare detector [I]. `0xD121A` widens a left/right speed tolerance from 40 to 250 while b1 is
set. `0xD0456` clears b1 after a count of 121 once `0x403224` b5 is set (wheels agree again). [C structure, I]

## 5. Start-up restore and reset

- **Restore** (0xD1F42–0xD2070): with `0x403254` b4, `0xD273E(2)` reads each wheel's stored byte (case 2: from
  `0x403255[w]` when `0x403254` b2, else 255). Per axle the **larger** of the two is kept (fronts r13, rears r14).
  It is floored at **225** (0xD1FB8: values below 225 become 225) and written to rec+0x35 and `0x403214[w]`.
  rec+0x2C = 100 × the value. Without valid storage every factor is 255. [C]
- **Reset** (0xD1C7A–0xD1CA0): `0x403214[w]` = rec+0x35 = 255 for all wheels and flags cleared. Trigger not
  traced. [C / open]

## 6. Who uses the corrected speed, and who doesn't

| User | Speed used | Tag |
|---|---|---|
| vref wheel picks Cmax / Fmax (§3) | corrected inline | C |
| Event classifier slip2 = ref − rec+0x1C: EV0.b7 "faster than reference", EV0.b1 pause reapply, phase flags b4–b6 (`08_phase_control.md` §3.2) | corrected | C |
| Event classifier main slip sp+40 = ref − rec+0x1A (entry, gross slip, 7 % test); fronts switch to rec+0x1C when `0x408DF1` b7, the factory-stagger switch (§3.1) | **raw** (fronts corrected under b7) | C |
| TCS / MSR / AYC readers of rec+0x1C (`tcs_yaw_slip_term` 0xC9450, code near `msr_cycle_entry` 0xCBF58, `tcs_torque_ctrl_entry` 0xCC9A0, `tcs_reduction_floor` 0xCD7FE, AYC 0x627F6 / 0x63D8E / 0x645D8), `chassis_state_flags_update` 0x91070, 0x94EC4, 0xC75A6 | corrected | C (reads; uses not traced) |
| Wheel accel rec+0x20 (`wheel_accel_update` 0xD20DC, fed the raw speed delta by `wheel_speed_update` 0x7525C at 0x75482) and the excess speed loss rec+6 built from it | **raw** | C |
| `ay_wheel_estimate_update` 0xD21C4 (front L/R), `abs_side_select` 0x5AEEE (rear L/R) | corrected | C |
| CAN 0x0CE wheel speeds, 0x1A0 vehicle speed (front mean) | raw (FACTS "CAN 0x1A0 vehicle speed") | C |
| Wheel-ratio plausibility (§7) | sorted list `0x4027F8` built at 0xB63CA; source field not confirmed | I: raw |

**Effect of a front/rear mismatch m** [I]:

- **Unlearned** (start of a drive beyond the 3 % restore, or learning paused): vref follows the fastest-reading
  wheels. The other axle reads about m·v of phantom slip, so route A and the 7 % confirmation fire early on that
  axle. The MR2 track log (3.3 %, rear-only ABS at ~1.1 g) matches this case.
- **Learned:** vref sits on the slowest axle's scale. The faster-reading axle reads about −m·v of slip, so it needs
  m extra real slip before route A or the 7 % test passes (late entry, deeper slip). Route B's decel tests are
  rate-based and are affected only by the m scale on wheel accel.
- **Exception:** a front-faster mismatch of about 1.5–3 % with each axle matched (the stock M3 stagger) sets the switch
  in §3.1 once learned, and the fronts' main slip then uses the corrected speed. The rears and the wheel
  accelerations stay raw.

## 7. Wheel-ratio plausibility `wss_ratio_plausibility` 0xB6A08

Called from 0xB6EB4, which is called from the wheel monitor 0xB651C. [C]

- **Ratios.** It forms the six ratios ×100 of the sorted speeds v0 ≥ v1 ≥ v2 ≥ v3 (`0x4027F8`, pointers
  `0x40280C`): v0/v1, v0/v2, v0/v3, v1/v2, v1/v3, v2/v3 → bits 0–5. [C]
- **Band.** A ratio counts when lo < r < hi.
  - hi = 250, or the adapted value in `0x402926`.
  - lo comes from ROM curve x `0xF56E6` = {2000, 4000} (v2, 0.01 km/h), y `0xF56EA` = {150, 125}: 150 below
    20 km/h, 125 above 40 km/h.
  - The counter limit comes from `0xF56EE` = {3000, 1000}.
  - After 16 counts the window narrows to the measured ratio ±5 (0xB6BF8). [C]
- **Counter.** `0x40291E` +1 per pass while the bit pattern is 7, 30, 51 or 52, v2 > 20 km/h and `0x402920` = 0.
  Otherwise it resets. [C]
- **At the limit:**
  - pattern 7 or 51 (one wheel high) → pending b2 and `fault_set(group 2+w, bit 10)` = **5Dx5** on the fastest
    wheel;
  - pattern 30 (two high, two low) → 5Dx5 on both fast wheels;
  - pattern 52 or 51 (one wheel low) → bit 11 = **5Dx3** on the slowest wheel. [C]
  - Each also sets `0x400952[w]` b0 (wheel faulted). [C]
- **Separate start-up check.** The 5Dx3 path in the same routine fires when v0/v2 < 1.05, v2/v3 > 20 and
  `0x40292A` > 1000: one wheel stopped while the others turn. [C]
- **5Dx4 "long-term".** Raised in 0xB651C (0xB65E4–0xB6618) when a wheel in dump/hold (`rec[0] & 0x28`) has
  rec+0x28 > 2800 in the braking regime. That is a release held too long, not a ratio test. [C structure, I
  meaning]

## Open

- Writers of `0x40320F` b3 and `0x403224` b6. Meaning of 0x403210 b0 and the 0x403212 counter that gate the
  stagger switch (§3.1).
- The stagger switch in the 1M image (non-M has none, §3.1). Time for the learner to report converged after
  power-up.
- The EEPROM save condition for block 22, and its two extra bytes.
- The call rate of 0xD144A (assumed 10 ms) and of 0xB6A08, which set the learning time and the fault delay.
- The source field of `0x4027F8`.
- Whether 6862873A (non-M) is identical.

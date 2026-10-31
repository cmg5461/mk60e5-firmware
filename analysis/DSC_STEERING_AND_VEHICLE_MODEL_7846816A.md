# Steering data flow, and fitting the DSC model to another car — 7846816A (E9x M3)

Two questions behind this doc:

1. How does the steering angle get from the SZL (F-CAN 0x0C9) to the ABS and DSC, including the zero-offset
   learner and the steering-ratio curve?
2. To run AYC, or just the steering- and lateral-aware parts of ABS, on a car that is not an E9x M3, what has to
   change so the sensors and the vehicle model are about right?

Read from the disassembly (`analysis/7846816A_main.lst`), not bench-tested. CPU addresses; file = CPU + 0x8000.
Tags: **[C]** read from code, **[I]** inferred, **[U]** user-supplied, **[open]** not traced. The steering LSB
(≈ 0.044° steering wheel per count) is **unverified**, so every degree figure is [I]. Counts are exact. One
cross-check [I]: the commonly quoted 0x0C9 LSB 0.04395°/bit, after the ·1029/1024 in the handler, gives
0.04374°/count, and the non-M custom-curve coding unit (91.42 counts, `CODING_BYTES_6862873A.md` byte 13) is then
exactly 4.00°. Symbols:
`7846816A_symbols.md` § "CSI / steering / yaw reference". ABS side of the steering signal:
`agents/abs_full/09_chassis_sensor_use.md` §7.

## 1. Steering data flow

```
F-CAN 0x0C9 sig 43 ── canrx_steer_angle_0C9 0xC5C78 (·1029/1024) ──► 0x401644  steer_angle_can
0x0C9 status       ── fcan_rx_0C9_angle_status 0xC5E20 ──────────► 0x40164D b7:6

steer_task 0x91008 (called from 0x8F028 ← 0x7101A; period [open])
 ├─ steer_capture 0x901D4          0x401644 → raw 0x4020D0, IIR 0x4020D2 (k 241/256)
 └─ steer_offset_and_ratio 0x90384
     ├─ steer_offset_learn 0x9020C  offset 0x4020A6 (Q6) update, gated (§2)
     │                              every call: 0x402132 = 0x4020D0 − 0x4020A6/64   (corrected SW angle)
     └─ steer_ratio_convert 0x9032E 0x4020D4 = old 0x40212E;
                                    0x40212E = 29360·a / R(|a|), a = 0x402132 clamped to ±xs[3]   (§3)
steer_rate_update 0x90408           0x402130 from raw 0x4020D0 (offset-free)

getters 0x94120 / 0x9403C / 0x940AE  → ABS 0x408EDE angle / 0x408EE4 road-wheel / 0x408EE6 rate (valid 0x408E6D b5)
                                       invalid on 0x402888 b0 or 0x402884 b3
tcs_sensor_latch 0xCC89C             → road-wheel angle into the traction copy (0x403064 b4)
yaw reference (sub_090D10, 0x90E5C)  reads 0x40212E → closed-form r_ref 0x4020EC (AYC target seed)
chassis state flags 0x91070          0x402144 b5 / b4 = |0x40212E| > 1127 / > 8208
```

[C] for every arrow. Readers of 0x40212E are only 0x9032E, 0x90E8A (yaw reference), 0x9112C (state flags) and
the getter 0x94046. Readers of 0x402132 are 0x9020C, 0x9032E, the getter 0x94120 and 0x94192.

| RAM | Type / scale | Meaning |
|---|---|---|
| 0x401644 | s16 counts | CAN angle ·1029/1024 |
| 0x40164D | u8, b7:6 | 0x0C9 angle status |
| 0x4020D0 | s16 counts | raw steering-wheel angle |
| 0x4020D2 | s16 counts | IIR of raw (learner target) |
| 0x4020A6 | s16 Q6 counts | learned zero offset |
| 0x402132 | s16 counts | corrected steering-wheel angle |
| 0x40212E | s16, LSB = SW LSB / 28.67 | road-wheel angle (29360/1024 = 28.67) |
| 0x4020D4 | s16 | previous 0x40212E |
| 0x402130 | s16, ≈ counts/s [I] | steering rate |

## 2. Zero-offset learning

### 2.1 Limits [C]

| Limit | Value | Where | Effect |
|---|---|---|---|
| Step clamp | target within ±228 counts (≈ ±10°) of offset/64 | 0x9020C (0x902AA–0x902CC; +228 = `movi`/`bseti` at 0x902AC, −228 = literal 0x903D0) | Target = IIR angle 0x4020D2, clamped to offset ± 228. **A clamp, not a gate:** a large error still pulls the offset at full step. |
| Fault | \|offset\| > 0x3924 = 14628 Q6 = **228.6 counts (≈ 10°)** | `steer_offset_fault_monitor` 0xBF868 (literal 0xBF8D0) | `fault_set(0x120001)`. Checked while 0x4020FD b6 and (0x402904 & 0x84) = 0x80. |
| Hard clamp | ±0x7249 = 29257 Q6 = **457 counts (≈ 20°)** | literal 0x903D4 → `clamp_sym16` 0x91A0E | offset never exceeds this |
| Restore clamp | ±29257 | table 0xDA974[0] | applied when the offset is loaded from EEPROM |
| Raw range | \|raw 0x4020D0\| > 16457 counts (≈ 720°) | 0xBF898 (`movi`/`bseti`) | also 0x120001, when 0x40164D & 0xC0 = 0 |

So the usable range is about **±10°** of steering-wheel offset. The learner can reach ±20°, but past 10° the
fault sets.

### 2.2 Update rule [C]

Runs when the down-counter 0x402134 (reload 100) reaches 0, and only with 0x4020FD b7 (set by the record state
machine 0x92104 after the EEPROM restore) and 0x402147 b7 (writer not traced). Skipped while 0x402884 b3
(steering fault reaction).

```
A = interp(|0x4020DC|, xs 0xDA8FA = {299, 3199}, ys 0xDA8FE = {3000, 9000})   ; alt ys 0xDA902 = {700, 3000} if 0x4020FD b4
B = interp(|0x40211C|, xs 0xDA906 = {1745, 6981}, ys 0xDA90A = {3000, 700})
D = min(A, B) · 1200 / [0x400B2C]
offset += (clamp(0x4020D2, offset/64 ± 228)·64 − offset) / D
offset  = clamp(offset, ±29257)
```

- 0x4020DC is `ay_signal_get` idx3 (a lateral quantity, scale [open]). Larger lateral → larger D → slower.
- 0x40211C = clamp(0x4020F8 − 0x402118, ±31415) (`steer_yaw_residual_update` 0x90BC0); a yaw-side residual
  [I, low]. Larger → smaller D → faster.
- 0x400B2C is also used by the yaw observer; initialised to 1 at 0x647A0; role [open].
- The same pass also does 0x402136 += vref/360 (cap 60000), zeroed while 0x4020FC b7.

[I] A slow low-pass zero tracker for a few degrees of alignment or sensor drift, not a fix for a sensor
installed off-centre. The time constant in seconds needs the `steer_task` period and the scales of the three
inputs [open].

### 2.3 Persistence [C]

`sensor_offset_record` 0x4020AE (17 × u16, EEPROM block 8 at 0x160, load 0x8F1F8 / save 0x92796):

| Record word | Goes to |
|---|---|
| +0 | checksum = `xor16_checksum` 0x920D8 over +2..+33 (16 words; result 0 or 0xFFFF → 0x4852, then inverted) |
| +2 | 0x4020FA |
| +4 / +6 / +8 / +10 | 0x4020A6 steering / 0x4020A8 lateral / 0x4020AA, 0x4020AC master pressure offsets, each clamped by 0xDA974 = {29257, 30581, 16000, 21600} |
| +16.. | 0x4049FD / 0x404A04 … (not decoded) |

`sensor_offset_record_sm` 0x92104 (state 0x402142): checksum mismatch → `fault_set(0x81000)`. So a bad learned
offset survives power cycles; after moving the sensor, re-zero rather than wait for the learner.

### 2.4 Diagnostic zero [C structure]

`31 21 00` (`LENKWINKEL_DSC_ABGLEICHEN`) needs 0x40200C b5 (steering ready), else NRC 0x22
(`SERVICE_ROUTINES_7846816A.md`). What it writes is **[open]** (expected: 0x4020A6 or the record).

## 3. Steering-ratio curve

### 3.1 Layout [C]

`steer_ratio_convert` 0x9032E: k = f+5 (0x4031AF), xs = 0x40EB4 + 8k, ys = 0x40ECC + 8k, 4 × s16 each.
x = corrected steering-wheel angle (counts), y = overall ratio × 1024. The input is clamped to ±xs[3] and
interpolated on \|a\| (`interp_linear_xy` 0x7119E, end-clamped), so it is symmetric and the road-wheel angle stops
growing past the last breakpoint. y is the **secant** ratio (total SW angle / total road-wheel angle).

| f+5 | NCS [U] | x (counts) | ≈ SW ° | y/1024 |
|---|---|---|---|---|
| 0 | E90 M3 | 0, 3383, 6926, 10880 | 0, 148, 303, 476 | 15.90, 15.36, 13.89, 12.59 |
| 1 | unused (custom ESM, ignored) | = set 0 | | = set 0 |
| 2 | E92/E93 M3 | 0, 2263, 5120, 10788 | 0, 99, 224, 471 | 15.90, 15.48, 14.15, 12.45 |

- **Only 3 sets fit.** The x sets end where y set 0 starts (0x40ECC) and the y sets end at the sign tables
  (0x40EE4). A set 3 would read x = {16282, 15729, 14223, 12892} and y = {−1, −1, −1, −1}, giving a garbage,
  sign-inverted road-wheel angle. It cannot be coded: field limit 0xF68A0[5] = 3 rejects it on write (NRC 0x31,
  fault 0xC0002) and zeroes the image at boot (`CODING_BYTES_7846816A.md`).
- **Value 1** reads ROM set 1 (a copy of set 0) and needs c41–c47 ≠ 0 (`coding_custom_words_check` 0xCF32C).
  Nothing reads those bytes in this image. (In the non-M 6862873A, value 1 does build the curve from coding words;
  `CODING_BYTES_6862873A.md`.)
- The 1M (7846411A) has a single set at 0x40A10 / 0x40A18 with no coding index (14.6 → 12.5).

### 3.2 What the curve implies [I]

Road-wheel angle = SW / R(SW). For set 0:

| SW | Road wheel | Local ratio over segment |
|---|---|---|
| 0–148° | 0 → 9.6° | 15.4 |
| 148–303° | 9.6 → 21.8° | 12.7 |
| 303–476° | 21.8 → 37.8° | 10.8 |

A ~32 % drop in local ratio to ~38° road wheel at lock. [U] The M3 rack is constant-ratio; the drop is steering
linkage geometry (arm angle / Ackermann). Which road wheel the firmware means (inner, outer, mean) is [open].

Set 2 vs set 0 at the same SW angle: 0.4 % quicker at 100°, 2.7 % at 150°, 3.4 % at 225°, 2.1 % at 300°, 1.1 %
at lock. [U] All E9x M3 share rack, wheelbase and track, so the difference is not hardware. [I] Most likely an
effective ratio tuned with each body's yaw-response fit (the vehicle-model columns also differ: v_ch sedan 128.8
vs coupe 109.0 km/h), or two measurements of the same hardware. Coupe and convertible share set 2 but not a
vehicle model (v_ch 109.0 vs 121.8), so it was not fitted per variant.

The ratio matters almost not at all for ABS (`09_chassis_sensor_use.md` §7.5) but directly scales the DSC yaw
reference.

## 4. Fitting DSC to another car

### 4.1 Prerequisites [C]

- **Frames:** SZL 0x0C9, yaw / lateral cluster 0x0CD / 0x0D1 on F-CAN, and the DME frames on PT-CAN. Without the
  DME frames AYC and all traction channels are inhibited (FACTS "DSC-off and the traction channels"). Without the
  SZL, lateral and yaw are invalid too and ax is never trusted (FACTS "Steering-sensor loss", "ax trust needs the
  SZL").
- **AYC engine side** goes out as the torque request on 0x0B6; brake-only AYC works whether or not anything acts on it.
- **DSC mode:** only MDM reaches `tcs_mode` = 3 and so m ≠ 0; m1 vs m2 is coding byte 10 bit 5 (FACTS "Yaw /
  single-track model + DSC mode", "DSC driver mode").

### 4.2 ABS cornering features need sensors, not geometry [C]

The ABS uses steering as a validity switch plus a few to-taste thresholds in counts, g and deg/s
(`09_chassis_sensor_use.md` §2, §7). Needed, in order: valid frames > sign > zero offset > scale > ratio (≈ none).
**Correction (2026-10-23):** the ABS reads the observer target 0x400B1A well outside the AYC-gated monitor 0x4A254.
13 more literal words load it, in the event classifier `sub_04D270`, `abs_side_select` 0x5AEEE,
`abs_corner_peak_track` 0x5A4E4, 0x50894, 0x57024 and 0x5971C. 0x55420 reads the closed-form steering reference
0x4020EC. These sites compare measured yaw with the target and are gated on yaw-valid, not on steering or AYC. So
with a working SZL, parts of the ABS cornering logic do follow the vehicle model (FACTS "ABS reads the
steering-based yaw target").

### 4.3 Sensors

| Item | What to do | Ref |
|---|---|---|
| Steering zero | Mount the SZL centred within 1–2°; run `31 21 00` wheels straight. The learner covers a few degrees; > 10° faults (§2.1). | §2 |
| Steering sign | Must match the M3 convention: ISO 8855, positive = left, the same sign as lateral and yaw when driving forwards (owner-confirmed 2026-10-26); reversed sign inverts the GMA rate term, the countersteer test and the yaw reference | `09` §7.5 |
| Steering scale | An E9x SZL keeps it (·1029/1024 in the CAN handler) | §1 |
| Cluster orientation | Mount as in the M3; CSI per-variant sign tables 0x40EE4 / 0x40EFC / 0x40F14 are −1 for every variant (roles per XDF: ay / ? / yaw [low]) | symbols CSI |
| Tyre size | BFU circumference 0x41CF4 / 0x41CF6 = 2073 mm, teeth 0x41CF8 / 0x41CFA = 48. Tolerance learning applies only ~3 % at start-up, so patch for a real size change. vref scales the yaw reference directly. | `TYRE_TOLERANCE_LEARNING_7846816A.md` |

### 4.4 Vehicle model [C layout, I procedure]

**There is no coding route to custom geometry.** Variant 1 (Custom ESM) only non-zero-checks c31–c40; the loaders
0x5DE44 / 0x5E424 read ROM column 1. So patch the ROM column of the variant `0x4031AA+1` is coded to, and keep it
in 0–9: the ABS decel curves are also variant-indexed (10/11 are more permissive above 150 km/h) and 0x4D946 has a
variant-10 branch (`CODING_BYTES_7846816A.md`). Rows are 12 × s16, stride 2 (XDF "Vehicle model (coding-variant)"):

| Row | Unit | Set to |
|---|---|---|
| l_f 0xD6F42, l_r 0xD6F5A | Q10 m | CG to each axle from wheelbase and corner weights (wheelbase = l_f + l_r; no wheelbase scalar) |
| mass 0xD6F72 | kg | driving weight (stock rows are 1–4 % above curb) |
| Jz 0xD6F8A | kg·m² | measured if known; stock Jz / (m·l_f·l_r) = 0.75–0.99 (most 0.88–0.97) |
| track 0xD6FA2 / 0xD6FBA | **Q10 m, not mm** | real tracks; also sets the wheel-speed yaw term 0x400AF4 = round(56888 / track_Q10) |
| Cf 0xD6ECA, Cr 0xD6EE2 | units [open] | fit (below) |
| sensor x 0xD6F2A | −Q10 m | −(yaw / lateral sensor distance behind the front axle); M3 −1204 = 1.176 m [I]. 0x5E424 forms l_f + x, x, L + x → 0x400AEC / 0x400AF0 / 0x400AF2, the CG / front / rear lever arms of `ay_axle_est_calc` 0x8FFE8 (≈ 0.19 m steps) |

Patch: `mk60e5_patcher` `patches/basic/vehicle_model` writes all of the above plus the steering curve (§4.5) into
every variant column and ratio set, from profile params. Its README has the starting-value formulas. Replaying
both loaders: observer coefficient 0x400AD8 (read at 0x5F9CC) ∝ v_ch², stock 14444 at 128.8 km/h, so it saturates
at v_ch ≈ 194 km/h. A neutral model (Cr·l_r = Cf·l_f, i.e. Cf / Cr = W_f / W_r) divides by zero in 0x5E424, and an
oversteering one divides unsigned by a negative. So a rear-heavy car needs Cf / Cr rescaled, not left stock, and a
near-neutral car needs a deliberately finite v_ch.

**Cornering stiffness sets the yaw reference.** Loader 0x5E424 derives v_ch at run time (v_ch² = 32·AEA·AE8,
RAM 0x400AE8 / 0x400AEA) from the column, with the understeer term Cr·l_r − Cf·l_f; in textbook form [I]
`v_ch² = L²·Cf·Cr / (m·(Cr·l_r − Cf·l_f))`. Stock v_ch per variant: {0/5: 128.8, 1/6: 109.1, 2/7: 136.8,
3/8: 109.0, 4/9: 121.8, 10: 142.1, 11: 105.5} km/h (1M 97.65). Closed form: `r_ref = δ·v / (L·(1 + v²/v_ch²))`;
the dynamic observer (`yaw_observer` 0x5EBC4) uses the same coefficients and produces the target 0x400B1A.
Procedure [I]:

1. Start from M3 Cf / Cr scaled by your axle loads.
2. From steady-state cornering logs (yaw rate, road-wheel angle, speed), fit r/δ = v / (L·(1 + v²/v_ch²)) for
   the car's real v_ch.
3. Adjust Cr/Cf until the model's v_ch matches; check offline with `agents/yawmodel/sim.py`.

Leave the observer tyre terms 0x415F8 / 0x41610 / 0x41628 and the lag curves 0xD704A / 0xD70AA stock at first
(their exact roles are only partly decoded).

### 4.5 Steering-ratio curve [I]

Code f+5 = 0 or 2 and overwrite that set (not 1). Measure, don't calculate: turn plates or an angle gauge on the
hub, SW angle against both road-wheel angles at several points to full lock; use the left / right mean unless the
firmware's reference wheel turns out otherwise. Put the 4 breakpoints where the curve bends most, last at or just
past full lock (it is also the input clamp). Then trim against the yaw overlay (§4.7), as BMW's two sets are a few
percent apart on identical hardware.

### 4.6 Brakes and AYC gains

How AYC works end to end (target, error thresholds, PD response, distribution, modes, ABS coupling, numeric limits):
`AYC_7846816A.md`.

- AYC requests ~0.1 bar per moment count per wheel through the same COA p-V curves as ABS
  (`ayc_moment_to_wheel_pressure` 0x616A4), so the brake model must fit the hardware (MR2 / Volvo caliper work).
- A lighter car with lower Jz gets more yaw acceleration from the same pressure; the PD gains 0x413AA (47 / 47)
  and the per-mode % curves are the tuning. Entry / hold thresholds are round deg/s values (4 / 8 / 2 / 30 deg/s)
  and carry over between cars.

### 4.7 Validation

Log in steady cornering below the limit, at several speeds:

- target yaw 0x400B1A vs measured yaw 0x402100 (1/20000 rad/s), and closed-form r_ref 0x4020EC. They overlay
  when geometry, Cf / Cr, steering curve and tyre size are right. Fix this before touching AYC thresholds.
- 0x402132 near 0 when driving straight, and 0x4020A6 steady, well inside ±14628.
- 0x40212E against a measured road-wheel angle at a few static steering angles.

## 5. Open

- `steer_task` period, so the learner time constant can be given in seconds.
- Scales of 0x4020DC, 0x40211C, 0x400B2C; writer of 0x402147 b7; meaning of 0x402904 b7/b2 and 0x4020FD b5.
- What `31 21` writes.
- Which road wheel (inner / outer / mean) 0x40212E represents.
- Cf / Cr units.

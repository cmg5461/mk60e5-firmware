# MK60E5 ABS algorithm — M3 7846816A (full characterization)

Summary of the ABS controller, byte-verified against `flash/bin/7846816A_00000000.bin`. Per-domain detail
lives in `analysis/agents/abs_full/`:

| # | File | Domain |
|---|------|--------|
| 1 | `01_core_slip_loop.md`      | overview: vref, slip thresholds, phase machine, pair logic |
| 2 | `02_decel_threshold.md`     | wheel-decel trigger, effective threshold formula |
| 3 | `03_lateral_g_influence.md` | lateral-g / yaw / steering effect on ABS (vs DSC) |
| 4 | `04_pressure_actuation.md`  | valve chain, pressure sensing, COA P-V model (fluid detail: `../HYDRAULIC_MODEL_7846816A.md`) |
| 5 | `05_edge_cases_variants.md` | µ-split/GMA, µ-flag, rough-road, failsafe, variants |
| 6 | `06_pressure_sensors_recheck.md` | the five pressure transducers and how each is used |
| 7 | `07_pressure_on_can.md`     | pressure and ABS state on CAN |
| 8 | `08_phase_control.md`       | event classifier 0x4D270, phase machine, pressure targets, hold, reapply, end-of-event reset (instruction-level) |
| 9 | `09_chassis_sensor_use.md`  | every ABS use of lateral / yaw / steering, and what changes with a dead steering sensor |
| 10 | `10_vref_and_ax.md`        | vref, the decel estimate and the longitudinal accelerometer |

**Conventions:** CPU addresses below; **file offset = CPU + 0x8000 = XDF address**. Frame = 10 ms.
Units: speed/slip **0.01 km/h**, decel/accel **0.01 g**, pressure **0.01 bar** (pinned by CAN:
0x2B2/0x19E send the internal value ÷100 as integer bar). Tags: **[C]** confirmed from bytes/listing,
**[I]** inferred, **[open]** unresolved.

This is a *superset* of the 1M doc (`ABS_ALGORITHM.md`); core architecture matches opcode-for-opcode,
but RAM/cal addresses differ (M3 vref 0x408DA8 vs 1M 0x408D84, etc.).

---

## 0. The intervention triggers (the headline)

The per-wheel event classifier starts a dump on either of two kinds of test, interlocked in the phase machine:

1. **Slip trigger** — plain slip *speed* `slip = vref − wheelspeed` (0.01 km/h, **not a ratio**):
   - **Gross-slip threshold** curve 0xD6CE2: 4.0 km/h @0, flat ~**6 km/h** over 20–55 km/h, then slope
     **113/1024 = 11.04 % of vref** above 55 (10.9 @100, 22 @200 km/h). Slip ≥ this (+ margins) starts a dump. [C]
   - (A separate slip *ratio* signal 0x408F84 = (vref−wheel)·10000/vref exists but is downstream, not a trigger.)
2. **Decel-rate trigger** — a wheel's filtered deceleration crossing a speed- and g-dependent threshold (§2),
   confirmed by slip.

Recovery (spin-up) uses a **positive** wheel-accel threshold. The curve 0x40DB6 (XDF "ABS entry-slip
threshold", ~1.3–2.0 km/h, 2-frame debounce 0x40DB4) is a partner-slip test inside the µ-split pair logic, not
a general entry gate.

---

## 1. Core loop

- **vref** `vref_update` 0x449D0 → **0x408DA8**: a slew-limited tracker over the compensated wheel speeds, not a
  max-select. Rise: +22/frame (0.62 g) outside the braking regime (`0x408DA1` b4) only while every wheel is
  above it; +44/frame (1.25 g) toward the fastest front in the regime; +282 snap in some controller modes.
  Fall only when vref is above every counted wheel: a fixed step (normally −22/−32/−44, range −11 … −49) bounded
  by a limiter on the wheel-derived decel estimate `0x408DAF`. Floor ~0.6 km/h. [C] (`10_vref_and_ax.md`)
  - The ax-based fall (`vref_fall_from_ax` 0x50FF4, `max(−44, (−|ax| − margin)·0.36)`) runs only with ax trusted
    and lateral, yaw, steering and pressure all valid with |lat| < 0.3 g. [C]
  - In all-wheel slip vref is an open-loop extrapolation; a wheel recovering above it pulls it back up. [C]
- Per wheel: `abs_event_classifier` 0x04D270 builds thresholds and emits an event word → per-wheel **phase
  machine** `abs_phase_sm` 0x04FC3C → dispatch 0x0504D0 → handlers write commanded pressure → arbiter (ABS
  id 1, rear 11; apply ramp id 19). [C]
- **Rears are select-low**: `abs_rear_lead_select` 0x05184C picks the lead rear by phase score (and lateral sign
  when lateral is valid); the follower is clamped to the lead. Rear reference = same-side front pressure. [C]
- **µ-split (GMA)**: `abs_pair_logic` 0x54D9A runs only after a yaw kick opens `abs_pair_gate` 0x54B70; it then
  paces the high-grip wheel's rebuild (`abs_gma_hold_frames` 0x54BE8). [C]
- **Phase machine** (rec[0] bits, table 0x40BF00 + 0x40·wheel): `0x80 armed → 0x21 DUMP → 0x09 HOLD → 0x11
  REAPPLY → (0x15 paused)`; pre-control 0xC0, overspeed 0x84. [C] (`08_phase_control.md`)
  - **DUMP**: entry target = lock-onset pressure 0x408FD0 − R, R ≈ 8 % of it plus decel-rate, wheel-decel,
    rear-slip and decel-onset terms, capped at wheel pressure − 0x401D00[w]; rate −8000. Later frames pause,
    release continuously (10 bar/frame), or step.
  - **HOLD**: command = measured pressure, rate 0.
  - **REAPPLY**: staircase of steps sized from the dump depth (≈ 0.19·H then 0.16·H), ramped at 3 / 5 bar/frame
    (front / rear) with a 7-frame wait; continuous ramp after a step limit.
  - **Front staged dump** (`abs_dump_stage` 0x5424C): pulls the other front to the first front's lock pressure
    − 10/15/20 bar, staged by peak decel {−62,−78,−94} (≈ −9.9/−12.5/−15 g) or {−25,−44,−62}.
- **Exit**: the end-of-event reset in `abs_state_aggregate` 0x45808 returns all wheels to 0x80; the apply
  request (id 19) is dropped below 4 km/h (0x442AC). [C]

---

## 2. Decel-rate trigger

- `wheel_accel_update` 0x0D20DC: wheel accel = two-frame mean of (Δwheelspeed × **2.8316**), 2.8316 = 57991/20480 (literal 0xE287; earlier notes said 58023). **Unit = 0.01 g** proven (1 count Δv/frame = 0.028325 g physical). [C]
- **Effective dump threshold** (0.01 g, negative), builder `abs_decel_threshold_builder` 0x047BDC → 0x4090E6[wheel]
  (full build order in `02_decel_threshold.md` §2):

```
thr = base(−1.16 g) − speed_term(vref) − g_term(|vehicle decel|)
      thr = max(thr, −2.40 g)                 # absolute floor 0x4061E
      low-µ flag: thr = −1.30 / −1.35 g, no 60 km/h floor
      if vref < 60 km/h: thr = max(thr, −1.32 g)   # floor table 0x4065C (var10/11: −1.40); skipped with trusted, pegged ax
      if vref < 20 km/h: thr = max(thr, −1.27 g)   # floor table 0x40644
      front split-µ imbalance term, small trims
      if |wheel_accel| < 0.15 g: thr = −0.99 g
Dump when wheel filtered decel < thr.
```

- **speed_term** front var0 (0x40412): deepens threshold with speed → 0@0, 0.09 g@100, 0.29 g@200, 0.80 g@300 km/h.
  Rear single curve 0x405F2 evaluates the same.
- **g_term** var0 (0x40674): deepens with current decel → 0 below 0.3 g, 0.10 g@0.6, 0.35 g@1.0, 0.60 g@1.27 g.
  Input is the measured decel when ax is trusted, else the wheel-derived estimate.
- Worked points: 100 km/h @1.0 g → −1.60 g; 300 km/h @1.0 g → −2.31 g; 50 km/h → −1.32 g (floor60); 15 km/h → −1.27 g (floor20).
- **Re-apply**: positive spin-up threshold, +0.63 g idle / +2.85 g (or +1.30 g) in-cycle.

---

## 3. Lateral g / yaw / steering affect ABS — YES

Runs **inside the ABS controller**, independent of DSC, and **active in ABS-only** — but only with valid chassis
sensors. `abs_sensor_gather` 0x5D82C latches lateral accel → **0x408ECA**, yaw → 0x408ECC, yaw accel → 0x408ECE,
steering → 0x408EDE/EE4/EE6, with validity bits in 0x408E6D. (`03_lateral_g_influence.md`)

1. **Rear strategy from the lateral-g curves** [C]: `abs_decision_classify` 0x51B54 uses
   P_lo = 100·curve **0x40E26**(|lat|) and P_hi = 100·curve **0x40E0A**(|lat|) (+5 bar above 0.8 g) as
   driver-pressure thresholds. With lat + pressure valid and the rear cornering latch: driver pressure below
   P_lo → code 1 (rears independent); a dumping wheel with driver pressure above P_lo → code 32 with
   **pct = 100·(P_drv − P_lo)/(P_hi − P_lo)** (0x51F42). `abs_decision_pressure_exec` 0x58FF4 (code 32 @0x59222)
   then **reduces** a rear's command to max(1 bar, PM − pct·G/100), G = the source wheel's dump depth LOCKEST − CMD.
   pct is not clamped and wraps at 256 %; which rear is reduced is open (`09_chassis_sensor_use.md` §2.1 item 7).
2. **Lateral-g build step** [C]: code 256 (via `abs_decision_resolve`) adds +0.8 bar steps to light-pressure
   wheels at |lat| ≥ 0.65–0.8 g (exec @0x59064).
3. **µ-split pair logic** 0x54D9A [C]: gated on yaw; rebuild paced by predicted yaw (yaw + yaw accel/2), steering
   rate and steering added since the event began.
4. **Inside/outside rear lead** 0x5184C [C]: lateral-accel sign/magnitude picks the lead rear.
5. **Dump steps** are cut to ½ / ⅓ on the selected front above 0.5 / 0.8 g [C].

Steering reaches ABS directly: it gates the yaw-stable flag `0x408E5F` b4 (reset above ≈ 130° steering-wheel
angle), feeds the GMA pacing and the countersteer test, and its validity gates the rear cornering latch and
the ax-based vref fall.

**Negatives (exhaustively confirmed):**
- **Vehicle model (mass/l_f/l_r/Cf/Cr/Jz, loaders 0x5E424/0x5DE44) feeds ONLY DSC** — zero reads in the ABS
  region; no model→EBD/slip/pressure path. [C] Variant-0 models ~50/50 (l_f=l_r=1.38 m), understeer term
  Cr·l_r−Cf·l_f = +4.34e6 (yaw-stable), used only by the DSC yaw reference.
- **EBD (front/rear) is decel-driven, not model-based**: builder 0x47BDC, separate front 0x40412 / rear
  0x405F2 curves; rear references same-side front pressure. Always active.
- `abs_yaw_deviation_monitor` 0x4A254 (curve 0x40C5A) is the only possible model→ABS route and is **gated by
  AYC active** (flags 0x408DEA b6/7, 0x401FF2) ⇒ **inert with DSC off** [I]. The mechanisms above do not depend on it.

**Which sensors each mechanism needs (detail `09_chassis_sensor_use.md`).** A dead steering sensor (0x0C9) makes
lateral, yaw and steering all invalid, and then:
- the classifier straight shortcut (→ code 1, rears independent) and the lateral-curve code 32 / code 1 never run,
  so a controlling rear is always select-low (code 64);
- the rear cornering latch (needs lat + pressure + steering + yaw) never sets;
- `abs_rear_lead_select` is skipped; `abs_side_select` falls back to the rear wheel-speed difference;
- `abs_pair_logic` never leaves gate state 0, so the yaw-triggered µ-split codes 32 / 1024 / 16 are off;
- dump steps are not cut to ½ / ⅓ in corners; the front staged dump is not cancelled in corners;
- ax is never trusted (initial trust needs lateral, pressure and yaw-stable), so vref never takes its ax-based
  step, the decel estimate is not clamped to ax, and the decel-threshold g-term uses the wheel-derived estimate.
Unaffected: slip / decel thresholds, phase machine, dump / hold / reapply, EBD, front staged dump, low-µ coupling.

---

## 4. Pressure actuation & the COA P-V model

- **Wheel pressure is measured and closed-loop.** The firmware samples all **five** MK60E5 transducers:
  the master/input sensor (`pressure_adc_track` 0x8F344 → `0x401FF8` → driver pressure `0x404994`, 0.01 bar,
  200 bar clamp) and the **four wheel-output sensors** (fast SPI burst `sub_06FD90` → `sub_08FA00` →
  `0x402198[w]`; control getter `sub_091A50`). [C]
- **PM `0x4016E2[w]` = measured wheel pressure** in normal operation: `sub_082BC0` (inside
  `hydraulic_model_step` 0x82EF4) overwrites PM with the sensor value each 10 ms and re-syncs the model
  volume. The volume model (`valve_flow` 0x818B6: Q = isqrt(|dp|)·open·k/4096, COA compliance curve,
  `coa_vol_to_pressure` 0x819FE) supplies PM only while a wheel's outlet valve is dumping, or for all
  wheels when a wheel sensor is invalid / a pressure-sensor fault is latched. [C]
- ABS also reads the measured value directly: `sub_046ADC` filters it into `0x408E20 + 14·w`;
  `sub_055A84` keeps a 7-deep history; `abs_hold_entry_sync` and `abs_decision_resolve` call the getter.
  How those feed the decisions is [open]. CAN 0x2B2 bytes 0–3 broadcast PM (÷100 → bar). Detail:
  `analysis/agents/abs_full/06_pressure_sensors_recheck.md`.
- COA p-V table (0x41978): pressure axis 0x41B4E {0,4,7,10,15,20,30,60,120,327 bar}; front vol 0x41B62, rear
  0x41B8A. **COA bodies byte-identical to the 1M — NOT M3-retuned.** [C]
- Valve chain (`analysis/INLET_VALVE_CONTROL_7846816A.md`): mode 0x401AA8+8w = 1 hold / 2 build / 4 release
  from the sign of the request rate; build is a **metered inlet current** (feed-forward from the calibrated
  hold current and the brake compliance, G = 0x41A76=800 front / 0x41A78=350 rear, corrected every 5 ms on
  measured pressure); the outlet is open-loop timed. Dump rate −8000 and slew 0x584CC are pressure-level
  units. Pump = timer-PWM 0x88EC0. [C]
- **Owner's sluggish-brakes question — answered:** For ABS (pedal down, locking) the dominant loop is
  **measured slip + wheel-accel, closed every 10 ms**, robust to P-V error. An off P-V model degrades
  modulation precision/feel (feed-forward sizing, reapply granularity), **not braking authority**. Onset
  "softness" is set by the request rates and slew, not the P-V curve. An off P-V model only causes sluggish /
  overshooting build in **autonomous DSC/AYC/TCS build (no pedal)** or in sensor-fault fallback. [C/I]

---

## 5. Edge cases, failsafe & coding variants

- **Variants:** ABS has only two flavors — **0–9 (standard: M3 and Competition sedan/coupe/convertible, Custom ESM)**
  vs **10/11 (more permissive: GTS coupe / GTS sedan)**. Only the
  front speed-term (0x40412) and g-term (0x40674) families are variant-indexed (in builder 0x47BDC); 10/11
  differ only at high speed and raise the <60 km/h decel floor to −1.40 g ⇒ later/less-intrusive ABS at
  speed. Everything else (rear curve, entry-slip, decel scalars) is **global**. **M3 coded index is in EEPROM**
  (coding byte[1]&0x1F, setter 0x0CFDD8), default 0 after RAM clear — not in flash. [C]
- **µ-split / GMA**: `abs_pair_logic` 0x54D9A, only after `abs_pair_gate` 0x54B70 has left state 0 (needs a
  measured yaw rate past cal 0x40DD4 and the yaw-stable flag). Code 32 when the partner dumps; rebuild steps
  (+0.8 bar via code 1024 / cal 0x40D90, +3 bar via `abs_gma_hold_frames` pacing / cal 0x40DB0); restricted
  further while AYC yaw-deviation persists (0x408EA6 ≥ 15). [C] (`05_edge_cases_variants.md` §1)
- **Low-µ** = per-wheel deep-slip flags (byte 0x40902E + 3w, b1/b4, writer 0x4F9D4): set outside a cycle when
  lock-depth 0x409010 > 50 (cal 0x40D40) under braking (incl. > 70 bar, 0x40D42); b1 below 80 km/h, b4 from
  60 km/h. b1 sets the decel threshold to −1.30 g (−1.35 g with b4) without the 60 km/h floor. **No continuous µ
  estimator, no µ-indexed slip remap, no NVM µ-learning.** [C]
- **Rough-road suppressor** 0x5567C (cal 0x40D66..0x40D7E, not retuned vs 1M) blocks false triggering on vibration.
- **Standstill** 0x41CF2=72; ABS apply cut below 4 km/h (0x442AC). **ABS runs in reverse** (direction from wheel
  sensors; gear/CAN never gates ABS). [C]
- **BENCH UNIT:** a sensorless/partial unit does **NOT** degrade gracefully — zero wheel edges raise group-1
  plausibility faults → global inhibit 0x4009BC → clears master gate 0x401FF2 b7 → **ABS pipeline never arms.**
  ABS will not actuate without plausible wheel signals. [C]
- **Unmapped global cal to add to XDF:** 0x40C40, 0x40C5A, 0x40D24, 0x40D40(=50), 0x40D42(=7000),
  0x40DD2(=1748)+0x40DD8, rough-road 0x40D66..0x40D7E. (CPU addrs; file +0x8000.)

---

## 6. Tuning levers for a track car (synthesis)

Ranked by expected impact for a 1.3 g race-tire car braking at/near the grip limit:

1. **Code-32 cornering rear knock-down** — the mid-corner pressure cut: exec 0x58FF4
   max(1 bar, PM − pct·G/100) (`09_chassis_sensor_use.md` §2.1 item 7), pct from the driver pressure's position between the lateral-g curves
   **0x40E26** (P_lo) and **0x40E0A** (P_hi) (XDF "ABS cornering lat-g pressure term A / B"). Raising P_lo widens the light-pedal band
   with independent rears and no knock-down; raising P_hi lowers pct at a given pedal. Only active with working
   chassis sensors. [I direction]
2. **Request rates / slew** (reapply ramp cals 0x40D5E/0x40D60, step fraction 0x40D62/0x40D64, slew 0x584CC) —
   govern pressure-build *onset* feel ("bite"), independent of the P-V model.
3. **Decel-threshold floors & variant choice** — variants 10/11 (the GTS codings) already tolerate deeper wheel decel at speed
   (−1.40 vs −1.32 g <60 km/h); or edit the floors/speed-term directly.
4. **Gross-slip limit slope** (0xD6CE2 k=113 → ~130–150 ≈ 12.5–14.5 % of vref). Smallest gain — stock ~11 %
   is already near peak-µ for most race tires; only worth it on stiff slicks that peak late, and it trades
   lateral grip for longitudinal.
5. **The ~1.25 g estimation ceiling [I].** vref cannot fall faster than −44/frame (1.25 g; −49 on one branch);
   the ax byte (`0x4049FC`), lateral byte (`0x408ECA`) and decel estimate (`0x408DAF`) all saturate at ±1.27 g;
   the g-term input is byte-wide without ax trust and wraps above 1.27 g with it (the curve itself runs to
   1.83 g). A slick/aero car decelerating harder than that outruns vref, apparent slip
   grows and ABS over-releases. The error builds through the stop. Once it reaches the gross-slip limit, the car
   is held at ≈ 1.19 g for the rest of the stop: about +6 % distance at 1.5 g and +22 % at 1.8 g from 200 km/h
   (point-mass model; FACTS "Size of the effect"). These are code literals and byte-wide signals — a code patch, not a cal edit
   (`10_vref_and_ax.md` §5). Arguably the first thing to address on a high-grip car, ahead of 1–4.

**Not levers for ABS:** the vehicle model (mass/l_f/l_r/Cf/Cr/Jz) — DSC-only; the COA P-V tables — feel/
precision only, not authority (and 1M-identical, so not a known defect to "fix").

**Flashing reminder:** every cal edit changes the ROM MISR (re-sign site 0x4249C) + BMY signature → run
`tools/bmy_resign.py fix` before repack/flash. Bench unit only; experimental images must not go in a car.

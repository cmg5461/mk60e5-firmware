# MK60E5 7846816A (E9x M3) — Pressure actuation chain: command → valves, and is pressure closed-loop?

Scope: the actuation chain from an ABS pressure command to the hydraulic valves, and whether wheel
pressure is controlled closed-loop on sensors or open-loop on a modelled (P-V) estimate.
CPU addresses; file offset = CPU + 0x8000. Byte reads from `flash/bin/7846816A_00000000.bin`.
Confidence: **CONFIRMED** = read from bytes/listing here · **INFERRED** = read from code structure ·
**UNCONFIRMED** = not resolved.

---

## 0. Bottom line (answers the owner's concern)

**ABS wheel-pressure control in this firmware is NOT closed-loop on any wheel pressure sensor.** The
controller tracks each wheel's caliper pressure with an *internal volume-domain model* (fluid volume
integrated from valve open-times, converted to pressure by the COA pressure↔volume compliance curves).
The only *measured* pressure is the **master-cylinder / line pressure** on a single ADC channel; it enters
the model as the hydraulic **supply** pressure, not as a per-wheel feedback.

The dominant ABS regulation loop is **slip + wheel-acceleration** (the classic ABS loop), which is
measured and closed every 10 ms. Dump/hold/build *decisions* (when to act) come from that loop and are
**robust to P-V error**. The P-V model only governs *metering* (how much valve time per pulse, and what
caliper-pressure number the reapply/hold targets are compared against).

**Would an off P-V model make braking sluggish/soft?** For **ABS** (driver on the pedal, wheel locking):
mostly no — the slip loop still fires dumps on lock and re-applies on recovery regardless of P-V accuracy,
so braking won't "run away" or go persistently soft; a wrong P-V curve degrades *modulation precision/feel*
(pulses sized wrong → coarse or slightly laggy reapply, not loss of braking). For **DSC/AYC/TCS active
build** (no pedal, ECU building pressure autonomously): the P-V feedforward *is* the primary metering
against the measured line pressure, so an off model there would directly make autonomous pressure build
sluggish or overshoot. Keep the two cases distinct — see §6.

---

## 1. Valve driver outputs + pump (CONFIRMED structure, roles INFERRED)

Dispatcher slot 32 `hydraulic_actuation_pipeline` 0x843BC → `valve_pulse_sequencer` 0x853A8 builds a
**10-step current profile per wheel channel** each frame. Verified flow of 0x853A8:

- Front/rear split at `cmplti r2,2` (r2 = wheel 0..3). Per-wheel **start offset** loaded from COA:
  front `0x41A72` = **40**, rear `0x41A74` = **20** (bytes `00 28 / 00 14`, CONFIRMED). Base profile
  slots preloaded with hold/boost current literals (`125<<4`=2000, `125<<6`=8000 seen at 0x853BE/0x853C6).
- **Inlet mode byte** read at `0x401AA8 + 8*wheel` (0x85402): **1 = hold**, **2 = build**, **4 = release**
  (`cmpnei r7,1/2/4` at 0x8540E..0x85418). Mode written by `inlet_mode_select` 0x84460 (INFERRED: from
  sign of pressure error).
  - **Hold (1)** 0x8541C: 10-step profile held at the last value, clamped to `0x604`=**1540**
    (literal `0x5F4`=1524 fallback).
  - **Build (2)** 0x854AC: computes pressure error = supply − modelled PM, interpolates the COA p-V curve
    (front coding `0x4031AA+3`/table `0x41B62`, rear `+4`/`0x41B8A`, shared pressure axis `0x41B4E`) and
    scales by the **build gain** front `0x41A76`=**800**, rear `0x41A78`=**350** (bytes `03 20 / 01 5E`,
    CONFIRMED). Result → number of valve-open steps (`r14`, clamped 0..10 at 0x856C8).
  - **Release (4)** 0x857B8: profile forced to dump current `0x5FC`=**1532** (clamp `0x604`=1540), counters
    reset, modelled pressure snapshotted to `0x401C08`.
- A per-wheel temperature/compensation value is read at `0x401FF7` (byte, sign-extended, clamped to
  [−30,+100]) and folded into the profile (0x853E6..0x85402). (INFERRED: valve-current temp comp.)

**Output stages (INFERRED from CS usage, per existing symbols):** 12 solenoid channels (mask table
0xD7634; actuator-test order 0xF2EF0 = [0,4,1,5,2,6,3,7,8,9,10,11]). ch0-3 = inlet (analog current via
ASIC CS5 `asic_reg_xfer32` 0xD4A30, cmd 0xFA), ch4-7 = outlet/dump (digital latch via CS4
`spi_cs4_out16` 0xD4BF4, cmd 0xFB), ch8-11 = USV/HSV circuit isolation valves.

**Pump motor** `pump_motor_control` 0x88EC0: reads cal `0x419D4`/`0x419D8`/`0x419DA` = **0 / 100 / 50**
(byte-verified, plus `0x419D6`=5) and a commanded level, drives a **timer-PWM** on module 0xF80000
(`pump_motor_set_level` 0x73250 ≈ 4000 ticks/level, ISR 0x70314). Pump is **not** on SPI. (Roles med.)

---

## 2. Pressure sensors — how many are MEASURED, their scale (CONFIRMED)

**Firmware reads exactly ONE pressure sensor: the master-cylinder / front line pressure.** No per-wheel
pressure acquisition exists in the control path.

- Acquisition `pressure_adc_track` 0x8F344 reads **MCU ADC channel 21** (primary) and **channel 6**
  (companion/redundant rail) via the 59-entry ADC jump table `adc_read` 0x6FB30 (`movi r2,21` / `movi r2,6`
  at 0x8F34C/0x8F350, CONFIRMED). Scale: `p = adc * 0x5EE8 / 0xFFC0` then offset (0x5EE8=24296,
  0xFFC0=65472 → ×0.371; offsets `0x556A`=21866 / `0x97D`=2429). Dual-track ratiometric with a 113/128
  low-pass blend of the two elements (0x8F3B2) — characteristic of one safety-grade MC pressure sensor,
  not four independent caliper sensors.
- Result stored as master pressure **`0x404994`** (also written by `driver_pressure_from_sensor` 0x8CE8E
  from pointer table `0x40171A`). Compared directly against modelled caliper pressures and clamped to
  `0x4E20`=**20000** in `supply_pressure` — so its unit is the same **~0.01 bar** domain (20000 = 200 bar).
- A sweep of every `adc_read` call site shows pressure-related reads only on **ch21** (+ch6); channels
  0/1/2 at 0xB1A06 are the KWP diagnostic supply-rail reads, not caliper pressures (CONFIRMED by context —
  that block is in the kwp 0x21 handler region writing 0x409435/0x409489).

**Owner's "4 wheel pressure sensors":** whatever the hardware carries, **this firmware does not sample or
use any per-wheel pressure signal for control.** The per-wheel "pressure" the controller works with is the
*modelled* value `0x4016E2[ch]` (see §3) — it is written only by the volume→pressure model and the ABS
pressure bookkeeping, never by an ADC/ASIC sensor read. (CONFIRMED: `0x4016E2` writers are all in the COA
model, abs_pm, and AYC code; none is a sensor-acquisition routine.)

---

## 3. The P-V feedforward model — what it computes, and the (absent) closed-loop trim

**It is a volume-domain estimator**, run as dispatcher slot 8 `hydraulic_model_step` 0x82EF4 (10 ms):

1. `valve_flow(dp, k, open)` 0x818B6: **Q = isqrt(|dp|) · open · k / 4096**, clamp ≤ 2000. `isqrt` via
   0x71172; `dp` and `k` supplied by the caller. (CONFIRMED arithmetic.)
2. `wheel_volume_delta` 0x8216E computes `dp = supply_pressure − modelled caliper pressure` per wheel and
   calls valve_flow with the inlet/outlet flow coefficient `k`.
3. `circuit_volume_update` 0x826C0: `V[w] += dV`, routes dumped fluid to the low-pressure accumulator,
   clamps `V ≤ 30000`. Volume RAM `0x4016DA[w]`.
4. `coa_vol_to_pressure(w)` 0x819FE: **PM `0x4016E2[w]` = P(V)**, the *inverse* compliance curve lookup —
   this is the modelled caliper pressure the whole controller consumes.

`supply_pressure(w)` 0x84D42 (CONFIRMED): `supply = max(partner-wheel modelled PM, measured master
`0x404994`)`, clamp [.,20000]. **So the one measured pressure (line) sets the driving head `dp`; the
caliper pressure itself is never measured and never corrected by a sensor.** This is an **open-loop
estimator seeded by the measured supply pressure** — there is **no caliper-pressure closed-loop trim**.

### Decoded COA p-V table (CONFIRMED bytes, COA block 0x41978)

Shared **pressure axis** `0x41B4E` (10 pts, unit 0.01 bar):

| idx | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| P (0.01 bar) | 0 | 400 | 700 | 1000 | 1500 | 2000 | 3000 | 6000 | 12000 | 32700 |
| = bar | 0 | 4 | 7 | 10 | 15 | 20 | 30 | 60 | 120 | 327 |

**Front caliper, brake-code 0** volume set `0x41B62`:
`{0, 1600, 2200, 2650, 3300, 3900, 5050, 8150, 13300, 31200}` (model volume units).
Front code 1 `0x41B76` `{0,1600,2150,2600,3250,3800,4950,8150,14000,32750}`.
**Rear code 0** `0x41B8A` `{0,1000,1500,1850,2350,2750,3400,5050,7850,17550}`;
rear code 1 `0x41B9E` `{0,900,1350,1650,2100,2500,3250,5400,9250,22550}`.

Reading front code 0: raising front pressure 0→4 bar swallows ~1600 volume units (pad/caliper take-up, the
soft "dead" region), 0→10 bar needs 2650, 0→20 bar 3900, 0→60 bar 8150, 0→120 bar 13300. `coa_vol_to_pressure`
interpolates P from accumulated V on this curve; `coa_pressure_to_vol` 0x816E8 is the forward direction used
to pre-size build pulses. Flow coefficients (k_in/k_out, front/rear) and the LPA tables live in the same COA
block and are in the XDF. Bodies are **byte-identical to the 1M 7846411A** — not retuned for M3.

**How measured pressure corrects the feedforward:** only through the `supply` term (measured line pressure
as the source head for `dp`). The caliper estimate is self-consistent model state; a divergence between
modelled and real caliper pressure is **not** detected or trimmed by this firmware.

---

## 4. Pulse timing & slew limiting (CONFIRMED values)

- **Build:** valve-open step count = f(pressure error, COA p-V) × build gain (front 800 / rear 350), 0..10
  steps per 10 ms frame. So build is **pressure-gradient / P-V based**, not a fixed pulse width.
- **Dump:** release forces dump current, with the *amount* set upstream by `abs_dump_stage` 0x5424C →
  `abs_dump_entry_target` 0x55F06: target = `max(LOCKEST − R, 0)`, R from the staged ladder (−10/−15/−20 bar
  of lock-onset pressure), emitted at rate literal **−8000** (max dump rate, hard-coded).
- **Reapply/apply ramp** `abs_apply_ramp` 0x443F4: CMD **+400/frame** (cal ABS+0x0C), cap 25000; small nudges.
- **Slew limiter** `abs_cmd_slew_limiter` 0x584CC: `CMD=min(CMD,TGT); RAMP=min(RAMP, CMD−SNAP)` — this is
  the onset rate limit that shapes how fast commanded pressure can move. Expressed in **pressure-level
  units**, so it is *independent of P-V accuracy*. **Onset "softness" is set by these ramp/slew constants,
  not by the P-V model.** (All CONFIRMED against the listing / existing byte-verified symbols.)

---

## 5. EBD / front-rear & per-wheel distribution (CONFIRMED location)

No standalone EBD module; EBD-like rear limiting is folded into the same ABS controller:

- `abs_rear_lead_select` 0x5184C: rear-axle **select-low** behavior; a rear wheel's pressure reference is
  the **same-side front wheel's modelled pressure** (per ABS_ALGORITHM §5). Rear reapply uses arbiter
  **id 11** (rear-only; loses priority to the driver's master-cylinder id 0).
- `abs_pair_logic` 0x54D9A pairs front(0,1)/rear(2,3), runs the axle-pair S0..S3 cycle, and a cornering
  clause (lateral-accel term) relaxes rear pressure in corners.
- Distribution is therefore **model-pressure-referenced** (rear target derived from modelled front
  pressure), reinforcing that the whole per-wheel pressure picture is the model, not sensors.

---

## 6. Direct answer: closed-loop vs feedforward (the owner's concern)

| | ABS (pedal down, wheel locking) | DSC/AYC/TCS active build (no pedal) |
|---|---|---|
| Decision loop | **Slip + wheel accel, measured, closed** | Yaw/slip error, measured, closed |
| Pressure metering | Target pressure-level + P-V-sized pulses | **P-V feedforward vs measured line pressure** |
| Caliper pressure feedback | **None** (modelled) | **None** (modelled) |
| Effect of wrong P-V | Pulses mis-sized → coarse/soft *feel*, slip loop still arrests lock | Direct: build sluggish or overshoots |

- There is **no caliper pressure sensor feedback** in either case — wheel pressure is always the volume
  model. The single measured pressure (master/line, ADC ch21) is dominant only as the **supply head**.
- For **ABS**, the measured **slip loop** is dominant, so an inaccurate P-V model would **not** make ABS
  braking persistently sluggish; it degrades modulation precision/feel (reapply granularity, pulse sizing).
- For **autonomous DSC build**, the P-V feedforward *is* the metering authority, so an off P-V model there
  would plausibly make active pressure build feel sluggish or grabby — but that is DSC active-build, a
  different function from driver-braking ABS.
- Note COA bodies are byte-identical to the 1M image (not a M3-specific mis-tune); brake-code selects only
  code 0 vs 1 per axle.

## 7. Open / unconfirmed
- `inlet_mode_select` 0x84460 exact predicate (hold vs build vs release thresholds) — INFERRED from error sign.
- ch6's exact role vs ch21 (redundant element vs reference) — INFERRED.
- Absolute truth of the 0.01-bar unit — self-consistent across axis (327 bar max), supply clamp (200 bar),
  and pedal values, but not proven against a gauge (needs a bench pressure trace).
- Whether the hardware actually has 4 caliper sensors is irrelevant to control: firmware samples none.

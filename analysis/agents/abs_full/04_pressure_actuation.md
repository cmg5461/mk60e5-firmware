# MK60E5 7846816A (E9x M3) — Pressure actuation chain: command → valves, and is pressure closed-loop?

Scope: the actuation chain from an ABS pressure command to the hydraulic valves, and how wheel pressure
is fed back (measured wheel-output sensors, with the COA P-V model as feed-forward and fallback).
CPU addresses; file offset = CPU + 0x8000. Byte reads from `flash/bin/7846816A_00000000.bin`.
Confidence: **CONFIRMED** = read from bytes/listing here · **INFERRED** = read from code structure ·
**UNCONFIRMED** = not resolved.

---

## 0. Bottom line

**Wheel pressure is closed-loop on measured pressure.** The MK60E5 has a pressure transducer on each of
the four wheel outputs plus one on the master/input side, and the firmware uses all five. Each 10 ms
frame the per-wheel pressure PM `0x4016E2[w]` is overwritten with the measured wheel-output pressure
`0x402198[w]`, and the internal volume model is re-synchronised to it (`sub_082BC0`, §3). Everything
downstream — the valve sequencer's pressure error, ABS PM `0x408F2A`, `supply_pressure`, CAN 0x2B2 — works
from that measured value.

The **volume-domain model** (fluid volume integrated from valve open-times, converted to pressure by the
COA pressure↔volume compliance curves) has two jobs: **feed-forward** (the brake compliance term in the
reapply current, and the outlet dump time) and **fallback** (supplying PM while a wheel's outlet valve is dumping, and
whenever the wheel sensors are faulted or invalid).

The dominant ABS regulation loop is still **slip + wheel-acceleration**, measured and closed every 10 ms.
Dump/hold/build *decisions* come from that loop; pressure feedback governs *metering*.

**Would an off P-V model make braking sluggish/soft?** With healthy sensors, little: a wrong curve
mis-sizes the feed-forward current or dump time, and the measured pressure corrects the error (the 5 ms
inlet loop's learned offset, and PM re-sync each frame). It matters
during dump phases (PM is modelled until the inlet side is active again) and matters fully in sensor-fault
fallback, where the model is the only wheel-pressure source. Onset "bite" is set by the apply-ramp/slew
constants (§4), not the P-V curve. See §6.

---

## 1. Valve driver outputs + pump (CONFIRMED structure, roles INFERRED)

Full decode of the inlet side: `analysis/INLET_VALVE_CONTROL_7846816A.md`. Fluid model, LPA and pump (supersedes the loose
pump/accumulator notes below): `analysis/HYDRAULIC_MODEL_7846816A.md`. Three rates:

- **10 ms** — dispatcher slot 32 `hydraulic_actuation_pipeline` 0x843BC → `inlet_mode_select` 0x84460 and
  `valve_pulse_sequencer` 0x853A8. The mode byte at `0x401AA8 + 8*wheel` comes from the sign of the
  arbitrated request rate: **1 = hold** (rate 0), **2 = build** (> 0), **4 = release** (< 0). For build the
  sequencer computes a feed-forward current `I_build` = the valve's calibrated hold current for the present
  Δp (supply − PM), lowered by up to 40 % (front) / 20 % (rear) (COA `0x41A72` = 40 / `0x41A74` = 20) in
  proportion to the requested rate over `D = C·Δp/(G + temp)`, where C is the brake compliance from the COA
  p-V curve and **G** = COA `0x41A76` = **800** front / `0x41A78` = **350** rear (bytes `03 20 / 01 5E`,
  CONFIRMED); temp = byte `0x401FF7`, clamped [−30, +100]. Rate 9000 (full build) instead opens the inlet
  fully for a counted number of steps.
- **5 ms** — `inlet_fast_loop` 0x85282 closes the loop on the measured wheel pressure: a setpoint ramps
  toward the target at the requested rate (1–6 bar/frame), and the build current `I_build − learn` adapts
  `learn` when the pressure lags or overshoots the ramp. Hold and release keep the inlet closed: peak
  1524 mA (hold) / 1532 mA (release) for two half-frames, then 1100 mA hold-in. Release also snapshots PM
  to `0x401C08`.
- **1 ms** — `valve_output_1ms` 0x741F4 clocks one of 10 steps per wheel to the valve ASIC.

So reapply is a **proportional (partly energised) inlet**, not a count of open/closed pulses. The outlet
side is open-loop timed: `outlet_dump_time_calc` 0x85A42 books outlet-open time from the p-V volume
difference and orifice flow.

**Output stages (INFERRED from CS usage, per existing symbols):** 12 solenoid channels (mask table
0xD7634; actuator-test order 0xF2EF0 = [0,4,1,5,2,6,3,7,8,9,10,11]). ch0-3 = inlet (analog current via
ASIC CS5 `asic_reg_xfer32` 0xD4A30, cmd 0xFA), ch4-7 = outlet/dump (digital latch via CS4
`spi_cs4_out16` 0xD4BF4, cmd 0xFB), ch8-11 = USV/HSV circuit isolation valves.

**Pump motor** `pump_motor_control` 0x88EC0: reads cal `0x419D4`/`0x419D8`/`0x419DA` = **0 / 100 / 50**
(byte-verified, plus `0x419D6`=5) and a commanded level, drives a **timer-PWM** on module 0xF80000
(`pump_motor_set_level` 0x73250 ≈ 4000 ticks/level, ISR 0x70314). Pump is **not** on SPI. (Roles med.)

---

## 2. Pressure sensors — five measured (CONFIRMED)

Full acquisition detail: `06_pressure_sensors_recheck.md`.

- **Master / input sensor:** `pressure_adc_track` 0x8F344 conditions the dual-element sensor (ASIC
  channels 6 / 7; scale `adc * 0x5EE8 / 0xFFC0` ≈ ×0.371, offsets `0x556A` / `0x97D`, 113/128 low-pass
  blend) into the validated value `0x401FF8`. `dispatch_slot00_driver_pressure` 0x8CE5E commits it as
  driver pressure **`0x404994`**; if the master sensor is invalid it falls back to the mean of the valid
  wheel pressures (`sub_08CDC4` → `0x404996`), then to a modelled circuit pressure `0x40171A`.
  `0x404994` is clamped to `0x4E20` = 20000 in `supply_pressure`, i.e. the **0.01 bar** domain
  (20000 = 200 bar).
- **Four wheel-output sensors:** sampled several times per frame by the fast SPI burst `sub_06FD90` →
  `sub_08FA00` (zero-offset corrected, 4-sample average) into **`0x402198[w]`** `{value, flags}`, same
  0.01 bar unit. Each has a redundant second element used for plausibility. Control reads them through
  getter `sub_091A50(w)` (valid bit in r2).
- (`adc_read(21)` at 0x8F34C returns a constant stub and is discarded; channel 21 is not a sensor.)

---

## 3. The P-V model and the measured-pressure selector

**The model is a volume-domain estimator**, run as dispatcher slot 8 `hydraulic_model_step` 0x82EF4 (10 ms):

1. `valve_flow(dp, k, open)` 0x818B6: **Q = isqrt(|dp|) · open · k / 4096**, clamp ≤ 2000. `isqrt` via
   0x71172; `dp` and `k` supplied by the caller. (CONFIRMED arithmetic.)
2. `wheel_volume_delta` 0x8216E computes `dp = supply_pressure − PM` per wheel and calls valve_flow with
   the inlet/outlet flow coefficient `k`.
3. `circuit_volume_update` 0x826C0: `V[w] += dV`, routes dumped fluid to the low-pressure accumulator,
   clamps `V ≤ 30000`. Volume RAM `0x4016DA[w]`.
4. **`sub_082BC0` (0x82F36) selects PM `0x4016E2[w]`** (CONFIRMED):
   - **normal:** `PM = measured 0x402198[w]`, then `coa_pressure_to_vol(w)` 0x816E8 rewrites `V[w]` from
     it, so the model restarts from the measurement every frame;
   - **outlet/dump active** (valve state `0x401A16[w]` negative, latched in `0x401715[w]` until the state
     goes positive): `PM = coa_vol_to_pressure(w)` 0x819FE, the inverse compliance lookup P(V). On the
     first frame back, the volume discrepancy is pushed into the circuit accumulator `0x4016F2[c]`;
   - **inlet fully open (state 20) with recent pump flow in the circuit:** `PM = min(model, measured)`;
   - **sensors unusable** (`0x402888` b5, any of fault ids 35/57/59/61/63 `<<15`, or any one of the four
     sensors invalid): `PM = coa_vol_to_pressure(w)` for all wheels.

`supply_pressure(w)` 0x84D42 (CONFIRMED): `supply = max(partner-wheel PM, driver pressure 0x404994)`,
clamp [.,20000]. Both terms are measured in normal operation.

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

**How measured pressure corrects the feedforward:** directly — PM is replaced by the measured wheel
pressure and the volume state is recomputed from it each frame the inlet side is active. A divergence
between model and reality persists only within a dump phase or in sensor-fault fallback.

---

## 4. Pulse timing & slew limiting (CONFIRMED values)

- **Build:** metered inlet current (§1), feed-forward from the calibrated hold current and the compliance,
  corrected every 5 ms on measured pressure. The requested rate is clamped to 1–6 bar/frame in the fast loop.
- **Dump:** the *amount* is set upstream by `abs_dump_entry_target` 0x55F06 (entry: lock pressure minus
  R ≈ 8 % of it plus decel terms, capped at wheel pressure − `0x401D00[w]`) and the later dump stages
  (`08_phase_control.md` §5.2–5.3), emitted at rate literal **−8000** (max dump rate, hard-coded). The outlet
  time to reach it is booked by `outlet_dump_time_calc`.
- **ABS reapply:** a staircase of steps sized from the dump depth, ramped at cal 0x40D5E = 3 bar/frame (front)
  / 0x40D60 = 5 bar/frame (rear) with a 7-frame wait (`08_phase_control.md` §5.4).
- **Apply ramp** `abs_apply_ramp` 0x443F4 (request id 19): CMD **+400/frame**, cap 25000; dropped below 4 km/h.
- **Slew limiter** `abs_cmd_slew_limiter` 0x584CC: `CMD=min(CMD,TGT); RAMP=min(RAMP, CMD−SNAP)` — this is
  the onset rate limit that shapes how fast commanded pressure can move. Expressed in **pressure-level
  units**, so it is *independent of P-V accuracy*. **Onset "softness" is set by these ramp/slew constants,
  not by the P-V model.** (All CONFIRMED against the listing / existing byte-verified symbols.)

---

## 5. EBD / front-rear & per-wheel distribution (CONFIRMED location)

No standalone EBD module; EBD-like rear limiting is folded into the same ABS controller:

- `abs_rear_lead_select` 0x5184C: rear-axle **select-low** behavior; a rear wheel's pressure reference is
  the **same-side front wheel's pressure PM** (per ABS_ALGORITHM §5). Rear reapply uses arbiter
  **id 11** (rear-only; loses priority to the driver's master-cylinder id 0).
- With valid lateral, the lead rear follows the lateral sign and the classifier's lateral-g curves
  switch the rears between independent and select-low / knock-down (`03_lateral_g_influence.md` §2).
  `abs_pair_logic` 0x54D9A is µ-split yaw-moment limiting, active only after a yaw kick.
- Distribution is therefore **referenced to front wheel pressure PM**, which is the measured front
  output pressure in normal operation.

---

## 6. Closed-loop vs feed-forward, by case

| | ABS (pedal down, wheel locking) | DSC/AYC/TCS active build (no pedal) |
|---|---|---|
| Decision loop | **Slip + wheel accel, measured, closed** | Yaw/slip error, measured, closed |
| Pressure metering | Target pressure + rate; metered inlet current, timed outlet | Same, toward the requested pressure |
| Wheel pressure feedback | **Measured** (model during dump phases) | **Measured** |
| Effect of wrong P-V | Feed-forward off until the 5 ms loop corrects it; dump-phase estimate off until re-sync | Feed-forward off until corrected |
| Sensor-fault fallback | Pure volume model: P-V error accumulates | Pure volume model: build sluggish or overshoots |

- With healthy sensors the P-V curves are a feed-forward term inside a measured-pressure loop; they
  affect modulation granularity, not braking authority.
- With the wheel sensors faulted or unplugged (e.g. bench unit), PM, CAN 0x2B2 and all metering run on
  the model alone, seeded by driver pressure as the supply head.
- COA bodies are byte-identical to the 1M image (not M3-retuned); brake-code selects only code 0 vs 1
  per axle.


## 7. Open / unconfirmed
- How each ABS routine that reads the measured wheel pressure (`sub_046ADC` filters `0x408E20+14w`,
  `abs_hold_entry_sync`, `abs_decision_resolve`) uses it in its decisions.

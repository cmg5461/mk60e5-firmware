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
COA pressure↔volume compliance curves) has two jobs: **feed-forward** (sizing how many valve-open steps a
given pressure error needs) and **fallback** (supplying PM while a wheel's outlet valve is dumping, and
whenever the wheel sensors are faulted or invalid).

The dominant ABS regulation loop is still **slip + wheel-acceleration**, measured and closed every 10 ms.
Dump/hold/build *decisions* come from that loop; pressure feedback governs *metering*.

**Would an off P-V model make braking sluggish/soft?** With healthy sensors, little: a wrong curve
mis-sizes an individual pulse, and the measured pressure corrects the error on the next frame. It matters
during dump phases (PM is modelled until the inlet side is active again) and matters fully in sensor-fault
fallback, where the model is the only wheel-pressure source. Onset "bite" is set by the apply-ramp/slew
constants (§4), not the P-V curve. See §6.

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
  - **Build (2)** 0x854AC: computes pressure error = supply − PM (measured wheel pressure, §3), interpolates the COA p-V curve
    (front coding `0x4031AA+3`/table `0x41B62`, rear `+4`/`0x41B8A`, shared pressure axis `0x41B4E`) and
    scales by the **build gain** front `0x41A76`=**800**, rear `0x41A78`=**350** (bytes `03 20 / 01 5E`,
    CONFIRMED). Result → number of valve-open steps (`r14`, clamped 0..10 at 0x856C8).
  - **Release (4)** 0x857B8: profile forced to dump current `0x5FC`=**1532** (clamp `0x604`=1540), counters
    reset, PM snapshotted to `0x401C08`.
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

- **Build:** valve-open step count = f(pressure error vs measured PM, COA p-V) × build gain (front 800 / rear 350), 0..10
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
  the **same-side front wheel's pressure PM** (per ABS_ALGORITHM §5). Rear reapply uses arbiter
  **id 11** (rear-only; loses priority to the driver's master-cylinder id 0).
- `abs_pair_logic` 0x54D9A pairs front(0,1)/rear(2,3), runs the axle-pair S0..S3 cycle, and a cornering
  clause (lateral-accel term) relaxes rear pressure in corners.
- Distribution is therefore **referenced to front wheel pressure PM**, which is the measured front
  output pressure in normal operation.

---

## 6. Closed-loop vs feed-forward, by case

| | ABS (pedal down, wheel locking) | DSC/AYC/TCS active build (no pedal) |
|---|---|---|
| Decision loop | **Slip + wheel accel, measured, closed** | Yaw/slip error, measured, closed |
| Pressure metering | Target pressure-level + P-V-sized pulses | P-V-sized pulses toward the requested pressure |
| Wheel pressure feedback | **Measured** (model during dump phases) | **Measured** |
| Effect of wrong P-V | Pulse mis-sized for one frame; dump-phase estimate off until re-sync | Pulse mis-sized for one frame |
| Sensor-fault fallback | Pure volume model: P-V error accumulates | Pure volume model: build sluggish or overshoots |

- With healthy sensors the P-V curves are a feed-forward term inside a measured-pressure loop; they
  affect modulation granularity, not braking authority.
- With the wheel sensors faulted or unplugged (e.g. bench unit), PM, CAN 0x2B2 and all metering run on
  the model alone, seeded by driver pressure as the supply head.
- COA bodies are byte-identical to the 1M image (not M3-retuned); brake-code selects only code 0 vs 1
  per axle.


## 7. Open / unconfirmed
- `inlet_mode_select` 0x84460 exact predicate (hold vs build vs release thresholds) — INFERRED from error sign.
- How each ABS routine that reads the measured wheel pressure (`sub_046ADC` filters `0x408E20+14w`,
  `abs_hold_entry_sync`, `abs_decision_resolve`) uses it in its decisions.

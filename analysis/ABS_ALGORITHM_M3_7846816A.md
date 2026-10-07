# MK60E5 ABS algorithm — M3 7846816A (full characterization)

Consolidated from five parallel agent passes (2026-10-05), each byte-verified against
`flash/bin/7846816A_00000000.bin`. Per-domain detail lives in `analysis/agents/abs_full/`:

| # | File | Domain |
|---|------|--------|
| 1 | `01_core_slip_loop.md`      | vref, slip, entry/gross-slip thresholds, phase machine |
| 2 | `02_decel_threshold.md`     | wheel-decel trigger, effective threshold formula |
| 3 | `03_lateral_g_influence.md` | lateral-g / yaw effect on ABS (vs DSC) |
| 4 | `04_pressure_actuation.md`  | valve chain, pressure sensing, COA P-V model |
| 5 | `05_edge_cases_variants.md` | µ-split/GMA, µ-flag, rough-road, failsafe, variants |

**Conventions:** CPU addresses below; **file offset = CPU + 0x8000 = XDF address**. Frame = 10 ms.
Units: speed/slip **0.01 km/h**, decel/accel **0.01 g**, pressure **~0.01 bar** (self-consistent,
needs a bench gauge trace to prove absolute scale). Tags: **[C]** confirmed from bytes/listing,
**[I]** inferred, **[open]** unresolved.

This is a *superset* of the 1M doc (`ABS_ALGORITHM.md`); core architecture matches opcode-for-opcode,
but RAM/cal addresses differ (M3 vref 0x408DA8 vs 1M 0x408D84, etc.).

---

## 0. The two intervention triggers (the headline)

ABS fires a wheel on **either** of two independent triggers, interlocked in the per-wheel phase machine:

1. **Slip trigger** — plain slip *speed* `slip = vref − wheelspeed` (0.01 km/h, **not a ratio**):
   - **Entry gate** curve 0x40DB6: ~**1.5 km/h** at rest, dips to 1.29 @50, rises to 2.02 @300 km/h. Arms ABS. 2-frame debounce (0x40DB4). [C]
   - **Gross-slip arming limit** curve 0xD6CE2: 4.0 km/h @0, flat ~**6 km/h** over 20–55 km/h, then slope **113/1024 = 11.04 % of vref** above 55 (10.9 @100, 22 @200 km/h). The deep lock-plausibility threshold. [C]
   - (A separate slip *ratio* signal 0x408F84 = (vref−wheel)·10000/vref exists but is downstream telemetry, not the gate.)
2. **Decel-rate trigger** — a wheel's filtered deceleration crossing a speed- and g-dependent threshold (§2).

Recovery (spin-up) uses a **positive** wheel-accel threshold to end a dump and rebuild.

---

## 1. Core loop (agent 1)

- **vref** `vref_update` 0x449D0 → **0x408DA8**: rate-limited integrator, **not** pure max-select. Rises toward fastest front capped +44/frame (+1.25 g), +22 in-ABS, +282 snap; during ABS falls **decel-limited**, capped −44/frame; floor ~0.62 km/h. [C]
- Per wheel: `slip = vref − wheelspeed`; `abs_event_classifier` 0x04D270 builds thresholds + emits an event word → per-wheel **phase machine** `abs_phase_sm` 0x04FC3C → dispatch 0x0504D0 → handlers write commanded pressure → arbiter (ABS id 1, rear 11, reapply 19).
- **Pair logic** `abs_pair_logic` 0x54D9A: per-**axle** (fronts 0/1, rears 2/3), **rear select-low** (lead rear via 0x05184C); rears add a cornering/lateral clause (0x54BE8, lateral vs cal 0x40DD2 = 1748); rear reference = same-side front pressure. [C]
- **Phase machine** (rec[0] bits, table 0x40BF00 + 0x40·wheel): `0x80 armed → 0x21 DUMP → 0x09 HOLD → 0x11 REAPPLY/BUILD → 0x15`; pre-control 0xC0, rear-overspeed 0x84.
  - **DUMP**: staged on filtered wheel decel {−62,−78,−94} ≈ −9.9/−12.5/−15 g (set A) or {−25,−44,−62} (set B); target = lock-onset pressure 0x408FD0 − {10,15,20} bar, floor 20 bar, ramp −8000.
  - **HOLD**: pressure held, rate 0.
  - **BUILD**: `cmd = min(cmd+400, 25000)` per frame; gated off below ~4 km/h.
- **Exit**: slip recovers → rec[0]→0x80; low speed (~4 km/h)/standstill → no new arm.

---

## 2. Decel-rate trigger (agent 2)

- `wheel_accel_update` 0x0D20DC: wheel accel = two-frame mean of (Δwheelspeed × **2.8332**), 2.8332 = 58023/20480 (literal 0xE287). **Unit = 0.01 g** proven (1 count Δv/frame = 0.028332 g ≈ physical). [C]
- **Effective dump threshold** (0.01 g, negative), builder `abs_decel_threshold_builder` 0x047BDC → 0x4090E6[wheel]:

```
thr = base(−1.16 g) − speed_term(vref) − g_term(|vehicle decel|)
      thr = max(thr, −2.40 g)                 # absolute floor 0x4861E
      if vref < 60 km/h: thr = max(thr, −1.32 g)   # floor table 0x4865C (var10/11: −1.40)
      if vref < 20 km/h: thr = max(thr, −1.27 g)   # floor table 0x48644
      if |wheel_accel| < 0.15 g: thr = −0.99 g
      front wheels also: thr −= clamp(ΔPM/300, ≥8)
Dump when wheel filtered decel < thr.
```

- **speed_term** front var0 (0x48412): deepens threshold with speed → 0@0, 0.09 g@100, 0.28 g@200, 0.74 g@300 km/h. Rear single 0x45DF2 similar.
- **g_term** var0 (0x48674): deepens with current decel → 0 below 0.3 g, 0.10 g@0.6, 0.36 g@1.0, 0.60 g@1.27 g.
- Worked points: 100 km/h @1.0 g → −1.61 g; 300 km/h → −2.26 g; 50 km/h → −1.32 g (floor60); 15 km/h → −1.27 g (floor20).
- **Re-apply**: positive spin-up threshold, +0.63 g idle / +2.85 g (or +1.30 g) in-cycle; crossing ends dump, starts rebuild.

---

## 3. Lateral g / yaw affects ABS — YES (agent 3)

Runs **inside the ABS controller**, independent of DSC, and **active in ABS-only**. The ABS block has its
own sensor gather (~0x5D8xx) latching lateral accel → **0x408ECA**, yaw → 0x408ECC, yaw accel → 0x408ECE.

1. **Code-32 cornering handling (decision code 32)** [C]: `abs_decision_classify` 0x51B54 reads |ay| (byte
   0x408ECA) → `abs_decision_pressure_exec` 0x58FF4 (code-32 @0x59222). **The exec REDUCES commanded pressure**
   `CMD = PM − pct·(LOCKEST−CMD)/100` via pct byte 0x408DE0 (producer untraced) + rear select-low ⇒ trail-
   braking at the lateral limit gets *less* rear ABS pressure. **CORRECTION (2026-10-05):** the ABS cal
   curves **0x40E0A/0x40E26** are NOT this knockdown — they are a lateral-g PRESSURE term (x=|ay| ~0.01 g/ct,
   output ×100 → 0.01 bar) that *RISES* with g (26→49 / 14→40 bar); separate regs, role (ceiling/reference)
   UNCONFIRMED. Earlier "curves scale pressure down / 0–100 % factor" was wrong on direction.
2. **Pair-logic cornering gate** 0x54D9A [C]: predicted yaw = yaw + yaw_accel/2 gates the axle-pair cycle.
3. **Inside/outside rear select-low bias** 0x5184C [C]: lateral-accel sign/magnitude picks the lead rear.

**Negatives (exhaustively confirmed):**
- **Steering angle never reaches ABS** — DSC/CSI yaw reference only. [C]
- **Vehicle model (mass/l_f/l_r/Cf/Cr/Jz, loaders 0x5E424/0x5DE44) feeds ONLY DSC** — zero reads in the ABS
  region; no model→EBD/slip/pressure path. [C] Variant-0 models ~50/50 (l_f=l_r=1.38 m), understeer term
  Cr·l_r−Cf·l_f = +4.34e6 (yaw-stable), used only by the DSC yaw reference.
- **EBD (front/rear) is decel-driven, not model-based**: builder 0x47BDC, separate front 0x40412 / rear
  0x405F2 curves; rear references same-side front pressure. Always active.
- `abs_yaw_deviation_monitor` 0x4A254 (curve 0x40C5A) is the only possible model→ABS route and is **gated by
  AYC active** (flags 0x408DEA b6/7, 0x401FF2) ⇒ **inert with DSC off** [I]. The three mechanisms above do not depend on it.

---

## 4. Pressure actuation & the COA P-V model (agent 4)

> **✔ RE-INVESTIGATION RESOLVED (2026-10-05) — the "one sensor" count below is WRONG; corrected here.**
> Firmware READS **5 pressure transducers** (10 ADC channels, S1 0x402954 … S5 0x4029BC; acquisition
> `sub_0B85EC`) — matching the 5-transducer MK60E5 hardware. **But only S1 (master line) is USED for
> control + the 0x19E broadcast; S2–S5 are measured and routed ONLY to fault/plausibility monitoring**
> (zero reads in control/CAN/model). Per-wheel pressure `0x4016E2[w]` is a **pure COA forward model — NOT
> fused** (no `pred+K·(meas−pred)` anywhere); the Kalman hypothesis is refuted. 0x2B2's four wheel
> pressures are the MODEL output, not S2–S5. Bias-bar observation = S1's port teed to the rear circuit
> (plumbing) + the model inheriting master as supply. So the paragraph below is right that *control* uses
> one measured pressure and models the rest, but wrong that only one sensor is read. Detail:
> `analysis/agents/abs_full/06_pressure_sensors_recheck.md`; FACTS.md "[RESOLVED 2026-10-05]".

- **ABS wheel-pressure control is NOT closed-loop on wheel pressure.** Firmware samples **one** pressure
  sensor — master/front-line, ADC ch21 (ch6 companion), `pressure_adc_track` 0x8F344, ×0.371 → 0x404994,
  ~0.01 bar (200 bar clamp). **No per-wheel caliper pressure is read** anywhere in the control path. [C]
  - ⚠️ **Contradicts the owner's "4 wheel + 1 line = 5 measured" belief.** Hardware may carry wheel-pressure
    sensors, but **this firmware consumes none of them.** Needs a bench gauge trace to settle. [open]
- **Per-wheel caliper pressure is MODELLED**: volume-domain model `hydraulic_model_step` 0x82EF4 integrates
  valve open-times (`valve_flow` 0x818B6: Q = isqrt(|dp|)·open·k/4096) through the **COA compliance curve**
  (`coa_vol_to_pressure` 0x819FE → PM 0x4016E2[w]). Measured line pressure enters only as the supply head
  (`supply_pressure` 0x84D42). No measured-pressure trim. [C]
- COA p-V table (0x41978): pressure axis 0x41B4E {0,4,7,10,15,20,30,60,120,327 bar}; front vol 0x41B62, rear
  0x41B8A. **COA bodies byte-identical to the 1M — NOT M3-retuned.** [C]
- Valve chain: `valve_pulse_sequencer` 0x853A8 (10-step profile/wheel); mode 0x401AA8+8w = 1 hold/2 build/4
  release; build gain front 0x41A76=800 / rear 0x41A78=350; **apply +400/frame, dump −8000, slew 0x584CC** —
  all pressure-LEVEL units, independent of P-V accuracy. Pump = timer-PWM 0x88EC0.
- **Owner's sluggish-brakes question — answered:** For ABS (pedal down, locking) the dominant loop is
  **measured slip + wheel-accel, closed every 10 ms**, robust to P-V error. An off P-V model degrades
  modulation precision/feel (pulse sizing, reapply granularity), **not braking authority**. Onset "softness"
  is set by the **apply-ramp/slew constants**, not the P-V curve. An off P-V model only causes sluggish/
  overshooting build in **autonomous DSC/AYC/TCS build (no pedal)** — a different function. [C/I]

---

## 5. Edge cases, failsafe & coding variants (agent 5)

- **Variants:** ABS has only two flavors — **0–9 (standard: M3 and Competition sedan/coupe/convertible, Custom ESM)**
  vs **10/11 (more permissive: GTS coupe / GTS sedan)**. Only the
  front speed-term (0x40412) and g-term (0x40674) families are variant-indexed (in builder 0x47BDC); 10/11
  differ only at high speed and raise the <60 km/h decel floor to −1.40 g ⇒ later/less-intrusive ABS at
  speed. Everything else (rear curve, entry-slip, decel scalars) is **global**. **M3 coded index is in EEPROM**
  (coding byte[1]&0x1F, setter 0x0CFDD8), default 0 after RAM clear — not in flash. [C]
- **µ-split / GMA (decision code 32)**: set in 0x54D9A when the partner wheel dumps; staged +80-count rebuild
  on the high-grip wheel, **gated by lateral g 0x408ECA** (suppressed below ~40 counts, full step above 80);
  reinforced by yaw-deviation persistence 0x408EA6 (≥15). Rear cornering clause 0x54BE8 (cal 0x40DD2=1748). [C]
- **Low-µ** = per-wheel deep-slip flag (0x40902E b4, writer 0x4F9D4) when lock-depth 0x409010 ≥ 50 (cal 0x40D40)
  under >~70 bar (0x40D42=7000) below 80 km/h. **No continuous µ estimator, no µ-indexed slip remap, no NVM µ-learning.** [C]
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

1. **Code-32 cornering rear-knockdown** — the real mid-corner pressure cut: exec 0x58FF4
   `CMD = PM − pct·(LOCKEST−CMD)/100`, driven by pct byte **0x408DE0 (producer UNTRACED — trace next)** + rear
   select-low 0x5184C. This is the lever for trail-brake authority. **NOTE:** the cal curves 0x48E0A/0x48E26
   are NOT this — they're a lateral-g pressure term that *rises* with g (added to XDF/cal as `lat_g_press_a/b`);
   their exact role is UNCONFIRMED, so don't flash a sign-blind edit. Earlier "softens build, biggest lever"
   pointed at the wrong table.
2. **Apply-ramp / slew constants** (apply +400/frame @0x44614-equiv, slew 0x584CC) — govern pressure-build
   *onset* feel ("bite"), independent of the P-V model.
3. **Decel-threshold floors & variant choice** — variants 10/11 already tolerate deeper wheel decel at speed
   (−1.40 vs −1.32 g <60 km/h); or edit the floors/speed-term directly.
4. **Gross-slip limit slope** (0xD6CE2 k=113 → ~130–150 ≈ 12.5–14.5 % of vref). Smallest gain — stock ~11 %
   is already near peak-µ for most race tires; only worth it on stiff slicks that peak late, and it trades
   lateral grip for longitudinal.

**Not levers for ABS:** the vehicle model (mass/l_f/l_r/Cf/Cr/Jz) — DSC-only; the COA P-V tables — feel/
precision only, not authority (and 1M-identical, so not a known defect to "fix").

**Flashing reminder:** every cal edit changes the ROM MISR (re-sign site 0x4249C) + BMY signature → run
`tools/bmy_resign.py fix` before repack/flash. Bench unit only; experimental images must not go in a car.

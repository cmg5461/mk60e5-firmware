# MK60E5 ABS regulation algorithm (1M 7846411A)

A synthesized, cross-verified overview of the ABS control loop, assembled from four agent passes
(`analysis/agents/{abs,control,absphase,absvref}/REPORT.md`) with every headline constant re-read from
`flash/bin/7846411A_00000000.bin`. CPU addresses; file offset = CPU + 0x8000. **Frame = 10 ms.**
Confidence: **[verified]** = read from bytes/listing here; **[agent]** = interpretation; **[open]** = not resolved.

> Research notes only. The image cannot be flashed (ROM self-test + BMY signature). Pressure-domain unit
> (0.01 bar) and wheel-accel unit (0.01 g) are agent readings, not proven.

## 1. Architecture at a glance

```
                 10 ms frame (task T3, body 0x071040)
  wheel edges ──► wheel-speed 0x752B8 ──► filter 0xB65DC ──► struct+0x1A (0.01 km/h)
                                                    │
                            per-wheel pass 0x8EE30  ├─► wheel accel struct+0x20 (0.01 g)
                                                    │        └► peak-decel byte w.39 = a/16
        ┌───────────────────────────────────────────┘
        ▼
  vref integrator  sub_044BF0  ──►  vref 0x408D84 (0.01 km/h)
        │                               │
        │   slip = vref − wheelspeed    │
        ▼                               ▼
  ABS controller  (0x44722 / 0x449E4, ~49 fns in 0x44000–0x5E000)
     entry: slip > curve(ABS+0x576, x=vref)  ≈ 1.3–2.0 km/h
     decel threshold builder 0x47DFC ─► 0x4090C2   (bidirectional accel threshold)
     dump-amount ladder 0x55D44/55EE8/56106 ─► 0x409110 (pressure reduction)
     phase machine: rec[0] bits + axle-pair S0..S3 (0x54D70) + global code 0x408DBA (0x51D54/0x54F9A)
     dump stages 0x5444C (−62/−78/−94 → 10/15/20 bar);  apply ramp 0x44614 (+400/cyc)
        │   commanded pressure level 0x408EFE[w]
        ▼
  request arbiter  0x831FA  (ABS id 1, rear id 11, reapply id 19)  ── priority ──► owner 0x401960[ch]
        ▼
  hydraulic/valve sequencer  0x840AC / 0x851C8  (COA pressure↔volume model) ──► valve pulse trains
```

Three things run the show: the **vref integrator**, the **49-function controller** (0x44000–0x5E000) that
decides pressure per wheel, and the **arbiter+sequencer** (0x8xxxx) that turns pressure requests into valve
pulses. The ABS *calibration block* (0x4039C) feeds the controller; COA + the 0xDA2F0 scalar block feed the
sequencer. Hard speed-dependent caps live in ROM curves 0xD713C–0xD7390 (**not** in any cal block → not tunable).

## 2. vehicle reference speed `vref` (0x408D84) — rate-limited integrator [verified]

Not a simple "fastest wheel". Writer `sub_044BF0`, once per 10 ms frame after the per-wheel loop, floor
0.62 km/h. Each cycle `vref += delta`:

| Situation | delta (0.01 km/h / 10 ms) | = accel |
|---|---|---|
| vref < fastest **front** wheel (compensated) | +44 | +1.25 g |
| ABS active, vref < slowest valid wheel | +22 | +0.62 g |
| init / controller modes 1,2,4 | +282 | ≈ +8 g (snap) |
| normal fall (vref above all wheels) | −22 … −44 | −0.6…−1.25 g |
| modes 1–7, Vmin < vref | −90 | −2.5 g |
| **during ABS** | `−(|decel est| + 20…30)·0.36`, capped −44 | decel-limited coast-down |

Wheel speeds are first scaled by a per-wheel tyre-circumference factor (Q10) before the max/min picks
(Cmax/Fmax/Vmin/Vmax). Invalid wheels (fault bit, or struct+0x19 & 0xC0) are excluded and force a hard
resync to a shadow integrator 0x408E5A. So vref tracks the fastest front wheel on acceleration and
coasts down at a brake-plausible rate during ABS, rather than following a locking wheel.

## 3. Per-wheel signals [verified except where noted]

- **slip** = `vref − struct+0x1A` (0.01 km/h). Slip ratio `0x408F60 = (vref−wheel)·10000/vref` (1e-4).
- **wheel acceleration** `struct+0x20` (0.01 g). Writer `sub_0D271C` (from wheel-speed update 0x752B8):
  two-frame mean of `Δv·2.833`, clamped to ±20 g by sub_0465B0; `w.39 = a/16` spans ±127. (sub_0B65DC's
  ±1.58 g is only a glitch-recovery path.) Low-passed to +0x24 (a_lp); `0x408DAC = a − a_lp` is the jerk-like
  "X" the ladder uses. **The dump stages are reachable**: −62/−78/−94 ≈ −9.9/−12.5/−15 g, −25/−44/−62 ≈
  −4/−7/−9.9 g.
- **peak-decel byte** `w.39 = a/16`, smoothed (sub_0465B0); used by the dump stages.

## 4. Deceleration threshold + dump amount (how targets are calc'd) [constants verified]

**Decel threshold builder `fn 0x47DFC` → 0x4090C2[w]** (bidirectional, 0.01 g):
```
thr = -116 (base, ABS+0xCC)
    - speed_term(vref)        ; front curve ABS+0x76 (0→74), rear ABS+0x9E, over 0→300 km/h
    - decel_term(|decel|)     ; curve ABS+0xF4 (0→60)
thr = max(thr, -240)          ; floor ABS+0xCA
thr = max(thr, -132) if vref<60 km/h ;  max(thr,-120) if vref<20 km/h
(front pressure-imbalance relaxation; result -99 when |a|<15; positive side 63/285/130 when above ref)
```
So the decel threshold deepens with speed (−1.16 g base → toward the −2.4 g floor), is softened at low
speed, and flips to a positive re-acceleration threshold when the wheel is spinning back up.

**Dump amount ladder → 0x409110[w]** (pressure-reduction amount, **not** a decel target):
```
R0 = L · pct(L)/100            ; pct front ABS+0x154 20→8% , rear ABS+0x17C 30→6%   (L = current pressure level)
R2 = ladder(X=jerk)            ; cal -140/-90/-40/-210 scaled /1,/2,/4 by vref; stages -150/-300/-500; jerk side -400/-650/-1000
R4 = decel×slip dump           ; only 20<vref≤60 km/h, clamp 100..1200
total = (R0+R2+R4) · rolloff(0xD72A0 if pressure<2500) + rear_slip_sum(0x56B96)
new_level = max(L - total, 0)  ; if new_level < commanded → reduce
```

## 5. The control decision — apply / hold / dump [verified flow]

Entry/continue condition: **slip > curve(ABS+0x576, x=vref)** ≈ 1.3–2.0 km/h. Three cooperating state layers:
- **per-wheel phase machine** `rec[0]` (sub_04FE3C), driven by an event word from the classifier sub_04D470:
  `0x80 armed-idle → 0xC0 pre-control / 0x84 rear-overspeed-hold → 0x21 DUMP → 0x09 HOLD → 0x11 REAPPLY →
  0x15 reapply-hold`. (bits: b0 in-cycle/"vehicle ABS active", b5 dump, b3 hold, b4 reapply, b6 pre-control.)
- axle-pair cycle phase **S0..S3** in 0x408E3B 6:5 (sub_054D70): S0 idle → S1 entry → S2 pair-hold/reapply →
  S3 rear-balance → S0.
- global decision code **0x408DBA** (sub_051D54, refined by sub_054F9A): 1 = no-control/build, 64 = rear in
  control (pair logic active), 32 = yaw/lateral-limited (0..100%), 1024/16 = reapply nudge/step, 2 = pair-hold
  done, 128 = special.

| Action | How decided | Amount |
|---|---|---|
| **Dump** | fn 0x5444C: peak decel w.39 crosses stage thresholds −62/−78/−94 (set A) or −25/−44/−62 (set B); gated vref-decel `0x408D8B ≥ −70` | target = lock-onset pressure 0x408F98 − **10/15/20 bar**, floored at 20 bar; emitted at max rate −8000 |
| **Hold** | partner clamped `min(CMD,0x408FF8)` or restored to saved level; ECC/ECB counters (limit 2, +8 cornering) | rate 0 |
| **Apply** | steady reapply while pressure deficit `0x408F0E−0x408F06 > 5 bar` | **+400/cycle** (ABS+0x0C), cap 25000; small nudges +0.8 / +2.4 bar |

Per-axle: pairs front(0,1)/rear(2,3) via `^0x40`; a rear wheel's reference is the same-side front wheel's
modelled pressure; a cornering clause (lateral-accel term, |lat|>1748) is rear-specific; reapply request
id 11 is rear-only.

## 6. From decision to valves [verified]

Commanded level 0x408EFE[w] → arbiter `0x831FA(op,id,ch,start,target,rate)`: ABS uses **id 1** (rear **id 11**,
reapply **id 19**). The arbiter picks a per-channel owner `0x401960[ch]` by priority — **ABS id 1 outranks
the driver's master-cylinder pressure (id 0) and TCS (id 2)**; rear id 11 loses to the driver. The winning
target+rate drives the hydraulic sequencer (0x840AC/0x851C8), which converts (target − modelled) pressure
into 0–10 valve pulse slots per channel using the **COA pressure↔volume curves** (axle- and brake-code-selected).

## 7. What's calibratable vs hard-coded

- **Calibratable (ABS block 0x4039C):** entry slip threshold (+0x576), decel threshold base/floor/curves
  (+0xCC/+0xCA/+0x76/+0x9E/+0xF4), dump stages (+0x61E/+0x65E) and amounts (+0x624), apply ramp (+0x0C),
  pressure-dump % (+0x154/+0x17C), the ladder (+0x2C8). All now named in `xdf/MK60E5_7846411A.xdf`.
- **Hard-coded in ROM (not tunable by editing a cal block):** the pressure clamps 25000 / −8000, and the
  speed-/state-dependent limit curves at 0xD713C–0xD7390.
- **Brake-hardware dependent:** COA pressure↔volume + gain curves, selected by coding fields +3/+4.

## 8. Open items

- **[resolved]** Normal-mode wheel-accel writer = sub_0D271C; range ±20 g; dump stages reachable (§3).
- **[resolved]** rec[0] phase states and 0x408DBA decision codes decoded (§5).
- **[partial]** Full EV0/EV1 event-word predicates in sub_04D470 (~3000 more instructions); phase-state
  names inferred from the transition pattern + the dump gate, not proven against valve outputs.
- **[needs-hw]** Real-world +0x20 distribution in braking (how often −10 g is crossed; low-speed
  quantisation) — needs a dynamic trace on the car.
- **[open]** Pressure-domain unit (assumed 0.01 bar); 0x408F4A setpoint vs ceiling.

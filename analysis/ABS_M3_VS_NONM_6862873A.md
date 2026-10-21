# MK60E5 ABS — M3 7846816A vs non-M 6862873A (algorithm and calibration)

Comparison of the ABS control path in the M3 image (7846816A, DSCM90) and the non-M image
(6862873A, DSC90, e.g. 335i). Static analysis only; nothing here has been checked
against logs. M3 behaviour is documented in `ABS_ALGORITHM_M3_7846816A.md` and
`agents/abs_full/*.md`; this doc only records what differs.

**Conventions:** CPU addresses. File offset: M3 `flash/bin/7846816A_00000000.bin` and non-M
`flash/bin/6862873A_00000000.bin` are both CPU + 0x8000. Frame = 10 ms. Units: speed/slip 0.01 km/h,
decel 0.01 g, pressure 0.01 bar (tables below are converted to km/h, g, bar). Tags: **[C]**
confirmed from the listing, **[I]** inferred, **[open]** unresolved.

**Address mapping between the images:**
- ABS RAM is shifted by −0x4EE0 (a few blocks −0x4EE4): vref 0x408DA8 → 0x403EC8.
- Coding image 0x4031AA → 0x40323C (variant byte at +1).
- ABS calibration block M3 0x4039C–0x40EA6 ↔ non-M 0x40100–0x40A40. The shift is not constant
  (−0x3DA … −0x446 through the block); use the tables below, not a fixed offset.
- ABS code 0x44000–0x5A000 sits at nearly the same addresses (shifts of +0x100 … +0x880).

## Method

- 49 M3 functions on the dump/hold/reapply path were matched to non-M functions by code and
  diffed instruction by instruction, with register allocation stripped and literals classified as
  RAM / CAL / ROM (literal pools excluded). Every function matched clearly.
- The two ABS calibration blocks were aligned word by word (difflib), so a calibration value is
  only called "different" when the surrounding words line up.
- The variant byte was traced by scanning the non-M listing for every `ld.b (·,1)` off the coding
  image.

## Summary

The phase machine, dump depth formula, step tables, hold and the reapply step pattern are the
same. The non-M differs in **when** things trigger and **how much the rear axle is trusted**:

1. **The vehicle-variant coding byte has no ABS effect on the non-M.** The M3's variant-indexed
   decel curves and floors are single fixed values, and the M3's variant-10 (GTS) classifier
   branch is gone.
2. **Shallower decel threshold:** absolute floor −1.80 g instead of −2.40 g, and shallower
   low-speed floors.
3. **Rears give up pressure sooner and rebuild slower:** combined rear-axle dump tiers 0.15 lower,
   new yaw-based rear dump triggers, 5× larger rear slip term C in the combined case, longer forced
   dump, rear-only reapply capped at 1 bar/frame.
4. **Reapply freezes sooner at high pressure** (0.03 g/step relaxation, −5 g build stop on any
   step), but the fast ramp is gated on wheel health instead of the re-decel count.
5. **Several branches depend on non-M-only flags** with no static writer found
   (0x400F5A b7, 0x402EF9 b4, …), so their relevance on a car is unknown.

## 1. Vehicle-variant coding byte (c[1] & 0x1F)

On the M3 the variant selects four ABS tables and enables one classifier branch. On the non-M
there are 17 reads of the variant byte, all between 0x5E000 and 0xD2000; ABS code
(0x44000–0x5A000) never reads it. **[C]**

### Decel-threshold builder (`abs_decel_threshold_builder`, M3 0x47BDC, non-M 0x47CA8)

Same code, but every value comes from a fixed address and there is no front/rear curve switch.

| Item | M3 | non-M |
|---|---|---|
| Speed-term curve (0/100/150/200/250/300 km/h, 0.01 g) | front `0x40412 + 0x28·var`: var 0–9 `[0,−10,−10,−50,−95,−277]`, var 10/11 `[0,−20,−20,−40,−85,−267]`; rear `0x405F2` | `0x4048C`, all wheels: `[0,0,−15,−55,−100,−215]` |
| g-term curve | `0x40674 + 0x40·var` (two sets: 0–9 / 10–11) | `0x404E2`: `[0,0,−38,−41,−41,−41,−41,−62,−118,−219]`, deeper at high g than either M3 set |
| Gain front / rear | 0x4061A / 0x4061C = 40 / 25 | 0x404B4 / 0x404B6 = 40 / 25 |
| Base | 0x40620 = −116 | 0x404BA = −116 |
| Absolute floor | 0x4061E = **−2.40 g** | 0x404B8 = **−1.80 g** |
| Floor below 60 km/h | `0x4065C[var]`: −1.32 g (var 10/11 −1.40) | 0x404E0 = **−1.28 g** |
| Floor below 20 km/h | `0x40644[var]`: −1.27 g (var 1–11 −1.20) | 0x404DE = **−1.16 g** |
| Override when low-µ flag bit 1 is set (0x40902E / 0x40414E) | immediates −1.30 / −1.35 g | immediates −1.20 / −1.25 g |

### Classifier pre-control hold (`abs_event_classifier` 0x4D270, test at 0x4D946)

The non-M copy (0x4D5A4, block at 0x4DC94) keeps only the branch for negative rec+6 (excess
speed loss) and exits otherwise. The whole positive-rec+6 path is missing: the 0x408E7B > 52 and
0x408E6A < 100 checks as well as the `var == 10` test. **[C]**

### What the non-M variant byte does drive (DSC/TCS, not ABS)

- Vehicle-model loaders 0x5E8B8 / 0x5F73C (M3 `vehmodel_load_singletrack_coeffs` 0x5DE44 /
  `vehmodel_load_axle_derived` 0x5E424) and 0x60408 (≈ `yaw_observer` 0x5EBC4). Unlike the M3,
  variant 1 really loads the custom coding words (0x40324A+28).
- CSI sensor sign tables 0x40A40 / 0x40A98 (M3 0x40EE4 / 0x40F14); every non-M entry is −1.
- TCS 0xCD11E (variants 17/21 with f+0 = 7 → 118 instead of 100) and 0xCD810 (table 0xE12F4,
  1300–2100, × vehicle accel).
- DSC steering-angle brake-request module 0x67AFC / 0x684F8: per-variant curves
  0x41116 / 0x411C6 + 8·var, gain 0x412E8[var] (4694 / 3755), offset 0x41314[var] (110 / 80).
  The M3 uses one fixed curve (0x416C6 axis, 0x416CE / 0x416D6) and gain/offset 3755 / 80
  (0x41752 / 0x41754); those equal the non-M fallback curves (0x41106 / 0x4110E, used only when
  cal 0x410C2 b4 is set — it isn't) and one of the non-M variant groups. Output goes to
  0x400B64 with update flag 0x400B52 b7.

**[open]** ABS reads 0x400B52 b7 at non-M 0x46AC8 and 0x5307E. That byte has over 100 writers, so
a variant change could reach ABS through that shared flag, but not through any ABS parameter.

## 2. Unchanged

Identical code and calibration in both images:
- **State machine and dispatch:** `abs_phase_sm`, `abs_wheel_phase_dispatch`, `abs_pm_snapshot`
  (dump cap).
- **Dump depth at entry:** R0 lock-percentage curves (M3 0x40994 / 0x409BC), A-term thresholds
  (0x40B08–0x40B12), B-term curves and factors, k1/k2 decel-onset curves. The low-pressure ×2
  scaling has the same values but moved from ROM to calibration (non-M 0x407FA).
- **Stepped dump:** step-period table `[178,5,3,2,2,1,0]`, `abs_dump_step_amount`,
  `abs_dump_step_scale`, `abs_dump_frame_flags`, continuous release 10 bar/frame.
- **Hold and reapply:** hold-tail rebuild rates 9000/600/400, reapply period table (0, then 7
  frames), base rates 3/5 bar/frame, step fraction m = 10, `abs_reapply_ramp_to_ceiling`,
  `abs_reapply_step_amount`, `abs_cmd_slew_limiter`.
- **Decision layer:** `abs_rear_lead_select`, `abs_decision_resolve`, `abs_cycle_ref_update`.
- **Rough-road / pump-demand detector** calibration (M3 0x40D5A–0x40D8E ↔ non-M 0x40914–0x40948).

## 3. Calibration differences

| Item | M3 addr | M3 | non-M addr | non-M |
|---|---|---|---|---|
| Forced-dump minimum duration (÷10) | 0x40AE4 | 5 frames | 0x406BE | **8 frames** |
| Forced-dump rear amount cap | 0x40B04 | 7 bar | 0x40716 | **6 bar** |
| Staged front dump ladder | 0x40E64–68 | 10 / 15 / 20 bar | 0x409EA–EE | **15 / 20 / 25 bar** if 0x402EF9 b4; else 10/15/20 with peak-decel thresholds ≈5 g deeper below 140 km/h (offset 0x40A28 = −31) |
| Early-step slip-ratio thresholds | 0x40BEA–EE | 160 / 140 / 120 | 0x40810–14 | **180 / 150** / 120 |
| Re-decel threshold relaxation per step above 70 bar | code | 0.04 g | 0x4090E | **0.03 g** |
| Rear-latch reapply lateral curve | 0x403B4 (cal) | 0 → 24, rising with lateral g | 0xD8D5E (ROM) | **flat 15, 12 above index 100**; no longer calibratable |
| Low-µ flag count thresholds | 0x40D40 / 0x40D42 | > 50 / > 30 | hard-coded | **> 68 / > 48** |
| Low-µ flag driver pressure | code | > 70 bar | code | **> 80 bar** |
| Entry-slip curve (pair logic) | 0x40DB6 | 1.5 km/h at 0 → 1.44 at 100 km/h | 0x40972 | **1.0 at 0 → 1.82 at 100 → 2.6 at 200 km/h** |
| Pair reapply nudge | 0x40D90 | 80 | 0x4094A | **30** |
| Combined rear-axle dump tier multiplier | code (120) | 1.20 | 0x40830 / 0x40848 | **1.05** |
| Mode-2 entry in `abs_state_aggregate` disabled | 0x40B42 | 1 (off) | 0x40752 | **0 (on)** |

## 4. Algorithm differences

### Dump

- **Rear slip term C** (`abs_dump_r_rear_slip`, M3 0x56996 / non-M 0x570D4). With the
  combined-rear-dump flag (M3 0x409057 b6), the non-M divides the wheel's own slip by 60 instead
  of 300, so the term is 5× larger. Where the M3 sets C = 0 because the rears weren't both armed,
  the non-M uses own/2 + 70·partner/250.
- **Decel-rate term A** (`abs_dump_entry_target`) is only added when the normal-mode flag
  0x403EE6 b6 is set (M3 equivalent 0x408DC6), b7 is clear, and 0x4026F8 b6 is clear.
- **Term B** (`abs_dump_r_wheel_decel`): the +200 can also be triggered by 0x400F5A b7.
- **Early dump steps** (`abs_dump_continue`, M3 0x562DC / non-M 0x56A94):
  - wait adjustment −3…+3 instead of −2…+4, so W is 1–7 frames instead of 2–8;
  - the M3's −2 for very high decel (front < −6 g, rear < −4 g) is gone;
  - the decel-rate triggers (front d < −2.1, rear d < −1.05) are gone; only the excess-speed-loss
    (rec+6) triggers remain.
- **Step period** (`abs_dump_step_period`, M3 0x56C60 / non-M 0x573C0):
  - the rec+0x10 b1 exemption from "locked → continuous release" applies at all speeds, not only
    ≥ 60 km/h;
  - with that bit set the 8k slip band gets P = 2 instead of 1;
  - the rear "+12 frames on the yaw side" rule is gone;
  - the decay-based extension is capped at 10 frames instead of 15.
- **Forced dump** (`abs_phase_dump_handler`, `abs_dump_forced_target`): 8-frame minimum and 6 bar
  rear cap (§3); the 500 constant moved into calibration.
- **Staged front dump** (`abs_dump_hold_stage_ctrl`, `abs_dump_stage`): no check of the M3 enable
  cal 0x40E9A (1 on the M3 anyway); 0x400F5A b7 added; ladder selected by 0x402EF9 b4 (§3).
- **Dump entry flags** (`abs_dump_entry_flags`): extra speed-dependent state resets.

### Hold

- With the rear latch active (M3 0x409049 b1), the M3 recomputes the alternate pressure ceiling
  every hold frame (`abs_phase_hold_handler`). The non-M computes it once at hold entry
  (`abs_hold_entry_sync`), folded into the headroom H with the 5-bar minimum applied.
- An extra low-µ flag gate (below).

### Reapply

- **Rear-only ABS** (`abs_reapply_rate_select`, M3 0x57952 / non-M 0x58138): the rear base rate
  of 5 bar/frame is capped at 1 bar/frame unless a front is in an ABS cycle (0x408DA2 b7 on the
  M3 numbering).
- **Rear-latch rate:** M3 4 bar/frame (3 with 0x408E1A b1). Non-M 5 bar/frame, dropping to 1 after
  a re-decel (2 in one flag case).
- **Build stop** (`abs_reapply_step`, M3 0x581BA / non-M 0x589E6): a step stops building whenever
  wheel decel is below −5 g with more than 5 km/h slip. The M3 applies this only to the first two
  steps.
- **Fast ramp** (6 bar/frame after N_max, `abs_phase_reapply_handler`): the M3 requires fewer than
  2 re-decels in this reapply. The non-M drops that and requires rec+6 ≥ 0, or decel > −3.5 g with
  slip < 1 km/h, or decel > −2 g with slip < 2 km/h.
- **Re-decel threshold** (`abs_reapply_conditions`): above 70 bar, T relaxes 0.03 g per step
  instead of 0.04 g.
- **Special rates** (`abs_reapply_special_rate`): lateral curve flattened and moved to ROM; extra
  0x400F32 b7 trigger.
- **Step boost** (`abs_reapply_step_boost`, M3 0x4C368 / non-M 0x4C558): same N0 = 5 and idle-wheel
  logic, substantially restructured with new gates. **[open]** Not fully decoded on either side.
- Reapply N_max of 12 under 0x400F5A b7.

### Classifier and flags

- **Combined rear-axle dump** (`abs_event_classifier`): same four tiers, every multiplier 0.15
  lower (1.05 from cal instead of 1.20 hard-coded). Fires with ~15% less combined decel and slip.
- **New rear dump triggers:** a rear with rec+6 < 0 can start a dump (EV0.b5) or dump again
  (EV0.b0) without its own slip trigger, when the combined-rear flag is set or a new flag is set.
  That flag uses yaw minus the AYC target beyond ±700 and driver brake pressure > 0.
- **Low-µ flags** (non-M 0x40414E, stride 3, writer 0x4FE14 = M3 0x4F9D4 `abs_lowmu_flag_update`):
  higher count and pressure thresholds (§3). An extra bit, 0x40414F b0, also gates the
  "0x4090B6 > 75" shortcuts in hold, period select and step boost.
- **Rear select-low** (`abs_decision_pressure_exec`, M3 0x58FF4 / non-M 0x59884): under 0x403F7F b3
  the follower offset is taken from 0x400F5E, written by another module.

## 5. "Rough-road" mode is a pump-demand mode

The mode byte M3 0x408DAD / non-M 0x403ECD is labelled "rough road" in `05_edge_cases_variants.md`
§3, which says it suppresses false ABS triggering. A full scan of the M3 readers shows **no ABS slip
or decel threshold code reads it**; its consumer is the return-pump demand. **[C]** for the
detector and the list of readers.

**Detector** (M3 0x5567C, non-M 0x55DE8), every frame while 0x408DC6 b2 and 0x408E6D b6 are set.
For each wheel in an ABS cycle it scores frames where measured pressure PM (0x408F2A) exceeds the
command CMD (0x408F22) by more than 0.5 bar (first loop) or 1 bar (second loop), with base weights
3/4/5/1 (0x40D78–0x40D7E). Extra score when CMD < 10 bar (0x40D6C), p_ref > 30 bar (0x40D70),
CMD < 1 bar (0x40D6E), the dump has lasted ≥ 21 or > 40 frames (0x408FAC), or a wheel has |peak
decel byte| > 63.

| Condition | Mode | Timer 0x408EAF |
|---|---|---|
| score > 24 | 3 | 80 frames (0x40D72) |
| score > 19 and timer < 60 | 5 | 60 |
| score > 14 and timer < 50 | 4 | 50 |
| sensor/normal flags invalid, braking (0x408DA1 b4) | 6; → 3 if ≥ 2 reapplying wheels have \|peak\| > 63 | — |

Entering a mode sets 0x408DF0 b0. The timer counts down; at 0 the mode returns to 0 unless it is
1, 2 or 7 or 0x408DA1 & 3 ≠ 0. Other writers: mode 2 from 0x5D4EE (only if mode was 0) and from
`abs_state_aggregate` 0x45808 when cal 0x40B42 = 0; mode 5 from `abs_side_select` 0x5C640 (yaw
condition); cleared at 0x44534 (frame entry), 0x51226 (reset, also clears the timer) and 0x4AF00
(dump entry clears mode 2).

**Effect:**
- **Pump state machine** (M3 sub_085E5E, from `hydraulic_actuation_pipeline` 0x843C8; non-M
  0x8CE32): mode 3 → fixed maximum-level state (0x419C6 = 14); mode 2 keeps the pump running while
  LPA volume 0x4016F2 > 6500 (0x419D2).
- **Pump level** (helper 0x85E14; the non-M reads the mode in 0x8CD38, counterpart of M3 0x85D64,
  and 0x8CE32): level = 3 + 11·(LPAvol − 3000)/9000
  (0x419C6–0x419CC), plus +3 / +7 / +14 in modes 4 / 5 / 6 (0x419C0–C4), capped at 14, written to
  0x401D08 and read by `pump_motor_control` 0x88EC0 and `pump_volume_frame` 0x82824. **[I]** that
  0x401D08 is motor demand (from its readers); LPA volume units unknown.
- **ABS side:** while 0x408DF0 b0 is set, `abs_dump_frame_flags` (0x4B18C) skips the forced-dump
  override that raises the re-accelerating threshold to 60/90. Nothing else.

So it spins the pump up for 0.5–0.8 s when dumps aren't keeping up (pressure not following the
command, long dumps, large decel peaks). The only M3/non-M difference is cal 0x40B42 = 0, which
enables the extra mode-2 entry: the non-M keeps the pump running longer during ABS events while
the accumulator holds volume. It does not change how much slip ABS tolerates. **[open]** No writer
found for modes 1 and 7; the bits behind the 0x5D4EE mode-2 entry are not identified.

## 6. Non-M-only flags

| Flag | Used in | Writer |
|---|---|---|
| 0x400F5A b7 | B-term +200, early-step +10, staged-dump control, reapply N_max 12, step boost | none found (struct 0x400F58, module ≈0x6B0DC–0x6C8xx) |
| 0x400F5E | rear select-low follower offset | same module |
| 0x402EF9 b4 | staged front ladder 15/20/25 bar | none found |
| 0x400F32 b7 | `abs_reapply_special_rate` trigger | not traced |
| 0x4026F8 b6 | A-term gate | not traced |
| 0x40414F b0 | low-µ shortcut gate | not traced |

Until the writers are known, the branches gated by 0x400F5A b7 and 0x402EF9 b4 are of unknown
relevance on a real car.

## 7. Function map

All pairings matched by code. "—" = no difference worth noting beyond addresses.

| M3 | Symbol | non-M | Difference |
|---|---|---|---|
| 0x47BDC | `abs_decel_threshold_builder` | 0x47CA8 | fixed cal, no rear curve, shallower floors (§1) |
| 0x4D270 | `abs_event_classifier` | 0x4D5A4 | combined-rear tiers −0.15; new rear triggers; variant-10 branch gone |
| 0x4FC3C | `abs_phase_sm` | 0x5005C | — |
| 0x504D0 | `abs_wheel_phase_dispatch` | 0x508EC | — |
| 0x50580 | `abs_phase_armed_handler` | 0x5099C | trivial |
| 0x50894 | `abs_phase_precontrol_handler` | 0x50CB0 | minor |
| 0x4AAA8 | `abs_phase_dump_handler` | 0x4AB48 | forced dump 8 frames |
| 0x55F06 | `abs_dump_entry_target` | 0x566A2 | A term gated; low-pressure curve in cal |
| 0x55B44 | `abs_dump_r_decel_rate` | 0x562DC | — (compiler idiom only) |
| 0x55CE8 | `abs_dump_r_wheel_decel` | 0x5647E | +200 also via 0x400F5A b7 |
| 0x56996 | `abs_dump_r_rear_slip` | 0x570D4 | own slip ÷60; not zeroed when unarmed |
| 0x4B09C | `abs_dump_frame_inputs` | 0x4B1F4 | — |
| 0x4B012 | `abs_dump_entry_reset` | 0x4B12E | — |
| 0x4ADD4 | `abs_dump_entry_flags` | 0x4AE74 | extra speed-dependent resets |
| 0x4B160 | `abs_dump_frame_flags` | 0x4B2A0 | — |
| 0x559CC | `abs_pm_snapshot` | 0x56164 | — |
| 0x562DC | `abs_dump_continue` | 0x56A94 | W 1–7; decel-rate triggers removed |
| 0x56C60 | `abs_dump_step_period` | 0x573C0 | exemption at all speeds; no rear +12; cap 10 |
| 0x56728 | `abs_dump_step_amount` | 0x56E64 | — |
| 0x56EDC | `abs_dump_step_scale` | 0x575E4 | — |
| 0x57024 | `abs_dump_forced_target` | 0x57710 | rear cap 6 bar |
| 0x53940 | `abs_dump_hold_stage_ctrl` | 0x53CF4 | no enable cal; 0x400F5A b7 |
| 0x5424C | `abs_dump_stage` | 0x546B0 | ladder by 0x402EF9 b4 |
| 0x543FC | unnamed (second staged-dump writer) | 0x548B0 | |
| 0x57200 | `abs_hold_entry_sync` | 0x578F4 | rear-latch reference folded into H |
| 0x4CA3C | `abs_phase_hold_handler` | 0x4CD50 | per-frame alternate ceiling removed; low-µ gate |
| 0x57378 | unnamed (hold tail) | 0x57AA0 | |
| 0x4CF76 | `abs_hold_set_reapply_frac` | 0x4D29C | — |
| 0x4B680 | `abs_phase_reapply_handler` | 0x4B7CC | fast-ramp gate changed |
| 0x4B970 | `abs_reapply_entry_flags` | 0x4BB2C | trivial |
| 0x4BB52 | `abs_reapply_frame_prep` | 0x4BD22 | — |
| 0x4B9E2 | `abs_reapply_entry_init` | 0x4BBA0 | also clears a staged-dump pair bit |
| 0x4BC84 | `abs_reapply_conditions` | 0x4BE5C | 0.03 g/step above 70 bar |
| 0x4C0BC | `abs_reapply_period_select` | 0x4C2AC | low-µ gate |
| 0x581BA | `abs_reapply_step` | 0x589E6 | −5 g build stop on every step |
| 0x4B3C8 | `abs_reapply_special_rate` | 0x4B508 | lateral curve flat, in ROM; 0x400F32 trigger |
| 0x57952 | `abs_reapply_rate_select` | 0x58138 | rear-only cap 1 bar/frame; rear-latch rates |
| 0x57E48 | `abs_reapply_ramp_to_ceiling` | 0x58674 | — |
| 0x57F62 | `abs_reapply_step_amount` | 0x5878A | — (1000 now a cal) |
| 0x4C368 | `abs_reapply_step_boost` | 0x4C558 | restructured **[open]** |
| 0x584CC | `abs_cmd_slew_limiter` | 0x58D1C | — |
| 0x5884A | `abs_cycle_ref_update` | 0x590C8 | — |
| 0x5862C | `abs_lockon_pressure_estimator` | 0x58E80 | minor extra flag conditions |
| 0x45808 | `abs_state_aggregate` | 0x458FC | mode-2 entry enabled (0x40B42 = 0) |
| 0x5184C | `abs_rear_lead_select` | 0x51C9C | — |
| 0x51B54 | `abs_decision_classify` | 0x51FA4 | minor (cal-gated flag) |
| 0x58B30 | `abs_decision_resolve` | 0x593B4 | — |
| 0x58FF4 | `abs_decision_pressure_exec` | 0x59884 | offset from 0x400F5E under 0x403F7F b3 |
| 0x4F9D4 | unnamed (`abs_lowmu_flag_update`) | 0x4FE14 | thresholds 68/48/80 bar |
| 0x446B6 | unnamed | 0x44806 | |
| 0x5173C | unnamed | 0x51B8C | |
| 0x5567C | unnamed (pump-demand detector) | 0x55DE8 | — |
| 0x85E5E | unnamed (pump demand state machine) | 0x8CE32 | not diffed |
| 0x710FC | `curve_interp_s16` | 0x76384 | helper |
| 0x7119E | `interp_linear_xy` | 0x76426 | helper |

## 8. RAM map (ABS items used above)

| Meaning | M3 | non-M |
|---|---|---|
| vref (`vref_abs`) | 0x408DA8 | 0x403EC8 |
| Pump-demand ("rough-road") mode | 0x408DAD | 0x403ECD |
| Wheel-derived decel estimate (`abs_decel_est`) | 0x408DAF | 0x403ECF |
| ABS normal-mode flags | 0x408DC6 | 0x403EE6 |
| Frame counter (runs while 0x401FF2 b5) | 0x408E6A | 0x403F8A |
| Classifier input (> 52 check, M3 only) | 0x408E7B | 0x403F9B **[I]** |
| Longitudinal accel (`abs_ax`) | 0x408E80 | 0x403FA0 |
| Per-wheel pressure (`abs_p_wheel`) | 0x408F2A | 0x40404A |
| Per-wheel reference pressure (`abs_p_ref`) | 0x408FF0 | 0x404110 |
| Per-wheel reapply-decel counter (`abs_reapply_decel_count`) | 0x409014 | 0x404134 |
| Per-wheel low-µ flag bytes (stride 3) | 0x40902E | 0x40414E |

## 9. Expected behaviour on a car

Read from code and calibration; the size of each effect is unknown.

- **Hard stop on grip:** the non-M treats a wheel as unstable at shallower decel (−1.80 g cap vs
  −2.40 g, shallower low-speed floors), so it dumps earlier. Expect slightly lower peak decel. The
  higher entry-slip curve at speed partly offsets this.
- **Rear axle:** pressure is given up sooner (lower combined tiers, yaw-based triggers, larger C,
  longer forced dump) and rebuilt slower (1 bar/frame when only the rears are in ABS). More stable
  in trail-braking and braking in a corner, less rear contribution and rotation. The M3 keeps more
  rear brake and accepts more yaw.
- **Reapply:** freezes sooner at high pressure, but can return to lock pressure faster when the
  wheel is clearly healthy (fast-ramp gate).
- **Dump steps:** follow up about a frame sooner, with fewer triggers and a shorter fade
  extension — a softer, less peaky pressure pattern.
- **Split-µ front:** stronger (15/20/25 bar) if 0x402EF9 b4 is set, otherwise rarer staged dumps.
  Which applies is unknown.
- **Low µ:** slower to set the low-µ flags (higher count and 80 bar).
- **Pump:** runs longer during ABS events (mode-2 path); no change to ABS thresholds.

Equal calibration numbers don't imply equal brake torque: the hydraulic/pressure models and
caliper coding differ between the cars (`CODING_BYTES_6862873A.md`).

## Open questions

- Writers of 0x400F5A b7, 0x402EF9 b4, 0x400F32 b7, 0x4026F8 b6, 0x40414F b0.
- `abs_reapply_step_boost` on both sides.
- Whether the variant-dependent DSC request ever sets 0x400B52 b7 in a way ABS acts on.
- Pump-demand modes 1 and 7 (no writer found) and the 0x5D4EE mode-2 condition.

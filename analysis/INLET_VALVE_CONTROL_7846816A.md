# Inlet valve control, 7846816A (traced 2026-10-17)

How a wheel's pressure request becomes inlet-valve current on the wire. CPU addresses. Names and
signatures are in `7846816A_symbols.md` ("Hydraulic actuation"). Confidence is high unless marked.

## 1. Rates and buffers

| Rate | Code | Job |
|---|---|---|
| 10 ms | `wheel_valve_frame` 0x85D64 (slot 32) → `inlet_mode_select`, `valve_pulse_sequencer` 0x853A8 | mode per wheel; feed-forward reapply current I_build; full-build profile |
| 5 ms per wheel (2.5 ms task phases 0 and 2) | `inlet_fast_loop` 0x85282 | closed loop on the measured wheel pressure; writes 5 steps of output per call |
| 1 ms | `valve_output_1ms` 0x741F4 → `valve_output_step` 0x73DBC | sends step i of every wheel to the valve ASIC (QSPI CS5) |

The output buffer `inlet_out_dac` 0x400F2E is u8[4 wheels][10 steps], one step per ms, DAC code = mA × 51 / 400
(229 ≈ 1800 mA). In each frame:

1. **2.5 ms phase 0:** `valve_output_frame_merge` 0x74320 refills all 10 steps. A step takes the `valve_pulse_set`
   stage value if one was staged, otherwise `inlet_base_current_dac` 0x4009AC. Failsafe 0x40287D can force a
   wheel to 0 or 229 instead.
2. **Same phase:** `inlet_fast_loop`(w, half 0) overwrites steps 0–4.
3. **Phase 2:** `inlet_fast_loop`(w, half 1) overwrites steps 5–9.
4. **Every 1 ms:** step i is clocked out.

**What the base current and staging do in normal driving:** nothing. `inlet_base_current_dac` has non-zero
writers only in the manufacturing test protocol (`mfg_test_cycle` 0x76036, including `coa_wheel_gain_apply`).
`valve_pulse_set` is called for the inlet channels (0–3) only from that protocol and from actuator tests. So in
normal operation any step the fast loop does not write stays 0 mA, i.e. a de-energised, open inlet.
(Base = 0 at RAM init is assumed, not checked.)

## 2. Modes

`wheel_p_request` 0x401AA8[w] = {u8 mode, s16 rate}. The rate is the arbitrated request rate in 0.01 bar per
10 ms frame; 9000 means a full, unmetered build. `inlet_mode_select` sets the mode from the rate's sign:
0 → hold (1), > 0 → build (2), < 0 → dump (4). Mode 0 means no request.

The fast loop copies the mode into `inlet_ctl` 0x401AF8[w].mode. Every 5 ms `inlet_fast_mode_refine` 0x84772 can
switch it between 1, 2 and 8 using hysteresis on target − measured. Mode 8 ("settle") is closed and lasts up to
5 half-frames (med; not every branch traced).

| Mode | Inlet | Current |
|---|---|---|
| 0 none | open (de-energised) | 0 mA (nothing written; base = 0); learned offset cleared |
| 1 hold | closed | peak 1524 mA for 2 half-frames, then hold-in 1100 mA (`inlet_holdin_current`) |
| 4 dump | closed (the outlet does the dumping, `outlet_dump_time_calc`) | peak 1532, then 1100 |
| 8 settle | closed | peak 1492, then 1100 |
| 2 build, rate 9000 | fully open for n steps, then closed | 0 mA × n steps, then 1540 (sequencer profile; n from 0x85340, ≥ 3) |
| 2 build, normal rate | **metered: partly energised** | I = I_build − learn on all 5 steps of a half-frame while target − measured ≥ rate/10; otherwise closed (1540, 1100 after two closed halves) |

For rear wheels with 0x408DA0 b3 set, the closed currents are capped at `inlet_current_for_dp`(w, 130 bar)
(`inlet_profile_fill`). The meaning of that bit is not identified.

## 3. Metered reapply

**Feed-forward, 10 ms** (`valve_pulse_sequencer` build branch):

```
dp     = supply_pressure(w) - PM[w]                     // across the inlet, 0.01 bar
I_hold = inlet_current_for_dp(w, dp)                    // routine-0x28 calibration: current that just holds dp
y      = interp(dp; 0, 20, 80 bar -> front 0, 10, 40 % / rear 0, 5, 20 %)    // 40/20 = COA 0x41A72/74
C      = curve_slope_fwd(PM, p-V curve)                 // brake compliance dV/dp per bar at PM (0x852B6)
D      = C * dp / (G + temp)                            // G = 800 front / 350 rear (COA 0x41A76/78), temp 0x401FF7
k      = clamp(100 - rate * y / D, 100 - y, 100)        // %; D <= 0 -> 100 - y
I_build = I_hold * k / 100                              // -> 0x401C00[w]
```

The current starts at the valve's own hold point for the present Δp. It is lowered by up to y % (40 % front at
≥ 80 bar) in proportion to rate / D. A low rate keeps the valve just past cracking. A high rate opens it further.
D works like "the rate at which the full y reduction applies". It grows with Δp and with compliance C. Treating it
as a maximum achievable rate is an interpretation. A flow model would predict rate ∝ flow / C, while the code
multiplies by C, so a softer brake (low pressure) gets a smaller reduction for the same rate.

Example, front, code 0, PM 50 bar (C = 103), Δp 50 bar, temp 0: D = 103 × 5000 / 800 ≈ 643. Rate 300
(3 bar/frame) → k ≈ 100 − 300 × 40 / 643 ≈ 81 %. Rate 600 → 63 %.

**Feedback, 5 ms** (`inlet_fast_loop`):
- **Setpoint:** p_sp starts at the measured pressure and ramps by rate/2 per half-frame up to the target. The
  rate is clamped to 100..600, i.e. 1–6 bar per frame.
- **Current:** I = I_build − learn, floored at 180 mA (`inlet_build_profile` 0x84A56).
- **Learn increases** (less current, more opening) when the pressure lags the ramp: err_sp > 8 / 4 / 2 bar for
  1 / 3 / 7 consecutive half-frames.
- **Learn decreases** (`inlet_build_adapt` 0x850AA) when the measured rise rate (`inlet_rate_achieved` 0x84F02,
  6-tap filtered dp/dt) exceeds the commanded rate by more than 30 %.
- **Limits:** learn ≥ −150 mA; cleared when the wheel leaves control (mode 0).
- **Rate drop:** if the requested rate falls below the previous half-frame's, that half uses 1508 mA, effectively
  closed.

So reapply is a proportional valve. A calibrated hold-current model gives the feed-forward, and a learned offset
on measured pressure corrects it. The valve is not pulsed open/closed. The digital-valve style still exists only
as the full-build (rate 9000) path and in the sequencer's step count.

## 4. Other paths

- **Outlet / dump timing** (`outlet_dump_time_calc` 0x85A42, 10 ms): open loop, no pressure feedback inside the
  frame. When the target drops below `dump_ref_pressure`, it books
  t = 10 · (V(target) − V(ref)) / q_frame(ref − p_LPA) ms of outlet time. V is the p-V curve, q_frame is the orifice
  flow for one full 10 ms opening, and ref becomes the target. The debt is paid out at up to 10 ms per frame, with a
  4 ms minimum pulse (`coa_dump_predict_level`). A new plan is made only if one minimum pulse (`dump_step_dp`, predicted
  by the hydraulic model) would not take the wheel below the target. The step count goes to `valve_cmd` (the model)
  and to `valve_pulse_set`(4 + w), outlet on for the first |n| ms of the frame. Hold with target 0 can add full
  dump frames on 70 of every 100 frames (`outlet_hold_bleed`, med).
- **Manufacturing test protocol** (`mfg_test_cycle` 0x76036): sets base currents directly (modes 0/5), from
  `coa_wheel_gain_apply` (modes 4/6: 91–92 % of the hold current at master − wheel Δp), and pulse lengths through
  `valve_pulse_set`.
- **0x8393C** (caller 0x83C00): builds a 10-step linear mA ramp (0..1540) and stages it like the sequencer.
  Context not traced.

## 5. Open

- `inlet_fast_mode_refine` mode 8 entry and exit conditions in full.
- 0x408DA0 b3 (rear closed-current cap).
- 0x85340 (full-build step count) and 0x85D10.
- The ASIC readback handling 0x73C46 (current monitoring?).
- No bench data for the EEPROM hold-current curve, so whether 1100 mA always exceeds I_hold(Δp) is not known.

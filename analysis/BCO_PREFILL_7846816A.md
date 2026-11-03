# BCO brake pre-fill: ready-alert (mode A) and wiper-driven disc drying (mode B) (M3 7846816A)

Static analysis only (disassembly `7846816A_main.lst`, calibration read from `flash/bin/7846816A_00000000.bin`,
file offset = CPU address + 0x8000). Nothing here has been bench-confirmed. Function and variable names are ours.
The BCO module contains **two independent request generators**, both submitting arbiter id 17: **mode A**
(`0x6B85E`, pedal-lift "ready-alert" pre-fill, §1–8) and **mode B** (`0x6C090`, wiper-driven brake-disc drying, §9).
Mode A matches the coding menu (byte 13 b4 = A.10 "ready-alert brake"); confidence **medium**. Mode B is
**medium-high**. The exact hydraulic effect of mode A is **[open]**, and its 20 bar target is suspect (§7).

## 1. Mode A behaviour in one paragraph

Each 10 ms loop `bco_main_state_machine` runs the trigger evaluator. When the driver lifts the accelerator fast
enough, with no brake pedal pressure, no stability intervention running and the car inside a speed window, the
state machine asks the pressure arbiter (request **id 17**) for pressure on all four wheels (target as in §7, suspect). It steps
the request in at once, holds it while the go flag holds, then drops it. The intent is to close the caliper/pad
clearance before a likely brake application.

## 2. Functions

Signatures are inferred from register use (M-CORE: args r2..r7, return r2). `sensor_sig_t` is
`{ s16 value; u8 st; u8 st2 }` (see FACTS "Steering-sensor loss"); valid ⇔ `(st & 0x78) == 0x60`, and the getters
below return their `want` argument (1) when valid, else 0, with `st` b7 set when valid.

| Address | Name | Signature | Notes |
|---|---|---|---|
| 0x06B85E | `bco_main_state_machine` | `void (void)` | Calls trigger eval (0x6B280), copies state `0x400EC1`→`0x400EC0`. State 0 idle, 1 active. Calls 0x6B51A, 0x6B6F4, 0x6B490 each loop. Resets via 0x6B254 (state 0, request dropped) when `0x400E9D==1` (inhibit), `0x400EC8==1` (pedal-pressed lockout) or `0x400ECE==1`, or when the go flag is clear. |
| 0x06B280 | `bco_trigger_eval` | `void (void)` | Builds `0x400EC2` flags and the go flag `0x400EBE`. See §3. |
| 0x06B6F4 | `bco_residual_stage` | `u8 (void)` returns `0x400EBA` b6 | Debounce of \|`0x402126`\| against `0x41770`/`0x41774`; sets `0x400EBA` b4/b5 (2-bit phase), b7 (armed), b6 (fired). Needs the lateral getter valid, else resets (b3 set, `0x400EBC`=0). |
| 0x06B6B4 | (helper) | `bool (u16 *timer, u16 limit-ish r3, s16 limit r4)` | Counter compare used by 0x6B6F4 with `0x400EBC` as the timer. Not decoded further. |
| 0x06B490 | `bco_inhibit_eval` | `void (void)` → writes `u8 0x400E9D` | **1 = inhibited**, 0 = OK (0x6B50E `mvc` of the failure branch). See §4. |
| 0x06B436 | `bco_init` | `void (void)` | Latches coding flags `0x400E9B` (A.10) and `0x400E9C` (A.9), zeroes state. |
| 0x06B254 | `bco_reset` | `void (void)` | Zeroes `0x400EC0/C1/9A/9E/9F/C4/C3/BE`, clears `0x400EBA` b6. |
| 0x06B220 | `bco_ramp_step` | `void (void)` | While `0x400EC4 < 0x417A4/10`: `0x400E9E = 0x400E9F = 20`, `0x400EC4++`. |
| 0x06B51A | (diagnostic counters) | `void (void)` | Fills `0x400EA0..EAA`, `0x400ECC/CD` from sensor 0x7F70E; not part of the trigger. |
| 0x06C31C | `pedal_gradient_update` | `void (void)` | Every second call: `0x400F0C = ((prev − now)·100/Δt)/10`-style, prev `0x400F0E` u8 ← `0x401142`. Positive = pedal lifting. Skipped if `0x401157 & 0x0C == 0`. Δt from 0x6C2C8 (field `0x401157` b3:2). |
| 0x0CFCC8 | `coding_A10()` | `u16 (void)` | Bit 10 of `0x4031F4` = byte 13 b4 (ready-alert brake). |
| 0x0CFD60 | `coding_A9()` | `u16 (void)` | Bit 9 of `0x4031F4` = byte 13 b3 (soft-stop assist). |
| 0x08D060 | `driver_mode_is_on` | `u8 (void)` | `0x4049B4[0]` ∈ {1,2,5}. DSC off (mode 0) → 0. |
| 0x08D45C | `driver_mode_get` | `u32 (u8 idx)` | Reads `0x4049B4[idx]`. |
| 0x093E1C | `master_pressure_get` | `s16 (u8 want, sensor_sig_t *out)` | `out->value = 0x401FF8` (master pressure); fitted = `sensor_fitted(5)`; invalid inputs `0x402888` b5, `0x402884` b4. Valid → returns `want`, `st` b7. |
| 0x093C22 | `lat_resid_get` | `s16 (u8 want, sensor_sig_t *out)` | `out->value = (s8)0x402126`; fitted = `sensor_fitted(6)`; invalid inputs `0x402888` b2, `0x402884` b5. |
| 0x0CF5C2 | `sensor_fitted` | `u8 (u8 n)` | `0xF6756[n]`, n ≤ 35 else 0xFF. 5 pressure, 6 lateral. |
| 0x0710FC | `curve_interp` | `s16 (const curve_t *c, s16 x)` | `{lo, hi, n, x[n−1], y[n], slope[n]}`: `y[i] + X·slope[i]/1024`, i = count of x < X, clamped to [lo, hi]. Pedal curve 0x4177A: x {38,62,100,150,200}, y {15,9,11,50,50,50}, slope {269,427,404,0,0,0}. |
| 0x08FFE8 | `ay_axle_est_calc` | `s8 (s16 a, s16 b, s16 c, s16 d)` | `clamp(c + b − (a·yaw_accel 0x402102)>>8, ±1270)/10`, b = low-passed lateral accel, c = yaw²-term. Feeds `0x402126`/`0x402125`/`0x402124` (0x90082/0x90096/…) with a = `0x400AEC` / `0x400AF2` / `0x400AF0`. See §11. |
| 0x0835F0 | `req_slot_store` | `s8 (u8 ch, u32 val, u32 pack)` | Stores a 3-byte tuple + word in the channel table `0x4018F0 + 32·ch`; max 4 entries. |
| 0x0833DA | `req_arbiter_submit` | `(op, id, ch, start, target, rate, flag)` | Used with `id`=17, `op`=1. Rejects if `0x6A8F8(id)`==0 or `0x8338A(id)`==1 — both pass for id 17. |
| 0x06A8F8 | `req_id_enabled` | `s8 (u8 id)` | Returns non-zero for id 17. |
| 0x08338A | `req_id_blocked` | `u8 (u8 id)` | Returns 0 for id 17 (no fault-matrix bit tied to it). |
| 0x0B4312 | `fault_latched` | `bool (u32 id)` | `0x402838[id>>16] & (u16)id`. BCO gate tests ids 35/57/59/61/63 `<<15`. |
| 0x068A6A | `dsc_func_state_get` | `u8 (void)` | Returns `0x404605`. The gate needs it = 3. Meaning **[open]** (state machine 0x68ABA/0x68A70, 0..5). |

## 3. Trigger (`bco_trigger_eval`)

Flags in `0x400EC2` (u8):

| Bit | Meaning |
|---|---|
| b6 | master pressure `0x401FF8` < 300 **and** `master_pressure_get` valid **and** `0x400B09` b5 clear (brake pedal not applied) |
| b5 | no intervention: none of `0x400B0A` b7 (AYC), `0x408DA1` b4 (ABS regime), `0x402FC0` b4 (TCS), `0x400DF4` b7 (DSC) |
| b4 | `0x417C0 < vref(0x408DA8) < 0x417A6` (speed window; image: 60 km/h … 500 km/h, so **BCO is inactive below 60 km/h**) |
| b3 | **trigger** (below) |

Trigger b3 = `!(0x401150 b5)` ∧ ( `(grad_fast ∧ r9)` ∨ `(0x400EBA b6 ∧ r13)` ):

- `grad_fast` = `curve_interp(0x4177A, pedal 0x401142) < 0x400F0C` (stored as `0x400EBA` b2).
- `r9` (**pedal-release path**) = `0x400E9B` (A.10 coded) ∧ `driver_mode_is_on()` ∧ `0xD7156[front code] != 1`.
  → front code 0 only.
- `r13` (**residual path**) = `0x400E9C` (A.9 coded) ∧ `0x41768 != 0` ∧ (`!driver_mode_is_on()` ∨ `0xD7156[front code] != 0`).
  Note: with the DSC *off* the table check is skipped (`bf 0x6B38C`), so this path stays armed. It only fires after
  `bco_residual_stage` sets `0x400EBA` b6, which needs the lateral getter valid.
- Front code = `u8 0x4031AA+3`; `0xD7156` = `s16[2]` = {0, 1}.

Go flag `0x400EBE` = (b3 ∨ `0x400EC3`>0) ∧ `(0x400EC2 & 0x70) == 0x70` ∧ not (`0x400F0C < 0` ∧ `0x400EBA` b6 ∧ pedal < `0x4176A`).
`0x400EC3` counts loops after the trigger, up to `0x41778/10`. Then `0x400EC1` = 1 (state 1).

## 4. Inhibit gate (`bco_inhibit_eval`, `0x400E9D`; 1 = inhibited)

`0x400E9D` is 0 (BCO allowed) only if all of these hold: `0x401150` b5 clear (DME pedal frame valid); `0x402888` b5 clear (pressure OK);
`0x402889 & 0x0F == 0`; `0x402888 & 0x0D == 0` (**steering b0, lateral b2, yaw b3 all valid**);
`0x40288C` b1 and b5 clear; `0x400952[0..3]` b0 clear (no wheel-speed fault); `dsc_func_state_get() == 3`;
fault ids `35, 57, 59, 61, 63` (`<<15`) not latched.

The five fault ids decode to group<<16 | 0x8000: `0x118000` (group 0x11, master-cylinder pressure sensor 1), `0x1C8000` / `0x1D8000`
/ `0x1E8000` / `0x1F8000` (FL / FR / RL / RR wheel pressure sensors). In `dtc_table` (0xF34FC, row = 16·group + bit) bit 15 of
these groups is "hydraulische Leckage": 0x11F → 5DA7 (front or rear axle), 0x1CF → 5D9D (FL, front axle), 0x1DF → also
5D9D (FR is aliased to FL), 0x1EF → 5DBD (RL, rear axle), 0x1FF → also 5DBD (RR aliased to RL). DTC numbers are medium
confidence (table layout, KWP 18 path not traced). **Nothing in 7846816A sets these bits**: no literal, no computed id and
no other writer of `0x402838` reaches them (the pressure-sensor id tables use only bits 0, 1, 6, 8, 9, 11, 12), so these
five checks never inhibit. The same five-id list is tested at 0x6C054 (`bco_dry_inhibit_eval`), 0x82BEC, 0x85CD8 and
0x8CDF4. The only way to see one latched is an EEPROM block 0x31 image that already has the bit (the latch array is
NVM-backed; restore direction not verified). The leak monitor is probably in other variants or compiled out of the M3 build.

## 5. Variables

| Address | Name | Type | Notes |
|---|---|---|---|
| 0x401142 | `pedal_u8` | u8 | from 0x0AA byte 3 (0xFF invalid) |
| 0x401150 | `dme_invalid_flags` | u8 | b5 = pedal invalid |
| 0x401157 | `dme_age_field` | u8 | b3:2 used as time base of the gradient; source **[open]** |
| 0x401FF8 | `master_pressure` | s16 | master cylinder pressure (units as `0x404994`, driver pressure) |
| 0x402126 | `ay_axle_est` (was `ay_resid`) | s8, 0.01 g | model-based axle lateral-acceleration estimate (§11); \|x\| compared with 60 / 20 (code 0) or 87 / 76 (code 1), i.e. about 0.60 / 0.20 g or 0.87 / 0.76 g |
| 0x400F0C | `pedal_gradient` | s16 | prev − now; positive on lift |
| 0x400F0E | `pedal_prev` | u8 | |
| 0x400E9B / 0x400E9C | `bco_cod_A10` / `bco_cod_A9` | u8 | latched coding bits |
| 0x400E9D | `bco_inhibit` | u8 | 1 = a precondition failed (§4) |
| 0x400EC8 | `bco_press_lockout` | u8 | set when `0x400F0C < 0x417A2` (−12, pedal pushed back down) or still counting; cleared when `0x400ECA` ≥ `0x417A8/10`. 1 → reset |
| 0x400ECA | `bco_lockout_cnt` | u16 | loops since lockout set |
| 0x400E9A | `bco_active` | u8 | set to 1 when a request starts; read by 0x68A70 (state 4 → 1 needs it 0) |
| 0x400E9E / 0x400E9F | `bco_req_front0/1` | u8 | ramp value (0 → 20) |
| 0x400EBA | `bco_flags` | u8 | b1 mode on, b2 grad fast, b3 reset, b4/b5 phase, b6 fired, b7 armed |
| 0x400EBC | `bco_debounce` | s16 | |
| 0x400EBE | `bco_go` | u8 | |
| 0x400EC0 / 0x400EC1 | `bco_state_prev/cur` | u8 | 0 idle, 1 request |
| 0x400EC2 | `bco_cond` | u8 | §3 |
| 0x400EC3 | `bco_trig_cnt` | u8 | |
| 0x400EC4 | `bco_ramp_cnt` | u8 | |
| 0x400EC6 | `bco_wait_cnt` | u16 | vs `0x417A8/10` |

## 6. Calibration (BCO block 0x41758, s16, values from the image)

| Address | Value (code 0 / code 1) | Use |
|---|---|---|
| 0x41764 | 500 / 500 | debounce for phase 1 (`0x6B6B4` limit) |
| 0x41768 | 1 | enables A.9 path when non-zero |
| 0x4176A | 12 | pedal level used in the go-flag exception |
| 0x4176C | 400 / 100 | debounce for phase 2 |
| 0x41770 | 60 / 87 | \|ay_resid\| threshold |
| 0x41774 | 20 / 76 | second threshold |
| 0x41778 | 500 | trigger hold (÷10 loops) |
| 0x4177A | curve {lo 0, hi 250, n 6, x…38, 62, 100, 150, 200, …} | pedal → gradient threshold; layout not fully decoded |
| 0x417A2 | −12 | `0x400F0C` below this sets the lockout `0x400EC8` (pedal pushed back down): request dropped, no re-trigger for `0x417A8/10` loops |
| 0x417A4 | 30 | ramp length (÷10 = 3 loops) |
| 0x417A6 | 50000 (read unsigned) | vref upper bound, 0.01 km/h |
| 0x417A8 | 1500 / 500 | wait time (÷10 loops) |
| 0x417C0 | 6000 | vref lower bound, 0.01 km/h → **60 km/h** |
| 0x417B4 | 50 / 150 | % scale on the request when `0x400EBA` b6 |
| 0xDA08D/8E | table bytes, pack of the id-17 request | 0x6B8C2 |

## 7. What it does once triggered (pressure / where / how fast)

State 1 (`0x400EC1` = 1) runs every 10 ms loop in `bco_main_state_machine` (0x6B8A6 onward):

- **Where: all four wheels, not just the fronts.** The code walks `wheel_rec` (0x40BF00 + 0x40·w) twice and
  submits `req_arbiter_submit(op 1, id 17, ch = rec+0x2A wheel index, start 0, target, rate 10000)`.
  Wheels 0 and 1 (FL, FR) take target A = `0x400E9E`·scale, wheels 2 and 3 (RL, RR) take target B = `0x400E9F`·scale.
  `bco_ramp_step` sets both bytes to 20, so front and rear get the same target. (Earlier notes said "wheels 0/1";
  that was the two `req_slot_store` registrations, which are circuits/channels 0 and 1.) Wheel-index order is
  FL, FR, RL, RR.
- **How much / how fast: see the trace below.** Short version: target = `0x400E9E`·scale = 20 × 100 = 2000 in
  0.01 bar = **20.00 bar absolute wheel pressure**, applied in **one 10 ms frame** (rate literal 10000 means "jump
  to target"). On the residual path the scale is `0x417B4[front code]` (50 / 150) → 10 / 30 bar.
- **Ramp:** `bco_ramp_step` writes 20 on the first 3 loops (`0x417A4/10`); there is no gradual ramp, the step is
  instant (rate 10000 = jump).
- **Class:** the id-17 case in the arbiter jump table (0x8354C) sets bit 0 of byte +3 of the slot record; priority
  against ABS (id 1/11/19), AYC (3/20) and TCS is decided by `channel_owner_select` 0x83720 and was not traced.
  While ABS/TCS/DSC/AYC are active, trigger bit b5 is clear anyway, so BCO is not requested then.
- **How long:** while the go flag holds. The trigger bit is held for `0x41778/10` = 50 loops (≈ 0.5 s) after the
  pedal event, via the counter `0x400EC3`. It drops at once when any of these occurs: master pressure ≥ 3.00 bar or
  the pedal switch (`0x400B09` b5), an intervention starts, vref leaves 60–500 km/h, DME pedal invalid, inhibit gate
  trips, or the pedal is pushed back down (gradient < −12 → lockout `0x400EC8`, which also blocks a re-trigger for
  `0x417A8/10` loops = 1.5 s code 0 / 0.5 s code 1). Dropping runs `bco_reset` and ends the request.
- **Hydraulics:** the request goes through the normal pressure arbiter, so the pump runs for it only if the
  pump/valve logic accepts a demand with no ABS/TCS active (FACTS notes the pump can run with ST_CLCTR = 0, but this
  was not traced for id 17).


### Trace: cal → wheel pressure demand (unit 0.01 bar at the end)

| Step | Where | What |
|---|---|---|
| 1 | `bco_ramp_step` 0x6B220 (`6141 movi r1,20` at 0x6B234) | `0x400E9E` = `0x400E9F` = **20** (hard-coded, not calibration) |
| 2 | 0x6B8B0 (`664D movi r13,100`) | scale = **100** (hard-coded). If `0x400EBA` b6: `0x417B4[front code]` = 50 / 150 |
| 3 | 0x6B8E2 / 0x6B91A (`mult r9,r13`, `mult r11,r13`) | target_front = 20·scale, target_rear = 20·scale. **No divide by 100.** |
| 4 | 0x6B928 → `req_arbiter_submit` 0x833DA | per wheel: op 1, id 17, ch = rec+0x2A, start 0, target, rate **0x2710** |
| 5 | 0x833DA tail (0x83598…) | slot in `wheel_req` 0x401728 + 56·w, slot k at +8+12k: +0 id, **+4 start/current**, +6 rate, **+8 target** (all s16), +10 flag |
| 6 | `req_slot_step` 0x83F26 (called from 0x83FEC → writes `0x401A2A[id]`) | if rate == 0x2710: rate := target − current, so current := target. Other rates are in **0.01 bar per 10 ms frame** (ABS 300 = 3 bar/frame, apply ramp 400); ±8000 / 9000 are also "jump to target" |
| 7 | `channel_owner_select` 0x83720 | id 17 becomes owner (`0x401960[w]`) when slot byte +3 b0 is set (case 17 of the jump table at 0x834AC). Later rules override, so ABS/AYC/TCS ids outrank it |
| 8 | 0x83FEC tail (0x84050) | `0x4019FE[w]` = `0x401A2A[owner]`; this is `arbiter_channel_output` (0x836C8) |
| 9 | ABS/valve code | `0x4019FE` and the driver pressure (`0x404994`, which the arbiter itself submits as id 0, target = driver pressure at 0x8428C) are in the same domain: **0.01 bar** (pinned by CAN 0x2B2 / 0x19E ÷ 100 = bar) |

So the code as read asks for 20 bar at all four wheels immediately. There is **no pressure clamp** between step 3
and the valve loop that I found (0x83FEC applies the output as is). Cross-checks: the AYC front-outer pre-fill id 20
uses 500 (5 bar) in the same units, and the 1M firmware (7846411A, 0x6B95C… `movi r13,100`, `mult r9,r13`,
rate 0x2710) has identical code, so this is not an M3-specific change.

Why it may still be wrong: (a) the cal `0x417B4` is described as "% scale", which suggests a divide by 100 that the
code does not contain (20 × 100 % = 2000 would then be a missing `/100`, giving 0.20 bar = a plausible slack take-up
pressure); (b) 20 bar on all four wheels would give a clearly noticeable drag (~0.2 g). Neither is proven. The
direct test is to log `0x401A2A` (id 17 entry, i.e. `0x401A2A + 2·17`) and `0x4019FE[0..3]` during a trigger.

Patch levers (untested):

| Where | Was | Now | Effect |
|---|---|---|---|
| 0x6B234 (file 0x73234) | `6141` movi r1,20 | `6031` movi r1,3 | base 20 → 3: pedal path 3.00 bar, residual path 1.5 / 4.5 bar |
| 0x6B8B0 (file 0x738B0) | `664D` movi r13,100 | `60FD` movi r13,15 | pedal-path scale 100 → 15: 3.00 bar (residual path unchanged) |

## 8. Does it work with DSC off, or with only DME frames?

- **DSC off (switch or 0x398 → mode 0): no.** The A.10 pedal-release path requires `driver_mode_is_on()`.
  The A.9 path stays armed in mode 0 but needs the lateral/yaw residual stage, so it is dead without those sensors.
- **Only DME frames:** the inhibit gate (§4) trips on `0x402888 & 0x0D` as soon as steering, lateral or yaw are
  invalid, so nothing runs. Residual dependencies after that: pedal gradient needs `0x401157` b3:2 ≠ 0 **[open]**,
  `dsc_func_state == 3` **[open]**, and the front code must be 0 (or patch `0xD7156`).

### Minimal patch set (untested)

| Where | Was | Now | Effect |
|---|---|---|---|
| 0x6B34A (file 0x7334A) | `7FA3` jsri driver_mode_is_on | `6012` movi r2,1 | A.10 path no longer needs DSC on |
| 0x6B314 (file 0x73314) | `7FB1` jsri driver_mode_is_on | `6012` movi r2,1 | keeps `0x400EBA` b1 consistent |
| 0x6B4AC (file 0x734AC) | `2ED2` andi r2,13 | `2E02` andi r2,0 | gate ignores steering/lateral/yaw invalid |
| 0xD7156 (file 0xDF156) | `0000 0001` | `0000 0000` | force front-code-0 behaviour if the car is coded 1 |

Also needed: coding byte 13 b4 (A.10) set, a valid 0x0AA pedal with a running alive counter, `0x401157`
behaving as above, and `0x404605 == 3`. Check these on the bench by logging `0x400EC2`, `0x400E9D`, `0x400EBE`,
`0x400F0C`, `0x401157`, `0x404605` during a fast lift. After editing, re-sign (`tools/bmy_resign.py`).
**[open]** whether the id-17 request actually reaches the valves and pump with the DSC off; the arbiter
accepts it, but the downstream pump/valve path was not traced.

## 9. Mode B: wiper-driven brake-disc drying (`bco_dry_main` 0x6C090)

Static analysis only. A second, independent state machine in the same module also submits arbiter **id 17**, so it
shares the owner slot with mode A (§1–7). It is called separately from mode A (`0x6B85E`) and has its own RAM
(`0x400ED0…0x400F04`). Confidence: **high** on structure, **medium** on the wiper-code meaning. Everything below was
decoded from `0x6BAE8`, `0x6BBBE`, `0x6BCFE`, `0x6BFCC`, `0x6BFFE`, `0x6C090`.

### Inputs (what it needs)

- **Wiper state.** `bco_dry_wiper_decode` 0x6BBBE builds `0x400EDD` b4 (= wipers active) and b3:2 (= level 0..3):
  - `0x402E4C` bits 7:5 = 3-bit state from **F-CAN 0x2A6 byte 0** (`fcan_rx_2A6_byte0` 0xC630A); b1 = invalid/timeout.
  - value 2 → level 1, value 3 → level 2, value 1 → use **PT-CAN 0x226 byte 0** (`0x404714`) as a code:
    `0x00` off, `0xAA` level 1, `0xFD` level 2, `0x55` level 3, anything else off. 0 or invalid → off.
  - BMW names for 0x2A6 / 0x226 are not confirmed; the fit to a wiper/rain status is strong (cal "enable mode"
    `0x417C2`: 0 = disabled, 1 = needs wiper active, 2 = always on).
- **Speed.** vref `0x408DA8` (0.01 km/h). Accumulates above 70 km/h (`0x41824` = 7000); request window 82 km/h
  (`0x41826` = 8200) to 500 km/h (`0x417FE`, 50000 unsigned).
- **Outside temperature.** `0x4046E0` (CAN 0x310 byte 0). `0x7D1F6` returns `400 − 3·raw`; if that is below
  `0x417CE·10` (= 50) and the temperature is valid (`0x7D206` = 0), the thresholds are scaled by `0x417C6` = 50 %
  instead of 100 %. With raw = 2·T + 80 this is T > about 18 °C, so warm rain halves the exposure needed.
  (Interpretation of the raw scaling is medium confidence.)
- **Pedal.** `0x401142` > `0x417CA` (25) and valid, and gradient `0x400F0C` < `0x417C8` (38): the driver is on the
  throttle and not lifting.
- **Brake / stability.** master pressure < 300 and valid and `0x400B09` b5 clear; no ABS/AYC/TCS/DSC intervention
  and mode A inactive (`0x400E9A` = 0). **No `driver_mode_is_on()` check, so it works with DSC switched off.**
- **Inhibit gate** `bco_dry_inhibit_eval` 0x6BFFE → `0x400EEA` (1 = inhibited): the same list as mode A (§4)
  with one addition, `0x402E4C` b1 (wiper signal invalid) must be clear. It still contains `0x402888 & 0x0D`
  (steering / lateral / yaw), `0x404605 == 3` and the fault ids 35/57/59/61/63.

### Condition word `0x400EDC` (`bco_dry_cond`, built in `bco_dry_cond_eval` 0x6BCFE)

| Bit | Meaning |
|---|---|
| b7 | wiper enable: `0x417C2` = 0 → 0, 1 → `0x400EDD` b4, 2 → 1 |
| b6 | master pressure < 300, valid, pedal switch (`0x400B09` b5) clear |
| b5 | no intervention and `0x400E9A` = 0 |
| b4 | 82 km/h < vref < 500 km/h |
| b3 | pedal 25 < p valid and gradient < 38 |
| b2 | distance accumulator `0x400ED0` > threshold (below) |
| b1 | `0x400EDE` = 2 (request finished) |

Derived: `0x400ED6` = b7∧b6∧b5 (arm), `0x400ED7` = ¬(b6∧b5) (abort), `0x400ED8` = arm ∧ b4 ∧ b3 ∧ b2 (fire),
`0x400ED9` = ¬fire ∨ b1 (end).

### Accumulator (`bco_dry_exposure_update` 0x6BAE8)

`0x400ED0` (u32) adds `10·vref/3600` per 10 ms loop while vref > 70 km/h and subtracts it (floor 0) below, so it
integrates "wet driving at speed". Threshold = cal × scale, with the cal picked by wiper level: level 1
`0x417CC` = 1500, level 2 `0x417C4` = 1000, level 0/3 `0x41828` = 2000, each × 100 × scale/100.
At 100 km/h that is about 2780 counts/s, so the request becomes due after roughly 54 s (level 1), 36 s (level 2)
or 72 s (level 0/3) of continuous wet driving; 50 % scale halves these. `0x400ED4` = `0x400ED0`/10 (diagnostic).

### State machine (`0x400EDB`)

0 idle → 1 when `0x400ED6`; state 1 accumulates (when b7) and goes to state 2 on `0x400ED8` (sets `0x400EE6`);
state 2 requests pressure; any of `0x400ED7`, `0x400ED9` (end) or `0x400EEA` = 1 or `0x417C2` = 0 resets
(`bco_dry_reset` 0x6BB5E). After a request, `0x400EDE` = 1 while counting `0x400EE0` and 2 once
`0x400EE0` > `0x41800/10` (3000 ms → 300 loops), which ends it. So **one request lasts up to 3 s**.

### What it requests

`bco_dry_target` 0x6BFCC: `0x400EE8` = ((`curve_interp`(`0x417D0`, vref) / 100) · `curve_interp`(`0x41802`, `0x400EE0`·10)) / 10.

Curve layout (decoded from `curve_interp` 0x710FC): `{lo, hi, n, x[n−1], y[n], slope[n]}`, output
`y[i] + X·slope[i]/1024` clamped to [lo, hi], with i = number of x < X.

| Curve | Result |
|---|---|
| vref `0x417D0` (hi 15000) | 0 + v·125/1024 up to 8200 (≈ 1000 at 82 km/h), then 1152 at 100 km/h, 1280 at 120, 1402 at 150, 1457 at 180, 1496 at 272 km/h and above |
| time `0x41802` (percent, hi 100) | rises to about 75 at 0.2 s, 100 from about 0.3 s to 1.8 s, then ramps down to about 1 at 3.0 s, 0 after |

So the target is **1.00 bar at 82 km/h rising to a peak of 1.40 bar at 150 km/h and above** (steps because `B/100` is an
integer 10..14), shaped by the time profile below. **Front wheels only**: the first loop submits the target to wheels 0 and 1, the second loop
submits target 0 to wheels 2 and 3 (`req_arbiter_submit(1, 17, w, 0, target, 10000)`).

### Decoded output of `bco_dry_target` (`0x400EE8`, 0.01 bar)

`0x400EE8` = ((`B(vref)` / 100) · `A(t)`) / 10 with truncating division. `t` = `0x400EE0`·10 ms (EE0 counts one per 10 ms
loop from 0 and ends the request after 300 loops). `B` = curve 0x417D0 (vref in 0.01 km/h), `A` = curve 0x41802
(percent). Evaluated with `curve_interp` exactly as in the code (values checked against the image):

`B(vref)`: 82 km/h 1000 → B/100 = 10; 90 → 1069 (10); 100 → 1152 (11); 120 → 1280 (12); 150 → 1401 (14); 180 → 1449 (14);
272 → 1495 (14).

`A(t)` percent: 0 ms 0; 50 ms 18; 100 ms 37; 200 ms 75; 300 ms 76; 500 ms 80; 1000 ms 90; 1500 ms 100; 1800 ms 100;
2000 ms 84; 2400 ms 51; 2800 ms 18; 3000 ms 1; > 3000 ms 0.

`0x400EE8` in 0.01 bar (rows vref km/h, columns t ms):

| vref \ t | 0 | 100 | 200 | 300 | 1000 | 1800 | 2200 | 2600 | 3000 |
|---|---|---|---|---|---|---|---|---|---|
| 82 | 0 | 37 | 75 | 76 | 90 | 100 | 68 | 35 | 1 |
| 100 | 0 | 40 | 82 | 83 | 99 | 110 | 74 | 38 | 1 |
| 120 | 0 | 44 | 90 | 91 | 108 | 120 | 81 | 42 | 1 |
| ≥ 150 | 0 | 51 | 105 | 106 | 126 | 140 | 95 | 49 | 1 |

Because rate is 10000 (jump to target), the commanded front pressure follows this table frame by frame:
0 at the first frame, about 0.4–0.5 bar after 100 ms, about 0.8–1.05 bar by 200 ms, about 0.9–1.3 bar at 1 s, the peak
1.0–1.4 bar at 1.5–1.8 s, then a linear fade to about 0.01 bar at 3 s. Rear wheels get 0.

### Decoded output of `bco_ramp_step` (mode A, the closest equivalent)

`bco_ramp_step` 0x6B220 has **no shaping at all**. On each call while `0x400EC4 < 0x417A4/10` (30/10 = 3) it writes the
immediate constant 20 to `0x400E9E` and `0x400E9F` and increments the counter. It reads no curve, speed or time. Both bytes then
stay 20 until `bco_reset`. The state machine multiplies them by the scale:

| Path | Scale | Target per wheel (0.01 bar) | All four wheels |
|---|---|---|---|
| pedal release (A.10) | 100 (hard-coded at 0x6B8B0) | 2000 | yes |
| residual (A.9), front code 0 | `0x417B4[0]` = 50 | 1000 | yes |
| residual (A.9), front code 1 | `0x417B4[1]` = 150 | 3000 | yes |

Contrast with mode B: B has a speed curve, a 3 s time profile, `/100` and `/10`, and drives the fronts only; A is a constant
step to 10–30 bar on every wheel with no time or speed dependence. If mode A was meant to follow the same recipe, the missing
`/100` (or `/10`) is the obvious candidate; a `/100` would give 0.20 / 0.10 / 0.30 bar, a `/10` would give 2.0 / 1.0 / 3.0 bar.

### Why this matters for mode A

Mode B writes its pressure with an explicit `/100` and `/10`, giving 1.0–1.4 bar in the same units. Mode A has no such
scaling and results in 20 bar (§7). That is a further hint that §7 may contain a unit mismatch, but nothing in the
code proves it.

### With only DME frames (standalone)

- Works with DSC off (no `driver_mode_is_on`).
- Needs a **wiper signal**: F-CAN 0x2A6 byte 0 (3-bit state) and, for state 1, PT-CAN 0x226 byte 0; plus outside
  temperature 0x310 for the threshold scale (an invalid temperature leaves scale 100 %).
- Is blocked by the same `0x402888 & 0x0D` (steering / lateral / yaw) inhibit as mode A, so the patch at
  `0x6C022` (`2ED2` → `2E02`) is needed without those sensors.
- **Needs the disc-drying coding bit.** `bco_dry_init` 0x6BB82 (reached by a `jmpi` from 0x68A00) sets `0x400EE7` =
  (`coded_feature(18)` == 1), and `bco_dry_main` does nothing while it is 0. `coded_feature(18)` is **coding byte 13 bit 5** ("brake-disc drying"): `coding_feature_combo_check` 0xD024C requests
  feature-word 2 bit 1 when c13 b5 is set, and `coded_feature` case 18 tests word 2 bit 1 (verified in code). Cal `0x417C2`
  is a second gate (0 = off). The flag-word-A bit 11 getter `0xCFD0A` is **A.11 (GMB, c14 b5)**, a different thing, read only by
  `abs_front_split_detect` (0x53FFC). An earlier version of this document said the code was gated by the cal only, and
  another called bit 11 "disc drying"; both were wrong. `0x400EE7` also feeds the CAN status
  `0x7B668` (drying state 0 / 1 / 2).

## 10. Apply / hold / release in plain English

Static analysis only; times are for the 10 ms loop.

### Mode A (pedal lift)

- **Apply.** On the first loop where the trigger and all conditions are true, the full target is requested on all four
  wheels at once (rate 10000 = jump to target). There is no ramp-in in the BCO code. Target as in §7 (pedal path 2000 = 20 bar, suspect).
  The residual (A.9) path first needs the yaw-model residual high for 0.5 s and then quiet for 0.4 s (code 0; 0.1 s for
  code 1) before it fires.
- **Hold.** The trigger is held for `0x41778/10` = 50 loops (about 0.5 s) after it first fires (`0x400EC3`), and longer if the
  lift is still fast. The request is re-submitted every loop with the same target.
- **Release.** There is no ramp-down in the BCO code. It ends when: the hold timer expires and the trigger is gone; master
  pressure reaches 3 bar or the pedal switch trips; ABS/AYC/TCS/DSC starts; vref leaves 60–500 km/h; the DME pedal goes
  invalid; the inhibit gate trips; or the pedal is pushed back down (gradient below −12, which also sets a lockout).
  Then `bco_reset` zeroes the targets and the state, and BCO stops submitting.
- **Re-arm.** After any reset it cannot start again for `0x417A8/10` loops: 1.5 s (front code 0) or 0.5 s (code 1).

### Mode B (wiper-driven drying)

- **Apply.** Once the exposure counter is due and every gate is true, the target follows the time curve from 0:
  about 0.4–0.5 bar at 0.1 s, 0.75–1.05 bar at 0.2 s. The ramp-in is the curve itself (about 0.2 s), not a rate limit.
- **Hold.** About 0.9–1.3 bar at 1 s and the peak (1.0 bar at 82 km/h, 1.4 bar from 150 km/h) from 1.5 to 1.8 s.
- **Release.** A linear fade from 1.8 s down to about 0.01 bar at 3.0 s, when the request ends. It is cut immediately if
  the driver brakes (3 bar or pedal switch), an intervention starts, vref leaves 82–500 km/h, the throttle drops to 25 raw
  or below or is lifted fast (gradient 38 or more), the wipers stop, or the inhibit gate trips.
- **Re-arm.** The reset zeroes the exposure counter, so the next drying event needs the full wet-driving exposure again
  (about 36–72 s at 100 km/h).

### Open: does the arbiter slot disappear on release?

Neither mode ever calls the arbiter to remove its id-17 slot; they just stop submitting. What the arbiter does with a slot
that is no longer refreshed was **not** established. The slot table (`0x401728`, 4 slots per wheel) is only cleared by
`0x830A2` (called from the test-mode cycle) or when a higher-`op` request re-initialises the wheel record (`0x8308C`),
and I did not find a per-frame clear. If stale slots persisted, the last target would keep being commanded. That cannot be
the intended design (ABS ids would fill the table), so a clear path probably exists that I haven't found. Log
`0x401A2A + 2·17` and `0x4019FE[0..3]` after a trigger to settle it.

Arbiter priority also matters: `channel_owner_select` ranks id 17 below the driver's own request (id 0), ABS (1/11/12),
AYC (3), TCS and others, and above only ids 20 and 16. While anything higher is the owner, BCO's request is not what the
wheel follows.

## 11. The "yaw-model residual" `0x402126` decoded, and what it does in a corner

`sub_09001E` (called each 10 ms from the cluster conditioning) builds three signed bytes. Inputs:

- `ay_lp` `0x40212C` = IIR of the offset-corrected lateral acceleration `0x4020DA` (1 mg): `new = ay + (old − ay)·189/256`
  (time constant about 40 ms).
- `ψ̇` `0x402100` (yaw rate, 1/20000 rad/s) and yaw acceleration `ψ̈` `0x402102` (`abs_yaw_accel_get`).
- Model coefficients from `vehmodel_load_axle_derived` 0x5E424: `0x400AEC`, `0x400AF0`, `0x400AF2` (axle-derived gains,
  `10000·(table ± ...)/1916` from the per-variant tables, constants for a given car) and `0x400AEE`.

Result: `s = clamp( c + ay_lp − (a·ψ̈)/256 , ±1270 ) / 10` with `c = (ψ̇/256)² / 0x400AEE`, one result per coefficient `a`
(`0x402126` ← `0x400AEC`, `0x402125` ← `0x400AF2`, `0x402124` ← `0x400AF0`). Units: mg / 10 = **0.01 g**.

So it is a model-based estimate of an axle's lateral acceleration (measured `ay` combined with the yaw-acceleration and
yaw-rate terms from the single-track model). Which axle `0x402126` is (front or rear) is not established. The name
"residual" was misleading: it does not subtract the measured `ay` from a prediction, and with `ψ̈ ≈ 0` it is roughly `ay`
itself. In steady cornering it is therefore large, near the cornering g; going straight it is near zero.

### Behaviour in a corner

- **Residual (A.9) path: yes, it is a cornering detector.** It arms after `|s|` has stayed at or above `0x41770` for 0.5 s
  (`0x41764`), then fires after `|s|` has stayed at or below `0x41774` for `0x4176C` ms. Front code 0: arm at about 0.60 g,
  fire after about 0.20 g for 0.4 s. Front code 1: arm at about 0.87 g, fire after 0.76 g for 0.1 s. Between the two
  thresholds the timer counts back down (it does not reset). So in plain terms: hard cornering for half a second, then
  the car straightens up (or just eases off) and the request fires. It needs the lateral and yaw signals valid; without
  them `bco_residual_stage` resets every loop and this path never fires.
- **Pedal-release (A.10) path: no direct lateral-g condition.** It does not read `0x402126`. A fast lift in a corner
  fires it like on the straight, provided no ABS/AYC/TCS/DSC intervention is active (those block it through
  `0x400EC2` b5). The one cross-link: if the residual path has fired (`0x400EBA` b6 set) the pedal path uses the
  residual scale `0x417B4` (50 / 150) instead of 100.
- The throttle-lift trigger and the corner trigger are alternatives: the trigger is
  `pedal-fast-lift AND A.10 AND DSC on AND front code 0`, OR `residual-fired AND A.9`.

### Hold timer (pedal path)

`0x41778` = 500 (ms, one value, not code-indexed). The state machine divides it by 10 (50 loops). `0x400EC3` counts loops
while the go flag is set; the request is held until the count exceeds 50 (about 0.51 s). At expiry the counter is cleared. On the
residual path (b6 set) that also calls `bco_reset`, so the request ends. On the pedal path it only clears the counter, so
the request continues only if the trigger (pedal gradient above the curve) is still true on that loop; otherwise go drops and
BCO resets. The gradient is updated every second loop and held in between.

## 12. Which trigger runs on which brake code, and what it is probably for

Front pressure-model code (user-confirmed hardware): **code 0 = M3** (floating calipers), **code 1 = M3 GTS / CRT**
(larger rotors, fixed 6-piston calipers).

With the DSC mode on:

| Front code | Pedal-lift path (A.10) | Post-corner path (A.9) |
|---|---|---|
| 0 (M3) | enabled | disabled (cleared when `0xD7156[code] == 0`) |
| 1 (GTS/CRT) | disabled | enabled (needs `0x41768 != 0`) |

With the DSC mode off, the pedal-lift path is always disabled, and the post-corner path stays armed on either code if A.9
is coded (the table check is skipped on that branch of the code; this looks unintended).

Tuning per code (cal block 0x41758): arm / release thresholds 60 / 20 (M3) vs 87 / 76 (GTS) in 0.01 g; fire debounce 400 ms
vs 100 ms; scale 50 % vs 150 %; re-arm lockout 1.5 s vs 0.5 s.

**Probable purpose (inference, not in the code): pad knock-back compensation.** Sustained high lateral load flexes the
hub, caliper and rotor and pushes the pistons and pads back, so the next application has a long, soft first part of pedal
travel. A pre-fill when the lateral load comes off re-seats the pads before the driver reaches the brakes. That fits a
trigger of "at or above about 0.6 g (M3) / 0.87 g (GTS) for 0.5 s, then relaxed". The larger scale and the higher thresholds
on the GTS fit fixed calipers on bigger rotors, which knock back more and corner at higher g. The lift-off pre-fill on the M3
takes up the clearance ahead of a likely braking event. The requested 10 to 30 bar looks far larger than re-seating needs
(see §7), which is another reason to suspect a unit or scale problem. The NCS label "soft-stop assist" for A.9 does not match
this behaviour and should not be relied on.

## 13. Patches

Three experiment patches live in `../mk60e5_patcher` (profiles `bco_liftoff_force`, `bco_liftoff_track`, `bco_antiknock`, and
the combination `bco_track_all`): force the lift-off BCO to fire for observation; retune it for a track car (any lift above
10 km/h, 5 bar, 1 s); and turn the drying mode into a fixed 20 s anti-knock-back pulse. They are byte patches only
(addresses in this document). The anti-knock-back patch takes its interval from the profile param `antiknock_interval_s` (default 20; thresholds
0x417CC / 0x417C4 / 0x41828 = 10 per second) and, as a test, sets the signed cals `0x41824` (accumulate above) and
`0x41826` (request window floor) to -1 so it works at standstill (vref >= 0 passes `vref > -1`). The pulse height is
still the speed curve 0x417D0, which is 0 at 0 km/h, so a stopped car runs the sequence but requests about 0 bar.
`bco_liftoff_enable` adds the DSC-off and no-chassis-sensor enablers. The lift-off
patches keep the A.10 coding and front-code-0 requirements unless noted.

## 14. Where the BCO coding bits are in the raw 48 bytes

All from `coding_pack_flag_words` 0xCFF1A and `coding_feature_combo_check` 0xD024C (full map in
`CODING_BYTES_7846816A.md`, "Flag word A bit map"). Byte numbers are the payload bytes of the `2E 30 00` write (EEPROM
0x400 + n); byte 0 is the checksum and must be recomputed after any edit.

| Function | Raw bit | Mask | Read by |
|---|---|---|---|
| Lift-off pre-fill, A.10 ("ready-alert brake") | **byte 13, bit 4** | `0x10` | `bco_init` via flag word A bit 10 (0xCFCC8) |
| Post-corner pre-fill, A.9 (NCS "soft-stop assist") | **byte 13, bit 3** | `0x08` | `bco_init` via flag word A bit 9 (0xCFD60); nothing else reads it |
| Wiper-driven disc drying | **byte 13, bit 5** | `0x20` | `coded_feature(18)` → `bco_dry_init` |
| Front pressure-model code (selects lift-off vs post-corner with DSC on) | **byte 2, bits 3-5** | `0x38` | f+3 (0 = M3, 1 = GTS/CRT) |
| Rear pressure-model code | byte 2, bits 0-2 | `0x07` | f+4 (unused by BCO) |
| Related, not BCO: GMB (A.11) | byte 14, bit 5 | `0x20` | `abs_front_split_detect` |
| Related, not BCO: hill-start assist | byte 13, bit 6 | `0x40` | `coded_feature(11)` |

The NCS label for A.9 ("soft-stop assist") does not describe what the bit does in this firmware. The soft-stop module
(0x6ACC6, arbiter id 18) is gated by cal `0x4182A`, not by the coding. Note that bits 3, 4 and 5 of byte 13 sit next to the
steering-ratio select in bits 0-2.

## 15. DME status nibble watched by mode A (`bco_dme_status_monitor` 0x6B51A)

`0x6B51A` runs every loop from `bco_main_state_machine` and fetches signal 0 (`rx_sig_fetch(0)` 0x7F70E), which is
`0x40470C`: the 4-bit field at **0x0AA byte 6 bits 4-7** (`can_rx_0AA_nibble`, sig 130; a received 15 is stored as 8). It
keeps two saturating counters:

- `0x400ECC` (ECC) goes up by 1 and `0x400ECD` (ECD) down by 1 per loop while the value is 8, 9 or 11; the reverse for any
  other value.
- ECC reaching 100 clears both counters and `0x400ECE` (ECE) (no event). ECD reaching 100 sets **ECE = 1 for one loop** and clears both.
- If the field is invalid (no fetch, or status bit 5 set after a timeout) ECE is 0.

`bco_main_state_machine` resets mode A (`bco_reset`) whenever ECE = 1 (together with `0x400E9D = 1` and `0x400EC8 = 1`).
So if the DME sends a value outside {8, 9, 11} for about a second (for example 0, the value a minimal fake frame would
carry), mode A is reset once a second: an active request is cut and the re-arm lockout (`0x417A8/10` loops) starts. Sending 8
keeps ECE at 0. Mode B does not use this monitor. Meaning of the nibble on a real DME: unknown (the monitor suggests 8/9/11 are
the normal states).

Only the 0x0AA frame is needed for the other DME inputs of mode A: pedal (byte 3), the pedal-validity flag (`0x401150` b5, set only
by a 0xFF pedal), the gradient time base (`0x401157` bits 3:2 = alive-counter step of 0x0AA, from `can_rx_0AA_alive` 0x7BD44) and
this nibble. A missing 0x0A8 / 0x0A9 raises D354 / D355 after 500 ms and the group-A fault reactions (`0x402880`, `0x40288E`), but
none of the BCO conditions or the inhibit gate (`0x402888`, `0x402889`, `0x40288C`, `0x404605`, fault ids 35/57/59/61/63) read those, per
FACTS "Not affected by DSC-off or the DME timeout". `0x404605` was not traced back to its source and should be checked on the bench.

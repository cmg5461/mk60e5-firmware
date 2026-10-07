# MK60E5 7846816A (E9x M3) — ABS edge cases, modifiers & coding-variant effects

CPU addresses; file offset = CPU + 0x8000 = XDF address. Curve record `[lo,hi,n, x[n-1], c[n], k[n]]` s16,
`y = clamp(c[i] + (x*k[i])>>10, lo, hi)`, reader `0x710FC`. Units: speed/slip 0.01 km/h, decel/g 0.01 g,
pressure 0.01 bar (pinned by CAN 0x2B2 ÷100 = bar). Evidence tags: **CONFIRMED** (read from bytes/opcodes here) /
**INFERRED** (interpretation) / **UNCONFIRMED** (not resolved). Scope: **ABS only** — kept distinct from
DSC/TCS/AYC except where an AYC signal explicitly feeds the ABS pressure loop.

Companion: `analysis/ABS_ALGORITHM.md`, `analysis/7846816A_symbols.md`, agents `m3abscore/`, `m3absslip/`,
`absevent/`. Cross-checked against `xdf/MK60E5_7846816A.xdf`.

---

## 1. mu-split / yaw-moment-build limiting ("GMA")

**Mechanism = decision code 32 ("yaw/lateral-limited build"), applied per wheel on the pressure-building
(high-grip) side, scaled by lateral acceleration.** This is BMW's Giermomentenaufbau-Begrenzung analogue.

- **Who sets code 32:** `abs_pair_logic 0x54D9A`. The axle is handled as a pair (front 0/1, rear 2/3,
  partner = `wheel ^ 0x40` in the record pointer). When the **partner** wheel is in ABS dump (its rec[0]
  bit5 set, tested at `0x54E1E`) **and** the partner's commanded pressure `0x408F42[w]` exceeds this wheel's
  command `0x408F22[w]` (`0x54E40`), it writes `0x408DDE = 32` (`0x54E44–0x54E48`). CONFIRMED.
  - If instead this wheel's command has fallen below 0.60× the partner's saved level, it writes code **1024**
    (reapply nudge, `0x54EAE`, uses cal `0x40D90`=**80**) or code **16** (stepped reapply, `0x54F00`,
    DDE+4 = `0x40D90`). CONFIRMED.
- **How code 32 limits the build:** `abs_decision_pressure_exec 0x58FF4`, code-32 arm at `0x59064`:
  - reads lateral accel `0x408ECA` through `sub_06D0CC` (abs). **If |lat| < 40 counts → skip (exit, no
    build)**. If **|lat| > 80** → add one **+80**-count pressure step toward cap **0x61A8 = 25000**
    (`0x5908A–0x590C4`). If **40 < |lat| ≤ 80** (and the other |lat|>65 branch) → a gated, smaller step.
    CONFIRMED. Build step **80** and cap **25000** are code literals (patch-only, not cal).
  - Net effect: the high-grip wheel's pressure is **released toward the partner's low-mu level and then rebuilt
    in small +80 steps, and the rebuild is throttled by how hard the car is cornering** (lateral-g). More
    lateral g → larger permitted step; below ~40-count lateral the staged build is suppressed entirely so the
    yaw moment is held. INFERRED (behavioral reading of CONFIRMED code).
- **AYC→ABS yaw-deviation feedback** reinforces this: `abs_yaw_deviation_monitor 0x4A254` computes
  `e = measured_yaw 0x408ECC − target 0x400B1A` (AYC observer target), writes `0x408E9C/0x408EA2`, and runs a
  **persistence counter `0x408EA6` (cap ~20, `0x4A364`)** driven by a gain curve at **`0x40C5A`** (ABS cal,
  x = lateral accel via `0x6D0CC`; `[lo0,hi3490,n9, x:20,45,62,80,100,130,150,200 …]`). CONFIRMED.
  - The reapply handler `0x4B680` clears the restriction bit (`0x40903A` b4) only when `0x408EA6 < 15`
    (`0x4B9C2–0x4B9D2`). So **while yaw deviation persists (counter ≥ 15) the pressure rebuild on that wheel
    stays restricted.** CONFIRMED.
- **Rear-axle cornering clause:** `abs_pair_cornering_rear 0x54BE8` gates rear select-low by a lateral value
  (`lat = 0x408ECC + 0x408ECE/2`) against cal **`0x40DD2 = 1748`** (`[1748,1399,1047]` + curve `0x40DD8`
  `[lo0,hi4000,n3, x:50,100, c:2000,2000,1750, k:10240,10240,12800]`). CONFIRMED values.

**Governing cal (all ABS block):** `0x40C5A` (yaw-dev gain), `0x40D90`=80 (pair reapply step),
`0x40DD2`=1748 (+curve `0x40DD8`) rear cornering, entry-slip `0x40DB6`. Build step/cap (80/25000) and the
lateral gates (40/65/80) are **ROM code literals, not tunable cal**.

---

## 2. Low-mu vs high-mu adaptation (per-wheel deep-slip flag)

There is **no continuous surface-µ estimator in the ABS path and no µ-indexed slip-target remap.** Adaptation
is a **per-wheel "deep-slip / low-grip" flag** plus the speed/g-dependent decel-threshold shaping (§5).

- **Flag:** `0x40902E[w] bit4`, sole writer `abs_lowmu_flag_update 0x4F9D4`. CONFIRMED.
  - Input is a **peak wheel-speed-drop counter** `0x409010[w]`: `wheel_speed_history_diff(0x403296)/40`,
    clamped 0..200, running-max (writer `0x585C0–0x585D2`). `0x40900C[w]` is the instantaneous value.
    CONFIRMED (this is a lock-depth measure, **not** a filtered µ).
  - Flag set when peak counter `0x409010[w] ≥ 0x40D40` (**50**) with the vehicle under braking
    (driver pressure `0x408EB2 > 0x40D42` = **7000** ≈ 70 bar) and `vref 0x408DA8 < 80 km/h` (8000) /
    gated by `0x408E6D` b6, `0x408DC6` b2. CONFIRMED values.
- **Consumers (behavioral effect):**
  - `abs_decel_threshold_builder` region reads bit4 at `0x473F0` / `0x47CE0` — biases the per-wheel decel
    threshold / dump staging on a wheel flagged deep-slip. CONFIRMED (read sites).
  - Axle pressure-coupling `0x48EB0` at `0x49154/0x49168/0x491B2/0x491C4`: if **either** this wheel's or the
    partner's bit4 is set, a pressure step is skipped — i.e. the low-grip partner constrains the pair.
    CONFIRMED.
  - Also read by hold-threshold / event-prefilter code (`0x4F38E` tests the neighbouring **bit6**, a separate
    threshold-builder flag — do not conflate). CONFIRMED.
- **Learned/adaptive RAM:** the counter `0x409010/0x40900C` is recomputed each cycle and **not persisted to
  NVM**; no persistent ABS µ-learning value was found. UNCONFIRMED that any NVM-stored ABS adaptation exists
  (none located in the fault/coding NVM blocks).

Upshot: the controller does not "switch maps" by surface, but a wheel that locks deep at moderate speed under
braking is tagged, which deepens/relaxes its own threshold and holds the partner — a staged low-mu response,
not a global map change.

---

## 3. Rough-road / wheel-vibration, standstill/creep, reverse

### Rough-road / vibration suppressor — "score detector" `0x5567C` (CONFIRMED)
Runs every 10 ms from `abs_frame_entry_b 0x447C4` (dispatcher slot 13) at `0x44910`, **before** the apply
ramp and the 4 km/h gate. Iterates per-wheel records (`0x40BF00`, stride 0x40), accumulates a disturbance
score, then writes a **rough-road mode byte `0x408DAD` (3/4/5/6)** and disturbance flags in `0x408DEA`
(+5 b4, +6 b0) plus a wheel counter `0x408EAF`. These feed the decision/classify layer (`0x45808`,
`0x51226`, `0x5C63C/0x5D4E6`) to **suppress false ABS triggering on rough road**. CONFIRMED.

Cal fields (ABS block; byte-verified, **identical to 1M, only relocated** → detector not retuned for M3):

| CPU | Value | Role |
|---|---|---|
| `0x40D66` | 24 | score threshold → mode 3 (strongest) |
| `0x40D68` | 14 | → mode 4 |
| `0x40D6A` | 19 | → mode 5 + score clamp |
| `0x40D6C` | 1000 | PM-delta threshold |
| `0x40D6E` | 100 | PM-delta threshold |
| `0x40D70` | 3000 | PM threshold |
| `0x40D72` | 80 | score emitted at mode 3 |
| `0x40D74` | 50 | wheel-count gate mode 4 (vs `0x408EAF`) |
| `0x40D76` | 60 | wheel-count gate mode 5 |
| `0x40D78/7A/7C/7E` | 3/4/5/1 | score weights |

These `0x40D66..0x40D7E` fields appear **unmapped in the XDF** (add to §6 candidates). The separate slip-arming
gates are the event prefilter `0x4FFF6` (E+24=vref/33, E+26=vref/50) and `abs_gross_slip_threshold 0x52380`
(ROM curve `0xD6CE2` ≈ 11 % vref) — distinct from this vibration suppressor. CONFIRMED.

### Standstill / creep + low-speed ABS disable (CONFIRMED)
- Standstill cal **`0x41CF2` = 72** (0.72 km/h), read in exactly one place `0x71CEC` inside the wheel-speed/
  direction task `0x71CC0`: counts wheels with speed (`rec+0x1A`) < 72 and faulted wheels (`0x400952[idx]`
  b0). If **≥3 wheels < standstill and < 2 faulted**, a persistence counter `0x4033D8[+1]` ramps to 10, then
  sets **standstill-confirmed flag `0x4033D8[+2] bit7`**. This latches "vehicle stopped" and freezes
  wheel-direction. CONFIRMED.
- **4 km/h apply cutoff:** `0x442AC` (called from `0x4491C` when `0x404998` b4). At `0x44338`: `vref 0x408DA8`
  vs 400 (= 4.00 km/h); below 4 km/h the per-wheel apply-request bit4 of `0x408D9C` (arbiter apply id 19) is
  cleared (`0x44382`) — **ABS pressure-apply ramp is suppressed at creep speed**. CONFIRMED.

### Reverse-gear / direction (CONFIRMED) — ABS runs in reverse
- Direction is derived from the **VDA wheel-speed sensors** (`wheel_direction_update 0xB9330`, valid ≤ 70
  km/h), **not from gear**. The ABS controller tallies per-wheel direction in `0x515D4` (from the
  `0x461C0` pressure-frame path) and writes a **vehicle-reverse consensus to `0x408DB5 bit4`**, consumed by
  the slip-threshold builders (`0x4F38E`, `0x4FFF6`, `0x50FF4`). So reverse **adjusts ABS slip thresholds; it
  does not disable ABS.** CONFIRMED.
- Gear from CAN 0x0BA (`0x4010F7`) is read **only by TCS/DSC/engine code** (0xC0000–0xC4000), never by the ABS
  controller. CONFIRMED.

---

## 4. Failsafe / degraded modes — what disables ABS (CONFIRMED)

- **Master ABS gate:** byte **`0x401FF2`** — **bit7 = operational-enable, bit5 = active/engaged** (read ~50
  sites across the controller; e.g. `0x458E0` tests `(0x401FF2 & 0xA0)==0x80`). (The 1M "`0x408D7D` mode
  bits" do **not** exist in M3; `0x401FF2` is the operative gate.) `abs_frame_entry 0x44502` also requires
  controller mode ∈ {1,2,4}. CONFIRMED.
- **Enable chain:** `0x08F0A8` (enable manager) sets `0x401FF2` b7 from the central verdict `0x06FE92`;
  `0x09486E` (reset/init) clears b7/6/5/4/3 = full disable. `0x06FE92` returns *disabled* when
  **global inhibit `0x4009BC bit5` is set** OR **`0x4009F4[2] bit4` (ABS-enabled) is clear**. CONFIRMED.
- **(a) Wheel-speed plausibility faults** (from `wheel_speed_update 0x75xxx` / wss monitors `0x71xxx`, off
  signal-health bytes `0x4009B4/B6/B8`): IDs `0x00010800`, `0x00060004`, `0x00010008`, `0x00010010`,
  `0x00010100`. These **also set the global inhibit `0x4009BC` b4** → `0x06FE92` → clears `0x401FF2` b7 →
  **ABS disabled**. Direction-plausibility IDs `0xF576C = {0x00020040,0x00030040,0x00040040,0x00050040}`.
  CONFIRMED.
- **(b) Voltage monitoring:** a supply monitor exists among `monitoring_main 0xB3FC0`'s ~26 sub-monitors; the
  exact function/threshold not isolated. Any such fault gates ABS through the same `0x4009BC`/`0x401FF2`
  chain. Gate mechanism CONFIRMED; specific fn LOW/UNCONFIRMED.
- **(c) Pressure-sensor fault:** five sensors are monitored (master + four wheel outputs, each dual-element
  with a plausibility cross-check). A master fault makes driver pressure `0x404994` fall back to the mean of
  the wheel sensors; a wheel-sensor fault (per-wheel invalid flag, `0x402888` b5, or fault ids 35/57/59/61/63
  `<<15`) switches all four wheel pressures PM to the COA volume model (`sub_082BC0`). BMW DTC numbers not
  pinned. CONFIRMED mechanism (see `06_pressure_sensors_recheck.md`).
- **(d) Missing/invalid wheel signal → fallback:** a wheel-speed sensor fault does **not** quietly exclude one
  wheel — it raises group-1 faults + sets `0x4009BC` → **ABS/DSC disabled entirely + lamp** (status on TX
  0x19E; no GPIO lamp). Predictable BMW behavior. CONFIRMED.
  - **Bench unit with no wheel sensors:** all four channels read zero edges → implausibility faults →
    `0x4009BC` inhibit → `0x401FF2` b7 = 0 → **the ABS pressure/decision pipeline never arms; ABS will not
    actuate on a sensorless bench.** The standstill detector (<2 faulted) and direction tally (<3 invalid)
    also bail. CONFIRMED.
- **vref invalid-wheel exclusion:** `vref_update 0x449D0` excludes faulted wheels and resyncs to the shadow
  integrator (per `ABS_ALGORITHM.md` §2). The specific 1M `struct+0x19 & 0xC0` mask could not be matched in
  M3 (offset computed, not a literal) — **UNCONFIRMED in M3**; the effect (fault bit0 `0x400952` + global
  inhibit) is as above.

Key RAM: `0x401FF2` master gate, `0x4009F4` mode/enable, `0x4009BC` global inhibit, `0x4009B4/B6/B8` signal
health, `0x400952[idx]` per-wheel fault b0, `0x4033D8` standstill latch, `0x408DAD` rough-road mode,
`0x408DB5` b4 reverse consensus, `0x408DA8` vref (4 km/h = 400).

---

## 5. Coding-variant effects on ABS (12 variants, index `0x4031AB` = EEPROM byte[1] & 0x1F)

Variant byte set by `coding_unpack_block 0x0CFDD8` (`[rec[1] & 0x1F] → 0x4031AB`); **not hard-coded in flash**
(after `ram_clear 0x6C9CC` the default is 0). The coded index lives in the car's EEPROM and is **not
statically recoverable** from the image. CONFIRMED. (Byte-verified by the variant-audit pass.)

**PER-VARIANT ABS tables (12 entries, indexed by `0x4031AB`):**

| Table | Base | Stride | Groups | Note |
|---|---|---|---|---|
| Front speed-term curve family | `0x40412` | 0x28 (20×s16, n6) | **vars 0–9 identical; 10/11 identical, differ** | subtracted from decel-base; indexed in `0x47BDC` at `0x47C92` (×0x28) |
| G-term curve family | `0x40674` | 0x40 (32×s16, n10) | **0–9 identical; 10/11 differ** | indexed in `0x47BDC` at `0x47CAA` (×0x40) |
| Decel floor <20 km/h | `0x40644` | 2 | var0=−127, var1–11=−120 | |
| Decel floor <60 km/h | `0x4065C` | 2 | var0–9=−132, var10/11=−140 | |

All four are **already mapped in the XDF** (var0..11 titled). CONFIRMED.

**GLOBAL (single, all variants):** rear speed-term curve `0x405F2`; decel scalars gain-front `0x4061A`=40 /
gain-rear `0x4061C`=25 / floor `0x4061E`=−240 / base `0x40620`=−116; entry-slip `0x40DB6` + debounce
`0x40DB4`=2; and **all §1/§2 edge-case fields** (`0x40C40/0x40C5A/0x40D24/0x40D40/0x40D42/0x40D90/0x40DD2`).
CONFIRMED.

**Behavioral meaning for variant choice:** only **two ABS behaviors exist** — variants **0–9** (standard) vs
**10/11** (more permissive). The front speed-term and g-term curves differ **only at high speed** (breakpoints
100/150/200/250/300 km/h): var 10/11 shape the decel threshold to allow **deeper wheel deceleration before
dumping at speed**, and set the <60 km/h floor to −140 (vs −132) = later/less-aggressive ABS intervention.
Front values:
- var0–9 speed-term c = `[0,−10,−10,−50,−95,−277]`, var10/11 = `[0,−20,−20,−40,−85,−267]`.
- g-term k-tail richer for 10/11. CONFIRMED (byte-verified).

**E9x M3 index:** not determinable from flash (EEPROM-coded). Vehicle-model geometry rows (`0xD6F42`…) show
**rows 0–4 duplicated as 5–9** (wheelbase l_f+l_r ≈ 2.76 m on every row) with **10/11 unique** — i.e. one M3
part number, coding picks body geometry and (for 10/11) the permissive ABS curves. Mapping (user-supplied,
added after this pass): 0 sedan, 1 Custom ESM, 3 coupe, 4 convertible, 5/8/9 Competition sedan/coupe/
convertible, **10 GTS coupe, 11 GTS sedan**; 2/6/7 not identified. So the standard and Competition cars all
use the 0–9 ABS set and the permissive set is the GTS calibration; the track-relevant lever is that 10/11
raise the high-speed decel ceiling.

---

## 6. ABS cal fields NOT yet in XDF/analysis (candidates to map)

Scan of the ABS block `0x4039C..0x40EA6` (XDF uses CPU+0x8000). All verified **global single** curves/scalars
(not per-variant). These are the §1/§2 edge-case knobs and are currently **unmapped**:

| CPU | File off | Content | Role (this pass) |
|---|---|---|---|
| `0x40C40` | 0x48C40 | curve `[0,50,3, x:20,60, c:30,32,27, k:0,−102,−23]` | lateral/yaw-limited-build shaping |
| `0x40C5A` | 0x48C5A | curve `[0,3490,9, x:20,45,62,80,100,130,150,200, …]` | yaw-deviation gain (`0x4A254`) |
| `0x40D24` | 0x48D24 | curve `[0,30,4, x:30,50,80, c:10,25,33,22, k:512,0,−171,−21]` | lateral build term |
| `0x40D40` | 0x48D40 | scalar **50** | low-mu deep-slip counter threshold (`0x4F9D4`) |
| `0x40D42` | 0x48D42 | scalar **7000** | low-mu brake-pressure gate (≈70 bar) |
| `0x40DD2` | 0x48DD2 | `[1748,1399,1047]` + curve `0x40DD8` `[0,4000,3,x:50,100,c:2000,2000,1750,k:10240,10240,12800]` | rear cornering lateral threshold |
| `0x40D66..0x40D7E` | 0x48D66.. | scalars 24/14/19/1000/100/3000/80/50/60 + weights 3/4/5/1 | rough-road score detector `0x5567C` (13 fields, all unmapped) |

(`0x40DB6` entry-slip and `0x40D90` pair-reapply step **are** already in the XDF.) The variant-audit pass
confirmed there are **no other** 12-wide per-variant tables or curve families in the ABS block beyond the four
in §5.

---

## Confidence summary
- CONFIRMED: decision-code-32 GMA mechanism and its cal; low-mu flag source/threshold; the four per-variant
  tables and their 0–9 vs 10/11 split (byte-verified); the six unmapped edge-case fields; variant setter.
- INFERRED: the precise ride/behavioral reading of the +80 staged build and of "permissive" 10/11; stock M3
  index = 0–9.
- UNCONFIRMED: any NVM-persisted ABS µ-adaptation (none found); pressure unit; §3/§4 fault detail pending the
  edge-case sweep.

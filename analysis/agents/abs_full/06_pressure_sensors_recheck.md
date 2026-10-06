# 06 — Pressure sensing RE-CHECK: how many sensors does 7846816A actually READ, and is per-wheel/rear pressure measured, modelled, or fused?

**Mandate:** challenge the prior claim (docs 04 / 07 / ABS_ALGORITHM §4) that *"firmware samples exactly
ONE pressure sensor — master/front-line on ADC channel 21."* Owner's physical evidence: the PCB carries
**FIVE** pressure transducers on the hydraulic block, and on the car the ECU's reported pressure FOLLOWS the
**rear** circuit set by a bias-bar pedal box (rear mechanically independent of front).

CPU addresses throughout; **file offset = CPU + 0x8000**. Byte reads from `flash/bin/7846816A_00000000.bin`,
disassembly `analysis/7846816A_main.lst`. **[C]** = read from bytes/listing, **[I]** = inferred from
structure, **[open]** = unresolved.

---

## 0. Bottom line (settles it)

1. **The prior "exactly ONE pressure sensor" count is WRONG.** The firmware samples **FIVE pressure-class
   transducers**, each **dual-element** (main + redundant), i.e. **10 ADC channels**, acquired every 10 ms by
   `sub_0B85EC` (0x0B85EC) and conditioned by the identical routine `0x0B800C` through the identical
   ratiometric transfer function (`0x0B83DA`, id=190, gains 0x5EE9/0x556B). This **matches the owner's five
   physical transducers.** [C]
2. **But the prior CONTROL conclusion is essentially RIGHT.** Only **one** of the five (S1 = master/primary
   brake-line pressure, raw 0x402954) reaches the hydraulic model, ABS/DSC control, and the CAN/diagnostic
   pressure reports. The other four (S2–S5) are measured, plausibility-checked, and routed **only to internal
   fault monitoring** — **not** to the per-wheel model, **not** to `supply_pressure`, **not** to CAN, **not**
   to KWP read-data. [C]
3. **Per-wheel / rear pressure in control is MODELLED, not measured and NOT fused.** The per-wheel caliper
   pressure array `0x4016E2[w]` has exactly three writers, all the COA volume→pressure model; **zero** sensor
   writers and **zero** Kalman/complementary `PM = PM_pred + K·(meas − pred)` writers. [C]
4. **The channel detail in the prior docs was also wrong.** "ADC channel 21" is not a pressure channel at all
   (see §1.3). The master sensor is on ASIC scan channels **ch6 & ch7**; the ×0.371 scale was right, the
   channel number was not.
5. **Rear-circuit resolution:** there is **no firmware path** that derives rear pressure as an independent
   *measured* rear-line value feeding control, and **none of the five sensors is labelled front/rear or
   circuit-1/2** — they are only numerically indexed. The ECU's single reported/controlling pressure is S1;
   if the reported pressure tracks the rear bias-bar circuit, that is because **S1's hydraulic port is teed
   into the rear circuit on the owner's car (a plumbing fact), not a firmware selection.** The owner's
   inference that the firmware *measures and uses* rear pressure is **not supported**; the owner's inference
   that there are *five real transducers the firmware reads* **is confirmed**. [C]/[I]

So: **5 sensors READ, 1 (master) USED for control/report, 4 read-but-ignored (fault-watch only); per-wheel/
rear is a pure forward model with no measured correction.**

---

## 1. The ADC acquisition, in full

### 1.1 `adc_read` 0x6FB30 is a RAM-mirror GETTER, not a hardware driver
`adc_read(idx)` (0x6FB30) is a 59-entry jump table (table @0x6FB44, byte-verified). 42 of 59 indices map to
the default stub 0x6FC56 which returns the constant **1** (no hardware access). The live indices each do
`ld.h` from the **ADC result mirror** `0x4009CE[]` (base lrw = 0x004009CE). Decoded index→RAM map [C]:

| logical idx | RAM | | logical idx | RAM |
|---|---|---|---|---|
| 0 | 0x4009D2 | | 34 | 0x4009E4 |
| 1 | 0x4009D4 | | 35 | 0x4009E6 |
| 2 | 0x4009D0 | | 36 | 0x4009E8 |
| 6 | 0x4009D8 | | 37 | 0x4009EA |
| 7 | 0x4009DA | | 44 | 0x4009EC |
| 23 | 0x4009D6 | | 45 | 0x4009EE |
| 52 | 0x4009DE | | 46 | 0x4009F0 |
| 56 | 0x4009E0 | | 47 | 0x4009F2 |
| 58 | 0x4009E2 | | | |

### 1.2 The real acquisition: `sub_06FCC0` scans ~19 ASIC channels over SPI
`sub_06FCC0` (0x6FCC0) fills the mirror `0x4009CE[0..18]` with a **burst of 19 reads from the safety ASIC
over QSPI CS5** (`qspi_xfer` 0xD4CA8, r2=5). The 19 ASIC MUX command words come from ROM table **0xD73DC**
(decoded: 144,80,152,176,120,224,240,200,96,216,136,192,88,104,128,112,208,184,0 — opaque ASIC pin selects).
So the firmware does acquire ~18 analog inputs; the pressure sensors are a subset. [C]

### 1.3 Why "channel 21" was a mis-read
`pressure_adc_track` 0x8F344 begins `movi r2,21 / jsri adc_read` — but `adc_read(21)` maps to the default stub
(returns 1) **and its result is immediately discarded** (overwritten at 0x8F350 by `movi r2,6`). The value
actually used is `adc_read(6)`. The KWP diag block at 0xB1A22 likewise reads `adc_read(21)` → stub → 1,
stored as a meaningless diagnostic byte. **"ADC channel 21" never carries pressure.** [C]

---

## 2. FIVE pressure sensors — the acquisition routine `sub_0B85EC` (0x0B85EC, 10 ms)

Called from the sensor dispatcher `sub_08F028` (0x8F04A), itself in the **T3 10 ms** cycle (0x7101A), before
the control dispatcher 0x8CCB8 — so the five sensors are **live every frame.** [C]

Each sensor = **two** `adc_read` channels (a main + a redundant element = ratiometric dual-die), stored to a
raw cell, processed by `0x0B800C`, then scaled by `0x0B83DA` (all five pass the **same** group id = 190,
`movi r9,62; bseti r9,7` @0x0B8616/18). [C]

| Sensor | raw RAM | ROM cal | ADC ch (companion / main) | role |
|---|---|---|---|---|
| **S1** | 0x402954 | 0x0F56F4 | 6 / 7 | **master / primary brake-line pressure** → control+report |
| S2 | 0x4029B6 | 0x0F570C | 34 / 44 | measured pressure, fault-watch only |
| S3 | 0x4029B8 | 0x0F5724 | 35 / 45 | measured pressure, fault-watch only |
| S4 | 0x4029BA | 0x0F573C | 37 / 47 | measured pressure, fault-watch only |
| S5 | 0x4029BC | 0x0F5754 | 36 / 46 | measured pressure, fault-watch only |

### 2.1 All five are the same sensor class (CONFIRMED by identical scaling)
`0x0B83DA` with id=190 (branch 0x0B84AA) applies, for **every** sensor, the two-element linear scale
`(gain·x)/den + off` with gains **0x5EE9 (24297)** and **0x556B (21867)** and offsets 0xFFFFF683 /
0xFFFFA117, then differences the elements for plausibility and sums them. These are the **same constants**
(to ±1 LSB) as the master `pressure_adc_track` chain (0x5EE8=24296, 0x556A=21866, 0x97D). Identical transfer
function ⇒ same physical quantity as the known brake-pressure sensor S1. [C]

### 2.2 The five ROM cal blocks are per-sensor fault descriptors, structurally identical
0x18 bytes each at 0x0F56F4 / 570C / 5724 / 573C / 5754. All share the plausibility signature
`02 8A 00 00` (650,0) and the same slot layout; they differ only in packed DTC words (cal+0x00 range DTC,
cal+0x14 timeout DTC) consumed by `fault_set` 0x0B427C. Same structure for all five = same sensor class,
each with its own fault code. [C] (Decoded bytes in the agent working notes; exact BMW DTC numbers need the
`fault_set` bitfield model — not required for this verdict.)

### 2.3 Honest caveat
Identical **dual-element ratiometric** processing is also what a dual-track position/travel sensor would use.
"Pressure" for S2–S5 is therefore **[C]** on *same-class-as-S1* and **[I]** on the literal word "pressure" —
but the identical scale to the confirmed brake-pressure sensor plus the owner's five physical transducers
make pressure overwhelmingly likely.

---

## 3. Where each sensor goes — only S1 reaches control/report

### 3.1 S1 → master pressure 0x404994 → the whole model
`driver_pressure_from_sensor` 0x8CE8E (dispatcher slot 0) select-lows the two conditioned master tracks in RAM
`0x40171A[0]/[2]` and commits to **0x404994** (sole writer, st.h @0x8CE9E). `0x404994` is read **~48×, all in
the control region 0x081xxx–0x08Cxxx** (hydraulic model, supply pressure, COA). S1's raw getter 0x0B8720 also
feeds a fault monitor (0x6A24C). [C]

### 3.2 S2–S5 → conditioning + fault memory ONLY
Raw S2–S5 (0x4029B6/B8/BA/BC) are referenced **only** in `sub_0B85EC` (writes) and getter `0x0B874E`
(indexed 0..3), which is called **only** from the two conditioning loops `0x08FBEA` and `0x091F62`. Those
loops plausibility-check and low-pass the values into 0x40207A / 0x402082 / 0x40208E / 0x402096 / 0x402280,
whose readers all live in 0x08Fxxx / 0x090–094xxx (internal conditioning + fault state, e.g. 0x09240A /
0x092962 call `fault_is_set`/`fault` 0x0B4312). **Region tally of every S2–S5 reference:**
`08F:15 · 090:1 · 091:4 · 092:33 · 093:3 · 094:4 · 0B8:48 · 0B9:22 · 0BF:4` — **zero** in the control region
0x081–088, **zero** at `supply_pressure` 0x84D42, **zero** near 0x4016E2, **zero** in the CAN-TX region
0x07Axxx–0x07Fxxx, **zero** in the KWP region 0x0B1xxx–0x0B3xxx. [C]

### 3.3 What IS reported is the master only
- **CAN 0x19E (StatusDSC) byte 6 "BrakePressure"** getter 0x7AD2A → `0x93F00(idx2)` → 0x401FF8 (master
  validated track). **Measured master.** [C] (cross-ref doc 07)
- **CAN 0x2B2 (WheelPressure) bytes 0–3** ← staging array 0x40499A ← **modelled** 0x4016E2[w] (`sub_08CFCC`).
  **Modelled per-wheel, not sensors.** [C] (cross-ref doc 07)
- **KWP SID 0x21** builds a response via `0x93F00`: call sites 0xB1A36 (idx0 → 0x4020DE) and 0xB1C2A
  (idx3 → 0x4020AA). The selector map (decoded from 0x93F00): idx0→0x4020DE, 1→0x4020E4, 2→0x401FF8,
  3→0x4020AA, 4→0x4020AC. **Crucially, 0x4020AA/0x4020AC are DERIVED FROM THE MASTER tracks** (written by
  `sub_08F488` from 0x4020E0 and 0x4020E6, the `pressure_adc_track` master cells) — **not** from S2–S5. So
  **every reported pressure, CAN or KWP, originates from the single master sensor S1.** [C]

**⇒ No reported pressure anywhere comes from the four extra sensors.** They are read-and-watched, nothing more.

---

## 4. Per-wheel pressure RAM 0x4016E2 — all writers (no sensor, no fusion)

Full register-taint sweep of all ~100 `=0x004016E2` sites isolated exactly **three** genuine writers; every
other reference is a read (for min/clamp/snapshot). [C]

| store CPU | fn | class | evidence |
|---|---|---|---|
| **0x081A34** | `coa_vol_to_pressure` 0x819FE | MODEL | `st.h r2,(0x4016E2+2w)`; r2 = volume→pressure interp (`0x7119E`) from gain tbl 0x4031AA, bp tbls 0x41B62/0x41B4E, volume state 0x4016DA. No sensor term. |
| **0x082E06** | model fn 0x082BC0 | MODEL + clamp | r14 = same interp, min-clamped to a table limit then **rate-clamped against the PREVIOUS modelled value** (0x4016E2[w]). The only nearby subtract is this clamp, not a fusion. |
| **0x082E9C** | model fn 0x082BC0 | MODEL | r7 = model-output buffer. The adjacent `subu` writes a *different* array (0x4016F2), not 0x4016E2. |

**No writer traces to `adc_read`, the ASIC acquisition, the sensor RAM (0x402954/0x4029B6..BC), or the
conditioned cells. No `(measured − predicted)·K + predicted → 0x4016E2` exists anywhere.** `0x4016E2` is a
**pure forward-model state.** [C]

`supply_pressure(w)` 0x84D42 confirms the same: `supply = max(PM[partner1], PM[partner2], 0x404994)`, clamp
0x4E20 (200 bar) — the only *measured* term is the master 0x404994; the partner terms are modelled PMs
(partner map ROM 0xDA1B8 = identity/cross pairs). [C]

---

## 5. The rear-circuit / bias-bar paradox — resolved

- The firmware's rear caliper pressure (control **and** CAN 0x2B2) is the COA volume model, driven by the
  **single measured supply head** (0x404994 = S1) and valve open-time integration. With a bias-bar pedal box
  the rear circuit is hydraulically independent of the front, so this model's rear estimate is **physically
  wrong on such a car** — but, per doc 04, ABS/DSC regulation is dominated by the measured slip + wheel-accel
  loop, so the car still brakes; only pressure *telemetry/metering* is affected. [C]/[I]
- **There is no measured independent rear-line channel feeding control.** None of the five sensors is tagged
  rear; S2–S5 are not used for control or report; S1 is the only control/report pressure. [C]
- Therefore **"the ECU's reported pressure follows the rear circuit" ⇒ S1's physical port is plumbed into the
  rear circuit on the owner's car.** That is consistent with everything here: the firmware faithfully reads,
  controls on, and reports its *one* primary sensor, whatever circuit it is teed to. The four extra measured
  pressure channels the owner sees on the PCB are genuinely read by the firmware but their values are used
  **only** for sensor-plausibility fault monitoring — they are not a per-circuit control input on this image.
  [C for the firmware facts; I for the specific plumbing conclusion]

---

## 6. Verdict vs. the prior claim and the owner

| Question | Prior claim | This re-check |
|---|---|---|
| How many pressure sensors does firmware READ? | 1 (master, "ch21") | **5 pressure-class (10 ADC ch), S1 ch6/7 + S2–S5 ch34–37/44–47** [C] |
| Channel of master sensor | ch21 ("primary") | **ch6/7** (ch21 is a discarded stub) [C] |
| Per-wheel pressure measured/modelled/fused? | modelled, no correction | **MODELLED; no sensor writer, no fusion** (3 model writers) [C] |
| Does measured pressure correct the model? | no | **no** — only the measured master sets the supply head in `supply_pressure` 0x84D42 [C] |
| Rear independently measured & used? | no | **no measured rear in control**; S2–S5 (incl. any rear) are fault-watch only [C] |
| Owner's 5 transducers real? | dismissed as irrelevant | **CONFIRMED read by firmware**; 4 of them simply unused for control/report [C] |

**The prior agent was INCOMPLETE** — it analysed only `pressure_adc_track` and missed the five-sensor
acquisition `sub_0B85EC` entirely, so it undercounted 5→1 and mislabelled the master channel. **The prior
agent was CORRECT** that the control model consumes a single measured pressure and that per-wheel/rear is an
uncorrected forward model. Both corrections are now byte-verified.

### Platform note
Both the M3 7846816A **and** the 1M 7846411A images contain **five** pressure-sensor cal blocks (plausibility
signature `02 8A 00 00` at 0xF5700/0718/0730/0748/0760 in M3; mirror set in 1M). The five-sensor acquisition
is **platform-standard MK60E5**, not M3-specific. [C]

### Open
- Exact BMW DTC numbers in the five cal blocks (need `fault_set` 0x0B427C bitfield model). [open]
- Absolute pressure scale (self-consistent ~0.01 bar; unproven vs a gauge). [open]
- Which physical block port each of S2–S5 is plumbed to (not in flash; needs the hydraulic drawing/bench
  probe). [open]

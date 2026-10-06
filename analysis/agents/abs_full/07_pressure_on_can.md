# 07 — Does the M3 DSC (7846816A) put pressure on CAN?

**Scope:** Whether firmware 7846816A TRANSMITS any brake/line/per-wheel pressure on CAN
(PT-CAN / F-CAN) and/or RECEIVES pressure over CAN, with RAM-source traceback and the
diagnostic read path. Addresses are CPU addresses (file offset = CPU + 0x8000).

> **⚠ CORRECTION (see the re-examination section at the end): the "zero pressure on CAN"
> bottom line below is WRONG.** The DSC DOES broadcast five pressures — 4 modelled per-wheel on
> **0x2B2** and 1 measured master/brake on **0x19E** byte 6. The error came from the cb_summary
> `ram=` extraction, which only lists `lrw`-absolute reads in the getter itself and misses the
> data staged into array **0x40499A** by `sub_08CFCC` and fetched through helpers
> `sub_08D030`/`sub_093F00`. The sections 1–5 below stand except for that conclusion; read the
> re-examination section as the corrected result.

## Bottom line

**The DSC broadcasts ZERO pressure signals on CAN** (main-CAN or F-CAN), and **receives
no pressure over CAN**. Every pressure value in this firmware stays internal to the ABS /
hydraulic-model code; none is packed into any TX frame and none is written by any RX
callback. This directly refutes the owner's belief that per-sensor pressures appear in
DSC-broadcast CAN messages. **[CONFIRMED]**

Method: the full TX/RX signal dictionary (`analysis/agents/m3cansig/`, byte-verified table
backbone) gives every TX message, its signals, and each signal's getter callback. I then
grepped the whole disassembly (`analysis/7846816A_main.lst`) for every reader of the four
pressure RAM cells and confirmed none lands in any CAN TX callback range; and grepped every
writer of the pressure RAM and confirmed none is a CAN RX callback.

---

## 1. CAN TX configuration (where the periodic frames are built)

Table backbone (byte-verified, from symbols + m3can):

| Bus | Config header | Message tbl (23 B) | Signal tbl (5 B) | Variable tbl (8 B, per-sig callback) |
|---|---|---|---|---|
| Main / PT-CAN | 0xD7F45 (20 TX / 27 RX) | 0xD7F65 | 0xD839E | 0xD88C0 |
| F-CAN | 0xF59C3 (14 TX / 18 RX) | 0xF59DD | 0xF5CBD | 0xF5ED0 |

Each TX message record carries CAN id, DLC, cycle time, and mailbox; each signal record
points at a **getter callback** that returns the signal value (the serializer calls the
getter, then packs the returned value at the signal's byte/bit offset). Every TX frame ends
with a checksum signal (`!k`, `can_tx_checksum8` 0x7D24C: S = Σ(DLC bytes)+id). **[CONFIRMED]**

### Main-CAN TX messages (20) — id / DLC / cycle

Periodic: **0C4** (7,10ms steering relay), **0CE** (8,20ms wheel speeds), **0E1** (6,20ms),
**0B6** (5,20ms DSC→DME torque), **0BF** (5,20ms), **19E** (8,20ms DSC/ABS status flags),
**1A0** (8,20ms ax/ay/yaw/vspeed), **1A3** (5,20ms), **1A6** (8,100ms distance/pulse),
**2B2** (8,20ms), **2B3** (5,50ms), **374** (5,1000ms).
Event: **193**, **31D**, **4A9**/**5A9** (NM), **629** (diag resp, addr 0x29),
**798**×2, **111**.

### F-CAN TX messages (14)

Periodic: **080** (event), **0CE** (8,10ms wheel speeds), **11E** (8,10ms), **130** (event),
**374** (5,1000ms). Diag/flash: **797/798/790/791/7D4..7D8** (event, no live signals).

Full per-signal layout: `analysis/agents/m3cansig/can_signal_tables_compact.txt`.

---

## 2. Pressure TX signals — NONE

The four pressure RAM cells in this firmware are:

| RAM | Meaning | Writer (sole) |
|---|---|---|
| **0x404994** | driver / master-cylinder LINE pressure (the one real pressure ADC, ch21, ×0.371, ~0.01 bar) | **0x8CE9C** inside `dispatch_slot00_driver_pressure` 0x8CE8E |
| **0x4016E2[w]** | MODELLED per-wheel caliper pressure (COA volume→pressure) | `coa_vol_to_pressure` 0x819FE |
| **0x408F2A[w]** | ABS per-wheel PM (a copy of 0x4016E2[ch]) | `abs_pm_snapshot` 0x559CC |
| **0x408EB2** | driver-brake-pressure latch inside the ABS sensor gather | ABS sensor-gather |

**No CAN TX getter callback reads any of these.** Grep of every `lrw …=0x404994 /
0x4016e2 / 0x408f2a / 0x408eb2` reference in the disassembly: **all readers are in the ABS /
hydraulic-model region** (0x44xxx–0x51xxx ABS, 0x55xxx–0x68xxx model/AYC, 0x81xxx–0x88xxx
hydraulic model). **Zero readers fall in the CAN TX callback ranges** (main 0x7Axxx–0x7Bxxx,
0x7Dxxx checksums, 0x7Fxxx; F-CAN 0xC5xxx–0xC6xxx). Filtered grep for those ranges returned
empty for all four cells. **[CONFIRMED]**

The TX getters that *do* exist read the CAN-staging mirror RAM (0x4046xx), torque RAM
(0x4010xx–0x4011xx), wheel-speed RAM (0x40BFxx), accel/yaw (0x40200A, 0xFFFFF801 scalers),
distance counters (0x404700 block) and status flags (0x40288x) — never a pressure cell.

**The 0x1A6 "looks numeric" trap:** 0x1A6 (100 ms) getters (0x7B2FA/0x7B32C/0x7B34E) read
0x404700/02/04/06, an **accumulator block** (writer 0x7F2xx does `ld.h; …; st.h` back to the
same cell, tied to status 0x4011A3 / 0x40288C). This is the DSC distance / wheel-pulse
(odometer) message, **not** pressure. The ×40 scale in sig75 is a pulse/geometry factor.
**[CONFIRMED not pressure]**

---

## 3. Pressure RX — NONE

No RX message carries pressure. The RX dictionary destinations are all torque (0x0A8/0A9/0AA
→ 0x40114x), pedal/rpm/gear (0x0AA/0x0BA), steering/yaw/accel cluster (F-CAN 0x0C9/0CD/0D1/0D4
→ 0x402F1x–0x402F3x), DME/engine (0x0AC/0B4), NM (0x480/580), tester (0x6F1), and the aux
torque-limit frame (F-CAN 0x78F/78E → 0x404634/36). **No RX callback writes 0x404994 or
0x4016E2** (filtered grep of writers in the RX code ranges returned empty). Corroborates the
cycle-5 FACTS note "no CAN brake-pressure RX." **[CONFIRMED]**

---

## 4. Source traceback (measured vs modelled) — moot for CAN, but recorded

Because nothing is transmitted, there is no "logged CAN pressure" to attribute. For
completeness:

- **0x404994 = MEASURED.** Written only by dispatcher slot 0 (`driver_pressure_from_sensor`
  0x8CE8E, store at 0x8CE9C) from the ADC-conditioning chain `pressure_adc_track` 0x8F344
  (ratiometric ADC ch21, dual-track 0x5EE8/0x97D/0x556A → 0x4020DE/E0/E4/E6, then the slot-0
  function commits the line-pressure value to 0x404994). This is the ONE physical pressure
  the firmware reads. **[CONFIRMED]**
- **0x4016E2[w] = MODELLED.** Output of `coa_vol_to_pressure` 0x819FE (volume-domain
  hydraulic model `hydraulic_model_step` 0x82EF4); the four "per-wheel pressures" are model
  state, never ADC inputs. The firmware reads **none of the four wheel pressure transducers**
  the owner's unit physically has. **[CONFIRMED, consistent with FACTS cycle 5/6]**

So even if a future patch were to broadcast a "per-wheel pressure," it would be the COA model
output, not a sensor. Only 0x404994 reflects a real transducer.

---

## 5. Diagnostic read path

- **Stock diagnostics cannot read these cells by address.** `kwp_23_read_memory` (0xB3112)
  serves only the logical NVM space (format 3) or two fixed descriptor records (format 7) —
  it rejects arbitrary RAM/flash (FACTS, verified on 1M; M3 handler is the port). **0x22**
  DIDs are 0x2501 / 0x1601 / 0x2502 (coding/ident records, not live sensor blocks).
  **`kwp_21_read_data_local_id` 0xB184A** reads only session/status RAM (0x409534/37/489/435).
  Grep of the whole 0xB0000–0xB4000 diag region found **no handler that reads 0x404994,
  0x4016E2, 0x408F2A, 0x408EB2 or the 0x4020DE sensor cells** — i.e. no stock measuring-block
  exposes pressure. **[CONFIRMED — no stock UDS/KWP pressure read found]**
- **Practical bench read (research only):** the repo's patched-image 0x23 sub-op 2
  (`mk60_can.py asic ram <addr>`) reads arbitrary RAM and WILL return 0x404994 / 0x4016E2[w]
  live — but that is a modified image, not the stock firmware. On a stock module the line
  pressure is observable only through whatever INPA/ISTA measuring-value block the SGBD maps
  (not resolvable from the flash image alone). **[INFERRED]**

---

## Confidence summary

| Claim | Verdict | Key evidence |
|---|---|---|
| No pressure on any CAN TX | CONFIRMED | no pressure-RAM reader in any TX callback range (grep) |
| No pressure on any CAN RX | CONFIRMED | no CAN-RX writer of 0x404994/0x4016E2; RX dictionary |
| 0x404994 = measured line pressure | CONFIRMED | writer 0x8CE9C via ADC chain 0x8F344 |
| 0x4016E2[w] = modelled | CONFIRMED | writer coa_vol_to_pressure 0x819FE |
| 0x1A6 404700 block = distance pulses, not pressure | CONFIRMED | accumulator writer 0x7F2xx, tied to status |
| No stock diagnostic pressure read | CONFIRMED (no path found) | 0xB-region grep; 0x23 NVM-only |

---

## Re-examination: 0x2B2 and 0x19E vs opendbc DBC

Prompted by ground-truth from `commaai/opendbc bmw_e9x_e8x.dbc` (DSC-sourced BO_ 690/0x2B2
"WheelPressure_KCAN" and BO_ 414/0x19E "StatusDSC_KCAN" with a BrakePressure byte at bit 48).
**The DBC is correct and my first verdict was wrong.** Both frames carry pressure; the data is
staged into a CAN array and fetched through a helper, so a getter-only grep missed it.

### Why the first pass missed it (method correction)

The TX getters do **not** `lrw` a pressure cell directly. Instead a per-frame builder copies the
pressure RAM into a CAN staging array **0x40499A[4]** (`sub_08CFCC`), and the getters call
helper fetchers (`sub_08D030` for 0x2B2, `sub_093F00` for 0x19E) that read that array / an ADC
block. The `cb_summary.txt` `ram=` field only captured `lrw`-absolute operands inside the getter,
so the staged pressure source was invisible to the earlier grep. **[root cause CONFIRMED]**

### 0x2B2 "WheelPressure" — ACTIVELY TRANSMITTED, DLC 8, 20 ms periodic [CONFIRMED]

Byte-by-byte (getter → source):

| Byte | Signal | Getter | Source | Meaning |
|---|---|---|---|---|
| 0 | 0.0/8 | 0x7B490 (idx 0) | `0x40499A[0]` ← `0x4016E2[0]` | wheel-0 pressure, ÷100, clamp 254, 0xFF=invalid |
| 1 | 1.0/8 | 0x7B4DE (idx 1) | `0x40499A[1]` ← `0x4016E2[1]` | wheel-1 pressure |
| 2 | 2.0/8 | 0x7B51C (idx 2) | `0x40499A[2]` ← `0x4016E2[2]` | wheel-2 pressure |
| 3 | 3.0/8 | 0x7B566 (idx 3) | `0x40499A[3]` ← `0x4016E2[3]` | wheel-3 pressure |
| 4.0–4.3 | 2+2 bits | 0x7B5A4/0x7B5E0 | status | 2 flag fields |
| 4.4–5.7 | 12s | 0x7B692 | ×939 (0x3AB) scaling | a yaw/accel-scaled dynamics value, **NOT pressure** |
| 6–7 | bits | 0x7B610.. | status/flags | validity + mode bits |

Getter `sub_07B490` logic (byte 0): `sub_08D030(idx=0)` → `ld.h value@0x40499A`; if valid bit set,
`out = clamp(value/100, 0..254)`, else `0xFF`. **[CONFIRMED, disassembled]**

Fetch `sub_08D030` (0x8D030): `r7 = 0x40499A + 4·idx` (`ixw`), returns value@+0 and valid@+2 bit7.
Array stride 4 = {u16 value, u16 flags}, 4 channels. **[CONFIRMED]**

Writer `sub_08CFCC` (0x8CFCC) — the decisive trace:
```
08CFD2  lrw r14,=0x0040499A      ; dest = CAN staging array
08CFD4  lrw r4, =0x004016E2      ; SRC  = MODELLED per-wheel pressure (COA vol->pressure)
08CFEA  ld.h r7,(r4,0)           ; r7 = 0x4016E2[w]
08CFEC  st.h r7,(r14,0)          ; dest[w].value = modelled pressure
08CFF0  bseti r6,6 / flags from 0x402888 bit5 and 0x401719
08D020  addi r14,4 / addi r4,2 / w++ ; loop w=0..3
```
**So 0x2B2 bytes 0–3 = the four per-wheel pressures, sourced from the MODEL `0x4016E2[w]`
(output of `coa_vol_to_pressure` 0x819FE / `hydraulic_model_step` 0x82EF4), scaled ÷100 → ~bar.
NOT four physical transducers.** Validity flags come from mode/status bytes 0x402888/0x401719.
**[CONFIRMED]**

### 0x19E "StatusDSC" byte 6 (bit 48) "BrakePressure" — ACTIVELY TRANSMITTED, DLC 8, 20 ms [CONFIRMED]

Getter `sub_07AD2A` (signal 57, byte 6): `sub_093F00(idx=2)` → `ld.h value@caller_buf`;
if `(status&0x60)==0`: `out = clamp(value/100, ±...)`, negative→0; else `0xFF`. ÷100, clamp 254.
**[CONFIRMED, disassembled]**

Fetch `sub_093F00` (0x93F00) is an index→analog-value selector:
`idx 0→0x4020DE, 1→0x4020E4, 2→0x401FF8, 3→0x4020AA, 4→0x4020AC, else→0xFFFF8000 (invalid)`.
Byte 6 uses **idx 2 → 0x401FF8**. **[CONFIRMED]**

Source traceback of 0x401FF8: written at 0x8F64E–0x8F648 as a copy of **0x4020E2**, which lives in
the ADC pressure-conditioning block produced by `pressure_adc_track` 0x8F344 (the dual-track
ratiometric master-cylinder/line pressure sensor; same family as 0x4020DE/E0/E4/E6 and the
ABS-side 0x404994). Indices 0/1 (0x4020DE/0x4020E4) are the two raw conditioned tracks; idx 2
(0x401FF8←0x4020E2) is the validated combined value. **So 0x19E byte 6 = the MEASURED
master-cylinder / brake-input pressure (the one real transducer), ÷100 → ~bar, 0xFF=invalid.**
Source = ADC **[CONFIRMED]**; "which pressure = master/line" **[INFERRED, matches DBC label +
adjacency to the known 0x404994 line-pressure chain]**.

### Reconciliation with the "5 transducers / 1 input + 4 output" claim [item 4]

- **This firmware (7846816A) DOES broadcast all five pressures the forums describe**, but with a
  split origin:
  - **1 input (master/brake) = MEASURED** → 0x19E byte 6 (from ADC via 0x401FF8/0x4020E2).
  - **4 output (per-wheel) = MODELLED** → 0x2B2 bytes 0–3 (from COA model 0x4016E2[w]).
- It is **not** a reduced/zero-fill variant: both frames are populated with live data, periodic
  at 20 ms. My earlier "uses none of the 4 wheel sensors" still holds for the *measurement* path —
  the four wheel values on CAN are the hydraulic-model estimate, not four independent ADCs.
- **A CAN logger cannot tell model from sensor by the bus alone.** The only distinguisher is in
  code: `sub_08CFCC`'s source pointer. Here it is `0x4016E2` (model). A part number that had four
  physical wheel-pressure transducers would instead (a) point that copy at an ADC result array and
  (b) condition four more ADC/ASIC pressure channels in the 0x8F3xx sensor code. On 7846816A only
  **one** pressure channel is conditioned (the master), confirming the per-wheel CAN values are
  model-derived on this image. **[INFERRED — the variant-distinguishing mechanism; CONFIRMED that
  on 7846816A the 0x2B2 source is the model]**

### Corrected verdict

| Frame | Signal | Bytes | Source RAM | Measured / Modelled | Verdict |
|---|---|---|---|---|---|
| **0x2B2** 20 ms | WheelPressure ×4 | 0–3 | 0x40499A[w] ← **0x4016E2[w]** | **MODELLED** (COA) | CONFIRMED |
| 0x2B2 | dynamics 12s | 4.4–5.7 | ×939-scaled | not pressure (yaw/accel) | CONFIRMED |
| **0x19E** 20 ms | BrakePressure | 6 | 0x401FF8 ← 0x4020E2 | **MEASURED** (ADC) | CONFIRMED (src ADC); master/line INFERRED |

Scaling note: raw pressure unit ~0.01 bar (unproven but consistent across the firmware); the ÷100
in both getters yields a CAN byte in ~bar (0–254, 0xFF invalid). A bench gauge vs. a 0x2B2/0x19E
capture would pin the absolute scale.

---

## 0x2B2 byte/wheel mapping + scaling

### 1. Byte → wheel index → corner
`sub_08CFCC` copies `0x4016E2[w]` → `0x40499A + 4·w` for w=0,1,2,3 in order (src+=2, dest+=4);
`sub_08D030(idx)` returns `0x40499A + 4·idx`; getters pass idx 0/1/2/3 (byte 0/1/2/3). So **byte
order = wheel-index order, 1:1** [CONFIRMED]:

| 0x2B2 byte | model idx | axle | corner |
|---|---|---|---|
| 0 | w0 | **front** (CONFIRMED) | FL (INFERRED) |
| 1 | w1 | front (CONFIRMED) | FR (INFERRED) |
| 2 | w2 | **rear** (CONFIRMED) | RL (INFERRED) |
| 3 | w3 | rear (CONFIRMED) | RR (INFERRED) |

Front=0/1, rear=2/3 is CONFIRMED (circumference selection, FACTS; wss REPORT). L/R within an axle
is INFERRED from the 0x0CE wheel-speed convention (tool: FL,FR,RL,RR), itself assumed. So a "rear"
value = byte 2 or 3.

### 2. Scaling — uniform
All four getters are byte-identical: `out = clamp(s16(value)/100, 0..254)`, negative→0, `0xFF`=invalid.
**No per-wheel gain/offset** [CONFIRMED, disassembled 0x7B490/4DE/51C/566]. 0x19E byte 6 master:
`out = clamp(s16(0x401FF8)/100, 0..254)`, same ÷100 [CONFIRMED]. Both display in the same unit *by
construction*; equality of the raw LSB (model 0x4016E2 vs ADC 0x401FF8/0x4020E2, both ~0.01 bar
family) is INFERRED — a bench gauge settles it.

### 3. Can modelled PM exceed master S1? — YES, not a hard clamp
`supply_pressure` 0x84D42 = `clamp(max(partner-wheel PM[], master 0x404994), 0, 20000=0x4E20)` —
inlet-valve inflow source, so PM→supply. **But the pump injects VOLUME directly into the circuit**
(`circuit_volume_update` 0x826C0: pump dV → circuit volume 0x4016FE / wheel volume 0x4016DA,
clamp V≤30000=0x7530), raising PM via the COA p→V curve **independent of master**. Through
partner-coupling this carries both circuit wheels above master. The only ceiling is **200 bar
(20000)**, not master. **So PM[w] > master is REAL model behaviour whenever the pump is active**
(DSC/DTC yaw braking, ASR/TCS, AYC, ABS re-apply) — and in those events the driver's foot is
often off the pedal, so master S1 ≈ 0 while calipers are pump-pressurised.

**Verdict:** a 0x2B2 rear > 0x19E master log is **NOT inherently a decode artifact** — it is
expected during any pump-active intervention. It would only indicate a decode/scaling error if the
capture was steady straight-line foot-braking with **no** DSC/ABS/TCS active (then rears are
EBD/select-low limited ≤ master). Recommend: check the capture context (was an intervention
flag/active in the same window?) before concluding a mapping error. [CONFIRMED model math]

---

## ST_CLCTR / control-state code

### Which CAN byte
**ST_CLCTR = 0x19E (StatusDSC) byte 0** — the transmitted DSC/ABS control-status field, getter
`can_tx_19E_status_flags` **0x7AEAA** (symbols: "DSC/ABS/torque-intervention status bits"). It is a
**BITFIELD, not an enum** [CONFIRMED, disassembled]. It is assembled from the ABS control-state RAM
block **0x408DA0/0x408DA2** (adjacent to the decision code 0x408DDE and request flags 0x408D9C),
plus intervention flags:

| bit | val | source | meaning (INFERRED unless noted) |
|---|---|---|---|
| 0 | 1 | 0x408DA2 bit7 | brake/slip-control active (build) |
| 1 | 2 | 0x402FC0 bit4 OR (0x402F6C b7 & +1 b3) | TCS/ASR intervention |
| 2 | 4 | 0x400B0A & 0xC0 | AYC/torque intervention |
| 3 | 8 | 0x400DF4 bit7 | (DSC function flag) |
| 4 | 16 | 0x402F6C+1 bit2 | (TCS mode flag) |
| 5 | **32** | 0x408DA0 bit1 | **lateral-limited / cornering build-limit active** |

**Important:** this getter sets only bits 0–5 (max 63); **it never sets bit6 (64)**. The value **64**
the user expects comes from the *internal* decision code **0x408DDE** (values 1/32/64…), which is
**NOT transmitted on CAN** (0 CAN getters read 0x408DDE — all 23 readers are in the ABS controller
0x4B–0x58). So the CAN ST_CLCTR byte is a *reduced bit-image* of the DSC control state, sharing the
1↔build and 32↔lateral semantics by bit position, but it cannot emit 64. If the user truly logs 64,
their DBC byte/bit mapping differs from this firmware (verify the byte offset). [CONFIRMED byte+bits;
the 1/32 ⇔ decision-code tie is INFERRED by bit position + adjacency to 0x408DDE]

### Decision code 0x408DDE (the semantic origin; internal only)
Bitfield (writers `abs_decision_classify` 0x51B54, `abs_decision_resolve` 0x58B30, exec 0x58FF4;
report 01 + symbols): **1 = build** (commands pressure **BUILD**, not dump), 2 = pair-hold-done,
16 = dump/hold-resolve, **32 = lateral-limited**, **64 = rear-control**, 128/256/1024 = reapply
chain, 16384 = reapply. It is a bitfield.

### Value 32 ⇔ cornering build-limiter [CONFIRMED]
Decision code 32 (`abs_pair_logic` 0x54D9A → exec `abs_decision_pressure_exec` 0x58FF4) **scales the
commanded ABS build pressure DOWN as |lateral g| rises**, via cal curves **0x40E0A / 0x40E26**
(|ay| breakpoints 40/65/80, FACTS). Rear-specific reduction is handled separately by the
inside/outside **rear select-low** `abs_rear_lead_select` 0x5184C (which also sets the rear-lead
flag in 0x408DA0 bit7); the code-32 limiter itself acts on the build command, and I did not find a
distinct front-vs-rear gain split inside code-32 (rears are already select-low limited). [CONFIRMED
tie; front/rear asymmetry = via 0x5184C, INFERRED]

### Empirical anomaly: ST_CLCTR=0, no ABS, modeled rear 0x2B2 > measured master 0x19E (~10 bar)

**1. Pump gating — pump CAN run with ST_CLCTR=0.** `pump_motor_control` 0x88EC0 is gated by
**0x401981 bit5**, a flag set in the **actuation/arbiter pipeline** (stores at 0x836D2, 0x83E4C,
0x843A0, 0x85F4C, 0x8730C — i.e. `req_arbiter`/`abs_pressure_arbiter` 0x8428C / `hydraulic_actuation`
0x843BC), **not** by the slip decision code 0x408DDE. Pump level = pressure-demand loop over
0x401D28−0x401D24 → 0x401D2E (0x8623E). So any autonomous pressure request (DSC precharge,
AYC/TCS, brake pre-fill id 20) runs the pump **independently of ST_CLCTR**. [CONFIRMED structural]

**2. The model's "master" term is a DIFFERENT, SELECTED cell from the 0x19E report.**
- 0x19E byte 6 ("measured S1") = **0x401FF8** (copy of ADC-conditioned 0x4020E2). 
- The model supply (`supply_pressure` 0x84D42) uses **0x404994**. Crucially **0x404994 ≠ 0x401FF8**:
  slot-0 `driver_pressure` 0x8CE5E *selects* it — it can be the measured sensor (via helper 0x93E1C
  reading 0x401FF8) **or a MODELLED circuit pressure `0x40171A[0/4]`** (chosen on 0x408DA1 bit4).
  So the supply the rear PM is clamped to is an **estimate that can lead / exceed the more-filtered
  value reported on 0x19E** during a fast ramp. [CONFIRMED the two cells differ and 0x404994 can be
  model-sourced; that this produces the lead = INFERRED]

**3. Simplest consistent explanation [INFERRED, strong]:** the anomaly is **a leading/estimated
supply term, not pump injection** (for pure driver braking). The model builds rear PM against
0x404994 — a selected/estimated master that leads the more-filtered 0x19E sensor cell (0x401FF8/
0x4020E2) by a few 10 ms frames; at a fast ramp a few frames ≈ ~10 bar. Discrete volume-integration
overshoot (CMD +400/frame toward the leading supply) adds a little. **Pump-active-despite-idle-state
is the explanation only if an autonomous build (DSC precharge/pre-fill) was running** — which is
possible with ST_CLCTR=0 (mechanism 1) but is a separate case from steady driver braking. To
distinguish on the bench: log 0x404994 vs 0x401FF8 (via the patched 0x23 RAM-peek) and the pump-gate
0x401981 bit5 during the ramp. A hard clamp of modeled PM to the *reported* 0x19E S1 does **not**
exist — PM is clamped to 0x404994 (the estimate) and ultimately to 200 bar. [INFERRED]

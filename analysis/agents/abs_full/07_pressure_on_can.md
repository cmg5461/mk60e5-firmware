# 07 — Pressure on CAN (M3 DSC 7846816A)

**Scope:** which brake pressures firmware 7846816A transmits on CAN, where each value comes from, what
it receives, and the diagnostic read path. CPU addresses (file offset = CPU + 0x8000).

## Bottom line

The DSC broadcasts **all five transducer pressures** and receives none:

| Frame | Signal | Bytes | Source RAM | Origin |
|---|---|---|---|---|
| **0x2B2** WheelPressure, DLC 8, 20 ms | wheel pressure ×4 | 0–3 | `0x40499A[w]` ← PM `0x4016E2[w]` | **measured wheel-output sensors** (`0x402198[w]`) in normal operation; volume model during a dump phase or with a wheel-sensor fault |
| **0x19E** StatusDSC, DLC 8, 20 ms | BrakePressure | 6 | `0x401FF8` | **measured master / input sensor** |

Both are `clamp(s16(raw)/100, 0..254)` → bar, `0xFF` = invalid. This matches
`commaai/opendbc bmw_e9x_e8x.dbc` (BO_ 690 / BO_ 414). How PM is selected between measurement and model:
`06_pressure_sensors_recheck.md` §4.

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

The pressure getters do not `lrw` a pressure cell directly: a per-frame builder stages the data into
`0x40499A[4]` (`sub_08CFCC`), and the getters call fetch helpers (`sub_08D030` for 0x2B2, `sub_093F00`
for 0x19E). A grep for pressure-RAM literals inside the TX callback ranges therefore finds nothing.

---

## 2. 0x2B2 "WheelPressure" — byte map [CONFIRMED]

| Byte | Getter | Source | Meaning |
|---|---|---|---|
| 0 | 0x7B490 (idx 0) | `0x40499A[0]` ← `0x4016E2[0]` | wheel 0 = LF, bar |
| 1 | 0x7B4DE (idx 1) | `0x40499A[1]` ← `0x4016E2[1]` | wheel 1 = RF |
| 2 | 0x7B51C (idx 2) | `0x40499A[2]` ← `0x4016E2[2]` | wheel 2 = LR |
| 3 | 0x7B566 (idx 3) | `0x40499A[3]` ← `0x4016E2[3]` | wheel 3 = RR |
| 4.0–4.3 | 0x7B5A4 / 0x7B5E0 | status | two 2-bit flag fields |
| 4.4–5.7 | 0x7B692 | ×939 (0x3AB) scaling | 12-bit signed yaw/accel-scaled dynamics value, not pressure |
| 6–7 | 0x7B610.. | status | validity + mode bits |

Front = 0/1 and rear = 2/3 are confirmed from the wheel→circuit map (ROM 0xDA1B4 = 0,0,1,1) and the
wheel-speed map; left/right within an axle follows the 0x0CE convention and the owner's logs.

**Getter** (all four byte-identical, no per-wheel gain/offset): `sub_08D030(idx)` returns
`0x40499A + 4·idx` = `{u16 value, flags}`; if flags b7 (valid) → `out = clamp(s16(value)/100, 0..254)`,
negative → 0; else `0xFF`.

**Writer** `sub_08CFCC` (0x8CFCC, control dispatcher, runs after `hydraulic_model_step` and
`abs_pm_snapshot`), for w = 0..3:
```
dest[w].value = 0x4016E2[w]                       ; PM (measured or model, see doc 06 §4)
flags b6 = !(0x402888 b5)                         ; wheel-sensor system enabled
flags b5 = (w<2) ? 0x401719 b7 : 0x401719 b6      ; PM is MEASURED this frame
flags b7 = b5 | b6                                ; valid
```
`0x401719` b7/b6 are set by `sub_082BC0` only when all four wheel sensors are valid and no gate fault is
latched, so **staging flag b5 tells measured from modelled**. The value bytes alone do not.

## 3. 0x19E "StatusDSC" byte 6 — master pressure [CONFIRMED]

Getter `sub_07AD2A` (signal 57): `sub_093F00(idx 2)` → `0x401FF8`; if `(status & 0x60) == 0` →
`out = clamp(value/100, 0..254)`, negative → 0; else `0xFF`. `0x401FF8` is the validated, offset-corrected,
filtered output of the master-sensor chain (`pressure_adc_track` 0x8F344 → `0x4020E2`). It is the same
value the control uses as driver pressure `0x404994` while the master sensor is valid.

## 4. Reading 0x2B2 against 0x19E in a log

- The two frames come from **different transducers**: 0x19E byte 6 is the input side, 0x2B2 the four
  wheel outputs. With valves at rest (inlets open) each wheel reads its own circuit's line pressure.
- **Wheel pressure above master is physical** whenever the wheel's circuit is not the one the master
  sensor sits on (independent front/rear master cylinders, bias bar), and during any pump-active build
  (ABS reapply, DSC/AYC, TCS, pre-fill), where the foot may be off the pedal.
- During an ABS **dump** on a wheel, that wheel's 0x2B2 byte is the volume-model estimate until the
  inlet side is active again (doc 06 §4.1); expect a small step when it re-syncs to the sensor.
- The pump is gated by `0x401981` b5 (set in the arbiter/actuation pipeline 0x8428C / 0x843BC), not by
  the slip-control state, so it can run while ST_CLCTR = 0.

## 5. Pressure RX — none

No RX message carries pressure. RX destinations are torque (0x0A8/0A9/0AA → 0x40114x), pedal/rpm/gear
(0x0AA/0x0BA), steering/yaw/accel cluster (F-CAN 0x0C9/0CD/0D1/0D4 → 0x402F1x–0x402F3x), DME/engine
(0x0AC/0B4), NM (0x480/580), tester (0x6F1) and the aux torque-limit frame (F-CAN 0x78F/78E →
0x404634/36). No RX callback writes `0x404994`, `0x4016E2` or `0x402198`. [CONFIRMED]

**Not pressure:** 0x1A6 (100 ms) getters 0x7B2FA / 0x7B32C / 0x7B34E read the accumulator block
`0x404700..06` (writer 0x7F2xx) — distance / wheel-pulse counters.

## 6. Diagnostic read path

- `kwp_21_read_data_local_id` 0xB184A builds a measuring block that includes pressure: raw `adc_read`
  bytes (0xB1A06..), master values through `sub_093F00` (0xB1A36 idx 0, 0xB1C2A idx 3), and the wheel
  sensors through `sub_0946D0` (0xB1AEE, 0xB1D32: measured value, redundant track, learned offsets).
  Local-id numbers and byte layout are [open].
- `kwp_23_read_memory` 0xB3112 serves only the logical NVM space and two fixed descriptor records; it
  does not read arbitrary RAM on a stock image.
- Bench: the patched-image 0x23 sub-op 2 (`mk60_can.py asic ram <addr>`) reads any cell live — useful
  ones are `0x402198 + 4·w` (measured wheel), `0x4016E2 + 2·w` (PM), `0x401FF8` (master), `0x404994`
  (driver pressure), `0x401719` (measured-valid bits).

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

### Value 32 ⇔ cornering knock-down
Decision code 32 (`abs_pair_logic` 0x54D9A → exec `abs_decision_pressure_exec` 0x58FF4) reduces the
commanded pressure on a rebuilding wheel: `CMD = PM − pct·(LOCKEST − CMD)/100` (pct byte `0x408DE0`,
producer untraced). Rear-specific reduction is the separate inside/outside rear select-low
`abs_rear_lead_select` 0x5184C (which also sets `0x408DA0` b7). The cal curves 0x40E0A / 0x40E26 are a
different lateral-g pressure term that rises with g (see FACTS).

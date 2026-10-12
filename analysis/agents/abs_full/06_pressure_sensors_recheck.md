# 06 — Pressure sensing on 7846816A: five transducers, all five used

How the firmware acquires the five MK60E5 pressure transducers (1 master/input + 4 wheel outputs), and
where each one enters control.

CPU addresses throughout; **file offset = CPU + 0x8000**. Disassembly `analysis/7846816A_main.lst`.
**[C]** = read from the listing, **[I]** = inferred from structure, **[open]** = unresolved.

---

## 0. Bottom line

1. **Five transducers are sampled, each dual-element** (main + redundant track). [C]
2. **All five are used for control.** The master sensor gives driver pressure `0x404994`. The four
   wheel-output sensors give measured wheel pressure `0x402198[w]`, which is read by the hydraulic model,
   the ABS controller, the valve sequencer and diagnostics through getter `sub_091A50` (16 call sites). [C]
3. **Per-wheel pressure `0x4016E2[w]` (PM) is measurement-primary.** Every 10 ms `sub_082BC0` overwrites
   it with the measured wheel pressure and re-syncs the model's volume state to match. The COA volume
   model supplies PM only while a wheel's outlet valve is active, or when the wheel sensors are unusable. [C]
4. **CAN `0x2B2` bytes 0–3 are therefore the measured wheel-output pressures** in normal operation
   (÷100 → bar, wheel order 0..3 = LF, RF, LR, RR). `0x19E` byte 6 is the measured master pressure. [C]
5. On a car with independent front/rear master cylinders (bias bar), `0x2B2` shows the real per-circuit
   pressures; rear above master is physical, not an artefact. [I]

---

## 1. ADC acquisition

### 1.1 `adc_read` 0x6FB30 is a RAM-mirror getter
`adc_read(idx)` is a 59-entry jump table (table @0x6FB44). 42 indices map to the default stub 0x6FC56
(returns constant 1). The live indices `ld.h` from the ADC result mirror `0x4009CE[]` [C]:

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

`adc_read(21)` (seen at 0x8F34C and in KWP 0xB1A22) hits the stub; channel 21 carries nothing.

### 1.2 Slow scan: `sub_06FCC0`
Fills the mirror `0x4009CE[0..18]` with a burst of 19 reads from the safety ASIC over QSPI CS5
(`qspi_xfer` 0xD4CA8, r2=5); MUX command words from ROM table 0xD73DC. [C]

### 1.3 Fast wheel-pressure burst: `sub_06FD90(phase)`
A separate 5-word QSPI CS5 burst (command table ROM 0xD73C8) returns the four wheel-output channels; the
results are shifted `<<6` and passed to `sub_08FA00(phase, raw[4])`. Called from the sub-frame task
`sub_070BFC` (0x70C14) with a phase index, so the wheel pressures are sampled several times per 10 ms
control frame. [C] (exact sub-frame period [open])

---

## 2. Master / input sensor (S1)

- Raw cell `0x402954` (ASIC channels 6 / 7), acquired by `sub_0B85EC` (10 ms), ROM cal block 0x0F56F4,
  getter `sub_0B8720`. Conditioned by `pressure_adc_track` 0x8F344 into two tracks `0x4020DE` / `0x4020E4`
  (ratiometric scale gains 0x5EE8 / 0x556A, offset 0x97D). [C]
- `sub_08F488` learns a slow zero offset per track (`0x4020AA`, `0x4020AC`, ×16 fixed-point) and produces
  the offset-corrected tracks `0x4020E2` / `0x4020E8`. The validated, filtered master pressure is
  `0x401FF8` (clamped at 0 below 300). [C]
- Getters: `sub_093E1C(1, out)` → `0x401FF8` + validity; `sub_093F00(idx, out)` selects
  0→`0x4020DE`, 1→`0x4020E4`, 2→`0x401FF8`, 3→`0x4020AA`, 4→`0x4020AC`. [C]
- **Driver pressure `0x404994`** is committed by `dispatch_slot00_driver_pressure` 0x8CE5E (sole store
  0x8CE9E) [C]:
  1. master sensor valid → `0x404994 = 0x401FF8` (measured master);
  2. else, if `sub_08CDC4` finds valid wheel sensors with mean ≥ 100 (1 bar) → `0x404994 =` that mean
     (`0x404996`);
  3. else → modelled circuit pressure `0x40171A[0]` (or `[+4]`, chosen on `0x408DA1` b4).

---

## 3. Wheel-output sensors (four, w = 0..3)

Each sensor has two elements, processed as two independent tracks.

### 3.1 Primary track → measured wheel pressure `0x402198[w]`
`sub_08FA00(phase, raw)` per wheel [C]:
- scale the raw sample (`0x91A40`, full-scale 0xFFC0), store to ring `0x40202A[w][phase]` (4 samples),
  subtract the learned zero offset `0x40218C[w] / 16`, clamp ≥ 0;
- average the 4-sample ring → **`0x402198 + 4·w`** = `{s16 value, flags}` (unit 0.01 bar);
- also fill `0x40206A + 4·w` (two halfwords): measured when the sensor is valid, otherwise a copy of
  PM `0x4016E2[w]`. This is the cell the valve sequencer reads.

The same element is also read on the 10 ms scan (`adc_read` channels ROM 0xDA966 = 34, 35, 36, 37) by
`sub_08FBEA` → `0x40207A[w]`, low-passed (113/256) into `0x40208E[w]`, the input to offset learning.

### 3.2 Redundant track → plausibility
Raw cells `0x4029B6 / B8 / BA / BC` (acquired by `sub_0B85EC`, companion channels 44–47, ROM cal blocks
0x0F570C + 0x18·n, getter `sub_0B874E(idx)`), scaled into `0x402082[w]`, low-passed into `0x402096[w]`
with its own learned offset `0x40209E[w]`. Readers are confined to 0x08F–0x094xxx (cross-check against the
primary track, fault latching) plus KWP. This track does not feed control directly; it decides whether
the primary track is flagged valid. [C]

### 3.3 Zero-offset learning
`sub_08FCE8` (10 ms, from `sub_091A7C`) slews the offsets `0x40218C[w]` (±26/step) and `0x40209E[w]`
(±6/step) toward the filtered reading every 100 frames while the learn-enable flags are set
(`0x4020FC+1` b7, `0x402144+2` b2), bounded by a window of ±1000 raw and clamps 16000 / 21600. [C]

### 3.4 Validity
`sub_091A7C` builds the per-wheel flag byte `0x40219A + 4·w`: bit 3 / bit 4 are per-wheel fault bits from
`0x402888+1` / `0x402884+1`; **bit 7 (valid)** is set when bits 6 and 5 are set and bits 3, 4 are clear. [C]

### 3.5 Getters
| fn | returns |
|---|---|
| `sub_091A50(w, out)` | `0x402198[w]` value + flags; r2 = valid bit. **The control-side getter.** |
| `sub_094634(w, out)` | same value with diagnostic status bits |
| `sub_0946D0(sel, w, out)` | sel 0 → `0x402198`, 1 → `0x402096`, 2 → `0x40218C`, 3 → `0x40209E` (KWP) |
| `sub_08D030(w, out)` | CAN staging `0x40499A[w]` (= PM + flags) |

A 5-deep per-wheel history of `0x402198` is kept in `0x402222[w][5]` (`sub_091EA0`). [C]

---

## 4. Where measured wheel pressure enters control

### 4.1 `sub_082BC0` — measured/model selector for PM `0x4016E2[w]`
Called from `hydraulic_model_step` 0x82EF4 at 0x82F36, after the volume updates, every 10 ms. [C]

**Gate.** The wheel sensors are used only if `0x402888` b5 is clear and none of the fault ids
`35<<15, 57<<15, 59<<15, 61<<15, 63<<15` is latched (`fault_is_set` 0xB4312). The four getters are then
polled; `0x401719` b7 (front) and b6 (rear) end up set **only if all four sensors are valid** — one
invalid sensor drops all four wheels to the model.

**Per wheel**, with `st = 0x401A16[w]` (signed valve-pulse state: 20 = inlet fully open, 2·n = n inlet
steps, negative = outlet/dump active) and `c = circuit(w)` (ROM 0xDA1B4 = 0,0,1,1):

| condition | PM `0x4016E2[w]` | store |
|---|---|---|
| gate closed | `coa_vol_to_pressure(w)` — pure volume model | 0x81A34 |
| `st < 0` (sets `0x401715[w] = 1`), and until `st` next goes positive | `coa_vol_to_pressure(w)` | 0x81A34 |
| `st == 20`, pump flow in circuit within the last 5 frames (`0x401724[c] > 0`), `0x401A16[c+6] > 0`, `0x401DCC[c] != 3`, and PM < `sub_081AF4(c)` | `min(model interp, measured)`; if PM < 500 also `≥` previous PM | 0x82E06 |
| otherwise (normal) | **`= measured 0x402198[w]`** | 0x82E9C |

After a measured store, `coa_pressure_to_vol(w)` 0x816E8 rewrites the volume state `0x4016DA[w]` from the
new PM, so the model always restarts from the last measurement. On the first frame after a dump ends
(`0x401715[w]` 1 → 0), the difference between the modelled volume and the volume implied by the measured
pressure is added to the circuit accumulator volume `0x4016F2[c]` (clamped by `0x41B1E+6`). [C]

Because `0x4016E2` is measured in the normal case, **every reader of PM consumes measured pressure**:
`abs_pm_snapshot` 0x559CC → ABS PM `0x408F2A[w]`, `supply_pressure` 0x84D42, `wheel_volume_delta`, the
arbiter, the valve sequencer's pressure error, and the CAN staging copy.

### 4.2 Direct consumers of the measured value

| consumer | use |
|---|---|
| `sub_046ADC` (ABS, called 0x4627A) | reads `0x402198[w]` directly → `0x4045F4`; per-wheel filters `0x408E20 + 14·w` (+0 = ½-step tracker, +6 = slower tracker with ±5 % deadband). The struct is referenced from ~15 ABS routines (0x4BDE2…, 0x57042, 0x575A6…, 0x5A37A, 0x5B8D8). |
| `sub_055A84` (ABS, called 0x444CC) | 7-deep per-wheel pressure history `0x403296`; measured when the staging flag b5 and the getter are valid, else PM |
| `abs_hold_entry_sync` 0x57200 (0x57250) | getter call |
| `abs_decision_resolve` 0x58B30 (0x58DD6, 0x58E0A) | getter call |
| `valve_pulse_sequencer` 0x853A8 → `sub_084620` | loads `0x40206A[w]` into the pulse struct `0x401AF8 + 20·w + 10` |
| `sub_08CDC4` (from driver-pressure slot 0x8CE5E) | mean of valid wheel pressures → `0x404996` (master fallback, §2) |
| `coa_wheel_gain_apply` 0x84E38 (0x84E5E) | getter call |
| `sub_069992`, `sub_089D8A` (×4), `sub_08A90C` (×2), `sub_08B9E0` | getter calls — role [open] |
| KWP `0x21` 0xB184A (0xB1AEE, 0xB1D32) | `sub_0946D0` — wheel pressure, filtered track, offsets |

What each ABS routine does with the value in its decision logic is [open]; that they read the measured
value is [C].

---

## 5. CAN reporting

- **`0x2B2` bytes 0–3**: `sub_08CFCC` (dispatcher, after the model step) copies PM `0x4016E2[w]` into the
  staging array `0x40499A + 4·w` and builds flags: b6 = wheel-sensor system enabled (`0x402888` b5 clear),
  b5 = "PM is measured" (`0x401719` b7 for w 0,1; b6 for w 2,3), b7 = valid (b5 | b6). Getters
  0x7B490 / 4DE / 51C / 566 send `clamp(value/100, 0..254)`, `0xFF` when invalid. [C]
- **`0x19E` byte 6**: `sub_093F00(2)` → `0x401FF8`, measured master, same ÷100. [C]

Detail and byte maps: `07_pressure_on_can.md`.

---

## 6. Consequences

- Wheel pressure is **closed-loop on measured caliper-line pressure**. The COA p↔V curves size valve
  pulses (feed-forward) and carry PM through dump phases; their error is corrected on the next frame the
  inlet side is active. [C]/[I]
- A failed wheel sensor (or any of the five gate faults) silently changes PM, `0x2B2` and every consumer
  to the pure volume model; `0x2B2` flag b5 distinguishes the two cases on the bus. [C]
- Front/rear circuits are separate (wheel→circuit map 0,0,1,1). With independent master cylinders the
  measured rear pressures are independent of the master sensor; which input circuit the master sensor
  sits on is not determinable from the flash. [I]/[open]
- Both the M3 7846816A and the 1M 7846411A images carry five pressure-sensor cal blocks; the five-sensor
  acquisition is platform-standard. Whether the 1M image has the same `sub_082BC0` selector is [open].

## Open
- BMW DTC numbers for the five gate fault ids and the per-sensor cal blocks.
- Sub-frame sampling period of `sub_06FD90`.
- Mapping of redundant-track index (`sub_0B874E` 0..3) to wheel, and of sensors to physical block ports.

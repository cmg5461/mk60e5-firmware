# MK60E5 7846816A (E9x M3) — ABS per-wheel phase control: event classifier, phase machine, pressure targets

Instruction-level read of the M3 listing (`analysis/7846816A_main.lst`, simplified copy of the classifier in
`analysis/agents/m3absslip/ev_4D270.txt`). `01_core_slip_loop.md` §4–5 is the summary of this file.

**Conventions:** CPU addresses; file offset = CPU + 0x8000. Frame = 10 ms. Slip / speed **0.01 km/h**, accel
**0.01 g**, pressure **0.01 bar**. `0x6D0CC` = abs(). Wheel record `rec` = `0x40BF00 + 0x40·w` (w = 0..3, fronts
0/1, rears 2/3; a rear pointer has bit 7 set); current-wheel pointer `0x400978`; wheel index = `rec+0x2A`.
Tags: **[C]** read from the listing, **[I]** inferred, **[open]** unresolved.

---

## 1. Call structure  [C]

| Slot | Function | Per-wheel work |
|---|---|---|
| 12 `abs_frame_entry_a` 0x44502 | → `0x45EC4` (call at 0x446AC) | loop over 4 records: `abs_event_classifier` 0x4D270 (which ends by calling `abs_phase_sm` 0x4FC3C), then `0x4A6F0`. After the loop: `0x59B58`, **`0x45808`** (end-of-event reset, §6), `0x55658`, tail `0x5A0DC`. |
| 13 `abs_frame_entry_b` 0x447C4 | → `abs_pressure_frame` 0x45F54 (call at 0x448F0) | `abs_wheel_phase_dispatch` 0x504D0 → phase handlers (§5); then decision / rear select-low `0x5173C`. |
|  | → `abs_emit_pressure_request` 0x446B6 (bsr at 0x4490E) | `req_arbiter_submit(op, id 1 / 11 rear, ch, start = abs_p_start, target = abs_p_req_target, rate = abs_p_req_rate, flag = 0x408EFD[w])` |

`abs_p_cmd` itself is never submitted; the arbiter sees start / target / rate.

---

## 2. Wheel record fields used here

| Offset | Type | Meaning | Tag |
|---|---|---|---|
| +0x00 | u8 | phase byte (§4) | C |
| +0x01 | u8 | previous phase byte (copied by `abs_phase_sm` on entry) | C |
| +0x06 | s16 | excess speed loss: while wheel accel is below the decel threshold, += (accel − threshold)·360/1000 per frame (0x47318), i.e. 0.01 km/h lost faster than the threshold allows; decays toward 0 as accel recovers. Compared with E+4. Latched to `0x409026[w]` at dump entry; forced to ≥ 360 by the end-of-event reset | C |
| +0x0C | u8 | b1 = slip < E+6/2 while holding (set after the phase machine) | C |
| +0x17 | u8 | bits 2:0 hold-frame counter (`0x4D21C`): cleared in dump, +1 per hold frame with wheel accel < +0.30 g, saturates at 7 | C |
| +0x18 | u8 | flags (b3 selects E+6 instead of E+14 as entry threshold; b5 used by dump-pause gating) | C (use) |
| +0x19 | u8 | b5 = glitch/suppress (part of the suppress condition S) | C |
| +0x1A | s16 | filtered wheel speed, **not** tyre-corrected (`wheel_speed_filter`; `WHEEL_SPEED_CHAIN_7846816A.md`) | C |
| +0x1C | s16 | tyre-corrected wheel speed = +0x1A × (769 + rec+0x35)/1024 (slip2 reference); `TYRE_TOLERANCE_LEARNING_7846816A.md` | C |
| +0x20 | s16 | wheel acceleration, two-frame mean (`wheel_accel_update` 0xD20DC) | C |
| +0x24 | s16 | ABS low-passed wheel accel: `abs_wheel_decel_filter` 0x46390, rec+0x24 += 46/256·(rec+0x20 − rec+0x24), reset at phase events, −10…+5 g; compared with E+22 | C |
| +0x39 | s8 | peak-decel byte (a/16) | C |

---

## 3. `abs_event_classifier` 0x4D270 — walkthrough

`void abs_event_classifier(void)`: operates on `*0x400978`; frame = 144 bytes locals + saved r8–r15.

### 3.1 Stack frame

Threshold block **E = sp+104** (each field filled by one helper; all s16 unless noted):

| E+ | Contents | Writer |
|---|---|---|
| +0, +2 | rear L/R speed split (+0 also slip aggregate) | `0x4F85A`, `abs_axle_speed_split` 0x4F7D6 |
| +4 | allowance for rec+6 (0.01 km/h, negative): −(E+26 + 224) in the braking regime (`0x401FF2` b7 and `0x408DA1` b4), else −(E+26 + 450); +112 / +168 under phase flags; × curve 0x40622(−`0x40909E`)/120 in a cycle, ×2/3 of it with `0x40902E` b0/b1 | `0x477E8` |
| +6 | gross-slip threshold, curve 0xD6CE2(vref) | `abs_gross_slip_threshold` 0x52380 |
| +8 | second slip threshold: 7 % of vref (70·vref/1000), with adjustments | `abs_event_thresholds_C` 0x52774 |
| +10 | "faster than reference" threshold: −100 / −400 / −1000 | `abs_phase_decel_threshold` 0x52C54 |
| +12 | ≈ 7 % of vref | `abs_vref_pct_threshold` 0x52CD0 |
| +14 | effective entry threshold | `abs_eff_entry_threshold` 0x4F278 |
| +16, +18 | slip margins | `abs_hold_slip_threshold` 0x4F38E |
| +20 | low-speed slip margin | `abs_lowspeed_slip_margin` 0x4F5D4 |
| +22 | second decel threshold vs `rec+0x24`, 0.01 g: −130 default; for armed wheels with cal enable 0x40C96 ≠ 0 (= 1) and `0x408DC6` b2, curve 0x40CFC(lock-depth `0x409010`) = −150 at ≤ 10 → −130 at ≥ 30; −100 / −90 (< 45 km/h) / −120 under `0x40902E` b1/b4; −100 / −110 rear cases; −80; with E+34 b5, clamp(vehicle decel − 50, −130, −70) | `0x466A4` |
| +24 | max(200, vref/33) | `abs_event_prefilter_flags` 0x4FFF6 |
| +26 | max(125, vref/50) | 0x4FFF6 |
| +28, +30 | slip sums | `abs_slip_aggregates` 0x4F85A |
| +34..+37 | u8 flag bytes; copied to `0x40911E[4w]` before the phase machine | 0x4FFF6, `abs_event_partner_flags` 0x4F518 (+36), body |

Other locals:

| Slot | Contents |
|---|---|
| sp+28 / sp+29 | **EV0 / EV1** (u8) — the event word |
| sp+32 | curve 0xD6CE2(vref) (end-of-function use) |
| sp+40 | **slip** = ref − `rec+0x1A` (uncorrected). ref = vref `0x408DA8`; rears use `0x408DAA` when it exceeds vref and (`0x402914` b6 or `0x408DC6 & 0xC0 == 0x40`). Fronts use `rec+0x1C` when `0x408DF1` b7, the factory-stagger switch set by `abs_wheel_signal_frame` 0x461C0 (`TYRE_TOLERANCE_LEARNING_7846816A.md` §3.1). |
| sp+56 | **slip2** = ref − `rec+0x1C` (tyre-corrected) |
| sp+44 | record pointer, then reused as the **decel flag** (§3.2 step 5) |
| sp+52 | slip ≥ E+12, or partner-pressure condition |
| sp+60 | **entry flag** (slip past entry threshold) |
| sp+64 / sp+88 | RR (`0x40BFC0`) / RL (`0x40BF80`) record pointers |
| sp+68 | yaw-deviation flag |
| sp+72 | rear wheel, or EV1.b6 already set |
| sp+80 | partner rear is in a cycle |
| sp+84 | **slip-confirmed decel flag** |
| sp+48, sp+76, sp+96 | scratch |

### 3.2 Blocks in order

1. **Prologue / thresholds 0x4D270–0x4D336** [C]. Zero E+16/+18, E+28/+30/+32 and the flag bits of E+34..+37;
   call 0x4F85A, 0x4FFF6, 0x4F7D6, 0x4F5D4, 0x52380, 0x52774, 0x52C54, 0x52CD0, 0x4F38E, 0x477E8, 0x466A4.
2. **Slip 0x4D338–0x4D3A2** [C]: sp+40 / sp+56 as above.
3. **Entry flag sp+60, 0x4D3A4–0x4D4FE** [C]. Set if
   - (dumping wheel, partner/peak conditions) slip ≥ E+6/2 + E+16 + E+18 **and** slip > 400 (4 km/h); or
   - slip ≥ E[k] + E+16 + E+18, k = E+6 if `rec+0x18` b3 else E+14.
4. **Threshold copies + 7 % flag 0x4D500–0x4D624** [C]. Copies to `0x4090EE`, `0x4090F6`, `0x4090FE`, `0x409106`,
   `0x40910E`, `0x409130[10w]` (per-wheel RAM). sp+52 = slip ≥ E+12, also set when the partner is in a cycle
   and its PM > 1.2 × `abs_p_ref`.
5. **Decel flag sp+44, 0x4D626–0x4D73E** [C]. Side effect: slip ≥ E+6 + E+16 + E+18 with E+34 b4 →
   `0x409056[2w]` b2 ("gross slip seen"). sp+44 = 1 if
   - `rec+6` < E+4 and not dumping (when `0x40902E` b3 is set the test becomes `rec+6` < E+4/2); or
   - dumping and `rec+6` < half the dump-entry latch `0x409026[w]`; or
   - `rec+6` < −50, `0x409056` b2, wheel accel < −1 g, vehicle decel `0x408DAF` > −0.6 g.
6. **Slip confirmation sp+84, 0x4D740–0x4D8D6** [C structure]. Calls 0x4F518(E). sp+84 = 1 when sp+44 is set and
   slip ≥ E+8 (some paths E+8 + E+26; one path also needs accel > −2.6 g and E+36 b1 clear), or when the wheel is
   already in a cycle with `rec+6` < 1.5·E+4 and slip > E+8/2. sp+84 with E+36 b1 and b2 (not dumping) latches
   `0x40902E` b3+b2; without sp+84 (not dumping) clears `0x409056` b1.
7. **EV1.b3 "stay in pre-control" 0x4D8D8–0x4DBCC** [C structure, I detail]. Wheels in pre-control only; blocked by
   `0x409046` rear flags and `0x408DA2` b5. Inputs: longitudinal accel `0x408E80` (−0.5 g / −0.3 g),
   `0x408E6A`, `0x408E7B`, coding byte `0x4031AB` == 10; result latched in `0x40902F` b7. EV1.b3 set at
   0x4DB80 / 0x4DBCA when `rec+6` < 0, or `rec+0x24` < E+22, or a decel-gate combination holds.
8. **Front cancel 0x4DBF8–0x4DD50** [C structure]. Clears sp+60 and sp+44 for fronts under conditions on vref,
   `rec+0x18` b3, the peak byte, `0x4090B6` > 75, `0x40903A` flags and driver pressure (cancels a front dump
   start). Rear path 0x4DD12 does the same when neither rear is in pre-control / dump and wheel accel > +1 g.
9. **EV0.b7, EV0.b6 0x4DD6A–0x4DEC2** [C].
   - EV0.b7 (armed → 0x84): sp+72 and slip2 < E+10 (wheel faster than reference).
   - EV0.b6 (pre-control): `rec+6` < 0 (or the `0x408DF1` b4 path), `rec+0x24` < E+22 (+30 / +10 margins
     by `0x408E7B`) or wheel accel < −1 g, vehicle decel `0x408DAF` < 0, sp+52 or rear, `0x408DC6` b6, no
     `0x409049` latch bits.
10. **Rear decel-gate latch 0x4DEC4–0x4DFA2** [C]. Rears with `0x408E1C` b7: `0x408E80` < −cal 0x40C94 (or
    −cal + 15), `rec+6` < 0, counter `0x409014[w]` ≥ 2, not in a cycle, no fault, `0x401FF2` b7, driver pressure
    `0x408EB2` > 0, `0x408E6D` b6 → `0x409049[4w]` b3, snapshot driver pressure to `0x408E72`.
    Trigger: (ax < −0.55 g AND `0x40902E[2w]` & 0x12) OR (`0x408E94` < −700 AND
    3 ≤ `0x408E6A` ≤ 24). Also needs `rec[0]` & 0x41 = 0 and no EV0.b6 this frame. This latch feeds CAN
    0x19E ST_CLCTR bit 32 when no rear is in an ABS cycle (see FACTS, ST_CLCTR).
11. **EV0.b5 — start a dump, 0x4DFA4–0x4E0DC** [C]. Cleared, then set at 0x4E052 if
    - slip ≥ E+6 + E+16 with ABS mode bits `0x408DA1 & 0xE0` clear; or
    - wheel accel < −1 g, `rec+0x24` < E+22 (fronts: < E+22 + 30 when `0x408DC4` b2 and `0x408E6A` ≥ 25), and
      sp+84; with mode bits set, also wheel speed < `0x408EC4`;
    - final gate: `0x408DC6` b6, or rear wheel with no sensor fault (`0x400952` b0).

    New dump latches `rec+6` → `0x409026[w]`. Second site 0x4E0CC: rear in pre-control, `0x408E98` > 80,
    E+35 b1 clear, `rec+6` < 0 or slip > E+6/2; also sets `0x40902F` b4.
12. **Yaw-deviation flag sp+68 0x4E0DE–0x4E1D4** [C]. Only with `0x408DF0` b7 / b6 and |lat| ≥ 40: compares
    yaw − AYC target (`0x408ECC − 0x400B1A`) with `0x408ED8` in ±1400 / ±700 bands.
13. **Combined rear-axle dump 0x4E1D6–0x4E59C** (rears only) [C].
    - Σ = `rec+6`(RL) + `rec+6`(RR), compared with E+4 × 1.2 / 0.7 / 1.3 / 1.45; each tier adds slip tests
      against E+8 × 0.7 / 1.2 / 0.6 (or E+28 × 0.5) and `0x409014` counters.
    - On a pass with neither rear reapplying / dumping: counter `0x409057[2w]` bits 2:0 += vref/1000
      (+1 per 10 km/h), capped at 7; otherwise cleared.
    - Counter ≥ 5, wheel not in a cycle → **EV0.b5** (0x4E586) and `0x409057` b6.
    - Effect: a large combined rear-axle decel starts a dump on a rear that is not slipping on its own yet.
14. **Yaw / dump-reduction inputs 0x4E59E–0x4E906** [C]. Lateral term + vref-dependent yaw threshold (sp+48).
    Same-sign yaw rate / yaw accel past limits vs `0x408EA0` / `0x408EA2` → **E+37 b7** (yaw-limited) and
    `0x40912E[10w]` = 100. Also writes `0x409134[10w]` = curve 0xD6CA8(vref/10) and `0x409132[10w]` =
    cal 0x40B06 − yaw-accel term (floor cal 0x403E4). These slots belong to the per-wheel 5 × s16 record
    `0x40912E + 10w`, which each phase overwrites with its own values (dump entry zeroes it and stores its R
    breakdown, §5.2), so they are not inputs to the dump target.
15. **Cornering latch 0x4E908–0x4EC1E** (rears only) [C structure]. Conditions: |lat| / yaw, driver pressure > 0,
    front PM > 1 bar, coding gates `0xCFC18` / `0xCFC56`, not in a cycle, no fault. Sets `0x409049[4w]` b2+b5 and
    snapshots lat byte → `0x408EDA`, driver pressure → `0x408ED6`, yaw → `0x408EA0`, yaw − target → `0x408EA2`,
    `0x408E1B` b1. Released at 0x4EBEC when driver pressure < curve 0x40E26(|lat|) × 100 or the lateral
    conditions lapse.
16. **0x4EC20–0x4EDEC** [C].
    - Rear-latch release: `0x409049` b3 cleared when ax > −cal + 15 or driver pressure leaves the snapshot window.
    - EV0.b6 second site 0x4ECBC: a `0x409049` latch bit and `0x408DC6` b6.
    - **EV0.b4** (0x4ECE8): `rec+6` ≥ 0; fronts also when wheel accel > +1 g with sp+52 and `0x408DC4` b2 clear.
      **Not read by the phase machine.** EV0.b2 is cleared and never set.
    - **EV0.b3** dump → hold (0x4ED94) [I detail]: via `rec+6` vs E+4/2, `rec+0x18` b3, `0x40902F` b4 and vehicle
      decel < −0.6 g, gated by the mode bits and sp+60; blocked while forced dump `0x40903A[3w]` b5 is set.
    - **EV0.b1** pause reapply (0x4EDEA): slip2 < E+10, (sp+72 or vref < 10 km/h), (`0x408DC6` b6, or
      `0x401150` b4 clear and fault 13 inactive via `0x7D16A(13)`), mode bits clear.
17. **EV0.b0 — dump again, 0x4EDEE–0x4EF7C** [C].
    - slip ≥ E+6 + E+16 + E+18 (+100 while holding with `rec+6` ≥ 0) with mode bits clear; or
    - wheel accel < −1 g, `rec+0x24` < E+22 and sp+84; or `0x40902E[3w]` b3;
    - 0x4EED8: `0x409057` count ≥ 5, wheel in a cycle, `0x408DA2` b7 clear (also `0x409057` b6);
    - rear clause 0x4EF72, gated by `0x408E5F` b1 or `0x400B09` b6: RR with `rec+6` < 0 and lat ≥ 6, or RL with
      lat < −5 → EV0.b0 if in a cycle, else EV0.b5 (direction-selective rear dump).

    Every site latches `rec+6` → `0x409026`.
18. **EV1 bits 0x4EF7E–0x4F02C** [C].
    - b7 hold → reapply: after `0x4D21C`, hold counter `rec+0x17 & 7` ≥ 3.
    - b6: sp+72, slip2 < E+10, mode bits clear, `0x40905E` b6 clear.
    - b5: slip2 ≥ E+10, or (sp+72 clear and `0x408DA1` b4 clear).
    - b4: slip2 ≥ E+10.
19. **Bookkeeping 0x4F02E–0x4F1AC** [C]. On EV0.b0: `0x409056` b1 and rear direction bit `0x40903B[3w]` b0.
    `*0x400980` wheel: `0x408DB5` b6 = slip ≥ curve(0xD6CE2)/4. Fronts not in dump / hold: `0x408DED` b4 (FL) /
    b3 (FR) = slip ≥ (E+6 + E+16 + E+18)/2 and `rec+6` > −100. `0x409056` b2 cleared when a reapply / armed wheel
    fires EV0.b0 / EV0.b5 (unless E+34 b4). E+34..+37 → `0x40911E[4w]`. Calls
    `abs_phase_sm((EV0 << 24) | (EV1 << 16))`.
20. **After the phase machine 0x4F1B0–0x4F236** [C]. New pre-control entry (with `0x408DA2` b6 and `0x401FF2` b7
    clear) → `0x408DEE` b4. `0x409056` b0 (low speed) = wheel speed < 4 km/h or `0x40094A[w]` < 400, and
    `0x408EC0` ≥ 30. In hold: `rec+0x0C` b1 = slip < E+6/2.

### 3.3 Event word summary

| Bit | Meaning | Set at | Used by `abs_phase_sm` |
|---|---|---|---|
| EV0.b7 | overspeed while armed | 0x4DD8E | armed → 0x84 |
| EV0.b6 | pre-control | 0x4DEC2, 0x4ECBC | armed → 0xC0 |
| EV0.b5 | start a dump | 0x4E052, 0x4E0CC, 0x4E586, 0x4EF72 | armed / pre-control → 0x21 |
| EV0.b4 | wheel not decelerating past threshold | 0x4ECE8 | no (logged) |
| EV0.b3 | release dump | 0x4ED96 | 0x21 → 0x09 |
| EV0.b2 | — | never set | no |
| EV0.b1 | pause reapply | 0x4EDEC | 0x11 → 0x15 |
| EV0.b0 | dump again | 0x4EE78, 0x4EED8, 0x4EF72 | 0x09 / 0x11 → 0x21 |
| EV1.b7 | hold → reapply | 0x4EFA2 | 0x09 → 0x11 |
| EV1.b6 | overspeed in hold | 0x4EFEA | 0x09 → 0x15 |
| EV1.b5 | overspeed cleared | 0x4F014 | 0x84 → 0x80 |
| EV1.b4 | overspeed cleared | 0x4F02C | 0x15 → 0x11 |
| EV1.b3 | stay in pre-control | 0x4DB80, 0x4DBCA | holds 0xC0 |

`abs_phase_sm` logs the word to `0x409116[2w]`.

---

## 4. `abs_phase_sm` 0x4FC3C  [C]

`void abs_phase_sm(u32 ev)`; EV0 = ev bits 31:24, EV1 = bits 23:16. Phase bits: b7 armed, b6 pre-control,
b5 dump, b4 reapply, b3 hold, b2 reapply-paused / overspeed, b0 in an ABS cycle.

**Preamble:**
- `rec+1` = old phase; event word → `0x409116[2w]`.
- (old b7 and EV0.b5) or (old & 0x18 and EV0.b0) → `0x409047[4w]` b3.
- `0x40903A[3w]` b5 → EV0 |= b0 | b5 (forced dump); if not dumping, `0x409026[w]` = `rec+6`.
- `0x40905E[3w]` b6 → clear EV0 b0, b3, b5, b6 and EV1 b7.
- `0x408DC6` b7 on a front wheel → clear EV0.b5.

**Suppress condition S** = (`0x400952[w]` b3 and (b0 or front wheel)) or `rec+0x19` b5.

| From | Condition | To |
|---|---|---|
| 0x80 armed | S | no change |
| 0x80 | EV0.b5 / EV0.b6 / EV0.b7 (first match) | 0x21 / 0xC0 / 0x84 |
| 0xC0 pre-control | S | 0x80 |
| 0xC0 | EV0.b5 | 0x21 |
| 0xC0 | EV1.b3 | stay |
| 0xC0 | otherwise | 0x80 |
| 0x84 | EV1.b5 | 0x80 |
| 0x21 dump | S or EV0.b3 | 0x09 |
| 0x11 reapply | S | no change |
| 0x11 | EV0.b0 / EV0.b1 | 0x21 / 0x15 |
| 0x09 hold | S or `0x409049[4w]` b0 | 0x11 |
| 0x09 | EV0.b0 / EV1.b7 / EV1.b6 (first match) | 0x21 / 0x11 / 0x15 |
| 0x15 | EV1.b4 | 0x11 |

No transition in `abs_phase_sm` returns a wheel from 0x09 / 0x11 / 0x15 to 0x80; that is done by `0x45808` (§6).

---

## 5. Phase handlers and pressure targets  [C unless tagged]

`abs_p_ref` 0x408FF0 is the previous cycle's lock pressure: `abs_cycle_ref_update` 0x5884A copies `abs_p_lock`
into it at the start of each dump (from armed or reapply).

Per-wheel pressure arrays are listed with types in `analysis/7846816A_symbols.md` (all `s16[4]` except
`abs_p_rear_cmd_prev` `s16[2]`).

The reference pressure is **`abs_p_lock` 0x408FD0** (lock-onset estimate): captured as min(`abs_p_wheel`, 20000)
in the reapply step (0x5820E) and maintained by `abs_lockon_pressure_estimator` 0x5862C. The cycle dumps below
it, holds, then steps back up toward it.

**Dump** `abs_phase_dump_handler` 0x4AAA8 (first frame → `abs_dump_entry_target` 0x55F06):
- `abs_p_dump_target` = max(0, `abs_p_lock` − R); R is built in 0x55F06 from a lock-pressure percentage plus
  decel-rate, wheel-decel and (rear) slip terms; full decode in §5.2.
- `abs_p_cmd` = min(`abs_p_dump_target`, `abs_p_dump_cap`) (0x56192), where `abs_p_dump_cap` =
  max(0, wheel pressure `0x4016E2[w]` − `0x401D00[w]`) is rewritten every frame by `abs_pm_snapshot` 0x559CC.
  The cap guarantees each dump goes at least `0x401D00[w]` below the current pressure.
- `abs_p_req_rate` = −8000 (maximum release); `abs_p_min` tracks min(`abs_p_wheel`).
- Later dump frames: pause / continuous / stepped release, decoded in §5.3.
- `abs_p_cmd_max` = `abs_p_cmd` at the end of each dump frame.

### 5.2 `abs_dump_entry_target` 0x55F06 — dump entry target  [C]

`s16 abs_dump_entry_target(void)` (current wheel `*0x400978`, i = wheel index). Called only from the dump
handler 0x4AAA8 (0x4AAF0), on the first dump frame (when `rec+1` b5 is clear). Writes `abs_p_cmd`,
`abs_p_dump_target`, `abs_p_req_rate`, the dump count, the sub-phase byte, and the breakdown record
`0x40912E + 10i` = {[0] R0, [1] A, [2] B, [3] R} (all s16).

Curves use `curve_interp_s16` 0x710FC: `[lo, hi, n, xs[n−1], cs[n], ks[n]]`, `i = count(xs[j] < x)`,
`y = clamp(cs[i] + x·ks[i]/1024, lo, hi)` (division truncates toward zero). None of the curves or constants below are in the XDF except
0x40B08 (XDF "ABS decel ladder", 6 values; this routine uses the first four).

**Re-dump from hold** (`rec+1` b3): no new R. `abs_p_cmd` = min(`abs_p_cmd`, PM) when `rec+0x10` b2 or
`0x408DEF` b1, else max(0, min(`abs_p_min`, `abs_p_dump_cap`)). Sub-phase byte 18. Then rate −8000.

**Otherwise** (entry from armed, pre-control or reapply):

1. `abs_p_cmd` = `abs_p_lock`; sub-phase byte `0x408FCC[i]` = 16.
2. **Base R0** = pct · `abs_p_lock` / 100, pct = curve(`abs_p_lock`): front **0x40994**, rear **0x409BC**.

   | lock (bar) | 10 | 17.5 | 20 | 30 | 40 | 50 | 60 | 66 | 80 | 100 | 150 |
   |---|---|---|---|---|---|---|---|---|---|---|---|
   | front pct | 16 | 11 | 11 | 11 | 10 | 8 | 8 | 8 | 8 | 8 | 8 |
   | rear pct | 16 | 13 | 13 | 11 | 10 | 10 | 9 | 6 | 6 | 6 | 6 |

   (front: lo 5, hi 50; rear: lo 5, hi 100). R0 is roughly 8 % of lock pressure at normal pressures (front 80 bar
   → 6.4 bar), more at low pressure, and the rear drops to 6 % above 66 bar.
3. **A** = `0x55B44()`, decel-rate term (→ `0x409130[10i]`). Input d = `0x408DD0` = `rec+0x20` − `rec+0x24`
   (wheel accel minus the second decel value, set by 0x4B09C at dump-handler entry; negative while decel is
   still building). Thresholds c1..c4 = cal 0x40B08 / 0x40B0A / 0x40B0C / 0x40B0E = −140 / −90 / −40 / −210
   and accel limits a1/a2/a3 = −300 / −220 / −170 (0.01 g). Below 60 km/h (or `0x408E1A` b0, or `rec+0x16` b7)
   all are halved (a = −150 / −110 / −85); below 20 km/h (or `0x408E1A` b0) halved again (a = −75 / −55 / −42).
   - A = 0 when: `0x408DF0` b7 and wheel = FL, or b6 and wheel = FR; rear with `0x408DEB` b5 or `rec+0x17` b7;
     `0x40902F[3i]` b4; or `abs_p_ref` ≤ 2000.
   - d ≥ 0 (decel easing): A = −400 (d ≤ 50), −650 (≤ 100), −1000 (> 100); 0 if `0x408DB5` b4.
   - c1 < d < 0, accel ≥ a1, `0x408DA1` b2 clear: A = −150; −300 if d > c2 and accel ≥ a2; −500 if also
     d > c3 and accel ≥ a3.
   - otherwise (decel building fast, or accel < a1, or `0x408DA1` b2): A = 200 if `0x408E1A` b0 or
     (`rec+0x16` b7 and vref < 60 km/h), else 0; plus, if d < c4 and `rec+0x10` bits 7:5 < 2,
     −cal 0x40B6E (= 20) · d / 10 = 2·|d|.
4. **B** = `0x55CE8()`, wheel-decel term (→ `0x409132[10i]`). 0 unless wheel accel `rec+0x20` < 0; then
   B = clamp(F · g · s · |accel| / 50000, 100, 1200):
   - F (`rec+0x16` b7 set): 100 below 50 km/h, 80 for 50–80, 60 at ≥ 80 km/h.
     F (clear): 90 below 50 km/h, else 60; halved when `0x40902E[3i]` b3 and vref > 60; then +200 if
     `0x408DEF` b7 (added to B, not F).
   - g = 100 and s = 10 by default. Only for 20 < vref ≤ 60 km/h (cal 0x40BE8 = 2000, 0x40BE6 = 6000):
     - g = 100 + curve **0x40BCA**(vref) (90 at 0 → 29 at 20 → 9 at 40 → 1 at ≥ 60 km/h); + curve **0x40B70**
       (`abs_p_lock`) (−40 at 0 → −2 at 80 → +40 at ≥ 120 bar) when flag P is set.
     - if `rec+0x10` b4 clear and `rec+0x0F` high nibble < 2: slip% = (vref − v)·100/vref (→ `0x408DD2`); when
       slip% ≥ 13 or (`rec+0x16` b7 and vref < 60): s = 10 + curve **0x40B92**(slip%) (0 below 13 %, 10 at 20 %,
       15 at 30 %, 25 at 50 %), + curve **0x40BAE**(wheel speed) (40 at 0 → 15 at 20 → 9 at 50 km/h) when P;
       +3 if (s ≥ 21 and not previously dumping) or P; + (slip% − 20) when `rec+0x0F` high nibble = 1;
       s clamped to [10, 25].
   - Flag P (fronts only, with `0x408E1A` b1): the other front has `rec+0x24` < −130 and `rec+6` < −100, and if
     it is dumping its slip exceeds vref/4.
   - Example: F 60, g 100, s 10 gives B = 1.2 × |accel| (3 g → 3.6 bar); clamp 1–12 bar.
   - F (60/80/90/100) are code literals (movi). The divisor 50000 is one literal-pool word at **0x560B0**
     (file 0x5E0B0) used only by the three B formulas (0x55E40 / 0x55E9E / 0x55EBE), so patching that word
     scales B globally (e.g. 100000 halves it). B is pressure per g of wheel decel, so it implicitly assumes
     stock brake torque per bar.
5. R1 = R0 + A + B (→ record [3]).
6. **Low-pressure scaling**: when (`0x408DEB` b5 or `rec+0x17` b6 or `0x408DEE` b6, or a front with `rec+0x17`
   b3) and PM < 2500: R ×= curve **0xD6C60**(PM)/100 (200 % below 10 bar, 166 % at 12, 133 % at 14, 100 % at
   ≥ 16 bar).
7. **Rear slip term C** (rears only, decision code `0x408DDE` ≠ 1): R += `0x56996()`.
   - own = (vref − own speed), partner = (vref − other rear speed), 0.01 km/h, negatives clamped to 0.
   - "low decel" L = vehicle decel `0x408DAF` > −0.5 g, or vref slope `0x408DB8` < 50.
   - Both rears were armed last frame:
     - own `0x409057` b6 (combined rear dump, classifier block 13): o = 30·own/300; p = 70·partner/250 if
       partner > 3.5 km/h.
     - else: o = 70·own/200 if L, else 0; p = 140·partner/120 if partner > 1.5 km/h.
     - o and p are doubled when the respective wheel has `0x40902E` b7.
   - Otherwise (own `0x409057` b6 set → C = 0):
     - o = 70·own/200 if L, else 70·own/300.
     - p needs partner `0x409056` b2 and partner > 2 km/h: 140·partner/120 if L, else 140·partner/300;
       p ≤ 200 when L.
   - p is skipped when the partner is reapplying (`rec+0x10` b4) without `0x40902E` b7.
   - C = o · curve **0xD6C4A**(`abs_p_lock`) / 1000 + p (curve 600 at 0 → 998 at ≥ 80 bar).
8. **Decel-onset scaling** by `0x40902E[3i]` flags and wheel accel < −2 g (k1 = curve **0x40B4C**(x),
   100–200 %: 100 at 0, 115 at 200, 139 at 300, 152 at 600, 169 at 1000; k2 = curve **0x40B14**(y), 0–50:
   0 below 400, 14 at 500, 40 at 800, 50 at ≥ 1200; x = −`0x40909E[i]`, the latched accel − `rec+0x24`
   difference from 0x4FB44; y = −accel):
   - b1 set: front R = R·k1(x)/100 · (1 + k2(y)/100); rear ×1.25 if a front is in dump / pre-control without
     `rec+0x16` b7 and `0x408DA2` b5.
   - b4 set (b1 clear): front same with x/2 and y/2; rear ×1.25 on the front condition alone.
   - b1, b4 clear and b3 clear: all wheels R = R·k1(x)/143 · (1 + k2(y)/133).
   - accel ≥ −2 g: no scaling.
   - k1 0x40B4C and k2 0x40B14 are read only here (0x560AA–0x5614C). k2 header is [lo 0, hi 150, n 5]; setting
     hi (0x40B16, file 0x48B16) to 0 removes the k2 boost without touching k1.
9. `abs_p_dump_target` = max(0, `abs_p_lock` − R). If below `abs_p_cmd`: `abs_p_cmd` = min(target,
   `abs_p_dump_cap`) and the dump count (high nibble of `0x408F1B[2i]`) +1.
10. Sub-phase byte 17, mode bits in `0x408EFD[i]`, `abs_p_req_rate` = −8000.

So the entry dump is: drop from the lock pressure by ≈ 8 % of it, corrected by how fast decel was building (A),
how hard the wheel is decelerating (B), low-pressure doubling, rear slip (C) and the decel-onset factors, then
never shallower than `abs_p_dump_cap`. The 10 / 15 / 20 bar ladder (cal 0x40E64/66/68) is not used here; it
belongs to `abs_dump_stage` 0x5424C (later dump stages).

Illustrative front case (inputs assumed, not logged): lock 80 bar, vref 100 km/h, accel −3 g, d between c2 and c3,
flags clear, `0x40909E` = −150: R0 = 640, A = −300, B = 360 → 700; ×k1(150) = 109/143 → 533; k2(300) = 0.
Target ≈ 74.7 bar, i.e. about 5 bar below lock, then capped by `abs_p_dump_cap`.

### 5.3 Dump phase, every frame after entry  [C unless tagged]

Each dump frame `abs_phase_dump_handler` 0x4AAA8 runs (i = wheel index):

1. `abs_dump_frame_inputs` 0x4B09C: d = `0x408DD0` = accel (`rec+0x20`) − `rec+0x24`; `0x408DCE` = accel/16;
   `0x4090BA[i]` = min(itself, peak byte `rec+0x39`); `0x4090A6[i]` = 1 if 0.
2. First frame only: `abs_dump_entry_reset` 0x4B012 (zeroes `0x408FAC[i]`, `0x408FB4[i]`, the dump-count nibble,
   `rec+0x30`; `0x40908E` = `0x409096` = 1; ...) and `abs_dump_entry_flags` 0x4ADD4 (flag bookkeeping only).
3. `abs_dump_frame_flags` 0x4B160 rebuilds flag word **`0x408DD4`** (bits 31..27) for this wheel:
   - **b31 "re-accelerating"**: wheel accel > T, T = 30 (60 / 90 under forced dump with driver pressure < 10 bar
     and `0x408E6D` b6), halved when `rec+0x38` > 0 and not forced. Also set on fronts early in the dump
     (`0x408FAC` < 13, v > 5 km/h, `abs_p_ref` > 40 bar) once accel/16 ≥ half the cycle's peak decel
     (`0x4090A6`) with accel > −3.5 / −2.5 / −2 g by sub-case. A rear under forced dump has b31 cleared if it slips
     at least as much as the same-side front. Copied to `0x40912E[10i]`.
   - **b30 "keep dumping"**: PM < 10 bar with (`0x408DEB` b5, or `rec+0x17` b6, or a front with `0x408DEE` b6);
     also set by 0x56C60 for very deep slip (below).
   - **b28 / b27 "cornering"**: |lat| > 50 / > 80 on the front selected by `0x408DF0` b7 / b6 (rear on that
     side not in a cycle, `0x408E6D` b7). They cut step sizes to 1/2 / 1/3 (0x56728).
4. `0x408FB4[i]` (**step-wait counter**) += 1; reset to 0 while the valve state `0x401A16[i]` < −5 (outlet
   still releasing). So the wait for the next step starts once the previous release has been delivered.
5. Release by flag (first frame: entry target §5.2, then `abs_p_min` = min(`abs_p_lock`, PM), forced-dump override
   0x57024, sub-stage `0x408F1A` bits 6:4 = 1). Later frames, `abs_p_min` = min(`abs_p_min`, PM), then:
   - **b31 → pause** (sub-stage 3, sub-phase 0x30): on the first paused frame, if `abs_p_cmd` < PM and
     `abs_p_cmd` < `abs_p_min`, `abs_p_cmd` = PM (stop where the pressure actually is); latch it in
     `0x408F9C[i]`; later paused frames hold `abs_p_cmd` = `0x408F9C[i]`. Rate 0.
   - **b30 → continuous** (sub-stage 2, sub-phase 0x20): `abs_p_cmd` = min(max(0, `abs_p_cmd` − 1000),
     `abs_p_dump_cap`) — 10 bar per frame — at rate −8000.
   - **neither → stepped** (sub-stage 5): while the valve is still releasing (`0x401A16` < 0), latch
     `0x40908E[i]` = accel (−1 if 0) and `0x409096[i]` = slip (1 if 0) — the reference values at the end of the
     release. Then `abs_dump_continue` 0x562DC.
6. Every frame: forced-dump flag `0x40903A[3i]` b5 is cleared after ≥ cal 0x40AE4/10 = 5 dump frames (or at once
   unless `abs_p_cmd` + 3 bar < PM, or a rear with yaw rate and yaw accel of the same sign); `0x408FAC[i]` (frames
   in dump) += 1, `0x408EF7[i]` = 0 at ≥ 50; `abs_p_cmd_max` = `abs_p_cmd`; `0x40907A[i]` = step period.

**`abs_dump_continue` 0x562DC** (sub-phase 0x51, rate −8000, clears `0x408DD4` b26):

- `abs_dump_step_period` 0x56C60 sets the **step period P** (frames) in `0x408DCC` from the table
  **cal 0x40BF0 = [178, 5, 3, 2, 2, 1, 0]**. With slip s = vref − v and k = max(400, vref/20) (i.e. 4 km/h or
  5 % of vref):
  - s ≥ 12k + 1000, or s ≥ 12k unless (`rec+0x10` b1 and vref ≥ 60 km/h): P = 0 and **b30 set** (next frame
    switches to continuous 10 bar/frame). 12k ≥ 48 km/h, i.e. the wheel is essentially locked.
  - s ≥ 8k: P = 1. s ≥ 5k: P = 2. s ≥ 4k with `0x408E7B` > 55 and `rec+0x16` b7: P = 2.
  - otherwise P = 3 or 5: 3 when `rec+0x17` b7, `0x409056[2i]` b7, `0x408DEE` b3, or `0x40907E[i]` > 3k
    (rears also when own + partner `0x40907E` > 1.5k); else 5. Rears: −1 when vehicle decel is weaker than 0.6 g or
    vref slope `0x408DB8` < 60. Fronts: P = 178 (no scheduled steps) when s < clamp(vref/20, 400, 600) and
    (vehicle decel ≤ −0.8 g or slope > 80).
  - rear with `0x40903C[3i]` b7 and not forced: +12 when the yaw rate is on that wheel's side of `0x408EA4`.
  - if P < 10 and not `rec+0x16` b7: +1 for each of current decel ≤ 75 %, 50 %, 25 %, 12.5 % of the cycle's peak
    decel (`0x4090A6` = peak a/16, kept by `wheel_peak_decel_byte` 0x46390). Capped at 15.
- n = step-wait counter (+1 if the valve is idle).
- **Scheduled step, n ≥ P** (sub-phase 0x52): D = `abs_dump_step_amount`() then `abs_dump_step_scale`() when the
  dump count is 1 or 2 and not forced; otherwise D = slip/2 (0.01 km/h read as 0.01 bar). Stored in `0x408DC8`.
- **Early step, n < P**: wait threshold W = cal 0x40B48 (4) + m (stored in `0x40912E[10i]`), with
  m from the decel ratio r = 100·accel/`0x40908E` and slip ratio q = 100·slip/`0x409096` (the release-end
  references):
  - with `0x40902E+2` (`0x409030[3i]`) b7: m = −2 for a front below −6 g or a rear below −4 g;
  - v > 10 km/h: r > 120 → −2; r > 100 or > 90 → −1; r < 20 → +4; < 30 → +3; < 50 → +2; 50–90: q > 160 → −2,
    q > 140 or > 120 → −1, else 0 (cal 0x40B36..0x40B40 = 120/100/90/50/30/20, 0x40BEA..EE = 160/140/120);
  - v ≤ 10 km/h: −2 (v < 5 km/h) else −1; front low-speed special case (`0x408E1A` b1 or `0x408DEF` b7) → +10.
  - So W = 2–8 frames (14 in the special case): decel deepening since the last release → step sooner;
    decel fading → wait longer.
  - Front steps when n ≥ W and (`rec+6` < −560, or d < cal 0x40B0E (−210), or v < 20 km/h with `0x408E1A` b1 and
    `rec+6` < −280). Rear steps when n ≥ cal 0x40B4A (4) and (`rec+6` < −400 or d < −105).
  - Step only if accel < −1 g or v < 10 km/h, not re-accelerating (b31), and not (`rec+0x10` b2 with
    `0x408E7B` ≤ 100). Sets b26, sub-phase 0x54, D = step_amount() → step_scale().
- **Apply**: if D < `abs_p_cmd`: `abs_p_dump_target` = `abs_p_cmd` − D, `abs_p_cmd` = min(that,
  `abs_p_dump_cap`), dump count +1 (max 14), sub-phase 0x52. If D ≥ `abs_p_cmd`: target = `abs_p_cmd` = 0.

**`abs_dump_step_amount` 0x56728** (→ `0x409136[10i]`; a = accel, s = slip, k = max(400, vref/20)):
- **Early step** (b26): if a < 0: rear D = |a|; front D = min(2|a|, 1200) when (`rec+0x16` b7 and
  `0x408EF7` < 15) or vref < 60 km/h, plus 2s/3 if a/16 < 2/3 of peak (`0x4090A6`) or s/3 if < 1/2 of peak;
  otherwise front D = max(1.5|a|, 2s/3). Then D = max(D, 400). If a ≥ 0, D starts at 0.
  - + 2|d| when d < cal 0x40B10 (−350) (with `rec+0x10` b4 clear, `abs_p_ref` > 30 bar, `0x408EF7` < 15,
    `0x40902F[3i]` b4 clear); + |d| more when d < cal 0x40B12 (−490). (These are the last two "ABS decel ladder"
    XDF values.)
- **Scheduled step**: D = max(1200, s/2) when `rec+0x16` b7, else max(1000, 2s/5); × 2/3 with `0x40903C[3i]` b7;
  then D = 800 when `rec+0x17` b7, `0x409056[2i]` b7, `0x408DEE` b3, `0x40907E[i]` > 3k, or (front and
  `0x40907E` > 1.5k or s > 2.5k). Rears in a coupled pair (code ≠ 1): + (partner slip − curve 0xD6C8C(vehicle
  decel)) when positive; curve 0xD6C8C = 200 down to −0.4 g, 280 at −0.6, 440 at −0.8, 600 at ≤ −1.0 g.
- Both: b27 → D/3, b28 → D/2.

**`abs_dump_step_scale` 0x56EDC** (applied to the two cases above) [C structure, I meaning]:
- c = max(1, s/32); ref = `rec+0x32` (byte, writer not traced); r5 = max(1, 100·ref/c).
- If c < ref or a ≥ 0: D = D·100/r5 (D scaled by current slip / reference); then D −= 200 when a > −1 g,
  r5 > 300 and ref > 12·vref/3200.
- Else: D = D·100/r4, r4 = min(100, 100·peak/(a/16 adjusted)) — D grows when the current decel is near or beyond
  the cycle peak.
- 0 < D < 200 → D = 200.

**Forced-dump override `abs_dump_forced_target` 0x57024** (first frame, only with `0x40903A[3i]` b5):
F from the front filtered-pressure difference e = |`0x408E20` − `0x408E2E`|: front F = 600 + (400 if e < 20 bar,
else clamp(800 − e/5, −100, 500)), × curve 0xD6C76(vref)/100; rear F = 800 (cal 0x40B46) + (with `0x408E6D` b6
and e ≥ 20 bar) min(clamp(400 − e/5, ≥ −100), cal 0x40B04 = 700); halved under an AYC yaw condition; F ≥ 0.
`abs_p_cmd` = max(0, `abs_p_lock` − F) (or the lower of that and the current command with `0x409047[4i]` b3),
then min with `abs_p_dump_cap`; rate −8000.

**Front-axle staged dump** (`abs_dump_hold_stage_ctrl` 0x53940 → `abs_dump_stage` 0x5424C, then 0x543FC)
[C structure, I roles]. Runs once per frame for the front pair when cal 0x40E9A ≠ 0, using pair state
`0x400A95` / `0x400A96`. With W = the front picked by `0x400A95` b2 and O = the other front:
- `abs_dump_stage` (cal 0x40E94 / 0x40E9C enables) runs when O is dumping with `rec+0x16` b7, vehicle decel weaker
  than 0.7 g, `0x400A95` b7, and O has been dumping < 7 frames.
- Stage by O's peak decel byte `rec+0x39` (a/16): ≤ −62 / −78 / −94 (cal 0x40E5E / 60 / 62, ≈ −9.9 / −12.5 /
  −15 g) → R = 1000 / 1500 / 2000 (cal 0x40E64 / 66 / 68); alternate thresholds −25 / −44 / −62 (cal 0x40E9E /
  A0 / A2) under `0x400A95` b1.
- `0x4091AC` = largest R so far; `0x4091AE` = clamp(`0x408FBC`[O] (lock-onset latch) − R, ≥ 20 bar,
  ≤ W's arbiter output `0x408F6E`); sets `0x408D9C`[W] b7, `0x400A96` b3, `0x408DBE` b4.
- Back in 0x53940, when `0x400A96 & 0x0C`: W's `abs_p_cmd` = `abs_p_cmd_max` = `0x4091AE`, rate −8000.
- So W (the front on the other side) is pulled down to O's lock pressure minus the staged amount: the
  10 / 15 / 20 bar ladder belongs here, not to the per-wheel dump. 0x543FC is a second writer of `0x4091AE` /
  `0x4091AC` (curve 0xD6D18(vref/100), cal 0x40E6A / 0x40E6C) and was not decoded.

**How a dump ends**: the dump phase continues (pause / continuous / stepped) until the event classifier raises
EV0.b3 (§3.2 step 16), which moves the wheel to hold (§4) and runs `abs_hold_entry_sync`.

**Hold entry** `abs_hold_entry_sync` 0x57200:
- Reads the measured wheel pressure via `wheel_pressure_get` 0x91A50 (fallback `0x4016E2[w]`) and sets
  **`abs_p_wheel` = `abs_p_cmd` = `abs_p_start` = `abs_p_min` = that pressure**.
- `abs_p_headroom` = max(500, `abs_p_lock` − `abs_p_min`); `abs_p_lock` may be raised by up to 5 bar.

**Hold, every frame** `abs_phase_hold_handler` 0x4CA3C:
- `abs_p_cmd_max` = min(25000, `abs_p_min` + `abs_p_headroom`·n/16), n = `0x408F02[w]` bits 7:4 (1 bar step
  under one `0x40903C` flag condition). Prepares the next reapply; `abs_p_cmd` does not change.
- Tail `0x57378`: with `0x408DDD` b5, `0x408E6D` b6, `0x408DC6` b2, `abs_p_req_rate` = 9000 / 600 / 400 for
  driver pressure `0x408EB2` < 1.3× / < 1.5× / ≥ 1.5× `abs_p_ref` (fast rebuild when driver pressure is low).

**Reapply** `abs_phase_reapply_handler` 0x4B680 + step routine 0x581BA: decoded in §5.4. In short, each step raises
`abs_p_cmd_max` by a fraction of the hold headroom, CMD ramps to it at cal 0x40D5E / 0x40D60 (a rate, 3 / 5 bar per
frame), then waits 7 frames; past a step limit it ramps continuously. A new lock (EV0.b0) returns to dump and
re-captures `abs_p_lock`.

**Clamp** `abs_cmd_slew_limiter` 0x584CC: when `abs_p_req_rate` > 0, `abs_p_cmd` = min(`abs_p_cmd`,
`abs_p_cmd_max`) and `abs_p_req_rate` is rewritten to `abs_p_cmd` − `abs_p_start`.

**No ABS request** (`0x408D9C[w]` b7 clear, 0x4479C): `abs_p_cmd` = `abs_p_cmd_max` = `abs_p_passthru`
0x408F3A; nothing is submitted, driver pressure passes through.

**Sub-phase log byte** `0x408FCC[w]`: dump 0x30 / 0x20 / 0x43 / 0x11 / 0x12, hold 0x60 / 0x62, reapply
0x81 / 0x83 / 0x85 / 0x87.

### 5.1 How a pressure is held

Hold is passive: the request goes to rate 0 and the valves trap the pressure.
- Hold means `abs_p_req_rate` = 0 and target = `abs_p_cmd`.
- Valve stage: `inlet_mode_select` 0x84460 reads `{u8 mode, s16 rate}` at `0x401AA8 + 8w` and picks the mode
  from the sign of `rate` only, no deadband: > 0 build (2), 0 hold (1), < 0 release (4). Rate 9000 is a
  special full-build value (treated separately by `wheel_volume_delta` 0x8216E and 0x84584).
- In hold mode `valve_pulse_sequencer` 0x853A8 keeps the inlet driven closed (current clamped at 1540) and the
  outlet closed (see `04_pressure_actuation.md`).
- **[open]** The arbiter step that writes `0x401AAA[w]` from the winning request's rate (0x8428C / 0x83720)
  was not located; "ABS rate → valve rate" is the likely reading.

### 5.4 Reapply, decoded  [C unless tagged]

Types and every address: `analysis/7846816A_symbols.md` "ABS reapply". Per-wheel state `abs_reapply_state` 0x408F02
(6 B: `ctl` = n [15:11], sub-stage [10:8], m [7:4], freeze-done [3]; `flags`; `ceil_saved`), scratch 0x408DD8
(period, n, cond, cond2) for the current wheel. H = `abs_p_headroom` = max(5 bar, `abs_p_lock` − `abs_p_min`), set at
hold entry.

**Per frame** (`abs_phase_reapply_handler` 0x4B680):
1. `abs_reapply_entry_flags` 0x4B970, `abs_reapply_frame_prep` 0x4BB52 (scratch.n = n, period = 0, sub-phase 0x80;
   first frame → `abs_reapply_entry_init` 0x4B9E2: counters 0x408F7E/76/7A = 0, `ceil_saved` = CMD_max).
2. `abs_reapply_conditions` 0x4BC84 → scratch.cond / cond2. The important bit is **cond b4, "re-decelerating"**: the
   slower decel value rec+0x24 is below T = −1.40 g (−1.30 g at ≤ 70 bar) + 0.04 g·n, capped at −1.30 / −1.25 /
   −1.20 g, with vref ≤ 30 km/h or rec+6 < 0 (plus two relative-decel variants). The threshold relaxes as steps
   accumulate.
3. Counters: 0x408F76 and 0x408F7A +1; in sub-stage 1, 0x408F7E +1 (not on a front with cond b4, and not at 0xFF).
4. `abs_reapply_period_select` 0x4C0BC: period = ROM 0xD6CF8[n] = **0 for the first step, 7 frames after**.
   Overrides: 21, 0, 2, cap 20, 0xFF with cond b4, min with 0x400A94.
5. Step limit N_max = 12 if the axle partner is in ABS, else 9; −3 if the diagonal wheel is not in ABS, −2 if the
   same-side wheel on the other axle is not; 12 for rears and with 0x40903C b7 / 0x408DEF b7. A lone front in ABS
   gets 4; both fronts with idle rears get 7.
6. fast_rate: 600 when n > N_max, `abs_reapply_decel_count` < 2, no 0x408E1A b1, and a filtered-pressure validity
   condition. Fronts also take it from cond b0 / b5 paths; a front above 80 bar PM (and no 0x408E1B b5) uses
   cal 0x40D5E (300) instead of 600.
7. cond b0 and n < 14 → n += 1.
8. `abs_reapply_step(n, fast_rate)` 0x581BA.
9. Phase 0x15 (wheel faster than vref): CMD = CMD_max = PM + 10 bar, rate 9000 (full build).

**`abs_reapply_step` 0x581BA:**
- Rate: `abs_reapply_special_rate` 0x4B3C8 if non-zero (or cond2 b0), else `abs_reapply_rate_select` 0x57952:
  cal 0x40D5E = 300 (front) / 0x40D60 = 500 (rear); front ≤ 200 when `abs_p_ref` < 30 bar and rec+0x10 [7:5] < 3;
  first-step variants from H/20 or H/30; clamp 150..500; at least 0x401C24[w]; fast_rate overrides.
- fast_rate ≠ 0: `abs_p_lock` = min(PM, 200 bar) every frame and period = 0, so the lock reference tracks the ramp.
- **Sub-stage 1 (wait).** If 0x408F7E ≥ period: start a step: sub-stage 2, `ceil_saved` = CMD_max,
  D = `abs_reapply_step_amount`(n), CMD_max = min(200 bar, max(0x401C14[w], CMD + D)), counters reset.
  Otherwise, with cond b4 and the freeze not yet done: CMD = min(CMD_max, PM) when n ≥ 3 (CMD_max when n < 3),
  rate 0 (sub-phase 0x87).
- **Sub-stage 2 (build).** Stop (rate 0, sub-phase 0x85) on cond b4 without fast_rate, on rec+0x0D b5, or for n < 2
  when rec+0x20 < −2 g (rec+6 < 0) or < −3 g with slip > 1 km/h. Otherwise `abs_reapply_ramp_to_ceiling` 0x57E48:
  CMD += rate; on reaching CMD_max, CMD = CMD_max, sub-stage 1, n += 1 (≤ 30).

**Step size `abs_reapply_step_amount` 0x57F62** (m = `ctl`[7:4], set in hold by `abs_hold_set_reapply_frac` 0x4CF76
from cal 0x40D62 / 0x40D64 = 10):
- D = H·(16 − m)/32 for the first step(s) (n ≤ 1 when m > 8, else n = 0), then H·(16 − m)/(48 − m).
  With m = 10: **0.1875·H, 0.1875·H, then 0.158·H per step**. Six steps cover the headroom.
- Variants: H·(16 − m)/24 with 0x40903A b4 set and b7 clear; ½ on fronts when `abs_cycle_count` ≥ 16;
  H·(16 − m)/44 with `abs_cycle_count` ≥ 16, rec+0x16 b7 and n ≥ 1.
- `abs_reapply_decel_count` ≥ 2 → D/3, ≥ 4 → D/4, then at least 2 bar. A wheel that starts decelerating again during
  reapply gets smaller steps.
- ×2 when cal 0x40D54 ≠ 0 (stock 0) and 0x408E7A > 105 or 0x408DEC b2.
- \+ `abs_reapply_step_boost` 0x4C368 [C structure, I detail]: (n − N0)·2.5 bar (front) or 1.7 bar (rear) once n > N0
  ≈ cal 0x40D52 (5) minus idle wheels (floor 3), when the wheel is not re-decelerating and the command has passed the
  previous lock pressure by > 10 % and > 3 bar (cal 0x40D5A), or the driver pressure exceeds 1.5 × `abs_p_ref`.
- Front cap 7 bar in the 0x40903A case. Record: 0x40912E[10w] = D, +2 = D + boost.

**Worked example** (front, the 58 → 33 bar log): H = 25 bar, rate 3 bar/frame, both fronts in ABS and idle rears
(N_max 7). Steps of 4.7, 4.7, 4.0, 4.0, 4.0, 4.0 bar reach 58 bar; each takes 2 frames of ramp plus 7 of waiting,
so the climb takes about 0.5 s. If the wheel has not re-locked once n exceeds N_max (after the 8th step), it ramps
continuously at 6 bar/frame (3 above 80 bar) until it does. A lone front (N_max 4) switches to the ramp after its 5th
step, at about 54 bar. The boost mostly applies once the command is past the previous lock pressure.

**Consequences for tuning.**
- The step size is proportional to H, the dump depth. Smaller dumps give proportionally smaller steps; the
  staircase needs no separate rescaling for a different plant gain.
- 0x40D5E / 0x40D60 are the ramp **rates** within a step and the fast-ramp rate above 80 bar, not step sizes.
- m (0x40D62 / 0x40D64) sets how many steps cover the headroom: (16 − m)/32 per early step. Larger m means finer
  steps.
- The period table 0xD6CF8 (7 frames) and N_max set the cycle time; the continuous ramp after N_max is the main
  reason a wheel re-locks quickly once grip is used up.

**[open]** Writers / meaning of 0x401C14, 0x401C24 (valve stage), `abs_cycle_count` 0x408EF7, scratch.cond b1/b2/b5,
the first-step rate variants in 0x57952 and the full N0 adjustment in 0x4C368.

---

## 6. End-of-event reset  [C]

`0x45808` (called by `0x45EC4` after the wheel loop), 0x458E0–0x45964: when `0x401FF2 & 0xA0 == 0x80` and the
ABS mode field `0x408DA1` bits 7:5 ≥ 5, every wheel gets `rec[0]` = 0x80 with bit 2 kept (0x80 or 0x84) and
`rec+6` = max(`rec+6`, 360). This is the only route from 0x09 / 0x11 / 0x15 back to armed. **[open]** what
advances the `0x408DA1` mode field.

---

## 7. Rear select-low (decision layer, runs after the handlers)  [C]

`abs_decision_stage` 0x5173C → `abs_rear_lead_select` 0x5184C → `abs_decision_classify` 0x51B54 →
`abs_decision_resolve` 0x58B30 → `abs_decision_pressure_exec` 0x58FF4.
- Lead rear = higher phase score `64·dump + 32·hold + 16·(reapply ∧ ¬b2) + 8·pre-control + 4·(reapply ∧ b2) +
  2·b2 + armed`; −1 / 0 for flagged / faulted wheels; ties keep the previous lead. `0x408DA0` b7 = 1 when
  wheel 2 leads. Index word `0x408DE8`: [15:14] slaved wheel, [13:12] lead, [11:10] follower, b9 zero offset.
- Code 8, exec 0x5932A: the follower's `abs_p_cmd` = max(0, `abs_p_cmd`[lead] + offset) when it is above that
  (0x593D6), or unconditionally = clamp(lead base + offset, 0, 25000) (0x5956C); follower inherits the lead's
  rate. Offset `0x408DE4` from 0x58B30; resolve swaps lead / follower when the follower's command goes lower.
- Code 1 = rears uncoupled (no case in the exec switch). Set when both rears are armed-idle (0x51C8C) and by
  the guards at 0x51E94 / 0x51F74 (e.g. vref < 15 km/h with `0x408DB5` b4).

---

## 8. Open items

- Exact boolean form of steps 7, 8, 15 and the EV0.b3 release condition (summarised above, not fully reduced).
- Writers of `0x401D00`, `0x401C14`, `abs_p_passthru` (`rec+0x1C` = `tyre_tol_learn`, `rec+0x24` = 0x46390, both
  now traced: `WHEEL_SPEED_CHAIN_7846816A.md`); meaning of
  `0x408DF0` b7 / b6, `0x408E6A`, `0x408E7B`.
- Arbiter → `0x401AAA` rate path; driver of the `0x408DA1` mode field.
- Pre-control (0x50894) and armed (0x50580) handlers not decoded.

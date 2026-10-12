# MK60E5 7846816A (E9x M3) — Core ABS slip-control loop & pressure-phase state machine

Scope: the **ABS** (anti-lock) slip control loop and its dump/hold/build state machine.
CPU addresses; **file offset = CPU + 0x8000 = XDF address**. 10 ms control frame (task T3, body 0x070FE4).
Confidence per claim: **CONFIRMED** (read from M3 bytes/listing in this pass) / **INFERRED** (read from M3
code, meaning deduced) / **UNCONFIRMED** (not resolvable from code alone).

Provenance note: the ABS controller (1M 0x44000–0x5E000) was ported to the M3 by clean opcode diff
(shift −0x220 for 0x44xxx–0x4Bxxx, −0x200 for ≥0x4Cxxx; ABS/vref RAM shifted **+0x24**). Where a claim rests
on that opcode-identity to the 1M rather than a fresh M3 byte-read, it is tagged **CONFIRMED(port)**.
This pass independently byte-decoded the two curve tables and disassembled the M3 compare sites.

Binary: `flash/bin/7846816A_00000000.bin`. Listing: `analysis/7846816A_main.lst`.
ABS cal block (ABS tag) base **0x4039C**, len 0xB0A.

---

## 0. One-paragraph map of the loop

Per 10 ms frame: wheel-speed chain → filtered per-wheel speed (struct+0x1A, 0.01 km/h) and wheel accel
(struct+0x20, 0.01 g). `vref_update` (0x449D0) builds the reference speed `vref` (0x408DA8) as a rate-limited
integrator over the 4 compensated wheel speeds. `abs_pressure_frame` (0x045F54) runs the per-wheel pass:
slip = vref − wheelspeed; the **event classifier** (0x04D270) fills a scratch struct E (threshold curves,
slip sums) and emits a 2-byte event word (EV0/EV1) → the **per-wheel phase state machine** `abs_phase_sm`
(0x04FC3C) which drives rec[0] bits (armed/dump/hold/reapply). `abs_phase_dispatch` (0x0504D0) routes each
wheel to its phase handler, which writes a commanded pressure CMD (0x408F22) / target / ramp. In parallel the
**decision layer** (0x05173C → 0x0518 4C/0x051B54/0x058B30) classifies an axle-level decision code (0x408DDE)
and `abs_pair_logic` (0x054D9A) does the per-axle (pair) select-low cooperation and the entry-gate slip test.
Commands leave via `abs_emit_pressure_request` (0x0446B6) → arbiter id 1 (rear id 11, reapply id 19).

---

## 1. vref (reference vehicle speed) — rate-limited integrator

- **Address / writer:** `vref` = RAM **0x408DA8** (s16, 0.01 km/h). Sole writer `vref_update` **0x449D0**
  (= 1M 0x44BF0). **CONFIRMED** it loads/stores 0x408DA8 (disasm 0x449FC `lrw r7,[…]=0x408DA8`).
- **Not a pure max-select.** Inputs are the 4 filtered wheel speeds (struct+0x1A) each multiplied by a
  per-wheel tyre-circumference factor (Q10) before the picks: Cmax (fastest compensated), Fmax (fastest
  **front**), Vmin (slowest valid), Vmax (raw max). **CONFIRMED(port)** (opcode-identical to 1M; 1M writer
  verified in `analysis/agents/absvref/REPORT.md`).
- **Ramp rates per 10 ms frame (0.01 km/h), CONFIRMED(port) — constants unchanged from 1M, and the M3 symbol
  table marks these "hard-coded, code-patch only, not cal":**
  | Situation | Δvref/frame | ≈ accel |
  |---|---|---|
  | vref < Fmax (fastest front, compensated) | +44 | +1.25 g |
  | ABS active & vref < Vmin | +22 | +0.62 g |
  | init / controller modes 1,2,4 (snap) | +282 | ≈ +8 g |
  | normal fall (vref above all wheels) | −22 … −44 | −0.6…−1.25 g |
  | mode field A[7:5]≠0 & Vmin<vref | −90 | −2.5 g |
  | **during ABS braking** | `−(|decel est| + 20…30)·0.36`, capped −44 | decel-limited coast-down |
- **Decel clamp during braking:** the ABS fall rate is set from the vehicle-decel estimate (capped −44/frame
  = −1.25 g), so vref coasts down at a brake-plausible rate rather than following a locking wheel.
  **CONFIRMED(port)** (helper = 1M sub_0511F4 analogue).
- **Standstill / floor:** after the integrator, `vref = max(vref, 0x4032D0)`. 0x4032D0 is a RAM floor computed
  at init from min tyre circumference (~0.62 km/h on the 1M). No separate standstill state beyond this floor.
  **CONFIRMED(port)** / floor-source **INFERRED**.
- **Reset / resync:** on an invalid-wheel flag (fault bit 0x400952+w bit0, struct+0x19 & 0xC0, or vmin bit
  0x40903A bit7) the wheel is excluded and vref resyncs to a shadow integrator (1M 0x408E5A analogue).
  **INFERRED** (M3 RAM shift +0x24 not individually re-read here).
- **Second reference speed** vref2 (1M 0x408D86; M3 +0x24) and a tyre-compensated per-wheel speed are also
  maintained for the classifier. **INFERRED**.

**UNCONFIRMED:** exact M3 RAM address of the shadow integrator and vref2 (not re-read byte-for-byte this pass).

---

## 2. Per-wheel slip computation & the two threshold compares

### 2a. The signals (all CONFIRMED by M3 disasm this pass)
- **Plain slip** = `vref − wheelspeed` = `0x408DA8 − struct+0x1A` (0.01 km/h). Seen directly in
  `abs_slip_aggregates` 0x04F85A (`0x4F870 ld.h r6,(r14,26)`; `0x4F872 vref`; `0x4F878 subu r13,r6`;
  `0x4F87A st.h r13,(r2,28)` → E+28). Slip sums E+28/E+30/E+32 (own / axle-partner / cross) are all **plain
  slip in 0.01 km/h**, not ratios.
- **Slip ratio** = `0x408F84[w] = (vref − wheelspeed)·10000 / vref`, clamped ≥0 (1e-4 units). Writer
  `abs_slip_ratio_update` **0x05898C**: `0x589A0 subu r7,r6` (slip) → `mult r7,0x2710(=10000)` →
  `divs r7,vref` → `st.h` to 0x408F84[w]; negative result forced to 0 (0x589BC). **CONFIRMED.** This ratio is
  a *separate* downstream signal (used by the decision/percent logic), **not** the entry-gate compare.

### 2b. Entry GATE curve — file 0x48DB6 / CPU **0x40DB6** (used by `abs_pair_logic` 0x54D9A)
Decoded stored table (`curve_interp_s16` layout [lo,hi,n,xs,cs,ks], Q10 slope):
```
lo=0  hi=900  n=2   xs=[5000]   cs=[150, 115]   ks=[-4, +3]
```
Evaluated at x = **vref** (0.01 km/h), output = slip threshold (0.01 km/h):
| vref km/h | 0 | 10 | 20 | 50 | 80 | 100 | 150 | 200 | 300 |
|---|---|---|---|---|---|---|---|---|---|
| threshold | 1.50 | 1.47 | 1.43 | 1.29 | 1.38 | 1.44 | 1.58 | 1.73 | 2.02 |
(km/h of absolute slip). **Engineering meaning:** a shallow, speed-shaped **entry/continue gate** — dips to a
minimum (~1.3 km/h) around 50 km/h, rises to ~2.0 km/h at autobahn speed. **CONFIRMED** (byte-decode).

**The exact compare (CONFIRMED by disasm, `abs_pair_logic` call site 0x54F3E–0x54F5A):**
```
r10 = vref (0x408DA8, sexth)
r11 = partner wheel struct (axle pair via ^0x40); r6 = ld.h (r11,26) = wheelspeed
r8  = vref - wheelspeed              ; PLAIN slip
r2  = curve_interp_s16(0x40DB6, x=vref)   ; jsri 0x710FC
cmplt r2, r8   ->  if (threshold < slip)  => entry/continue branch (0x54F66)
```
So **entry test = plain slip > curve(0x40DB6, x=vref)**. NOT a ratio. **CONFIRMED.**

- **Entry debounce** — file 0x48DB4 / CPU **0x40DB4** = word **2**. Used at 0x54F6A–0x54F76:
  `r7 = ld.h 0x40DB4 (=2)`; `r11 = ld.b 0x408EF0` (per-event counter); `cmplt r11,r7` → if counter < 2, skip
  the commit (0x54FF6). So the gate must persist ≥2 frames before the pair logic acts. **CONFIRMED.**
  (Neighbour cal words 0x40DB0=3, 0x40DB2=10 are adjacent counters/limits — **UNCONFIRMED** purpose.)

### 2c. Gross-slip LIMIT curve — file 0xDECE2 / CPU **0xD6CE2** (used by `abs_gross_slip_threshold` 0x52380)
Decoded stored table:
```
lo=0  hi=32767  n=3   xs=[2000, 5550]   cs=[400, 599, -13]   ks=[+102, 0, +113]
```
Evaluated at x = **vref** (0.01 km/h), output = slip threshold (0.01 km/h):
| vref km/h | 0 | 10 | 20 | 30 | 50 | 55.5 | 80 | 100 | 150 | 200 | 300 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| threshold | 4.00 | 4.99 | 5.99 | 5.99 | 5.99 | 5.99 | 8.69 | 10.90 | 16.42 | 21.94 | 32.97 |
(km/h of absolute slip). Three segments: **(a)** <20 km/h rises 4.0→6.0 km/h; **(b)** 20–55.5 km/h flat at
~6.0 km/h; **(c)** ≥55.5 km/h linear with slope **113/1024 = 11.04 % of vref** (the "~11 %" note confirmed).
**Engineering meaning:** a **deep gross-slip / plausibility arming threshold** — far larger than the entry
gate; marks "wheel is grossly behind the vehicle" (incipient full lock), ~11 % of vehicle speed at speed.
**CONFIRMED** (byte-decode).

**Usage (CONFIRMED by disasm, `abs_gross_slip_threshold` 0x52380):**
```
r13 = 0x408DA8 (vref); r2 = 0xD6CE2; r3 = vref (x)
jsri 0x710FC  ->  r2 = curve(0xD6CE2, vref)
st.h r2,(r14,6)        ; E+6 = base gross-slip threshold
+ adjustment terms (e.g. +122|0x80, or bmaski-11) added into E+6 (0x523B6–0x523C8)
```
E+6 is the gross-slip threshold the event classifier compares the **plain** slip sum (E+28, 0.01 km/h)
against — same units, so again a plain-slip compare, not a ratio. **CONFIRMED** (builder) / the EV0 predicate
that consumes E+6 is **INFERRED** (`EV0.5 main trigger: slipA ≥ E+6 + terms`).

### 2d. Units — CONFIRMED
Both curves and both slip signals are **0.01 km/h** of *absolute* slip (vref − wheelspeed). The entry gate is
a small fixed-ish margin (~1.3–2.0 km/h); the gross-slip limit is a speed-proportional deep threshold
(~11 % vref). The slip *ratio* (0x408F84, 1e-4) is a distinct downstream quantity.

---

## 3. `abs_pair_logic` 0x54D9A — per-axle, select-low cooperation

- **Granularity:** per **axle pair** (fronts 0/1, rears 2/3), not per individual wheel. The function toggles
  the partner via `xor …,64` (`^0x40`, 0x54DC8 / 0x54F3C) and does the entry-gate compare against the
  **partner** wheel's speed (§2b). **CONFIRMED** (disasm).
- **Select-low:** the companion `abs_rear_lead_select` 0x05184C scores the rear records and picks the "lead"
  (more-slipping / lower-speed) rear → sets lead flag in 0x408DA0 bit7 and DDE+10 index fields; rear axle is
  controlled select-low (the worse rear governs the pair). **INFERRED (M-H)** (code read; = 1M `abs_rear_lead_select`).
- **Front vs rear difference (CONFIRMED structure):**
  - Rears are handled through the pair/S-state machine with a **cornering clause**: `abs_pair_cornering_rear`
    0x054BE8 uses RL=0x40BF80 / RR=0x40BFC0 and lateral accel (lat = 0x408ECC + 0x408ECE/2) vs cal 0x40DD2
    (=1748); an ECC counter limit `2 + max(0, 8−(|lat|−1748)/126)`. Rear-only. **INFERRED (code).**
  - A rear wheel's pressure reference is the **same-side front wheel's pressure PM** (X[i] indexing).
    **INFERRED(port).**
  - Reapply request id 11 is **rear-only**. **CONFIRMED(port).**
- **Pre-gate:** `abs_pair_logic` first calls `abs_pair_pred_gate` 0x54B70 (predicates A..D at
  0x547D8/0x54954/0x54A80/0x54AF8); if it returns 0 the function exits early (0x54DBC `cmpnei r2,0` →
  `jmpi 0x553BE`). It also reads the axle-pair **S-state** at 0x408E5E byte+1 bits 6:5 (S1 test
  `cmpnei r12,1` at 0x54DDE). **CONFIRMED** (disasm).
- **Writes:** decision contributions 32 / 1024 / 16 / 2 into the decision block. **CONFIRMED(port).**

Summary: control is **per-axle (pair), rear select-low**, fronts governed individually within the pair with a
front pressure-imbalance relaxation; rears add a lateral/cornering counter clause.

---

## 4. Pressure-phase state machine (dump / hold / build)

Three cooperating layers (all CONFIRMED(port), state constants cross-checked this pass):

**(A) Per-wheel phase bits — `rec[0]` at 0x40BF00 + 0x40·w, machine `abs_phase_sm` 0x04FC3C.**
The M3 `abs_phase_sm` manipulates rec[0] **bit-by-bit** (bseti/bclri/btsti; no whole-byte state immediates
were loaded — CONFIRMED by immediate histogram), consistent with the bit semantics:
- b7 armed · b0 in-ABS-cycle ("vehicle ABS active", sets 0x408D7D-analogue) · b6 pre-control · b5 **DUMP** ·
  b3 **HOLD** · b4 **REAPPLY (build)** · b2 reapply-hold / rear-overspeed.

| State (rec[0]) | Name | Key transitions (event word EV0/EV1 from 0x04D270) |
|---|---|---|
| 0x80 | armed idle | EV0.5→0x21 (dump); EV0.6→0xC0 (pre-control); EV0.7→0x84 (rear overspeed hold) |
| 0xC0 | pre-control | EV0.5→0x21; else→0x80 |
| 0x84 | rear overspeed hold | EV1.5→0x80 |
| 0x21 | **DUMP** (b5+b0) | EV0.3→0x09 |
| 0x09 | **HOLD** (b3+b0, low-pressure) | EV0.0→0x21; EV1.7→0x11; EV1.6→0x15 |
| 0x11 | **REAPPLY/BUILD** (b4+b0) | EV0.0→0x21; EV0.1→0x15 |
| 0x15 | reapply-hold | EV1.4→0x11 |
Suppress → forces 0x21→0x09 and 0xC0→0x80 on `(0x400952[w] bit3 & (b0|front))` or rec[0x19] bit5 (glitch).
**CONFIRMED(port)** (transition pattern = 1M sub_04FE3C; bit manipulation re-confirmed on M3).

**(B) Axle-pair cycle phase S0..S3** in 0x408E5E bits 6:5 (= 1M 0x408E3B): S0 idle → S1 entry →
S2 pair-hold/reapply → S3 rear-balance → S0. Read by `abs_pair_logic`. **CONFIRMED** (read site in §3).

**(C) Global decision code 0x408DDE** (= 1M 0x408DBA; `abs_decision_classify` 0x051B54, resolved by
0x058B30, executed by 0x058FF4): 1 = no-control/build · 64 = rear in control (pair logic) · 32 =
yaw/lateral-limited (0..100 %) · 1024/16 = reapply nudge/step · 2 = pair-hold done (RAMP −8000) · 128 =
special/invalid. **CONFIRMED(port).**

**Dispatch** — `abs_phase_dispatch` 0x0504D0 routes rec[0] bit → handler: bit6→0x050894 (pre-control),
bit7→0x050580 (armed/idle), bit3→0x04CA3C (hold), bit4→0x04B680 (reapply), bit5→0x04AAA8 (dump), then
post-clamp 0x0584CC. **CONFIRMED** (callee list in `m3absslip/fnlist.txt`).

### Phase entry/exit amounts (CONFIRMED(port), M3 addresses)
| Phase | Handler | Entry condition | Pressure action |
|---|---|---|---|
| **DUMP** | 0x04AAA8 → target 0x055F06 | rec[0] b5; dump-stage gate `abs_dump_stage` 0x05424C: filtered peak decel w.39 crosses staged thresholds — **set A {−62,−78,−94}** (ABS cal +0xAC2) or **set B {−25,−44,−62}** (+0xB02), i.e. ≈ −9.9/−12.5/−15 g and −4/−7/−9.9 g; vref-decel gate 0x408D8B≥−70 | target = lock-onset pressure (LOCKEST 0x408FD0) − **{1000,1500,2000}** (10/15/20 bar, ABS cal +0x624), floored at 20 bar; RAMP = **−8000** (max dump rate) |
| **HOLD** | 0x04CA3C → sync 0x057200 | rec[0] b3 | PM=CMD=SNAP; target = PMMIN (0x408FC4) + headroom·n/16; RAMP 0 |
| **BUILD/REAPPLY** | 0x04B680 (+ ramp 0x0443F4, id 19) | rec[0] b4; deficit `0x408F0E−0x408F06 > 500` (5 bar) | CMD = **min(CMD+400, 25000)** per frame (apply ramp ABS cal +0x0C = 400); small nudges +80/+240 (0.8/2.4 bar) in pair logic |

- **Debounce / cycle-counting:** entry-gate debounce = 2 frames (0x40DB4, §2b). Rear-step planner
  `abs_rear_step_planner` 0x052004 keeps 5-bit step counters in 0x408F02[w] for stepped reapply; ECC/ECB
  cornering counters (limit 2, +8 in corners) in the rear clause. **CONFIRMED(gate)/INFERRED(counters).**
- **Adaptive behavior:** lock-onset pressure latch `abs_lockon_pressure_estimator` 0x05862C writes LOCKEST
  0x408FD0 (min-selected with wheel pressure PM, clamp 25000); dump targets reference it, so the dump floor
  adapts to the pressure at which lock last began. **INFERRED (M-H)** (= 1M estimator).

---

## 5. ABS exit / deactivation

- **Low-speed:** the apply/build path is gated off below ~4 km/h (apply-ramp vref gate, 1M 0x442AC region
  = 400 in 0.01 km/h). **INFERRED** (gate address noted in cycle-6 symbols; the 0x442AC M3 window read this
  pass is the per-wheel init loop, so the 4 km/h literal site was not re-pinned — **UNCONFIRMED** exact M3 addr).
- **Standstill:** vref clamps to the ~0.62 km/h floor (0x4032D0) and no new ABS cycle arms below the entry
  gate. **INFERRED.**
- **Slip recovered:** a wheel leaves the cycle when the event word no longer re-asserts dump/hold (rec[0]
  returns toward 0x80 armed-idle); the whole-vehicle "ABS active" bit (rec[0] b0 aggregate) clears when no
  wheel is in-cycle. Mode field 0x408D7D[7:5] ≥5 with 0x401FF2 & 0xA0 == 0x80 resets **all** wheels to 0x80
  (end-of-event resync). **CONFIRMED(port)** (= 1M sub_045776/045A28 mode counter).

**UNCONFIRMED:** exact M3 low-speed drop-out speed byte address and any min-cycle-time hold before full
deactivation (needs a dynamic trace to pin).

---

## 6. Keeping ABS distinct from DSC/ASC/EBD

- **ABS proper:** §§1–5 — `vref_update` 0x449D0, `abs_pressure_frame` 0x045F54, `abs_event_classifier`
  0x04D270, `abs_phase_sm` 0x04FC3C, `abs_phase_dispatch` 0x0504D0, dump/hold/reapply handlers, `abs_dump_stage`
  0x05424C, `abs_gross_slip_threshold` 0x52380, entry gate in `abs_pair_logic` 0x54D9A.
- **Pair/axle cooperation + cornering** (0x54D9A / 0x54BE8 rear lateral clause, decision code 32 = lateral)
  is the ABS *stability-aware* layer, but the yaw/β observer, yaw PD moment and brake-steer distribution
  (0x05EBC4 / 0x05F7BA / 0x0616A4, AYC id 3/20) are **DSC/AYC**, not ABS — shared only via the arbiter and the
  lateral-accel input 0x408ECA/0x408ECC that `abs_pair_logic` reads.
- **TCS/ASC** (drive-slip) uses a *different* reference `vref_tcs` 0x403066 and its own curves
  (0xF625C/0xF61F6, caps 0xF654C) + torque path (TX 0x0B6) — not this loop.
- **EBD:** the rear select-low + same-side-front reference and the pair-hold logic provide the brake-force
  distribution behavior, but no separate EBD module was identified; it is folded into the pair/decision layer.
  **UNCONFIRMED** whether a distinct EBD threshold set exists.

---

## 7. Open / needs-hardware
- Full EV0/EV1 predicate set in `abs_event_classifier` 0x04D270 (which bits consume E+6 gross-slip vs the
  entry gate) — structure confirmed, individual predicates INFERRED.
- Exact M3 RAM addresses of shadow vref integrator, vref2, and the low-speed drop-out byte (RAM shift +0x24
  not re-pinned here).
- Pressure-domain unit (assumed 0.01 bar), and real-world frequency of the −10 g dump-stage crossings — needs
  a dynamic bench/vehicle trace.
- Neighbour cal words 0x40DB0 (=3) / 0x40DB2 (=10) next to the entry-gate debounce — purpose UNCONFIRMED.

---

## Appendix — curve bytes (as stored, big-endian s16), re-derivable
Entry gate CPU 0x40DB6 (file 0x48DB6): `00 00 | 03 84 | 00 02 | 13 88 | 00 96 | 00 73 | FF FC | 00 03`
→ lo=0, hi=900, n=2, xs=[5000], cs=[150,115], ks=[−4,+3].  Debounce word CPU 0x40DB4 (file 0x48DB4)=`00 02`=2.
Gross-slip CPU 0xD6CE2 (file 0xDECE2): lo=0, hi=32767, n=3, xs=[2000,5550], cs=[400,599,−13], ks=[+102,0,+113].
Evaluator: `i = count(xs[j] ≤ x); y = clamp(cs[i] + ((x·ks[i])>>10), lo, hi)` (Q10 arithmetic-shift slope).

# MK60E5 7846816A (E9x M3) — Core ABS slip-control loop & pressure-phase state machine

Scope: the **ABS** (anti-lock) slip control loop and its dump/hold/build state machine. This file is the
overview; the instruction-level detail lives in `08_phase_control.md` (classifier, phase machine, pressure
targets) and `10_vref_and_ax.md` (vref and the decel estimate).
CPU addresses; **file offset = CPU + 0x8000 = XDF address**. 10 ms control frame (task T3, body 0x070FE4).
Confidence per claim: **CONFIRMED** (read from M3 bytes/listing) / **INFERRED** (read from M3 code, meaning
deduced) / **UNCONFIRMED** (not resolvable from code alone).

Provenance note: the ABS controller (1M 0x44000–0x5E000) was ported to the M3 by clean opcode diff
(shift −0x220 for 0x44xxx–0x4Bxxx, −0x200 for ≥0x4Cxxx; ABS/vref RAM shifted **+0x24**). Where a claim rests
on that opcode-identity to the 1M rather than an M3 byte-read, it is tagged **CONFIRMED(port)**.

Binary: `flash/bin/7846816A_00000000.bin`. Listing: `analysis/7846816A_main.lst`.
ABS cal block (ABS tag) base **0x4039C**, len 0xB0A.

---

## 0. One-paragraph map of the loop

Per 10 ms frame: wheel-speed chain → filtered per-wheel speed (struct+0x1A, 0.01 km/h) and wheel accel
(struct+0x20, 0.01 g). `vref_update` (0x449D0) builds the reference speed `vref` (0x408DA8) as a slew-limited
tracker over the compensated wheel speeds. Dispatcher slot 12 (`abs_frame_entry_a` → 0x45EC4) runs the
per-wheel **event classifier** (0x04D270): slip = vref − wheelspeed, a scratch threshold block E, and a 2-byte
event word (EV0/EV1) handed to the **per-wheel phase state machine** `abs_phase_sm` (0x04FC3C), which drives
rec[0] bits (armed/dump/hold/reapply); after the wheel loop `abs_state_aggregate` 0x45808 rolls up the
per-wheel state and does the end-of-event reset. Slot 13 (`abs_frame_entry_b` → `abs_pressure_frame`
0x045F54) runs `abs_phase_dispatch` (0x0504D0), which routes each wheel to its phase handler; the handlers
write a commanded pressure CMD (0x408F22) / target / rate. The **decision layer** (0x05173C → 0x05184C /
0x051B54 / 0x058B30 → exec 0x058FF4) sets an axle-level decision code (0x408DDE) for rear select-low and
cornering, and `abs_pair_logic` (0x054D9A) handles µ-split yaw-moment limiting once its yaw gate opens.
Commands leave via `abs_emit_pressure_request` (0x0446B6) → arbiter id 1 (rear id 11).

---

## 1. vref (reference vehicle speed)

Full decode: **`10_vref_and_ax.md`**. Summary:

- **Address / writer:** `vref` = RAM **0x408DA8** (s16, 0.01 km/h). Sole writer `vref_update` **0x449D0**
  (= 1M 0x44BF0). **CONFIRMED**.
- **Inputs:** the 4 filtered wheel speeds (struct+0x1A), each scaled inline by the per-wheel learned
  tyre-tolerance factor (769 + byte)/1024 before the picks. The factor is a ratio trim between wheels, not the
  circumference: that is already in struct+0x1A through K = 900·C. It is not struct+0x1C either
  (`analysis/TYRE_TOLERANCE_LEARNING_7846816A.md` §3). Picks: Cmax (fastest compensated), Fmax (fastest compensated **front**), Vmin (slowest
  valid raw), Vmax (fastest raw). Faulted wheels are excluded. **CONFIRMED**.
- **Rise:** while no wheel is in an ABS cycle (`0x408DA1` b4 clear) +22/frame (0.62 g) only while vref < Vmin, i.e.
  every wheel is above it; +282 (snap) in controller modes 1/2/4. In the regime +44/frame (1.25 g) toward
  Fmax. **CONFIRMED**.
- **Fall:** only when vref > Cmax (above every counted wheel). A fixed step of −11 … −49/frame (0.31–1.39 g,
  normally −22/−32/−44) is chosen from the wheel phase flags, then bounded by a limiter on the wheel-derived
  decel estimate `0x408DAF` (vref may fall at most ≈ 0.3–0.5 g faster than it). Controller mode ≠ 0: −90 while
  Vmin < vref. **CONFIRMED**.
- **ax-based fall:** `vref_fall_from_ax` 0x50FF4 replaces the step with `max(−44, (−|ax| − margin)·0.36)`, but
  only when ax is trusted **and** lateral, yaw, steering and pressure are all valid with |lat| < 0.3 g. Without
  the steering-angle sensor (SZL) it never runs. **CONFIRMED**.
- **Floor:** `vref = max(vref, 0x4032D0)`, a RAM floor computed at init from min tyre circumference (~0.6 km/h).
  **CONFIRMED**.
- **Shadow integrator** 0x408E7E, kept ≤ vref and ≥ floor (no reader found). A second reference **0x408DAA**
  is used for rear slip when it exceeds vref (`08_phase_control.md` §3.1). **CONFIRMED**.
- High-grip ceiling: about 1.25 g (1.39 g on one branch); a car decelerating harder outruns vref.

---

## 2. Per-wheel slip computation & the threshold compares

### 2a. The signals (CONFIRMED by M3 disasm)
- **Plain slip** = `vref − wheelspeed` = `0x408DA8 − struct+0x1A` (0.01 km/h). Seen directly in
  `abs_slip_aggregates` 0x04F85A (`0x4F870 ld.h r6,(r14,26)`; `0x4F872 vref`; `0x4F878 subu r13,r6`;
  `0x4F87A st.h r13,(r2,28)` → E+28). Slip sums E+28/E+30/E+32 (own / axle-partner / cross) are all **plain
  slip in 0.01 km/h**, not ratios.
- **Slip ratio** = `0x408F84[w] = (vref − wheelspeed)·10000 / vref`, clamped ≥0 (1e-4 units). Writer
  `abs_slip_ratio_update` **0x05898C**: `0x589A0 subu r7,r6` (slip) → `mult r7,0x2710(=10000)` →
  `divs r7,vref` → `st.h` to 0x408F84[w]; negative result forced to 0 (0x589BC). **CONFIRMED.** This ratio is
  a *separate* downstream signal (used by the decision/percent logic), not one of the entry compares.

The classifier's own entry tests (slip vs E+6 / E+14 plus margins, decel flags) are in
`08_phase_control.md` §3.2; the wheel-decel trigger is in `02_decel_threshold.md`.

### 2b. Pair-logic partner-slip curve — file 0x48DB6 / CPU **0x40DB6** (used by `abs_pair_logic` 0x54D9A)
XDF title "ABS entry-slip threshold"; it is only an entry test inside the pair logic.
Decoded stored table (`curve_interp_s16` layout [lo,hi,n,xs,cs,ks], Q10 slope):
```
lo=0  hi=900  n=2   xs=[5000]   cs=[150, 115]   ks=[-4, +3]
```
Evaluated at x = **vref** (0.01 km/h), output = slip threshold (0.01 km/h):
| vref km/h | 0 | 10 | 20 | 50 | 80 | 100 | 150 | 200 | 300 |
|---|---|---|---|---|---|---|---|---|---|
| threshold | 1.50 | 1.47 | 1.43 | 1.31 | 1.38 | 1.44 | 1.58 | 1.73 | 2.02 |
(km/h of absolute slip). A shallow, speed-shaped margin: minimum ~1.3 km/h around 50 km/h, ~2.0 km/h at
autobahn speed. **CONFIRMED** (byte-decode).

**The compare (CONFIRMED by disasm, `abs_pair_logic` 0x54F3E–0x54F5A):**
```
r10 = vref (0x408DA8, sexth)
r11 = partner wheel struct (axle pair via ^0x40); r6 = ld.h (r11,26) = wheelspeed
r8  = vref - wheelspeed              ; PLAIN slip
r2  = curve_interp_s16(0x40DB6, x=vref)   ; jsri 0x710FC
cmplt r2, r8   ->  if (threshold < slip)  => branch 0x54F66
```
So the test is **partner plain slip > curve(0x40DB6, x=vref)**, not a ratio. It only runs once the pair
gate is open (§3), so it is not the general ABS entry test.

- **Debounce** — file 0x48DB4 / CPU **0x40DB4** = word **2**. Used at 0x54F6A–0x54F76:
  `r7 = ld.h 0x40DB4 (=2)`; `r11 = ld.b 0x408EF0` (per-event counter); `cmplt r11,r7` → if counter < 2, skip
  the commit (0x54FF6). **CONFIRMED.** Neighbour cal 0x40DB0 = 3 is the GMA rebuild step (×100 = 3 bar,
  `09_chassis_sensor_use.md` §7.3); 0x40DB2 = 10 purpose **UNCONFIRMED**.

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
~6.0 km/h; **(c)** ≥55.5 km/h linear with slope **113/1024 = 11.04 % of vref**.
**Engineering meaning:** the **gross-slip / dump-start threshold** — "wheel is grossly behind the vehicle",
~11 % of vehicle speed at speed. **CONFIRMED** (byte-decode).

**Usage (CONFIRMED by disasm, `abs_gross_slip_threshold` 0x52380):**
```
r13 = 0x408DA8 (vref); r2 = 0xD6CE2; r3 = vref (x)
jsri 0x710FC  ->  r2 = curve(0xD6CE2, vref)
st.h r2,(r14,6)        ; E+6 = base gross-slip threshold
+ adjustment terms (e.g. +122|0x80, or bmaski-11) added into E+6 (0x523B6–0x523C8)
```
E+6 is compared with plain slip (0.01 km/h) in the classifier: EV0.b5 (start a dump) on slip ≥ E+6 + E+16,
EV0.b0 (dump again) on slip ≥ E+6 + E+16 + E+18 (`08_phase_control.md` §3.2 steps 11 and 17). **CONFIRMED.**

### 2d. Units — CONFIRMED
Both curves and both slip signals are **0.01 km/h** of *absolute* slip (vref − wheelspeed). The partner-slip
curve is a small margin (~1.3–2.0 km/h); the gross-slip limit is a speed-proportional deep threshold
(~11 % vref). The slip *ratio* (0x408F84, 1e-4) is a distinct downstream quantity.

---

## 3. Axle pairs, rear select-low and `abs_pair_logic` 0x54D9A

- **Rear select-low:** `abs_rear_lead_select` 0x05184C picks the "lead" rear by **phase score** (deepest ABS
  phase wins; `abs_decision_resolve` 0x58B30 then swaps to whichever has the lower command) → lead flag
  0x408DA0 bit7 and the DDE+10 index fields. The follower's command is clamped to the lead's + offset (exec
  0x5932A). With a valid lateral signal the lead choice also uses the lateral sign. **CONFIRMED**, see
  `08_phase_control.md` §7 and `09_chassis_sensor_use.md` §2.3.
- **`abs_pair_logic` is µ-split yaw-moment limiting (GMA), not general pair control.** At entry it calls
  `abs_pair_gate` 0x54B70 and exits (0x54DBC `cmpnei r2,0` → `jmpi 0x553BE`) while the gate state S
  (`0x408E5F` b6:5) is 0. S leaves 0 only on an axle pressure split with |yaw| > cal 0x40DD4 on the matching
  side and the yaw-stable flag set, so without valid yaw (e.g. no SZL) the function never runs. **CONFIRMED**
  (`09_chassis_sensor_use.md` §2.4).
- With S ≥ 1 it toggles the partner via `xor …,64` (`^0x40`, 0x54DC8 / 0x54F3C), runs the partner-slip test
  (§2b), and writes decision codes **32** (partner dumping with a higher command, 0x54E48), **1024** /
  **16** (rebuild step, 0x54EB4 / 0x54F08) and **2** (0x552BA / 0x553AC). **CONFIRMED.**
- **GMA rebuild pacing:** `abs_gma_hold_frames` 0x054BE8 (called at 0x55200) scores how long the high-grip
  wheel holds before each +3 bar rebuild step, from slip, speed, decel, predicted yaw (0x408ECC +
  0x408ECE/2), steering rate and steering added since the event began. Detail in
  `09_chassis_sensor_use.md` §7.3. **CONFIRMED.**
- A rear wheel's pressure reference is the **same-side front wheel's pressure PM** (X[i] indexing).
  **INFERRED(port).**

Summary: rears are select-low; fronts are controlled individually; on a yaw kick with an axle pressure split
the pair logic slows the high-grip wheel's rebuild.

---

## 4. Pressure-phase state machine (dump / hold / build)

Full decode: **`08_phase_control.md`** §3–§6. Summary:

**(A) Per-wheel phase bits — `rec[0]` at 0x40BF00 + 0x40·w, machine `abs_phase_sm` 0x04FC3C.**
Bits: b7 armed · b6 pre-control · b5 **DUMP** · b4 **REAPPLY** · b3 **HOLD** · b2 reapply-paused / overspeed ·
b0 in an ABS cycle (rolled up per axle into 0x408DA2 by `abs_state_aggregate` 0x45808).

| State (rec[0]) | Name | Transitions (event word from 0x04D270) |
|---|---|---|
| 0x80 | armed idle | EV0.b5→0x21 (dump); EV0.b6→0xC0 (pre-control); EV0.b7→0x84 (overspeed) |
| 0xC0 | pre-control | EV0.b5→0x21; EV1.b3 stay; else→0x80 |
| 0x84 | overspeed hold | EV1.b5→0x80 |
| 0x21 | **DUMP** (b5+b0) | EV0.b3→0x09 |
| 0x09 | **HOLD** (b3+b0) | EV0.b0→0x21; EV1.b7→0x11; EV1.b6→0x15 |
| 0x11 | **REAPPLY** (b4+b0) | EV0.b0→0x21; EV0.b1→0x15 |
| 0x15 | reapply paused | EV1.b4→0x11 |

A suppress condition (`0x400952[w]` b3 and (b0 or front), or `rec+0x19` b5) forces 0x21→0x09, 0xC0→0x80 and
0x09→0x11. Nothing in `abs_phase_sm` returns a wheel from 0x09/0x11/0x15 to 0x80; that is the end-of-event
reset (§5). **CONFIRMED.**

**(B) Axle-pair gate state S0..S3** in 0x408E5E/0x408E5F bits 6:5, read by `abs_pair_logic` (§3).
**CONFIRMED.**

**(C) Decision code 0x408DDE** (`abs_decision_classify` 0x051B54 → `abs_decision_resolve` 0x058B30 →
`abs_decision_pressure_exec` 0x058FF4). Classify/pair logic write 1 (rears uncoupled), 64 (rear select-low),
32, 128, 16, 1024, 2; resolve maps 64→16, 128→256/2, 16→8; exec acts on exact values 2, 4, 8 (select-low
follower), 32 (cornering knock-down) and 256 (lateral-g build step). **CONFIRMED** (switch at 0x58FFC).

**Dispatch** — `abs_phase_dispatch` 0x0504D0 routes rec[0] bit → handler: bit6→0x050894 (pre-control),
bit7→0x050580 (armed/idle), bit3→0x04CA3C (hold), bit4→0x04B680 (reapply), bit5→0x04AAA8 (dump), then
the slew clamp 0x0584CC. **CONFIRMED.**

### Phase actions (CONFIRMED, `08_phase_control.md` §5)
| Phase | Handler | Pressure action |
|---|---|---|
| **DUMP** | 0x04AAA8, first frame → `abs_dump_entry_target` 0x055F06 | entry target = `abs_p_lock` (0x408FD0) − R, R ≈ 8 % of lock pressure plus decel-rate, wheel-decel, rear-slip and decel-onset terms; command **capped** at `abs_p_dump_cap` 0x40901C = wheel pressure − 0x401D00[w]; rate −8000. Later frames: pause, continuous −10 bar/frame, or scheduled steps |
| **HOLD** | 0x04CA3C (entry sync 0x057200) | CMD = measured wheel pressure; rate 0 (valves trap the pressure); headroom H = max(5 bar, lock − min) prepared for reapply |
| **REAPPLY** | 0x04B680 + step 0x0581BA | staircase: each step raises the ceiling by ≈ 0.19·H then 0.16·H, ramped at 3 bar/frame (front) / 5 bar/frame (rear), 7-frame wait between steps; continuous ramp after N_max steps |

The front-axle staged dump (`abs_dump_hold_stage_ctrl` 0x53940 → `abs_dump_stage` 0x5424C) pulls the other
front down to the first front's lock pressure minus 10/15/20 bar (cal 0x40E64/66/68), staged by peak decel
{−62,−78,−94} or {−25,−44,−62} (a/16). It is not part of the per-wheel dump entry.

- **Adaptive behavior:** `abs_lockon_pressure_estimator` 0x05862C maintains LOCKEST 0x408FD0 (captured in the
  reapply step, min-selected with wheel pressure, clamp 25000); dump targets reference it, so the dump depth
  follows the pressure at which the wheel last locked. **CONFIRMED.**

---

## 5. ABS exit / deactivation

- **Low-speed:** below 4 km/h the apply request is dropped: 0x442AC (called from 0x4491C) compares vref with
  400 at 0x44338 and clears `0x408D9C` b4 (arbiter apply id 19) at 0x44382. **CONFIRMED**
  (`05_edge_cases_variants.md` §3).
- **Standstill:** vref clamps to the ~0.6 km/h floor (0x4032D0). **CONFIRMED.**
- **End of event:** `abs_state_aggregate` 0x45808 (0x458E0–0x45964): when `0x401FF2 & 0xA0 == 0x80` and the
  ABS mode field `0x408DA1` bits 7:5 ≥ 5, every wheel gets rec[0] = 0x80 (bit 2 kept) and `rec+6` ≥ 360. This
  is the only route from hold/reapply back to armed. **CONFIRMED**; what advances the mode field is open
  (`08_phase_control.md` §6).

---

## 6. Keeping ABS distinct from DSC/ASC/EBD

- **ABS proper:** §§1–5 — `vref_update` 0x449D0, `abs_event_classifier` 0x04D270, `abs_phase_sm` 0x04FC3C,
  `abs_pressure_frame` 0x045F54, `abs_phase_dispatch` 0x0504D0, dump/hold/reapply handlers, `abs_dump_stage`
  0x05424C, `abs_gross_slip_threshold` 0x52380, `abs_pair_logic` 0x54D9A.
- **Cornering inside ABS:** rear lead by lateral sign, classifier code 32 / code 1 by lateral-g curves, the
  rear cornering latch, GMA pacing — all need valid lateral/yaw (`03_lateral_g_influence.md`,
  `09_chassis_sensor_use.md`). The yaw/β observer, yaw PD moment and brake-steer distribution
  (0x05EBC4 / 0x05F7BA / 0x0616A4, AYC id 3/20) are **DSC/AYC**, not ABS — shared only via the arbiter and the
  sensor signals.
- **TCS/ASC** (drive-slip) uses a *different* reference `vref_tcs` 0x403066 and its own curves
  (0xF625C/0xF61F6, caps 0xF654C) + torque path (TX 0x0B6) — not this loop.
- **EBD:** the rear select-low + same-side-front reference and the decel-threshold front/rear curves provide
  the brake-force distribution behavior; no separate EBD module was identified. **UNCONFIRMED** whether a
  distinct EBD threshold set exists.

---

## 7. Open / needs-hardware
- Real-world frequency of the −10 g staged-dump crossings — needs a dynamic bench/vehicle trace.
- Purpose of cal 0x40DB2 (=10).
- Pre-control (0x50894) and armed (0x50580) handlers: summary in `08_phase_control.md` §5.5; mode field §6.1.

---

## Appendix — curve bytes (as stored, big-endian s16), re-derivable
Partner-slip curve CPU 0x40DB6 (file 0x48DB6): `00 00 | 03 84 | 00 02 | 13 88 | 00 96 | 00 73 | FF FC | 00 03`
→ lo=0, hi=900, n=2, xs=[5000], cs=[150,115], ks=[−4,+3].  Debounce word CPU 0x40DB4 (file 0x48DB4)=`00 02`=2.
Gross-slip CPU 0xD6CE2 (file 0xDECE2): lo=0, hi=32767, n=3, xs=[2000,5550], cs=[400,599,−13], ks=[+102,0,+113].
Evaluator `curve_interp_s16` 0x710FC: `i = count(xs[j] < x)` (strictly below), `y = clamp(cs[i] + x·ks[i]/1024,
lo, hi)` with the division truncating toward zero.

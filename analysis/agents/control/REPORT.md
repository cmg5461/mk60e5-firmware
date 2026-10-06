# ABS control targets / hold-dump logic (1M 7846411A)

Agent-derived (Sonnet), **key claims verified by main session** (ABS+0x576 slip curve, ABS+0x0C=400,
COA+0x1D6 axis, decel stages re-read byte-exact). Machine files in `analysis/agents/control/`
(`blkrefs.py`, `block_readers.txt`, `const_curves_d7xxx.txt`, `curves.py`, scratch fn dumps). CPU addresses.

## Answer first — corrects today's earlier framing
- **The ABS *controller* is the code at 0x44000–0x5E000** (the same code that reads the ABS cal block),
  **not** the 0x8xxxx code. The earlier "ABS block = estimation layer only" label was wrong: that block
  is the ABS controller's calibration (slip-speed threshold + decel stages + pressure-model shaping).
- The **0x8xxxx code is a per-wheel brake-pressure request *arbiter* + hydraulic/valve-pulse *sequencer*,
  calibrated by COA (0x41B98) and the 0xDA2F0–0xDB2FF scalar block** — not by the ABS block.
- **No explicit "target slip %".** The controller works in a **pressure-model domain** (per-wheel pressure
  levels, ~0.01 bar guess, range −8000..25000) driven by: a **slip-speed threshold curve**, **peak-decel
  stage thresholds**, and hard-coded curve tables at 0xD713C–0xD7390.

## Block → reader map [verified: literal-pool scan]
| Block | Reader range | | Block | Reader range |
|---|---|---|---|---|
| ABS 0x4039C | 0x44722–0x5B0EE (49 fns) | | COA | 0x8181E–0x8DDE8 (34 fns) |
| AYC | 0x5ECB0–0x68868 | | CSI | 0x8FC78–0x92980 |
| BCO | 0x69080–0x6C13C | | DDS | 0x96666–0xAE2A0 |
| TCS | 0xC78D0–0xCF670 | | VMO | 0xD1A8A–0xD3DF6 |
| LVC | 0xBFF06–0xC44E4 | | CSW | 0x954E2–0x9601E |

0xDA2F0–0xDB2FF scalar block: ~125 readers in 0x7B9xx–0xC87xx (arbiter/sequencer + DDS); **zero** in
0x44000–0x5E000, so the ABS controller does not use it.

## Dispatcher 0x8CAD8 [verified from listing]
ABS controller entries **0x44722 / 0x449E4** (run if 0x408ED2 mode nibble ∈{1,2,4} or 0x40491A bit5).
Arbiter/sequencer entry **0x840AC**. TCS at 0xCC828. 0x8CC7E computes driver (master-cyl) pressure
0x404974 from table 0x40171A.

## The ABS wheel-slip target [verified bytes; agent semantics, med]
- **Slip-speed threshold curve = ABS+0x576 (0x40912):** lo 0, hi 900, 1 breakpoint @5000, intercepts
  150/115, slopes −4/+3 (Q10); input = slip = vref(0x408D84) − wheel speed (struct+0x1A).
  Evaluated (0.01 km/h): 150 @0, 129 @50, 144 @100, 158 @150, 173 @200, 202 @300 km/h →
  **≈1.3–2.0 km/h of wheel slip as the ABS entry/continue condition.** This is the closest thing to a
  "slip target" and it IS in the calibratable ABS block. (fn 0x54F9A, top-level per-wheel pressure state;
  also uses 60%/30% scaling of a stored level.)

## Pressure control [verified bytes; agent semantics]
- Pressure-level arrays per wheel: 0x408EFE (commanded), 0x408F1E (saved at entry), 0x408F26 (snapshot),
  0x408F36 (ramp/step), 0x408F3E (upper). Modelled wheel pressure 0x4016E2[ch] → 0x408F06[w] (fn 0x55BCC).
- **Apply ramp: ABS+0x0C = 400 per cycle**, capped at 25000 (fn 0x44614, request id 19).
- **Pressure clamps 25000 / −8000 are hard-coded literals** (0x61A8 / 0xE0C0), not calibratable.
- **Dump-stage thresholds (decel-based, fn 0x5444C):** signed peak wheel-accel byte (struct+0x39, = accel/16
  ±127 clamp, fn 0x465B0) compared to ABS+0x61E set A −62/−78/−94 or +0x65E set B −25/−44/−62 (flag +0x65C);
  stage → pressure reduction ABS+0x624 = **1000/1500/2000 (= 10/15/20 bar @0.01 bar)**, written to 0x409188.
  Gate: vehicle byte 0x408D8B ≥ −70.
- Decel-threshold builder fn 0x47DFC + ladder (from the ABS report): base −116, floor −240, speed curves
  +0x76/+0x9E, +0x154 front curve; per-wheel target summed into 0x409110+10·w (0x40910C[] stays inside the
  ABS controller, reaches valves only via 0x408EFE → request id 1/11/19 → arbiter).

## Request arbiter 0x831FA + hydraulic/valve layer [verified call sites; agent semantics med]
- Channel structs @0x401728 stride 0x38, up to 4×12-byte request records; result state → 0x401960[ch]
  (codes 1/6/9/11, not decoded). Requester ids: ABS = 1/11/19 (0x448D6/0x44614); TCS = 2; driver pressure
  = 0 (r7=10000); AYC-region = 3/20; others 5/6/9/13/16/17/18.
- **COA volume→pressure (stiffness) characteristic**, fn 0x8181E: x-axis COA+0x1D6 (0x41D6E) =
  **0,400,700,1000,1500,2000,3000,6000,12000,32700** (verified); 4 mode y-tables at 0x41D82+20·m
  (e.g. 0,1600,2200,2650,3300,3900,5050,8150,13300,31200). Front uses mode byte 0x4031AA+3, rear +4.
- **Pulse sequencer fn 0x851C8:** pulse count n=0..10 from (target − modelled pressure) via COA curves;
  builds 10 u16 slots (full-on 0x604=1540, reduced 0x5F4/0x5FC) → 0x404872+20·ch (double-buffered).
  Hold vs dump = sign/size of (requested − modelled pressure); n=0 → hold. Phase byte 0x401AA8[ch·8] ∈{1,2,4}.

## Hard-coded curves outside any cal block: 0xD713C–0xD7390 [verified bytes]
~15 piecewise-linear curves read by the ABS controller via sub_071158, in the const area (NOT in the
12-block cal directory) → **effectively not calibratable by editing the ABS block**. These are the
speed/state-dependent caps & limits. Full table in `const_curves_d7xxx.txt`. Which one is the effective
per-axle slip limit was not closed out.

## Where each item lives (summary)
| Item | Home |
|---|---|
| ABS entry slip-speed threshold | **ABS +0x576 curve (0x40912): ≈1.3–2 km/h** |
| Dump stage thresholds / amounts | ABS +0x61E/+0x65E (decel) / +0x624 (10/15/20 bar) |
| Apply ramp | ABS +0x0C = 400/cycle |
| Pressure limits 25000/−8000 | hard-coded literals |
| Speed-dependent caps/ramps | 0xD7xxx const curves — hard-coded in ROM |
| Pulse timing / hydraulic gain | COA + 0xDA2F0 scalar block |
| Per-wheel decel threshold & ladder | ABS +0xCC/+0xCA/+0x76/+0x9E/+0x154 |

## Open
- Units of pressure levels (0.01 bar is a guess) and struct+0x20 (wheel accel).
- Request semantics (which of r5/r6/r7 is target/rate/limit).
- Which 0xD7xxx curve is the effective per-axle slip limit; front/rear split by wheel flag bit7 not traced.
- Whether 0xDA2F0–0xDB2FF is the hydraulic scalar block proper or mixed with DDS.
- 0x401960 state codes; pulse unit (1540 ticks vs 10 ms frame).

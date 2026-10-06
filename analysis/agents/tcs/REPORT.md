# TCS (traction) calibration block (1M 7846411A) — field decode

Agent-derived (Sonnet), **key claims verified by the main session** (base slip curves +0x086/+0x0EC/
+0x10E/+0x130, hysteresis +0x1DC/1DE, pct +0x1D4.., entry gates +0x14.., gross-slip +0x0C.., and the
5×8 map at +0x28E all re-read byte-exact). Machine tables on disk: `work/tables.md` (55-row curve
table), `work/dump.txt` (annotated raw u16), scripts in `work/`. Offsets relative to **CPU 0x40AB8**.

## Header [verified]
`TCS\x01`, version 4, id 0x5E301A81, body from +0x0C.

## 1. The 0xC79A0 "descriptor table" is NOT a table [verified]
0xC79A0..0xC8320 is interleaved **literal pools between ordinary code** (bodies of sub_0C7A34,
sub_0C7BC8, sub_0C7CCA…). No stride, no columns — each word is one `lrw` literal in order of use.
Literal kinds: `0x0004xxxx` = TCS field addresses; `0x0040xxxx` = RAM vars (different address space);
constants + fn pointers (`0x00071158` = the interpolator). **Fields are grouped by reader function.**
The controller is one module of ~60 functions at **0xC7600..0xCFA00**, reached from control dispatcher
0x8CAD8 (handlers 0xCC828, 0xCF760, 0xCF7BA, 0xCC4DC, 0xCCF5C, 0xCC87E, 0xCF670).

## 2. Block format [verified]
Mostly 1-D piecewise-linear curves read by `sub_071158(table, x)`, all s16:
`[ymin, ymax, n, x[n-1] ascending, A[n] intercepts, B[n] slopes (Q10)]`;
`y = clamp(A[k] + x*B[k]/1024, ymin, ymax)`; length 3+(n-1)+2n words. 55 tables found, 41 call sites.
Curves replicated per **mode m = 0,1,2** at stride 34/28/22 bytes (5/4/3-segment). Mode byte = 0x4031AA+7,
from states 0x4030A2/A3/A4; physical meaning unresolved.

## 3. Plumbing that gives fields meaning [agent, high]
- **Reference speed** `0x403066 = min(0x403076, 0x403078)` = filtered LF/RF (undriven front) speed, 0.01 km/h.
  It is the x input of nearly every curve.
- **Drive slip** `sub_0C957E`: `0x40307E[w] = wheel[w] − same-side front reference`; for w=2,3 that's
  driven−undriven delta. `0x403086[w]` = low-pass filtered version.
- **Rear-only**: per-wheel controller state `0x402FC4[w]` initialised only for w=2,3 → traction acts on
  the rear driven wheels.
- **Controller state** `0x4030A2` (3 = active); `0x402F6C` bit4 selects curve set A vs B.

## 4. Drive-slip targets and limits [agent, med; curves verified]
**No explicit "target slip %"** — slip is an absolute speed difference in 0.01 km/h, compared with
per-wheel limits built each cycle in `sub_0C78D0`: `0x403014[w]` (entry/upper), `0x40300C[w]` (exit/lower).

### Base slip-threshold curve (the central field)
`sub_0C7746`: `thr = curve(table, vref)`, table `+0x0EC + 34*m` (set A default) or `+0x086 + 34*m`
(set B, when `0x402F6C` bit4 set). All six: n=5, clamp 0..30000, breakpoints at 15, 25/50, 80, 100 km/h.

Evaluated **thr in 0.01 km/h** (verified) at vref 0/15/25/50/80/100/150 km/h:

| table | 0 | 15 | 25 | 50 | 80 | 100 | 150 |
|---|---|---|---|---|---|---|---|
| +086 (B m0) | 700 | 270 | 100 | 226 | 377 | 1182 | 2842 |
| +0A8 (B m1) | 700 | 651 | 649 | 647 | 679 | 1182 | 2838 |
| +0CA (B m2) | 700 | 551 | 550 | 548 | 580 | 1081 | 2742 |
| +0EC (A m0) | 1500 | 270 | 100 | 226 | 377 | 1182 | 2842 |
| +10E (A m1) | 1400 | 869 | 806 | 648 | 679 | 1182 | 2842 |
| +130 (A m2) | 1400 | 769 | 706 | 548 | 579 | 1082 | 2742 |

Reading: allowed rear−front difference ≈ 1–7 km/h at low speed, 3.8 @80, **11.8 @100**, 28 km/h @150.
m1/m2 are much flatter at low speed (≈6.5/5.5 km/h at 25 km/h vs ≈1 km/h for m0).

### Limit composition (`sub_0C78D0`)
- `0x403014[w] = thr + extras + (+0x1DE = 500 → 5.00 km/h) − R`
- `0x40300C[w] = thr + extras/2 + (+0x1DC = 300 → 3.00 km/h) − R`  → ~2 km/h + extras/2 hysteresis [low-med]
- `R = pct*0x40308E[w]/100`, pct from +0x1D4/6/8/A = **10/10/2/10 %**.
- extras from curve `+0x180+28*m`: 10.00 km/h @vref 0 → 2.00 km/h @15 km/h then flat; only when vref ≥ 2.5
  km/h and `0x402F7E` bit4 clear.

### Entry gates / windows [low-med]
- `sub_0C7BC8`: +0x14=1600, +0x16=1000, +0x18=2000, +0x1A=3000 (vref must be < 30.00 km/h).
- `sub_0C8384` gross-slip limit: `max(+0x0C=1500, +0x10=4000 − vref*(+0x0E=1000)/1000)` → 40 km/h @standstill
  → 15 km/h @25 km/h. +0x12=1500 vs 0x402F70. +0x3B0=350, +0x3B2=75 bound 0x402FC4[w].
- `sub_0C7CCA` state machine: +0x234/236/238 = 80/110/150 (vs 0x403024); +0x4A=-250, +0x4C=180;
  +0x6E/70=500; +0x1E0=1000, +0x1E2=-600.

### Exit/hold map at +0x28E (verified)
5×8 u16 map (row stride 16 B), read by `sub_0C892C`. Row = clamp((lower_limit − slip + 500)/500, 0..4);
col = clamp((0x40308E/10 + 201)/25, 0..7). Looks like release/hold time in cycles [low]:
```
 4  5  7 10 14 19 24 30
 3  4  6  8 10 14 18 24
 2  3  5  6  8 11 14 18
 1  2  3  4  6  8 10 12
 1  1  2  2  3  5  6  7
```
`sub_0C8A6A` uses +0x278..+0x28A = 95,-1000,80,15,50,10,2000,20,50,80 as percent gains/clamps.

### Engine-torque term [low]
`sub_0C9704` maps byte 0x401142 through curve +0x240 (A) / +0x25C (B): y = 14.00→30.00 over x 0..75,
→40.00 at x≥125; combines with +0x224..+0x22E, +0x23E into 0x403024.

### Torque-reduction thresholds — NOT tied down
No field confidently tied to torque reduction. Low-confidence candidates: +0x5C6/5E2/5FE (35%→10% vs
vref), 17-word sets +0x66E..+0x718, ramp sets +0x534/550/56C (x = signed byte 0x403096).

## 5. Other fields [low]
Gain/bias (sub_0C8E96): +0x37E..384 = 300,300,300,1; +0x376..37C = 130,40,-300,800. Large consts
+0x3A8=14000, +0x3AC=12000, +0x3B4=5. Tail +0x8FE..+0x930 (37CE,8B82,0B3B,9976,6F9B) = integrity/id words
(readers CF1BE/CF35C/CF29C). Zero/unused tables: +0x1E4,+0x310,+0x742,+0x826. +0x550,+0x56C duplicate +0x534.

## 6. Open
1. Physical meaning of modes 0/1/2 (DSC/DTC/off? surface?).
2. Units of 0x40308E (slip rate or wheel accel), 0x403024, 0x4030B6/AF/B8; engine inputs 0x401142/113C/113E.
3. Torque-request writer not traced → torque-reduction fields unconfirmed.
4. Whether 0x4030A3/A4 carry gear info.
5. "Drive-slip" label for +0x086..+0x130 rests on compare site (vs 0x403086) + curve shape; module is
   shared, some limits may be brake-side.

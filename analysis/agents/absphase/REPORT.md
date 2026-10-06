# ABS phase / decision logic (1M 7846411A)

Agent-derived (Sonnet), **constants verified by main session** (ABS+0x550=80, +0x570=3, +0x572=10,
+0x574=2, +0x594=1399, +0x520=500, +0x540/+0x542=1, +0x58E/590/592=126/8/1748, +0x654/+0x65C=1 all
byte-exact; slip curve +0x576 matches). Control flow from the listing. Machine tables in
`analysis/agents/absphase/tables.txt`. CPU addresses; ABS block base 0x4039C.

## The apply/hold/dump decision (overview)
No single per-wheel "phase" variable — **three cooperating layers**:
1. **Per-wheel phase bits** in wheel record `rec[0]` bits 6..3 (`rec` @ 0x40BF00+0x40·w; prev cycle in
   `rec[1]`). Transition fn `sub_04FE3C`. `rec[0]` bit5 = "wheel in ABS control".
2. **Axle-pair cycle phase S0..S3** in `0x408E3B` bits 6:5 (`sub_054D70`); `fn 0x54F9A` branches on it.
3. **Per-wheel request flags `0x408D78[w]`:** bit7 = dump/hold request this cycle (→ bit5 next cycle),
   bit4 = reapply (id 19) phase.
Plus a **global decision code `0x408DBA`** (1=build/none, 2=partner-hold/reduce, 16/32/64/128, 1024=reapply),
classified by `fn 0x51D54`, refined by `0x54F9A`.

## Entry condition [verified]
Wheel enters ABS when **slip > thr**, where `thr = curve(ABS+0x576, x = vref)` — i.e. the threshold is a
function of vehicle speed (corrects earlier "input is slip"): **150/129/144/173/202 ·0.01 km/h at vref
0/50/100/200/300 km/h ≈ 1.3–2.0 km/h** of absolute slip. Slip ratio itself `0x408F60[w] =
(vref − wheel)·10000/vref` clamped ≥0 (1e-4 units). Run gate (entry 0x449E4): `0x408ED2` low nibble ∈{1,2,4}
or `0x40491A` bit5, and `0x400966` bit6 clear.

## Dump — `fn 0x5444C` [verified]
Partner-based (per-axle). `p = rec[0x39]` (filtered peak decel, signed). Gates: `0x408D8B ≥ −70`,
`rec[22]` bit7, `rec[0]` bit5, `0x400A95` bit7, `0x408F88 < 7`. Stages (higher wins):
- Set A (ABS+0x654≠0, `rec[16]` bits7:5 <3): p ≤ −62 / −78 / −94.
- Set B (`0x400A95` bit1, ABS+0x65C≠0): p ≤ −25 / −44 / −62.
- Amount ABS+0x624/626/628 = **1000/1500/2000 (10/15/20 bar)**.
Target `0x40918A = max(lockonset 0x408F98 − amount, 0)`, **floored at 2000 (20 bar)**, min with ceiling
`0x408F4A`. Sets `0x408D78[partner]` bit7 → request id 1 (id 11 rear). So **dump target = lock-onset
pressure − 10/15/20 bar, never below 20 bar.**

## Apply / reapply — `fn 0x44614` (id 19) [verified]
Per wheel with `0x408D78[w]` bit4: if `0x401960[w]==11` CMD=0x408F16; `RAMP=ABS+0x0C=400`;
**CMD = min(CMD+400, 25000)** per cycle; arbiter(op1, id19, start=SNAP, target=CMD, rate=400). Reapply
continuation (`0x444CC`) requires ABS owns channel (`0x401960∈{1,11}`) and deficit `0x408F0E−0x408F06 > 500`
(5 bar) with summed deficit >1000. Aborts if vref>400 km/h, `0x408D7D`&0xE0/bit3, `0x408E44` bit2=0, or
`0x408D7E` bit6. Reapply **nudges** in 0x54F9A: `SAV + 80` (0.8 bar, ABS+0x550), or `+240` if `SAV<0.30·X`.

## `fn 0x54F9A` (pair logic per S-state) [verified flow, med semantics]
Runs when `0x408DBA∈{32,64}`, ABS+0x540≠0, ABS+0x542≠0. Names: CMD=0x408EFE, SAV=0x408F1E, UP=0x408F3E,
RAMP=0x408F36, PM=0x408F06, X[i]=word@0x408F06+2i−4 (rear → same-side front PM). 60%/30% scalings are
`SAV` vs `X`. Partner reduction uses RAMP=**−8000** (max-rate dump toward UP). Cornering clause in S2 is
rear-specific (RL=0x40BF80, RR=0x40BFC0), bounded by |lat|>1748 and ECC limit `2 + max(0, 8−(|lat|−1748)/126)`
(ABS+0x58E/590/592). Full pseudocode in the raw report / tables.txt.

### Axle-pair phase S (0x408E3B 6:5, sub_054D70) [verified transitions]
Predicates A(0x549D8, PM<0.30·0x408FCC or cross-axle+vref≥110 km/h), B(0x54B54, limit ABS+0x572×100=1000),
C(0x54C80), D(0x54CF8). S0 idle (54F9A sets MINA=32000) → S1 entry → S2 pair-hold/reapply → S3 end/rear-balance → S0.

## Output to arbiter [verified]
`0x831FA(op1, id, ch, start, target, rate, flag)`; slot records 12 B, ≤4/channel (struct 0x401728+56·ch).
`fn 0x448D6`: wheels with `0x408D78` bit7 → id 1 (if `0x408DA2` bit6) or id 11 (rear only, `0x408DA2` bit3
& `0x408D7E` bit5). **Channel owner `0x401960[ch]`** = winning requester (sub_083540), priority low→high:
16<20<17<12<11<0(driver)<13<14<3<2(TCS)<1<8<6<4<5<18. **ABS id 1 beats driver and TCS; id 11 loses to
driver.** Read back by 44614 (restore on state 11) and 444CC (ownership).

## Per-axle differences
Pairs front(0,1)/rear(2,3) via `^0x40`; cross-axle `^0x80`. `X[i]` makes rear compare vs same-side front
PM. id 11 rear-only. `0x408D7C` bit7 selects rear Δp (RL−RR) sign in S3.

## Open
- Event→state names for the `rec[0]` machine (0x4D470 event word, sp+114/sp+56 origins).
- Meaning of 0x408DBA codes 2/16/32/64/128; full 0x51D54 logic.
- Whether 0x408F4A is setpoint or ceiling; writer of state 19.
- Units of 0x408EA8/0x408EAA (lateral-like), 0x408F88, 0x408D8B. Pressure unit 0.01 bar assumed.

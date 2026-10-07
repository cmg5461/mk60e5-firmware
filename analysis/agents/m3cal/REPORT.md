# M3 (7846816A) ABS/TCS calibration vs 1M (7846411A) — field-level comparison

Agent-derived (Sonnet), **key claims verified by main session**: M3 relocated base-slip curves at
0xF61F6/0xF625C are byte-identical to 1M TCS+0x86/+0xEC; M3 ABS floor tables (+0x2A8 = −127 then −120×11;
+0x2C0 = −132×10 then −140×2); base/floor −116/−240. Machine files in `analysis/agents/m3cal/`
(`curves.py`, `evalall.py`, `tcs_1m_to_m3_curves.txt`, `abs_1m_m3_map.txt`, etc.). CPU addresses.

## Answer first — corrects the earlier "block size" inference
**The M3 is NOT meaningfully more permissive in the core slip or deceleration targets.** The earlier
read ("M3 TCS 5× smaller ⇒ traction restructured/moved to ABS") was misleading:

- **M3 TCS didn't shrink by deletion — the curves were RELOCATED, byte-identical, into constant ROM at
  CPU 0xF61B4–~0xF6730** (outside the 12-entry cal directory and the 0x1D4 TCS block). 39 of the 1M's 55
  TCS curves have an exact M3 match; all six base drive-slip curves are byte-equal. M3 TCS code reads them
  via `lrw 0xF61F6` etc. [verified]
- **M3 ABS growth (1.73×) is 12-way variant duplication** of three items (front speed-term curve 0x1E0 B,
  g-curve 0x300 B, floor tables 0x30 B ≈ 0x4A4 = 0xB0A−0x666), indexed by `0x4031AA+1`, a 5-bit EEPROM
  coding field read via `0x8E066(24,1)` — **not in the flash image**, so the active variant is unknown
  statically. [verified]

## Base drive-slip threshold: Δ = 0 [verified]
M3 == 1M exactly (re-evaluated from M3's own bytes at 0xF61F6…): set-A m0 = {1500,270,99,226,377,1182,
2842} at vref {0,15,25,50,80,100,150} km/h·100; all six tables match ±1 rounding. Same code structure
(A/B by 0x402F6C bit4, stride 34/mode, x = vref 0x403066). **No extra drive slip allowed.**

## ABS deceleration threshold: variant-gated [verified bytes]
Threshold = −116 − speed_term − g_term, floored at −240 (more negative = later ABS entry).
- **Variants 1–9: identical to the 1M.**
- **Variant 0:** floor for vref<20 km/h = −127 vs −120 (not binding at g=0).
- **Variants 10/11:** higher-speed thresholds more permissive — at 150/200/250/300 km/h = −139/−154/−177/
  −200 vs 1M −135/−144/−167/−190 (g-term up to +7 larger); floor for vref<60 km/h = −140 vs −132.
- Rear curve, base, floor, gains, ladder, stage thresholds all identical.
- **So the M3 is more permissive only if coded to variant 10/11** (= GTS coupe / GTS sedan; high-speed,
  ≥150 km/h, by ≈3–5% at 200–300) **or variant 0** (= M3 sedan; <20 km/h). The active variant lives in EEPROM, not the flash.

## TCS differences: small, unresolved sign [agent, low on direction]
- Three 0..16000 cap curves (1M +0x66E/690/6B2 → M3 0xF654C/656E/6590, ÷20 in code, fn 0x0CB576) are
  **+3000–3600 higher** in M3 (1.5×–3.5× at low/mid speed) — a *larger* cap on an added term.
- M3 TCS +0x038 cap curve is **tighter** at 50–120 km/h (199 vs 1197 @100 km/h).
- One widens, one narrows → **no evidence of a systematic motorsport-leaning TCS calibration**.

## Field maps (abridged; full in work files)
- **M3 ABS** (0x4039C, len 0xB0A, ver 4): +0x00C–0x09C identical to 1M; front speed-term 12× at +0x076+0x28·m;
  rear term single at +0x256; gains +0x27E/+0x280 = 40/25; floor +0x282 = −240, base +0x284 = −116;
  floor<20 +0x2A8+2m; floor<60 +0x2C0+2m; g-curve 12× at +0x2D8+0x40·m; ladder +0x76C; stages +0xAC2/+0xB02.
  Interpolator at 0x710FC. No M3-only slip-% or hold/dump target.
- **M3 TCS** (0x40FBC, len 0x1D4, ver 4): keeps per-mode triples, small curves, scalars; everything large
  relocated to 0xF61B4–0xF6730. ~25 1M scalar groups (gross-slip 1500/1000/4000, entry gates
  1600/1000/2000/3000, pct 10/10/2/10, hysteresis 300/500) have **no M3 data counterpart** — the M3 TCS
  code is a different generation (no 0xFA0 literal), so that logic is absent or inlined [agent, med].

## Open
1. Active EEPROM coding variant (0..11, record 24) and TCS mode byte for the real E9x M3 — unknown
   statically; the ABS verdict hinges on variant 10/11 vs 0 vs 1–9. Variant meanings since supplied by the
   user (0 sedan, 1 Custom ESM, 3 coupe, 4 convertible, 5/8/9 Competition, 10/11 GTS coupe/sedan): only the
   GTS codings get the permissive set.
2. Sign of the 0xF654C-set and +0x038 TCS effects (needs consumer trace of 0x402FB6/B8, unit of 0x403098).
3. Whether the M3 dropped the missing gross-slip/gate/pct/hysteresis scalars or inlined them as immediates.
4. M Dynamic Mode (MDM) permissiveness is more likely in DSC-mode logic / AYC / code constants than these blocks.
5. Whether a checksum/tool covers the relocated 0xF61B4–0xF6730 region and whether it's tunable.

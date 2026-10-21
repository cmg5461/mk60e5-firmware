# MK60E5 M3 (7846816A) — what the 48 coding bytes do

`c[n]` = byte n of the `22/2E 30 00` payload (EEPROM 0x400+n). Source: the `2E 30 00` validator
`coding_validate_write` 0xCF432 → `coding_validate_unpack` 0xD02E6, which clears the active image and
runs five stages over the receive buffer 0x403320: checksum (0xCFDB8), field unpack + checks
(`coding_unpack_block` 0xCFDD8), flag-word pack (`coding_pack_flag_words` 0xCFF1A), word unpack
(`coding_unpack_words` 0xD0064) and the feature-combination check (`coding_feature_combo_check`
0xD024C). They fill the active image (`f+n` = byte 0x4031AA+n, `w[n]` = u16 at 0x4031B6+2n, flag
words A = 0x4031F4 = w31, B = 0x4031F6 = w32), which is saved as EEPROM block 7 and reloaded at boot;
the raw bytes are not kept in RAM. Any stage failing → `coding_validate_finish` 0xD02C4: fault
0xC0002, image zeroed, image check byte deliberately wrong, NRC 0x31. Symbols:
`7846816A_symbols.md` § Coding write validator. Bit positions and constraints are read from the code (high). Feature *names*
are the NCS names already used in `wheelspeed/tool/src/Coding.tsx` and were not re-derived here.

## Byte 0 is a checksum

`c[0] = (c[1] ^ c[2] ^ … ^ c[47]) + 1` (0xCFDB8). Checked against the captured coding in
`wheelspeed/coding_write_dump.txt`: XOR of bytes 1..47 = 0xCA, byte 0 = 0xCB. Any edit must
recompute it or the write is rejected. (That capture is a non-M 335 coding; it confirms the
checksum but fails most of the M3 field rules below, so it is not an M3 test vector.)

## Byte map

| Byte | Bits | Goes to | Meaning | Constraint enforced |
|---|---|---|---|---|
| 0 | all | – | checksum | must match |
| 1 | 0–4 | f+1 | vehicle-model **variant** (selects the column of every variant-indexed table; values below) | < 12 |
| 1 | 5–7 | – | NCS "engine type" | must be 0 |
| 2 | 6–7 | f+2 | gearbox (0 manual, 2 DCT) | < 3 and ≠ 1 |
| 2 | 3–5 | f+3 | pressure model front: 0 = M3, 1 = M3 GTS (see below) | < 2 |
| 2 | 0–2 | f+4 | pressure model rear: 0 = M3, 1 = M3 GTS (see below) | < 2 |
| 3 | 0 | A.0 | BBV pad-wear compensation | |
| 3 | 1 | A.1 | Pre-MSR (inverted: 1 = off) | |
| 3 | 2 | A.14 | brake fan (Lüfter) | feeds feature check |
| 3 | 3 | – (feature check only) | RPA tyre-puncture warning | |
| 3 | 4 | A.2 | CBC (inverted) | |
| 3 | 5 | A.3 | SDR_CTC (inverted) | must be 1 |
| 3 | 6 | A.4 | engine power reduction for brake overheating | |
| 3 | 7 | A.5 | pre-understeer control (inverted) | |
| 4 | all | w1 | signed trim, yaw-control code (0x60738) | |
| 5 | all | w3 | no reader found | |
| 6 | all | w2 | signed trim, yaw-control code (0x6082C) | |
| 7 | all | w4 | no reader found | |
| 8 | all | w0 | signed trim, yaw-control code (0x62A3C, 0x62D8C) | |
| 9 | 0–3 / 4–7 | w7 / w8 | two 4-bit selectors (0x67C8E, 0x67F7C, 0x682E6) | |
| 10 | 0–3 | w5 | 4-bit value (0x5FB88, 0x60902) | |
| 10 | 4 | B.4 | DDS Plus | requires c[3] bit 3 |
| 10 | 5 | A.7 | USA M-Dynamic mode → DSC mode f+7 = 2 instead of 1 (`dsc_mode_select` 0xCF2E8; only matters while `tcs_mode` 0x4030A2 = 3, i.e. MDM) | |
| 10 | 6 | A.8 | rear-axle rotation direction: sense / ignore | |
| 10 | 7 | B.3 | lane-change logic (LCL) | |
| 11 | all | w21 | signed trim ×7.5 (0x6A462…) | |
| 12 | all | w20 | signed trim ×10 (0x69BD8) | |
| 13 | 0–2 | f+5 | steering-ratio curve select for `steer_ratio_convert` (0x9033C; sets 0x40EB4/0x40ECC + 8·f5). Sets 0 and 1 are identical in this image, set 2 differs. Value 1 = "custom", needs c[41..47] ≠ 0, but nothing reads those words | < 3 |
| 13 | 3 | A.9 | soft-stop assist | |
| 13 | 4 | A.10 | ready-alert brake | |
| 13 | 5 | – (feature check only) | brake-disc drying | |
| 13 | 6 | – (feature check only) | hill-start assist | |
| 13 | 7 | B.5 | brake fade compensation | |
| 14 | 0–3 | w6 | NCS "yaw moment compensation" | must be 0 |
| 14 | 4 | A.12 | trailer stabilisation | must be 0 |
| 14 | 5 | A.11 | GMB | |
| 14 | 6–7 | f+8 | RPA threshold (DDS code, 77 readers) | |
| 15 | 0 | A.13 | – | |
| 15 | 1–2 | f+10 | LVC / hill-start engine-speed limit: 0xF587E[f10] = 5000 / 5500 / 6000 / 6500 rpm; above it `0xC27E6` sets LVC condition 40 | < 4 |
| 15 | 3–7 | f+9 | NCS "hill-start assist level" (0xC0D44…) | |
| 16 | 0–3 / 4–7 | w29 / w30 | BBV pad-wear front / rear (0x95104 / 0x95140) | |
| 17 | all | w9 / w10 | no reader in this image. On the non-M firmware these nibbles are the effective friction radius front / rear (see `CODING_BYTES_6862873A.md`) | must be 0 |
| 18 | 0–2, 3–5 | w33, w34 | – | whole byte must be 0 (0xCFE56) |
| 18 | 6 | – | – | must be 0 |
| 18 | 7 | B.2 | – | must be 0 (whole byte) |
| 19 | all | w35, w36, B.0, B.1 | – | must be 0 |
| 20 | 6, 7 | B.7, B.8 | – | bits 0–5 must be 0 |
| 21–24 | all | w40, w41, w37, w39 / f+11 (c24 b7; no reader) | – | must be 0 |
| 25, 26 | 0–5 | w42, w38 | – | both bytes must be 0 (0xCFE6E / 0xCFE7A); the bits 6–7 check in stage 4 is redundant |
| 27–29 | all | – | – | must be 0 |
| 30 | 0–4 / 7 | f+0 / B.6 | f+0 has no consumer (copied to 0x402DAA by LVC init 0xC0DAE, never read) | bits 0–6 must be 0 |
| 31–40 | all | w11 (c31\|c32<<8), w12 (c33\|c34<<8), w13, w14, w15, w18, w17, w16/w19 | **custom vehicle-model parameters**, used only with variant 1 ("Custom ESM") | if variant = 1: c31, c32, c33, c34, c37, c38 ≠ 0 |
| 41–47 | all | w22–w28 | custom parameter set for `c[13]&7 = 1` | if selected: all ≠ 0 |

After the per-field checks the feature-combination stage runs. `coding_feature_combo_check` 0xD024C
turns c3 b2 (fan, inverted), c3 b3 (RPA), c13 b5 (disc drying), c13 b6 (hill-start) and c18 b6
(always 0) into requested bits under fixed masks. `coding_feature_row_select` 0xCF5D8 then looks
for the row 1–48 of the feature-word tables 0xF677A / 0xF67DC / 0xF683E (49 × u16 each) whose
three words match exactly, and stores its index as **f+6**. `coded_feature(n)` 0xCF478 (~40 call
sites) reads its bits from that row, so f+6 is a compressed copy of those coding bits. Every
combination of the inputs has a row in this image, so this stage cannot fail on its own.

## The 12 unpacked fields f+0..f+11

Limits from table 0xF68A0, checked by `coding_field_limit_check` 0xCFADC (field < limit), both in
stage 2 and at boot after block 7 is loaded (0xCFB14 → 0xCFBA6; failure zeroes the image).

| Field | Source | Limit | Use |
|---|---|---|---|
| f+0 | c30 b0–4 | 1 | none (always 0) |
| f+1 | c1 b0–4 | 12 | vehicle variant |
| f+2 | c2 b6–7 | 3 | gearbox (1 rejected separately) |
| f+3 / f+4 | c2 b3–5 / b0–2 | 2 / 2 | pressure model front / rear |
| f+5 | c13 b0–2 | 3 | steering-ratio curve set |
| f+6 | derived (stage 5) | 49 | feature row for `coded_feature` |
| f+7 | run time | 3 | DSC mode m, written every cycle by `dsc_mode_select` 0xCF2E8 |
| f+8 | c14 b6–7 | 4 | RPA threshold |
| f+9 | c15 b3–7 | 32 | hill-start level (LVC tables 0x422F8…) |
| f+10 | c15 b1–2 | 4 | LVC engine-speed limit (0xF587E) |
| f+11 | c24 b7 | 2 | none (written, never read; c24 must be 0) |

## Byte 2 bits 0–5: pressure model (front f+3, rear f+4)

A 0/1 selector per axle (NCS names: 0 = "M3", 1 = "M3 GTS") that picks the column of several
brake-hydraulics tables. Found by tracing every `ld.b` of `0x4031AA+3` / `+4` (about 65 sites) and
dumping the tables they index. The per-field limits come from the table at 0xF68A0
(`[1, 12, 3, 2, 2, 3, 49, 3, 4, 32, 4, 2]` for f+0..f+11), checked by 0xCFADC.

**1. Pressure↔volume curve (both axles) — the main effect.** About 20 functions in 0x816E8–0x880A8
(the COA hydraulic model) use `0x41B62 + 20·front` for wheels 0/1 and `0x41B8A + 20·rear` otherwise,
interpolated on the shared pressure axis 0x41B4E (0.01 bar) via 0x7119E. Volume unit not identified.

| Pressure (bar) | 4 | 7 | 10 | 15 | 20 | 30 | 60 | 120 | 327 |
|---|---|---|---|---|---|---|---|---|---|
| Front, code 0 | 1600 | 2200 | 2650 | 3300 | 3900 | 5050 | 8150 | 13300 | 31200 |
| Front, code 1 | 1600 | 2150 | 2600 | 3250 | 3800 | 4950 | 8150 | 14000 | 32750 |
| Rear, code 0 | 1000 | 1500 | 1850 | 2350 | 2750 | 3400 | 5050 | 7850 | 17550 |
| Rear, code 1 | 900 | 1350 | 1650 | 2100 | 2500 | 3250 | 5400 | 9250 | 22550 |

Slope of the same curves (volume per bar, i.e. compliance, per segment):

| Segment (bar) | 0–4 | 4–7 | 7–10 | 10–15 | 15–20 | 20–30 | 30–60 | 60–120 | 120–327 |
|---|---|---|---|---|---|---|---|---|---|
| Front, code 0 | 400 | 200 | 150 | 130 | 120 | 115 | 103 | 86 | 86 |
| Front, code 1 | 400 | 183 | 150 | 130 | 110 | 115 | 107 | 98 | 91 |
| Rear, code 0 | 250 | 167 | 117 | 100 | 80 | 65 | 55 | 47 | 47 |
| Rear, code 1 | 225 | 150 | 100 | 90 | 80 | 75 | 72 | 64 | 64 |

Front: within ~5 % below 60 bar; code 1 is 14 % more compliant above 60 bar. Rear: code 1 is slightly stiffer
below 15 bar and 15–36 % more compliant above 20 bar. Code 1 is nowhere meaningfully stiffer than code 0.

**2. BCO prefill tuning (front code only; the rear code is never read here).** 0x6B280 / 0x6B6F4 /
0x6B85E watch the accelerator pedal (0x401142) and request a small pressure on wheels 0 and 1.
Identification as ready-alert brake prefill is medium confidence; not fully decoded.

| Table | Code 0 | Code 1 | Use |
|---|---|---|---|
| 0xD7156 | 0 | 1 | trigger-path select: code 0 allows the pedal-release trigger (needs A.10); code 1 disables it and uses the path gated by A.9 and 0x400EBA bit 6 |
| 0x4176C | 400 | 100 | debounce count |
| 0x41770 | 60 | 87 | threshold on \|signal 0x402126\| (signal not identified) |
| 0x41774 | 20 | 76 | second threshold on the same signal |
| 0x417A8 | 1500 | 500 | wait timer (÷10 loops) |
| 0x417B4 | 50 | 150 | % scale on the requested pressure when 0x400EBA bit 6 is set (else 100) |

**3. Indexed by the code but identical for 0 and 1 (no effect in this calibration).** COA gain curves
0x41A38 / 0x41AA4 (28 bytes per code); COA volume offsets 0x41AE4 / 0x41AE6 / 0x41AF2 / 0x41AFC; the
0x94EC4–0x96738 cluster (tables 0xDAA1C–0xDAA40, probably BBV pad wear, not confirmed); the
0xCEB0C–0xCEDEC cluster (tables 0xF672E–0xF6752, per-wheel accumulators at 0x402FF4, purpose not
identified).

**Not coded on the M3: brake torque per pressure.** The torque↔pressure converter 0xD2898 (8 call
sites, including `ayc_wheel_request_submit` and the function next to `abs_apply_ramp`) uses two
constants set at 0xD2888: front 1762, rear 1016. The non-M firmware computes the same two factors
from the pressure-model code and coding byte 17 instead.

**1M (7846411A) is the same as the M3 here.** Same unpack (0xD0418), same two codes per axle (limit
table 0xF6606 = `[1, 1, 3, 2, 2, 1, 49, 3, 4, 32, 4, 2]`), and the p-V curves (front 0x41D82 /
0x41D96, rear 0x41DAA / 0x41DBE) match the M3's number for number. The 1M allows only variant 0.
The non-M cars (DSC90) have six front and five rear codes: see `CODING_BYTES_6862873A.md`.

## Byte 1 bits 0–4: vehicle variant

Model names are user-supplied (not derived from the image). The "tables" column is what the image
shows for that column of the variant-indexed tables (vehicle model 0xD6ECA.., ABS decel curves/floors
0x40412/0x40674/0x40644/0x4065C, yaw-observer arrays 0x415F8../0xD704A).

| Value | Vehicle | Model mass (0xD6F72) | Tables |
|---|---|---|---|
| 0 | M3 sedan | 1787 kg | base set; only variant with the −127 floor below 20 km/h |
| 1 | **Custom ESM** – vehicle model taken from coding bytes 31–40 | 1814 kg (ROM column) | validator requires c31–c34, c37, c38 ≠ 0; observer µ-term 17854 (others 11905) |
| 2 | not identified | 1845 kg | |
| 3 | M3 coupe | 1731 kg | |
| 4 | M3 convertible | 1947 kg | |
| 5 | M3 Competition sedan | 1787 kg | vehicle model = 0; ABS floor <20 km/h −120 instead of −127 |
| 6 | not identified | 1814 kg | every table = 1 (including the 17854 µ-term) |
| 7 | not identified | 1845 kg | every table = 2 |
| 8 | M3 Competition coupe | 1731 kg | every table = 3 |
| 9 | M3 Competition convertible | 1947 kg | every table = 4 |
| 10 | **M3 GTS coupe** | 1691 kg | own vehicle model, ABS curves and observer lag curve |
| 11 | **M3 GTS sedan** | 1674 kg | own vehicle model and observer lag curve (both differ from 10); ABS curves and floors = 10 |

- **10/11 (GTS) are the only codings with their own calibration.** They get a separate vehicle model
  (lightest mass, CG furthest forward: l_f 1352/1362 vs 1403–1501), the permissive ABS decel set
  (front speed-term and g-term curves that allow deeper wheel decel above 150 km/h, floor below
  60 km/h −140 instead of −132) and their own yaw-observer lag curves (0xD704A/0xD70AA; 10 and 11
  differ from each other as well as from 0–9).
- **Competition (5/8/9) is a relabel in these tables.** The columns repeat 0/3/4 byte for byte; the
  one difference is the sedan's <20 km/h ABS floor. Any Competition-specific behaviour would have
  to come from code that compares the variant value, which has not been looked for.
- **1 (Custom ESM)** is the only value the validator ties to other bytes (c31–c40), but in this image
  the coding words are **never used as model parameters**: the loaders 0x5DE44 / 0x5E424 read only the
  ROM column (1814 kg, l_f 1418, Jz 3203), and the override-row path at 0x5E03E is skipped for
  variant 1. The only readers of w11–w19 are the write validator (`coding_unpack_words`, check at
  0xD01AA) and `sub_0CF32C` (run at boot from 0xCF396 after the block-7 load), which sets fault
  0xC0002 if variant = 1 and w11/w12/w15/w18 are zero (the words of c31–c34, c37, c38), or if
  f+5 = 1 and any of w22–w28 is zero. For ABS, variant 1 = variants 2–9.
- **The vehicle model is DSC-only** (yaw observer / AYC / CSI yaw reference / yaw-steer plausibility
  0xBB814); see `ABS_ALGORITHM_M3_7846816A.md` §3. ABS sees the variant only through the decel
  curves (0–9 vs 10/11), the <20 km/h floor (0: −127, 1–11: −120), the <60 km/h floor (10/11: −140)
  and a variant-10-only branch of the classifier's pre-control hold (0x4D946). TCS also reads table
  0xF6496 (30000, except 2000 for 5/8/10/11) at 0xCB952; that role is not decoded.
- The masses fit the names: convertible heaviest, coupe lighter than sedan, GTS lightest.

## Limits of this pass

- No reader was found for the custom-parameter words (w11–w19, w22–w28) beyond the non-zero
  checks (validator and 0xCF32C). No literal pointer to 0x4031CC–0x4031DC exists and the model
  loaders index ROM only, so they look unused by this firmware (a computed-address read is not
  fully excluded).
- f+6 is derived from coding bits by the validator (see above) and stored in the image; three
  functions that would change it at run time (0xCF67C / 0xCF6D2 / 0xCF750) are unreferenced. f+7
  is not coding: `dsc_mode_select` writes the DSC mode 0/1/2 there every cycle.
- The six signed trims are located by their consumer code only; what they physically trim is
  not identified.
- The non-M firmware differs: the captured 335 coding has non-zero bytes 16–31, which this M3
  image would reject. What is known of the non-M layout is in `CODING_BYTES_6862873A.md`.

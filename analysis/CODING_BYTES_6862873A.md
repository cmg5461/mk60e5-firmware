# MK60E5 non-M (DSC90, 6862873A) — pressure model and friction radius coding

Scope: only the coding fields traced so far (byte 2 pressure model, byte 17 friction radius) and
what they feed. The rest of the 48-byte record has not been mapped for this image. Byte numbering
`c[n]` is the same as in `CODING_BYTES_7846816A.md`.

Source: `fw/6862873A.0pa`, disassembled to `analysis/6862873A_main.lst`:

    python tools/parse_0pa.py fw/6862873A.0pa --out n.bin      # image starts at file offset 0x3AC
    # pad the front with 0x3AC bytes so file offset = CPU + 0x8000, then:
    python tools/mcore_dis.py n_file.bin --base=-0x8000 --start 0x40000 --end 0xF6A00

The application ends near CPU 0xE191F; the listing past that is not code.

## Where the fields live

- Active coding image is at **0x40323C** (M3: 0x4031AA); the word array starts at 0x40324A (f+14).
- 0xD1C74 passes one record pointer to the checksum (0xD17F8, XOR over 48 bytes), the field unpack
  0xD1818 and the word unpack 0xD19D8. The path from the `2E 30 00` buffer / EEPROM into 0xD1C74 was
  not traced; it is assumed to match the M3.
- 0xD1818: `f+1 = c[1]&0x1F`, `f+2 = c[2]>>6`, **`f+3 = (c[2]>>3)&7` (front)**, **`f+4 = c[2]&7`
  (rear)** — identical to the M3.
- 0xD14B8 checks f+0..f+13 against the limit table at 0xE1710:
  `[12, 22, 3, 6, 5, 5, 49, 2, 4, 32, 4, 2, 8, 8]`. So **front 0–5, rear 0–4**, and 22 variants.

## Byte 2: pressure model

Which brake package each code is for, from BMW's NCS assignment rules (model examples are a reading
of the engine codes in those rules, not from the firmware). "Piston" is the firmware's own table.

| Front | BMW uses it for | Piston (0xE17C8) |
|---|---|---|
| 0 | 1 Series base (116i/118i/118d) without sport brakes; also the fallback for anything not listed | 54 mm |
| 1 | 1 Series upper (120i/120d/123d/125i/128i/130i); 3 Series four-cylinder (316i/318i/320i/318d) | 54 mm |
| 2 | 3 Series six-cylinder (325i/330i/325d, 330d from 2009) | 57 mm |
| 3 | 335i/335is/335d/330d; police and high-payload versions of the code 2 cars | 57 mm |
| 4 | 3 Series mid (320d, 323i, later 325i, US 328i, high-payload 320i) | 57 mm |
| 5 | Sport brakes: 135i as standard, any 1/3 Series with `NR_SPORTBREMSEN` (fixed caliper) | 57 (table entry) |

| Rear | BMW uses it for | Piston (0xE17D8) |
|---|---|---|
| 0 | 1 Series base hatch without sport brakes; fallback for anything not listed | 40 mm |
| 1 | 118d/120d hatch; E82/E88 below 135i without sport brakes | 40 mm |
| 2 | most four-cylinder 3 Series, 325i, 328i; 123d/130i; four-cylinder 1 Series with sport brakes | 42 mm |
| 3 | 330i/330d/335i/335d; police and high-payload cars | 44 mm |
| 4 | Sport brakes: 135i as standard, 123d/130i and six-cylinder 3 Series with sport brakes (fixed caliper) | 44 (table entry) |

The axles are assigned independently. The captured 335 coding (`wheelspeed/coding_write_dump.txt`,
`c[2] = 0x5B`) is front 3 / rear 3, which matches the rules for an N54 E9x.

### What the code selects

**Pressure↔volume curve** — same COA model as the M3; axis 0x41892 (0.01 bar), front
`0x418A6 + 20·code`, rear `0x4191E + 20·code`. Volume unit not identified.

| Pressure (bar) | 4 | 7 | 10 | 15 | 20 | 30 | 60 | 120 | 327 |
|---|---|---|---|---|---|---|---|---|---|
| Front 0 | 1450 | 1950 | 2350 | 2900 | 3350 | 4150 | 6100 | 9450 | 21000 |
| Front 1 | 1450 | 2050 | 2450 | 3050 | 3500 | 4300 | 6350 | 9750 | 21650 |
| Front 2 | 1450 | 2050 | 2500 | 3150 | 3750 | 4850 | 7750 | 12300 | 28000 |
| Front 3 | 1400 | 2050 | 2600 | 3350 | 4000 | 5150 | 8100 | 12900 | 28450 |
| Front 4 | 1700 | 2400 | 2950 | 3750 | 4400 | 5550 | 8500 | 13300 | 29650 |
| Front 5 | 1200 | 1800 | 2250 | 2900 | 3500 | 4600 | 7350 | 12050 | 28350 |
| Rear 0 | 850 | 1150 | 1350 | 1700 | 1950 | 2400 | 3500 | 5400 | 11850 |
| Rear 1 | 200 | 650 | 850 | 1250 | 1700 | 2300 | 3800 | 6550 | 15000 |
| Rear 2 | 950 | 1300 | 1550 | 2000 | 2250 | 2750 | 3950 | 5900 | 12600 |
| Rear 3 | 950 | 1400 | 1750 | 2250 | 2600 | 3250 | 4800 | 7450 | 16550 |
| Rear 4 | 800 | 1150 | 1450 | 1950 | 2350 | 3100 | 4750 | 7400 | 16600 |

None of these rows equals either M3 curve.

**Brake torque per pressure** — two uses:

- 0xD4090 builds the per-axle factors used by the torque↔pressure converters 0xD40E4 / 0xD4174
  (26 call sites in about 18 functions, 0x44610–0xD429A; the same converter as the M3's 0xD2898):
  `front = R_f · d_f² · 85 / 636620 · 44 + 1` → 0x403308, `rear = R_r · d_r² · 85 / 636620 · 39 + 1`
  → 0x40330A. `d` is the piston diameter above, `R` the friction radius from byte 17, 85 is the
  word at 0x4269C, 636620 = 2,000,000/π. On the M3 these two factors are constants (1762 / 1016).
- 0x6B6B6 multiplies the radius by a per-code coefficient and divides by 1000:
  front 0xD90F0 = `[2015, 2015, 2246, 2246, 2015, 2015]`, rear 0xD90FC = `[980, 980, 1081, 1186, 980]`.
  The coefficients follow piston area for codes 0–3. Front 4, front 5 and rear 4 use the
  small-caliper value although the diameter table says 57 / 44 mm; reason not known. The consumer
  of this result is not identified.

**Other COA tables that differ per code**

- Gain curves, 28 bytes per code: front 0x41664 (three distinct sets: codes 0/4/5, 1, 2/3), rear
  0x41740 (rear 1 differs from the rest).
- Volume offsets, 6 bytes per code: front 0x417D6 (−2250, −2500, then −1500 for 2–5), rear 0x417FA
  (rear 4 unique: −1000 / −2000); also 0x41816 / 0x417D4.

**Read the code, values differ, not decoded**

- 0x9CA20–0x9E168, tables around 0xDD074–0xDD0F8 (counterpart of the M3 0x94EC4–0x96738 cluster,
  probably pad wear). 0xDD0A8 front = `[4492, 4570, 5352, 5352, 5352, 4297]`, 0xDD0B4 rear =
  `[4336, 4375, 4375, 4375, 4492]`.
- 0xD03A8–0xD0688, tables 0xE157C–0xE15E0 (counterpart of the M3 0xCEB0C–0xCEDEC cluster).
- 0xD4CA2–0xD5534, tables 0x42588–0x42678; not matched against the M3 or 1M. Row widths of these
  tables are not confirmed.

**Sport-brake codes (front 5 / rear 4).** There is no fixed-caliper switch; they only select
different rows. Front 5 has the smallest low-pressure fluid take-up of any front code with
large-caliper displacement above ~60 bar. The piston-diameter entries and coefficients are not
distinct from the sliding-caliper codes (see above).

**No BCO reader.** The front-code BCO prefill tuning found on the M3 has no equivalent reader here.

## Byte 17: effective friction radius

NCS name: "yaw moment compensation effective friction radius", front axle = low nibble, rear axle =
high nibble. 0xD19D8 stores `c[17] & 0x0F` to 0x40324A+18 and `c[17] >> 4` to 0x40324A+20. Their
only reader, 0x6D0D2, treats each nibble as a signed 4-bit step `n` and writes
`139 + 3·n` to 0x400B80 (front) / 0x400B82 (rear). The 139 and 3 are immediates.

| Nibble | 8 | 9 | A | B | C | D | E | F | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mm | 115 | 118 | 121 | 124 | 127 | 130 | 133 | 136 | 139 | 142 | 145 | 148 | 151 | 154 | 157 | 160 |

- The unit (mm) is inferred from the formula and the NCS name, not stated in the code.
- Despite the NCS name it is not limited to yaw moment compensation: it feeds the general
  torque↔pressure factors above, so it scales every such conversion on that axle.
- The captured 335 has `c[17] = 0x23`: front 148 mm, rear 145 mm.
- Whether the validator restricts the nibble values was not checked.
- On the M3 the same bytes (w9/w10) must be 0 and have no reader.

# Geometry / mass vs EEPROM coding (1M 7846411A, M3 7846816A)

Agent-derived (Sonnet), **headline verified by main session**: wheelbase recovered as l_f+l_r in Q10
metres — 1M 1331+1393=2724 → **2660.2 mm (exact)**; M3 all 12 variants sum 2826/2827 → **2760/2761 mm**
(exact). Machine files: `analysis/agents/geom/vehicle_model_tables.txt`, `uses4031aa.py`, `sites*.py`,
`m3_main.lst`. CPU addresses; file = CPU + 0x8000.

## Verdict: PARTLY YES — coding selects geometry/mass, in ROM (not AYC/BCO/COA/VMO)
The 5-bit coding field **`0x4031AA+1`** (record byte 1 low bits; variant 0..11; read via `0x8E066(24,1)`)
indexes a **12-variant vehicle-model table** in constant ROM. In the **M3** it is at ~0xD6E16..0xD70FF;
the **1M** carries a single fixed scalar set at 0xD7458..0xD747E (no variant index). Layout: each parameter
is a row of **12 contiguous s16 variant values**, rows spaced 24 bytes.

## Coding byte array 0x4031AA (RAM) [verified]
Filled by unpacker 0xD0418. Fields: +0 (LVC), **+1 (vehicle variant 0..11)**, +2 (DDS/LVC), **+3 (front
brake code, 3b)**, **+4 (rear brake code, 3b)**, +5, +7 (DSC-mode flag from 0x4030A4/A2 + coding bit),
+8/+9/+10/+11. Field +1 is read at ~13 sites in the M3 (ABS curves 0x47C92/0x47CAA; vehicle-model
0x5DE48/0x5E42A/0x5EC70/0x67B64/0x67F30/0xCB952; special-cases incl. 0x4D946 ==10), vs only 3 in the 1M.

## Vehicle-model table (M3, indexed by +1) [values verified; roles agent med]
Row = 12 s16 (variant 0..11), stride 2; rows 24 B apart. Loaders 0x5DE44 / 0x5E424 → RAM
0x400AA4..0x400ABA, 0x400AE8..0x400AEE.

| Row | Role [conf] | Variants 0..4 (=5..9), 10, 11 — sedan, Custom ESM, ?, coupe, convertible (5..9 = Competition), GTS coupe, GTS sedan |
|---|---|---|
| 0xD6F42 | l_f (CG→front axle), 1/1024 m [med] | 1413,1418,1439,1403,1501, 1352,1362 |
| 0xD6F5A | l_r (CG→rear axle), 1/1024 m [med] | 1413,1408,1388,1423,1325, 1475,1464 |
| 0xD6F72 | **mass, kg** [med-low] | 1787,1814,1845,1731,1947, 1691,1674 |
| 0xD6F8A | yaw inertia Jz, kg·m² [low-med] | 2999,3203,2645,3006,3283, 2671,3082 |
| 0xD6ECA/0xD6EE2 | tyre/axle stiffness-like [low] | 7527.../10596... |

1M fixed scalars (0xD7458+): index14/15 = l_f/l_r = **1331/1393**, 16 = mass 1739, 17 = Jz 3039.

- **Wheelbase [verified]:** l_f+l_r → 1M 2660 mm, M3 2760/2761 mm (all variants). Not stored as a scalar;
  does not vary between M3 variants (only the split does). CG front share: 1M 51.1%; M3 v0–4 50.0–46.9%;
  v10/11 52.2/51.8% (l_f/l_r assignment is med — reversed reading flips the split).
- **Mass/inertia [med-low]:** J/m ≈ squared radius of gyration (~1.3 m) ≈ l_f·l_r, supporting the mass/Jz
  reading. 1M 1739 ≈ +4% over 1670 kg curb; M3 1691/1674 ≈ +1–2% over 1655 kg (but rows 10/11 are the GTS
  codings, so the like-for-like rows are sedan 1787 / coupe 1731 / convertible 1947). Unit not proven — needs a
  consumer trace or a known-weight coding dump.

## Brake coding (+3 front / +4 rear) [indexing verified; meaning agent]
Separate from geometry. Reader 0x81508 pairs +3 for wheels 0/1 and +4 for 2/3. Selects:
- **COA pressure↔volume curves** (stride 20 B, 10-pt, x-axis COA+0x1D6): front sets +0x1EA/+0x1FE,
  rear +0x212/+0x226 (2 variants/axle; differ: front top-y 31200 vs 32750, rear 17550 vs 22550).
- COA offset tables +0x16E/+0x17A ({0,−2500,…} / {0,−1000,…}); COA gain curves +0xC0/+0xDC, +0x12C/+0x148
  (byte-identical within axle here); BCO 2-entry threshold sets +0xC/+0x10/+0x14/+0x18; CSW+0x18.
- **Rotor diameter / piston area are NOT stored as scalars** — folded into the p-V and gain curves.

## The brief's "geometry-shaped" constants = curve data, not geometry [verified]
COA 2600–2750 = p-V curve points; BCO 322/1496 = curve y; BCO 300/358 = pressure compare thresholds
(0x400E3E); AYC 349/698 = angles (0.349 rad = 20°, ±20/±40 pair); VMO = wheel-speed timing/plausibility
monitor (no vehicle model). Identical 1M↔M3 because both images ship every variant.

## Needs hardware
- The car's actual coding values (+1, +3, +4) are not in flash. With +1, the 0xD6xxx row gives that car's
  mass/CG. Variant→model mapping now known (user-supplied; `analysis/CODING_BYTES_7846816A.md`): all rows are
  E9x M3 — 0 sedan, 1 Custom ESM, 3 coupe, 4 convertible, 5/8/9 Competition, 10/11 GTS coupe/sedan.
- Confirming 0xD6F72 as mass needs a known-weight coding dump or a trace of 0x400AA4.. consumers.

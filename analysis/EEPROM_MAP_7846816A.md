# MK60E5 EEPROM map (M3 7846816A; block table identical in 1M 7846411A)

Static analysis only — derived from the disassembly, **not checked against a real EEPROM dump**.
Addresses, lengths and RAM mirrors are byte-verified from the tables/code cited. Field *meanings*
are graded per row: **high** = behaviour read from code, **med** = inferred from the owning
module / KWP convention, **low** = guess, **?** = no consumer found.

## Device and addressing

- External SPI EEPROM on QSPI 0xDB0000 CS2. Write = opcode `02` + 16-bit address + data
  (`nvm_write` 0x6E8DC / 0x6E946), so a 25xx160-class part. Logical size 2 KiB (0x000–0x7FF).
- **Every byte is stored bit-inverted** (`not` at 0x6E910 / 0x6E96C / 0x6E976, undone on read).
  A raw chip read must be XORed with 0xFF to get the values below; a virgin (0xFF) cell reads as 0x00.
- Logical address = `block_table[blk].offset + sub_offset`. Block table = 63 × `{u16 offset, u16 len}`
  at **0xD7424** (1M: 0xD77B4, byte-identical). 27 blocks are populated and tile 0x000–0x7FF with
  no gaps.
- Job descriptor (12 B, e.g. 0xF31B4…): `u32 ram_ptr, u16 id, u16 len, u16 sub_offset, u8 op, u8 0`.
  `id = (blk << 4) | sub-id`, `op` 1 = read, 2 = write. Queue = 5 slots at 0x409364
  (`nvm_queue_job` 0x6E16C, worker 0x6DF1C). Boot-time sync read = `0x6E41E(blk, off, dst, len)`.
- Raw access from diag: `23 00 <addrHi> <addrLo> 03 <len≤4>` reads, `3D` writes, any logical
  address < 0x800.

## Answer to "are there others besides the 48 coding bytes?"

Yes. The 48 coding bytes are 2.3 % of the EEPROM (0x400–0x42F). The coding is in fact stored
**twice**: the raw 48 bytes the tester wrote (block 10), and an unpacked/validated image the
application actually runs from (block 7, 0x44B–0x4AF). The rest is identification data, fault
memory, learned/adaptation values and DDS (tyre-pressure) data.

## Block overview

| Logical | Len | Blk | Contents | RAM mirror | Owner / evidence | Conf |
|---|---|---|---|---|---|---|
| 0x000–0x01F | 32 | 0 | 30-byte record read by `1A 8F`, written by `3B 8F` (+2 spare) | 0x40331F (wr) | desc 0xF31B4 / 0xF3214 | high addr, ? meaning |
| 0x020–0x067 | 72 | 3 | Internal fault-manager store (FSF slot table 0xF57F8, id 0x31); first 2 B → 0x4028B6 at boot | 0x4028B6.. | `nvm_fault_slot_commit` 0xB433A, 0xB3F90 | med |
| 0x068–0x0EA | 131 | 5 | **KWP DTC memory** (see below) | 0x40950C, 0x4093E8 | 0xAF0DC (save), 0xAFEE8 (load), `kwp_17` 0xB301A | med-high |
| 0x0EB–0x0F9 | 15 | 6 | 0x0EB–0x0F1 (7 B): DME-interface state; 0x0F5–0x0F8 (4 B): sensor-cluster module value | 0x4047F6; 0x402F3E | `can_dme_iface_update` 0x7EB42; 0xC6656 / 0xC6FA8 | low |
| 0x0FA–0x121 | 40 | 23 | no consumer found | – | – | ? |
| 0x122–0x12B | 10 | 30 | no consumer found | – | – | ? |
| 0x12C–0x14B | 32 | 9 | DDS/RPA parameters: 10 fields from +0 (field table 0xDA994), 7 fields from +24 (0xDA9E4) | via field tables | 0x94C76 (load), 0x95230 / 0x95294 (save) | med |
| 0x14C–0x15F | 20 | 4 | +1: NVM-manager status (0x6EBDC); +2 (1 B): wheel-speed/ASIC module byte | 0x4033DB | 0x71BEC, desc 0xD7418 | low |
| 0x160–0x181 | 34 | 8 | 34-byte learned record (16 + 16 + 2) | 0x4020AE | 0x8F1F8 (load), 0x92796 (save) | low |
| 0x182–0x18F | 14 | 2 | 10-byte record (TCS-area RAM) | 0x403029 | 0xCE99A (load), 0xCEA0E (save) | low |
| 0x190–0x1A8 | 25 | 32 | 14-byte record (next to vref 0x408D84) | 0x408D8E | 0xD2BD8 (load), 0xD3238 (save) | low |
| 0x1A9–0x1BA | 18 | 11 | 0x1B7–0x1B9: **Prüfstempel** (test stamp), DID 0x1000 r/w; rest unreferenced | – | desc 0xF31E4 / 0xF325C | med |
| 0x1BB–0x1C8 | 14 | 12 | 4-byte value | 0x400D3E | 0x67B24 (load), 0x67E42 (save) | low |
| 0x1C9–0x268 | 160 | 42 | no consumer found | – | – | ? |
| 0x269–0x26E | 6 | 22 | 6-byte value | 0x403255 | 0xD26AC (load), 0xD24F6 (save) | low |
| 0x26F–0x280 | 18 | 47 | 0x26F–0x279 (11 B): DID 0x1603 | – | desc 0xF31F0 | high addr, ? meaning |
| 0x281–0x2D4 | 84 | 16 | **Valve self-calibration** (SID 31 routines 0x28 / 0x29), see "Block 16" below; 1 B at 0x2CD | 0x40493D, 0x401D70/0x401D90, 0x401E70, 0x401F52 | 0x86FA0, 0x8B16C (load); 0x8ACD0, 0x8B5FA (save) | high (layout) |
| 0x2D5–0x2E4 | 16 | 28 | Fault-manager slot (FSF id 0x1C1) | – | 0xB433A | med |
| 0x2E5–0x2E8 | 4 | 29 | no consumer found | – | – | ? |
| 0x2E9–0x304 | 28 | 26 | no consumer found (an unreferenced descriptor-shaped record at 0xD7DE8 points 28 B at 0x4008B0) | – | – | ? |
| 0x305–0x321 | 29 | 62 | no consumer found | – | – | ? |
| 0x322–0x3FF | 222 | 24 | **Identification / manufacturing data** (see below) | – | kwp 1A/22/3B/31 | high addr |
| 0x400–0x44A | 75 | 10 | **Raw coding** (see below) | not resident; read → 0x40943E (diag response buffer), write ← 0x403320 | kwp 22/2E DID 0x3000 | high |
| 0x44B–0x4E0 | 150 | 7 | **Active (unpacked) coding image** (see below) | 0x4030DC, 0x4031AA, 0x4031B6 | 0xCFB14 (load), 0xCFA40 (save) | high |
| 0x4E1–0x4EC | 12 | 27 | Fault-manager slot (FSF id 0x1B1) | – | 0xB433A | med |
| 0x4ED–0x50F | 35 | 61 | no consumer found | – | – | ? |
| 0x510–0x7FF | 752 | 14 | DDS/RPA learned data, 732 B used (0x510–0x7EB) | 0x4059A8 | 0x9A8AC (load), 0x9A904 (save), desc 0xDAABC/C8 | med |

"No consumer found" = no static descriptor, no `0x6E41E` call and no block id located for it. These
are still reachable through `23`/`3D` raw access; they may be spare, or used through a path this
pass did not resolve (ids built at run time).

## Block 10 — raw coding, 0x400–0x44A

| Logical | Len | Contents | Access | Conf |
|---|---|---|---|---|
| 0x400–0x42F | 48 | The coding bytes exactly as sent/returned on the wire. No RAM copy is kept: `22 30 00` reads straight into the diag response buffer 0x40943E (desc 0xF31FC, op 1); `2E 30 00` writes from `coding_write_buf` 0x403320 (desc 0xF3268, op 2) | `22 30 00` (desc 0xF31FC), `2E 30 00` (0xF3268) | high |
| 0x430 | 1 | Single byte, loaded at boot to 0x402F4B by the 0xC6xxx module; write desc 0xF3280. Probably DID 0x3001 | 0xC6FBE | med |
| 0x431–0x432 | 2 | DID 0x3FFF, r/w (BMW convention: coding test stamp / Codierprüfstempel) | desc 0xF3208 / 0xF3274 | high addr, med meaning |
| 0x433 | 1 | Diag-module flag, loaded to 0x40954D at boot, saved by 0xAF7F0 | desc 0xF2ED0 | low |
| 0x434–0x44A | 23 | unreferenced | – | ? |

Correction to earlier notes: descriptor word `00A3` is `(blk 10 << 4) | 3`, not "EEPROM offset
0xA3", and `0030` is the length (48), not a block id. The coding lives at **0x400**.

## Block 7 — active coding image, 0x44B–0x4E0

Written by `0xCFA40` after a coding write is accepted; loaded at boot by `0xCFB14`. This is what
the control code reads (variant, brake coding, DSC mode bit…), not block 10.

**Check byte = `XOR(image) + 1`** (`0xCF9C8`, the `+1` is at 0xCFA04 — same formula as the wire
checksum). Consequences, verified:
- An **all-zero** image (as the `.0pa` ships it, check byte 0x44B = `00`) computes to `1 ≠ 0` → the
  boot loader `0xCFB14` logs **fault 0xC0040**, zeroes the RAM image (`0xCF3EE`) and sets the
  coding-invalid flag in 0x4030E0 (`0xCF3C8`). So a blank/freshly-flashed module is *invalid*, not
  "valid zero-coding" — it is flagged as needing coding.
- **No boot-time rebuild from raw.** `0xCFB14` only loads block 7 and checks it; it never reads
  block 10 or runs the unpacker. The raw→active rebuild (block 10 → block 7) is driven **only** by a
  tester coding write: the validator/unpacker `0xCF432 → 0xD02E6 → save 0xCFA10/0xCFA40` has a single
  caller, `kwp_2E` (0xB2A3C). So a reflash (which zeroes block 7 — the genuine WinKFP log transfers
  the DF/EEPROM segments) forces the standard post-programming "codieren" step; it does not silently
  regenerate on first boot. Block 10 (raw) is absent from the `.0pa`, so a reflash leaves it as-is.

| Logical | Len | Contents | RAM | Conf |
|---|---|---|---|---|
| 0x44B | 1 | Check byte = XOR(image)+1 (`0xCF9C8`); mismatch → fault 0xC0040, image zeroed, invalid flag 0x4030E0 | 0x4030DC | high |
| 0x44C–0x457 | 12 | Unpacked coding fields | 0x4031AA..B5 | high |
| 0x458–0x4AF | 88 | 44 × u16 packed coding words (includes `coding_block_packed` 0x4031F4/F6 = words 31/32) | 0x4031B6..0x40320D | high |
| 0x4B0–0x4E0 | 49 | unreferenced | – | ? |

The 48 coding bytes are decoded field by field in `analysis/CODING_BYTES_7846816A.md`.

## Block 5 — KWP DTC memory, 0x068–0x0EA

Two parallel 31-byte stores of five parts each, plus 6-byte per-entry detail records served by
service 0x17 (ReadStatusOfDTC, handler 0xB301A). Which store is "primary" vs "shadow/info" is by
position, not proven.

| Logical | Len | Contents | RAM |
|---|---|---|---|
| 0x068 / 0x06D / 0x077 / 0x07C / 0x081 | 5 / 10 / 5 / 5 / 6 | store A | 0x40950C.. |
| 0x087 / 0x08C / 0x096 / 0x09B / 0x0A0 | 5 / 10 / 5 / 5 / 6 | store B | 0x4093E8.. |
| 0x0A6–0x0C3 | 5 × 6 | detail records, store A (`17` reads desc 0xF3394 + 12·n) | via 0x40943E |
| 0x0C4–0x0E1 | 5 × 6 | detail records, store B (desc 0xF340C + 12·n) | via 0x40943E |
| 0x0E2–0x0E7 | 6 | one more 6-byte record | via 0x40943E |
| 0x0E8–0x0EA | 3 | unreferenced | – |

## Block 24 — identification data, 0x322–0x3FF

Views overlap (the `1A 80` table contains several of the single-field ids). ISO 14230-3 names are
given for the `1A` ids; BMW may use them differently.

| Logical | Len | Access | Contents | Conf |
|---|---|---|---|---|
| 0x322 | 1 | – | unreferenced | ? |
| 0x323–0x332 | 16 | `31` routine r/w (desc 0xF3370/7C); loaded at boot to 0x40956C | 16-byte routine/auth data | low |
| 0x333–0x335 | 3 | written on `10` session change (0xF3388); 0x334–335 also 0xF3358; 0x335 read by `31` (0xF334C) | programming/session status bytes | low |
| 0x336–0x347 | 18 | `1A 86` | VM ident table | med |
| 0x348–0x37D | 54 | `22 25 00` | – | ? meaning |
| 0x37E–0x38D | 16 | – | unreferenced | ? |
| 0x38E–0x3A2 | 21 | `22 25 02` | – | ? meaning |
| 0x3A4–0x3AA | 7 | `1A 90`, `3B 90` | **VIN** (short, 7 chars) | med-high |
| 0x3AB–0x3AE | 4 | `1A 99` | programming date | med |
| 0x3AF–0x3B4 | 6 | – | unreferenced | ? |
| 0x3B5–0x3BD | 9 | `1A 89` | 9-char ASCII id (e.g. "61AB000B4") | high |
| 0x3BA–0x3BD | 4 | boot → 0x409564 (0xB00A2) | **last 4 chars of the above = auth `w564`** | high |
| 0x3BE–0x3C0 | 3 | `22 25 01` | – | ? meaning |
| 0x3C1–0x3C2 | 2 | `22 25 06` | – | ? meaning |
| 0x3C3–0x3D4 | 18 | `1A 91`; writable as 2 × 6 B (0x3C3, 0x3C9) | VM hardware number | med |
| 0x3CF–0x3EB | 29 | `1A 80` | ECU identification table | high addr |
| 0x3D5 / 0x3D6 | 1 / 1 | `1A 9A` / `1A 9B` | inside the 1A 80 table | med |
| 0x3D7–0x3D8 | 2 | `1A 9C` | 〃 | med |
| 0x3D9–0x3DA | 2 | `1A 97` | 〃 | med |
| 0x3DB–0x3DE | 4 | `1A 9D` | 〃 | med |
| 0x3DF | 1 | `1A 9E` | 〃 | med |
| 0x3E0–0x3EB | 12 | `1A 9F` | 〃 | med |
| 0x3EC–0x3FD | 18 | `1A 87` | VM spare-part number | med |
| 0x3FE | 1 | – | unreferenced | ? |
| 0x3FF | 1 | write desc 0xF3364 (from 0x403324) | – | ? |

Correction: FACTS says `0x409564` comes from "logical NVM 0x0322". The loader call is
`0x6E41E(blk 24, off 0x98, 0x409564, 4)` → **0x3BA–0x3BD**, i.e. the tail of the `1A 89` string, which
agrees with the later finding that `w564` = last 4 bytes of the `1A 89` response.

## Other DIDs seen that do *not* touch the EEPROM

`22 16 00/01/02`, `22 25 03` (12 B from ROM 0xF56D8), `22 25 04`, `1A 94` (30 B from ROM 0xF68FC).

## How to verify on a bench unit

Dump 0x000–0x7FF with `23 00 hh ll 03 04` in 4-byte steps and check: 0x400–0x42F equals the
`22 30 00` payload; 0x3B5–0x3BD equals the `1A 89` string; 0x3A4–0x3AA equals `1A 90`. That would
promote the layout from static to hardware-verified and show whether the "no consumer" blocks are
blank.

## .0pa seeds these blocks (EEPROM default image)

The flash file `fw/7846816A.0pa` ships a factory **default image** for part of this EEPROM, packaged
as a pseudo-segment "bank" at **0xDF0000**. These are *not* CPU addresses — the logical EEPROM offset
= `.0pa address − 0xDF8000`. Written DF segments and their blocks (byte-verified):

| `.0pa` seg | logical | block |
|---|---|---|
| 0xDF812C /0x1F | 0x12C | 9 (DDS/RPA params) |
| 0xDF8160 /0x22 | 0x160 | 8 (learned record, len-exact) |
| 0xDF8281 /0x4D | 0x281 | 16 (hydraulic/pressure learned) |
| 0xDF83C0 /0x01 | 0x3C0 | 24 (ident) |
| 0xDF83C3 /0x12 | 0x3C3 | 24 (`1A 91` hw/part number ×3) |
| 0xDF83D6 /0x03 | 0x3D6 | 24 (`1A 9B` coding idx; +diag idx) |
| 0xDF83E0 /0x06 | 0x3E0 | 24 (`1A 9F`; msg-catalog + func SW ver) |
| 0xDF844B /0x65 | 0x44B | 7 (active coding image, used len-exact) |

Bytes are stored *logical* (un-inverted) in the `.0pa`; the SPI chip holds them bit-inverted. This is a
partial **known-good default image** and an independent cross-check on the block table: two block
lengths match exactly (blk 8 = 34, blk 7 used = 101) and five block *starts* line up, corroborating the
static layout for blocks 7/8/9/16/24.

What the default image tells us about each block's factory state:

- **Only block 24 (ident) ships with real content.** Blocks 7, 8, 9 and 16 ship **all-zero** — the
  `.0pa` zero-initialises the learned/adaptation stores (8 learned, 9 DDS/RPA, 16 hydraulic/pressure)
  and the active-coding image (7). So a reflash **wipes adaptations and the active coding image**; the
  ECU re-learns and must be re-coded afterward. [inference from the zero fill]
- **A factory-flashed unit is uncoded.** Block 10 (raw coding, 0x400–0x44A) is **entirely absent** from
  the `.0pa`, and block 7's check byte (0x44B) ships `00` → mismatches `0xCF9C8()` → fault 0xC0040 /
  image zeroed. That is the blank-side confirmation of the block-7 check-byte logic: no coding until the
  tester writes it.
- **Per-unit identity is blank in the `.0pa`** (0 bytes present): VIN (0x3A4, `1A 90`), programming date
  (0x3AB, `1A 99`), the `1A 89` ASCII id (0x3B5) **and its `w564` auth tail (0x3BA–0x3BD)**, the VM ident
  table (0x336, `1A 86`) and VM spare-part number (0x3EC, `1A 87`). These are line-programmed per unit.
  **Security note:** `w564` is therefore *not* a firmware constant — it is per-unit production data.
- **Firmware-fixed ident defaults** (the only non-zero factory bytes, constant across all units of this
  part number): part number ×3 (0x3C3), coding index (0x3D6 = 8), diagnose index (0x3D7 = 1459),
  message-catalog SW (0x3E0 = 0.36.143), function SW (0x3E3 = 11.9.0), and the 0x3C0 marker byte (`02`).
- **"No consumer found" blocks ship blank** — none of 23/30/42/29/26/62/61 appear in the `.0pa`,
  consistent with their being spare/unused.

Caveat: the dump used here (`flash/bin/7846816A_00DF0000.bin`) is reconstructed from this same `.0pa`,
so it confirms the shipped *defaults*, not a real post-production bench EEPROM.


## Block 16: valve self-calibration (traced 2026-10-16)

Written by the unit itself when the tester runs SID `31` routine `28` (`ABGLEICH_ANALOG_EV`, inlet valves)
or `29` (`ABGLEICH_ANALOG_MCI_V`, the USV / master-cylinder isolation valves). Both start through
`kwp_31_start_routine` case 0xB2ECE -> `valve_cal_start(type)` 0x8AC10 (type 1 = inlet, 2 = MCI; state byte
0x404970). Each record is protected by `cal_checksum` 0x86724 (XOR of (byte + 1) over the data), stored
as {chk, ~chk} and checked by `cal_checksum_ok` 0x8673C.

| Block offset | Logical | Len | Contents |
|---|---|---|---|
| +0..+1 | 0x281–0x282 | 2 | MCI record checksum {chk, ~chk} |
| +2..+9 | 0x283–0x28A | 8 | MCI characteristic, circuit 0: pressure points, u8 bar |
| +10..+17 | 0x28B–0x292 | 8 | same, circuit 1 |
| +18..+25 | 0x293–0x29A | 8 | MCI characteristic, circuit 0: current points, u8 = mA × 255 / 2000 |
| +26..+33 | 0x29B–0x2A2 | 8 | same, circuit 1 |
| +34..+35 | 0x2A3–0x2A4 | 2 | inlet record checksum {chk, ~chk}; the low 5 bits of chk also index the status table 0xDA162 |
| +36..+75 | 0x2A5–0x2CC | 40 | inlet hold currents, s16[4 wheels][5], mA at Δp 0 / 20 / 50 / 90 / 140 bar (axis ROM 0xDA158) |
| +76 | 0x2CD | 1 | single byte, loaded with the inlet record (role not traced) |

- **MCI load** (`mci_cal_load` 0x86FA0): P = byte × 100 -> 0x401D70[c][8] (0.01 bar), I = byte × 2000/255 +
  COA 0x419BC/0x419BE / 10 -> 0x401D90[c][8] (mA). Both must be strictly increasing. On any failure:
  0x401DB0 b0 is set and the currents are zeroed. That latches **fault 0x088000** (0x8678A), and
  `usv_current_for_dp` returns 0.
- **Inlet load** (`inlet_cal_load` 0x8B16C) -> 0x401E70 {u8 chk, u8 ~chk, s16 f[4][5]}. On failure the
  factors are zeroed, 0x401E9A[4] b0/b2 are set and [5] = 20, which latches **fault 0x150004** (0x8B2D8).
  `inlet_current_for_dp` (0x84D98, the per-wheel counterpart of `usv_current_for_dp`) then returns 0.
- **Inlet use:** `inlet_current_for_dp`(w, dp) interpolates f[w] over the ROM Δp axis and extrapolates above
  140 bar with fixed slopes (~1.86 mA/bar front, ~1.20 rear). `coa_wheel_gain_apply` 0x84E38 scales it by a coded
  gain of 91 % front / 92 % rear and writes the inlet base current (capped at 1800 mA).
- **The .0pa EEPROM default image writes zeros over 0x281–0x2CD** (segment 0xDF8281/0x4D, in M3 and
  335 alike). An all-zero record has chk 0 and ~chk 0, which fails the check. So every reflash should leave
  both calibrations invalid and faults 0x088000 / 0x150004 set until routines 0x28 and 0x29 are run again.
  [inferred from code + .0pa contents; not yet observed on the bench]

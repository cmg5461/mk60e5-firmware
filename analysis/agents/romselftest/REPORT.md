# ROM/RAM self-test signature algorithm (1M 7846411A) — REPRODUCED

Agent-derived (Sonnet), **independently re-verified by the main session**: the MISR reproduces all three
stored expected values byte-exact over the current image. Script: `analysis/agents/romselftest/romsig.py`
(search scripts `try.py`, `try2.py`). CPU addresses; file = CPU + 0x8000.

> Analytical RE of an integrity-check algorithm on the author's own ECU. No modified calibration is produced
> here. The no-flash framing stands; the separate BMY bootloader signature is unaffected by this.

## Algorithm [verified by reproduction]
The hardware signature unit at **0x00D50200 is a 32-bit word-wise MISR, not a CRC**. Seed 0, no final XOR,
no reflection. For each **big-endian 32-bit word `w`** of a range, ascending:
```
s = ((s << 1) ^ (0x00400007 if (s >> 31) else 0)) & 0xFFFFFFFF   # Galois LFSR step, poly 0x00400007
s ^= w
```
Result = `s`. Reproduced (main session, over the unmodified image):
- [0x40000, 0x402F8) → **0xB6EFCB77** ✓
- [0x40300, 0x426BC) (= the 12 calibration blocks) → **0x03B09CDC** ✓
- [0x426C0, 0xF6684) → **0xD719D58D** ✓

## Range table at 0xD7584 [verified]
Three 8-byte entries `{start, end}`, both BE u32, end exclusive; **the expected value is the BE u32 stored
at the end address itself** (0x402F8 = B6EFCB77, 0x426BC = 03B09CDC, 0xF6684 = D719D58D). No skipped gaps.

## Driver [verified from disassembly]
- `sub_06DDE4` (`rom_test_step`) walks each range in chunks (multiples of 22 words), IRQs off; bulk via
  `sub_06CF30` (`ldm r5-r15`, 11 words/iter), final stretch via `sub_06CF54` (`ld.w`) which returns the result.
  If result ≠ word at `*end` → `set_error(0x10004)` (jsri 0xB4064) and set 0x40288C bit7.
- `sub_06DEFE` (`rom_test_init`) sets the first range + sanity-checks the three; `sub_06DDB4` advances;
  table index at 0x40930C+8.
- Register programming: **0xD50200** control (write 1 arm / 0 stop), **0xD50204** result (read, then write 0 to
  clear); init at 0xD56EA writes 0 to both. It is a **passive bus-read MISR** accumulating over the CPU's word
  reads of the range — the data-only model reproduces all three values, so bus-snoop details are moot.

## Feasibility (factual)
- The expected value for any range is now recomputable from the image bytes (`romsig.py`); the stored word at
  **0x426BC** (the calibration range's own signature) can be recomputed to match after a cal edit. So the ROM
  self-test alone no longer detects a cal change once that word is updated.
- **The BMY bootloader signature (probable 512-bit RSA over the application) is a separate check and still
  applies** — and the bootloader (file 0x0–0x47FFF) is not in the .0pa, so whether/how it enforces that remains
  unproven and cannot be analysed from this image.

## Open / needs-hw
- Not confirmed on hardware; instruction-fetch/other bus traffic exclusion not modelled (data-word model
  matches with no extra terms, so it appears moot).
- BMY signature enforcement needs the bootloader / secondary-bootloader image, which is not in the .0pa.

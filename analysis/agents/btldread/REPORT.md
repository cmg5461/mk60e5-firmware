# App-reachable bootloader read? + SecurityAccess 0x27 (1M 7846411A)

Agent-derived (Sonnet), **verdict corroborated and seed-gen re-verified by the main session; the agent's
0x27 XOR *constants* were WRONG and are corrected below.** CPU addresses; file = CPU + 0x8000.

## Verdict [agent, high — corroborated]
**No application/diagnostic path can read the bootloader region (CPU 0x0–0x3FFFF / file 0x0–0x47FFF).**
It is a structural block: **no read primitive in this firmware accepts a caller-supplied CPU address**, so no
session/security state can redirect a read there.
- **0x23 ReadMemoryByAddress** (handler 0x0B2EFA): the "address" is never a CPU address — format 3 reads the
  2 KiB logical NVM (addr<0x800, len≤4); format 7 serves only two fixed records (addr 0 or 18) and requires the
  *baseline* state (not after 0x27). Raising the security/session state does not widen it. (Matches the earlier
  FACTS entry.)
- **0x31 RoutineControl** (0x0B2904): start/stop-actuator & test routines (pump/valve/CAN test); no routine
  returns a caller-specified memory block, and there is no requestRoutineResults raw-buffer path.
- **Manufacturing/test ASCII protocol** (0x076092): only toggles ecu_mode / reduced-cycle state; no memory read.
- **No upload service**: confirmed — the 0xF33A8 SID table has no 0x34/0x35/0x36/0x37 (rules out RequestUpload).
- **MPU** (table 0xD7648, mpu_set_region 0x0D5654): protects RAM ranges; flash-region entries not fully decoded
  [agent, low] — moot, since no diagnostic primitive ever builds a flash-space read.

**So even a valid 0x27 unlock does not yield a bootloader read.** Getting the bootloader is a hardware job
(chip read-out / JTAG / BDM, if not fused), or moot if an alternative signed image (GT4) is obtained instead.

## SecurityAccess 0x27 seed→key (handler 0x0B12AA; seed-gen 0x0AF8D8, key-check 0x0AF8F8 + siblings)
- **Shape [verified]:** odd/even subfunction (request-seed vs send-key) selected by `0x409510` bit0. Grants a
  single level `0x409513 = 3`; per-SID required level is byte+1 of each 0xF33A8 record. It is a **fixed,
  image-derived transform with no per-unit/VIN secret** — so it is reproducible from the dump, and an
  EDIABAS/INPA "SA2" routine matching this permutation would compute key from seed (consistent with the user's
  expectation that the seed/key is INPA-reachable). This grants coding/NCS-type access only — NOT a memory read.
- **Seed [verified byte-exact]:** `seed16 = ( u16 @0x40095C ) XOR 0x3008`, forced to `0x53A1` if the low 16 bits
  are 0. The `0x3008` is `(byte@0xF6679 << 8) | byte@0xF6678` = `(0x30<<8)|0x08` (bytes just after the ID record
  "AZ2RAB00039"). `0x40095C` is a heavily-used free-running counter, not a secret.
  — **Correction:** the agent reported this constant as `0x4241` from ID-string bytes 'A','B'; that is wrong
  (the code loads a pointer to 0xF6674 and reads +4/+5 = 0x08,0x30).
- **Key [structure verified; constant UNVERIFIED]:** `t = ROR16(seed, 3)` (confirmed: `lsri r7,3` + `lsli r2,13`),
  then a per-bit swap/complement network (bit i vs i+8 → outputs at 7−i / 15−i), then `XOR` with a constant read
  from the same 0xF6674 record region. The agent's `0x4142` for this XOR is **not trusted** (it came from the
  same wrong ID-string attribution); the real constant must be re-read from the 0xF6674+offset bytes, and the
  bit-network of the two sibling check-fns (0x0AF986, 0x0B1250) was not hand-verified.

## Needs re-decode / hardware
- A clean re-decode of the key-check XOR constant and bit-network (sibling fns included), then **validation
  against a real INPA/EDIABAS 0x27 seed/key capture** — the only way to confirm the full algorithm bit-for-bit.
- Full MPU flash-protection decode (only relevant for a JTAG/BDM route).
- Whether the ID record ("AZ2RAB00039" and the following bytes) differs across DSC software versions — if so the
  XOR constants are per-software but still readable from each image.

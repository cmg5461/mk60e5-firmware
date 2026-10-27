# FACTS

Established facts only. Each entry says how it is known. Hypotheses and open questions are
kept separate at the bottom; move an item up only once it is verified.

Tags: **[verified]** checked in this repo's data · **[user]** reported from the physical unit ·
**[source]** from external tooling/docs (cited).

## Firmware files

- **[verified]** E9x M3 DSC = WinKFP family `DSCM90`, flash file `7846816A.0pa` (ZB 7846816).
  Final ZB of the M3 history chain 4791200 → … → 7844739 → 7846816 (`DSCM90.HIS`).
- **[verified]** E82 1M DSC = WinKFP family `DSCM80`, flash file `7846411A.0pa` (ZB 7846411).
  History 7845200 → 7845941 → 7846411 (`DSCM80.HIS`).
- **[verified]** Both families flash with `080100DSC81.ipo` (KFCONF10.DA2 in the E85_v74 pack).
  `30DSCM90.ipo` in INPA\SGDAT is an older (2006) script, not referenced by KFCONF.
- **[verified]** Neither family ships a `.0da`; each is a single `.0pa`.
- **[verified]** `.0pa` = Intel HEX + `$`/`;` header lines + record type `0x10`, which is a normal
  data record closing a block. All record checksums valid; bins round-trip byte-exact.
- **[verified]** Headers: M3 `$REFERENZ 01818I000900`, `$CHECKSUMME 0536`;
  1M `$REFERENZ 0182H200030A`, `$CHECKSUMME 850F`.
- **[verified]** `$CHECKSUMME` = **CRC-16/ARC** (poly 0x8005 reflected, init 0, xorout 0) over
  all data bytes in address order (gaps skipped). Reproduces both DSC files and 32/32 sampled
  files from other ECUs in the E89 WinKFP pack. `tools/bmw_hex2bin.py` verifies it. This is
  the file checksum only; it says nothing about the in-image signature (below).
- **[verified]** Each application ends with a `BMY\x01` block: 1M at file 0xFE68C (closing marker
  0xFE788), M3 at 0xFE924 (0xFEA20). Layout: `BMY\x01`, u32 (1M 0x000F59E0, M3 0x000F56D8),
  u32 0x00000010, then 64 high-entropy bytes (differ completely between images), zero padding,
  closing `BMY\x01`. **Inference:** 512-bit RSA signature over the application, consistent with
  the `ERROR_FLASH_SIGNATURE_CHECK` string in BMW's DSC SGBDs. If the bootloader checks it, an
  edited application won't run without re-signing or a bootloader bypass. The bootloader (file
  0x0–0x47FFF) is not in the .0pa.
- **[verified 2026-10-04]** `rsa-sig.json` (a factored 512-bit keypair, n=p·q, e=7, with d and both
  256-bit primes) **is the genuine BMY signing key.** Self-consistency: p·q==n, e·d≡1 mod λ(n), 512-bit.
  Signature verification against BOTH images: taking the 64 BMY bytes as sixteen 32-bit words,
  big-endian within each word but in **reverse word order** (least-significant limb first in memory —
  the mixed-endian a big-endian CPU's bignum lib produces), s = that integer, then `m = s^e mod n`
  recovers in **both** the 1M and M3 images a message of **exactly 48 zero bytes followed by a 128-bit
  digest** (1M: `5a82ab5b674551445fd070df77d5ce81`; M3: `fd6642311227ac53b02d3a605627e034`). Two
  independent images recovering the same 48-zero structure under one key is conclusive (random s^e mod n
  gives ~0 leading-zero bytes; P(48 zero bytes by chance) ≈ 2⁻³⁸⁴). **Signature scheme [fully resolved
  2026-10-04, byte-verified both images]:** raw RSA (no PKCS#1 padding) over `m = 0x00·48 || H`, where
  **H = reverse(MD5(image[0x48000 : BMY_start]))** — plain MD5 over the application region (0x48000 =
  end of the 0x0–0x47FFF bootloader region) up to but excluding the `BMY\x01` marker (1M end 0xFE68C,
  M3 end 0xFE924), with the 16-byte MD5 digest byte-reversed (MD5 read as a little-endian integer).
  Repro: `hashlib.md5(b[0x48000:b.find(b'BMY\x01')]).digest()[::-1]` == the recovered 128-bit tail for
  both images. **Implication:** with d in hand, an
  edited application's BMY block is re-computable, so the signature layer is no longer a hard blocker
  for loading a modified image on these units (the in-ECU MISR word, 0x426BC, was already recomputable).
  Confirms the earlier "Inference: 512-bit RSA signature" and resolves the open item on the BMY scheme.
- **[user]** In practice these units ARE flashable: a flashing service can load an alternative BMW
  application onto them (e.g. the **M3 GT4** motorsport flash). Reconciliation: the GT4/motorsport flash
  is itself a factory image carrying its own valid BMY signature + MISR words, so it passes both integrity
  checks normally — this confirms a *signed* image loads and runs, and does NOT imply the signature is
  absent. A custom byte-edit of a stock image still faces re-signing (BMY), even though the MISR word
  (0x426BC) is now recomputable. **Lead:** obtaining the GT4 (and/or E85 motorsport) flash file would give
  (a) a definitive field-level motorsport-vs-stock calibration diff — the project's original question — and
  (b) a second signed image to study the BMY scheme and the bootloader if it is a full image.
- **[verified]** The `.0pa`'s `0xDF0000` "bank" is **not a CPU memory bank** — it is the factory
  **EEPROM default image**, addressed as `logical_EEPROM_offset + 0xDF8000`. Proof: subtract 0xDF8000
  from each DF segment and it lands exactly on the EEPROM block table (0xD7424, see
  `analysis/EEPROM_MAP_7846816A.md`) — five exact boundary matches: 0xDF812C→0x12C (blk 9),
  0xDF8160/0x22→0x160 len-exact (blk 8), 0xDF8281→0x281 (blk 16), 0xDF83C3→0x3C3 (`1A 91` hw number),
  0xDF844B/0x65→0x44B len-exact = used active-coding image (blk 7). 0xDF0000 is not a valid CPU
  address and **no code loads from 0xDF83xx**; the data is read from EEPROM via the block table / NVM
  jobs. Bytes in the `.0pa` are *logical* (un-inverted); the SPI EEPROM stores them bit-inverted.
- **[verified]** `1A 80` readout path: `kwp_1A_read_ecu_id` **0xB213E** reads local-id (0x409534),
  −0x80, range-check ≤0x1F, jumps via a 32-entry table @ **0xB219C** (ids 0x80–0x9F). `1A 80` handler
  **0xB2242** loads descriptor **0xF31D8** → `nvm_queue_job` **0x6E16C** (op=1), which reads EEPROM
  **block 24 sub-off 0xAD len 29 = logical 0x3CF–0x3EB** into RAM 0x40943E. So the ident data comes
  from EEPROM, not a memory load of the DF addresses. (6E16C = `nvm_queue_job`, shared by many diag
  handlers; not the 1A dispatcher.)
- **[verified]** Field-by-field decode of the ident bytes (INPA-confirmed, M3 7846816A). Logical
  EEPROM offset = DF address − 0xDF8000 (all in blk 24, base 0x322):
  - `0xDF83C0` (log 0x3C0) = `02` — block/format marker.
  - `0xDF83C3` +0x12 (log 0x3C3–0x3D4, `1A 91` hw number) = ZB/part number **7846816** as packed BCD,
    stored **3×** (`00 00 07 84 68 16`). 1M 7846411A = `...07 84 64 11`; DSC90 6862873A = `...06 86 28 73`.
  - `0xDF83D6` (log 0x3D6, `1A 9B`) = `08` → **Codier-index 8** (coding index).
  - `0xDF83D7` +2 (log 0x3D7) = `05 B3` (big-endian) = 0x5B3 = **Diagnose-index 1459**. (So the 3-byte
    field `08 05 B3` = coding index + diagnose index packed.)
  - `0xDF83E0` +3 (log 0x3E0, in the `1A 9F` field) = `00 24 8F` = **Nachrichtenkatalog SW 0.36.143**
    (plain bytes major.minor.patch, not BCD).
  - `0xDF83E3` +3 (log 0x3E3) = `0B 09 00` = **Softwarenummer Funktionsoftware 11.9.0**.
  - These fall inside the `1A 80` table (log 0x3CF–0x3EB), so `1A 80` returns coding idx + diag idx +
    SW versions together; the part-number copies at 0x3C3/0x3C9 belong to `1A 91`, the copy at 0x3CF
    is where the `1A 80` table begins.
- **[verified]** Per-unit ident NOT in the flash image (searched all 3 banks): Varianten-Index
  (21591=0x5457), Hardwarenummer (01), Betriebssystem SW (0.0.0 = literally zero; MK60 has no
  separate OS SW number), and Herstelldatum (26.06.2008). These live in the runtime emulated-EEPROM
  block store (table 0xD7424), written at production, not shipped in the `.0pa`. So the `.0pa` carries
  firmware-fixed identity (part no., coding/diagnose index, SW versions); per-unit identity is EEPROM.
- **[verified]** M3 vs other-variant diff in the 0xDF0000 bank is confined to this ident block: the
  3× part-number BCD, the two version fields (0xDF83D6, 0xDF83E0), and a trailing zero-fill run at
  0xDF84B0+ (written `00` on 6862873A, left 0xFF on M3). Matches the earlier "12-byte M3-vs-1M diff".
- **[verified]** E85 MK60E5 (`dsc_85.prg`, KWP2000) has no programming jobs in its SGBD and no
  WinKFP family in any pack on this machine.

## Hardware

- **[user]** MK60E5 main MCU marking: `0994.8500 4` / `SC560002MVF92 M98A` / `DCTNP0842B`,
  Freescale with ATE logo. This is the late (M·CORE) flavor. Early MK60E5 units use an ARM
  TMS471 instead; see *Two MK60E5 hardware flavors* below.
- **[source]** SC560002MVF92 is a customer-specific Freescale automotive ABS IC; no public
  datasheet ([NXP community](https://community.nxp.com/t5/Other-NXP-Products/Freescale-SC560002MVF92/td-p/1768891),
  [Octopart](https://octopart.com/sc560002mvf92-freescale+semiconductor-84653843)).

## Two MK60E5 hardware flavors: ARM (TMS471) and M·CORE (2026-10-16)

- **[user]** MK60E5 comes in two hardware flavors. **Early** units use an ARM MCU, a **TMS471**
  (a private-label TMS470 derivative). **Late** units, including the E9x M3, use the Freescale
  M·CORE (SC560002, above). `fw/7841983A.0pa` is from an E60.
- **[verified]** The flavor can be read from the `.0pa` alone, with no disassembly. All nine images
  checked fall cleanly into one flavor or the other:

  | Flavor | ZB (`.0pa`) |
  |---|---|
  | ARM / TMS471 | 4029563A, 6775387A, 6776067A, 7837326A, 7841983A |
  | M·CORE | 6791524A, 6862873A, 7846411A, 7846816A |

  Files: `fw/7841983A.0pa` and `fw/check_arch/*.0pa`. The M·CORE ZBs are 6791524A, 6862873A
  (the `fw/` and `fw/check_arch/` copies are identical) and 7846816A. 7846411A is listed from its
  own section below and was not re-checked in this pass.
- **[verified]** Both flavors use the same BMW container. Each `.0pa` is Intel HEX with type-0x10
  block ends and a CRC-16/ARC `$CHECKSUMME`. Within that container, the two layouts differ:

  | `.0pa` feature | ARM / TMS471 | M·CORE |
  |---|---|---|
  | Flash-driver block (first block in the file) | 0x818–0x1573/0x1AA3 | 0x3AC–0x8EF |
  | Bootloader space below the application (not shipped) | 64 KiB | 288 KiB |
  | Application start | 0x10000 (CPU 0x8000) | 0x48000 (CPU 0x40000) |
  | First bytes of the application | ARM `B` vector table (`EAxxxxxx` ×8; 6th = `EAFFFFFE`) | 128 × 32-bit handler pointers |
  | Extra high block | 0xE00804–0xE0xxxx, 46–59 KiB, contents unknown | 0xFFFF00–0xFFFF07 |

  Both flavors share the rest of the container:
  - The application header: `LOCK` at +0x200, the ID/EEPROM-block-table/MISR pointers at +0x230,
    and the BMY pointer at +0x2F4. 4029563A has no `LOCK` string, but its pointers are still there.
  - The rule CPU = `.0pa` − 0x8000 for the application. In every image the ID and BMY pointers only
    land on their targets with this offset.
  - The `BMY\x01` signature block, ending 0xFF bytes before the end of the application.
  - The 0xDF8xxx EEPROM default image. Its block table uses the same `0210 0040 0040…` record format.
- **[verified]** Instruction-set signatures, as raw word counts over the first 1 MiB:

  | Flavor | ARM `stmfd {..lr}` | ARM `ldmfd {..pc}` | ARM `BL` | M·CORE `jmp r15` (`00CF`) |
  |---|---|---|---|---|
  | ARM | ~1.4–1.7 k | ~1.9–3.0 k | ~6.5–7.5 k | ~30–40 (noise) |
  | M·CORE | 0 | 0 | 2 | ~2.9 k |

  The ARM code is **big-endian** (`E1 2F FF 1E` = `bx lr`, stored in that byte order), which fits
  TMS470. Most ARM images return with `bx lr` (~1.15 k). 6775387A and 6776067A instead use
  `mov pc,lr` (~1.3 k), which points to a different toolchain or build.
- **[verified]** Peripheral constants in the code back up the split. The ARM images contain
  ~140–170 constants in 0xFFF7E000–0xFFF7FFFF and none in M·CORE's 0xD80000/0xF80000 timer range.
  The M·CORE images are the reverse: ~190–205 against at most 1. The ARM images also reference
  0xFFFFFDxx–FFxx and 0xFFE88000–0xFFEAxxxx.
- **[unverified]** The TI block identities are recalled from memory, not taken from a datasheet:
  the 0xFFF7Exxx/F7Fxxx frame (GIO 0xFFF7EC00, MibADC 0xFFF7F000, SCI 0xFFF7F400, SPI 0xFFF7F800,
  HET 0xFFF7FC00), the system module at 0xFFFFFDxx–FFxx, and flash control at 0xFFE88000. On the
  ARM flavor the RAM constants cluster in 0x400000–0x403FFF, suggesting ~16 KiB of SRAM against
  48 KiB on M·CORE.
- **Scope:** everything else in this file is about the **M·CORE flavor** (1M 7846411A, M3 7846816A)
  unless it says otherwise. `tools/mcore_dis.py` does not apply to the ARM flavor.
  `tools/bmw_hex2bin.py` handles both. To work on the ARM flavor, use a big-endian ARMv4T
  disassembler, for example `arm-none-eabi-objdump -EB` or Ghidra's `ARM:BE:32:v4t`.

## CPU / code (M·CORE flavor; 1M image 7846411A; M3 not yet examined)

- **[verified]** Instruction set is Motorola/Freescale **M·CORE**, big-endian, 16-bit opcodes.
  1264 `subi r0,N ; stm rX-r15,(r0)` prologues; `ldm … ; addi r0,N ; jmp r15` epilogues;
  `jmp r15` (0x00CF) is the 3rd most common halfword.
- **[verified]** Not ARM/Thumb (either endianness), not PowerPC classic or VLE (no r1 frames),
  not SH/SH-2A, ColdFire, H8S, FR, TriCore, V850, C166.
- **[verified]** Application block: CPU address = `.0pa` address − 0x8000
  (file 0x48000–0xFE78B → CPU 0x40000–0xF678B). With the correction 1031/1647 jsri targets
  sit right after `jmp r15`; without it, 9.
- **[verified]** RAM variables referenced at 0x00400000–0x004Cxxxx.
- **[verified]** Peripheral-like literal clusters: 0x00D8_0000–03FF (228 refs) and
  0x00F8_0000–03FF (215 refs), used in pairs by the same functions; same pairing for
  0x00D5_xxxx/0x00F5_xxxx. Also 0x00E1_0000 (76), 0x00DB_0000/0400, 0x00DD_0000, 0x00DE_0000.
- **[verified]** VBR = 0x00040000 (`lrw r7,=0x40000 ; mtcr r7,cr1` at 0x06CA18). The 128-entry
  vector table is the first 0x200 bytes of the application. Exception handlers 0x6C9B2… are
  0x3C-byte stubs; reset = 0x6C9B2. Vectored IRQs have bit 0 set (alternate register file);
  handler = address & ~1. Unused IRQs → 0x4273C.
- **[verified]** 0x00D8_0000 and 0x00F8_0000 are two instances of the same timer/capture module
  (not mirrors), each serving two wheel channels. Channel control regs at +0x8E and +0x9E.

## Wheel-speed input path (1M, verified from code)

- **[verified]** IRQ vectors 56–59 are the four wheel-speed edge ISRs:

  | Vector | Handler | Module + channel ctrl | Edge-count byte | Capture case |
  |---|---|---|---|---|
  | 59 | 0x070D2C | 0x00F8008E | 0x0040339A | 0 |
  | 57 | 0x070DB2 | 0x00F8009E | 0x0040339D | 1 |
  | 58 | 0x070E3C | 0x00D8008E | 0x0040339B | 2 |
  | 56 | 0x070EC6 | 0x00D8009E | 0x0040339C | 3 |

  Which physical wheel each one is: not yet known.
- **[verified]** Each ISR: counts edges per window (byte above); at ≥57 edges it disables its
  own interrupt. Otherwise reads a capture timestamp via `sub_0D5B4C(case)`, stores it >>2,
  computes the delta to the previous 32-bit timestamp (0x00409318/0x00409328 arrays), masks to
  24 bits, saturates at 0xFFFF, and stores it into a per-wheel halfword array (base pointer at
  0x004091A8) for edge indices < 22. Returns with `rfi`.
- **[verified]** Each channel has a 2-bit mode (ctrl & 3). Mode 3 uses status/enable regs
  +0x340/+0x344 and timestamps +0x80/+0x90; other modes use +0x300/+0x304 and +0x20/+0x40.
- **[verified]** `sub_0D5CDC(case 0–6, flags)` configures these channels (jump table; flag bits
  0x80, 0x08, 0x10 select register settings).
- **[verified]** Segment 1, physical 0x3AC–0x8EF (0x544 B), is the **flash-programming driver**: a
  position-independent routine (every internal address relocated via `r8`, so it runs from RAM while
  flash is being erased/written), dispatching on a command code in r3 (cases 2, 11, …), writing the
  flash-controller base `0x00F60000` into a RAM control block at 0x400338, and masking offsets with
  `0x000FFFFF`. Its "very low" address is real but **not** in the app's CPU window: the app uses
  CPU = phys − 0x8000, so phys 0x3AC would be negative — it lives in the low/bootloader flash
  (phys 0x0–0x47FFF), just above the protected reset/vector area (0x0–0x3AB). That is why the reflash
  erase begins exactly at 0x3AC: everything below it is never erased, and this driver is the first
  thing reflashed. It is the only part of the 0x0–0x47FFF region present in the `.0pa`; the rest of
  the bootloader is not shipped.
- **[verified]** M3 vs 1M: 0xDF8xxx blocks differ in 12 bytes; 0xFFFF00 block identical.

## OS / scheduling (1M)

- **[verified]** OSEK-style OS with 5 static tasks; config tables in flash: entries 0x42700
  {0x785DA, 0x785EA, 0x78602, 0x78778, 0x785BE}, u16 priorities 0x42714 {3,0,1,2,4} (0 = highest),
  autostart 0x42734 {1,0,0,0,1}, stack tops 0x426D8 / bottoms 0x426EC.
- **[verified]** Time base: vec60 → stub 0x42842 → 0x70A86, 13-slot sequencer with jump table
  0x70B28. Slot-to-task mapping and service names: see `analysis/agents/startup/REPORT.md`
  (agent-derived, medium confidence unless marked verified there).
- **[agent, med]** Startup: no .data copy, RAM 0x400000–0x40C000 zeroed; VBR set; INTC at
  0x00E10000; D8/F8 init mirrored; 0xAA stack canaries checked on every ISR exit / task switch;
  no watchdog service or ROM checksum identified yet.

## Platform (1M; detail in `analysis/agents/platform/REPORT.md`)

- **[verified]** Timers D8/F8 prescale 79 (÷80) set at 0x6F5BE/C6. **[agent, med]** 80 MHz system
  clock (baud divider table 0xD78E0 fits 5 MHz/N exactly), so 1 µs timer counts and a **10 ms
  frame** (slot deltas sum to 10000). T2 runs at 1 ms, T1 at 2.5 ms, T3 at 10 ms.
- **[verified]** Application header: "LOCK" at 0x40200; 0x402F4 → 0xF668C (BMY block);
  0xF6664 = 0x0C "AZ2RAB00039" (ID record, checked at init → error 0x12000).
- **[verified]** Calibration block directory at 0x40300: version 2, 12 entries of
  {tag[4], addr, len}, each block starting `TAG\x01`, u32 version, u32 id:
  ABS 0x4039C/0x666, CSI 0x40A04/0xB2, TCS 0x40AB8/0x932, AYC 0x413EC/0x58C,
  BCO 0x41978/0x220, COA 0x41B98/0x36C, BFU 0x41F04/0x1C, VAR 0x41F20/0xE, DDS 0x41F30/0x118,
  CSW 0x42048/0x1A, LVC 0x42064/0x5E0, VMO 0x42644/0x6C. Readings of the tags are guesses:
  AYC = Active Yaw Control, DDS = Deflation Detection System, TCS = traction control.
- **[verified]** Background ROM self-test ranges (table 0xD7584): [0x40000, 0x402F8),
  [0x40300, 0x426BC) = exactly the calibration blocks, [0x426C0, 0xF6684). Table = three 8-byte
  {start,end} BE-u32 entries (end exclusive); the expected BE-u32 is stored **at** each end address
  (0x402F8=0xB6EFCB77, 0x426BC=0x03B09CDC, 0xF6684=0xD719D58D). Mismatch → error 0x10004 (driver
  sub_06DDE4; unit regs 0xD50200 control / 0xD50204 result).
- **[verified]** **The self-test algorithm is REPRODUCED** (`analysis/agents/romselftest/`): the
  0xD50200 unit is a 32-bit **MISR**, not a CRC — seed 0, BE 32-bit word feed, per word
  `s=((s<<1)^(0x00400007 if s>>31 else 0))&0xFFFFFFFF; s^=w`. Reproduces all three stored values
  byte-exact (re-verified by the main session). **Consequence:** the expected word for the
  calibration range (0x426BC) can be recomputed after any cal edit, so the ROM self-test alone no
  longer blocks tuning once that word is updated. **Still separate and unresolved:** the probable
  512-bit RSA **BMY** signature over the application — the bootloader (file 0x0–0x47FFF) is not in
  the .0pa, so whether it enforces that at flash/boot cannot be determined from this image.
- **[verified]** BMY header u32 0x000F59E0 points to the reference string "0182H200020A"
  (not a length).
- **[agent, high]** Bootloader hand-off 0x0D5684: 'SBL!' at 0x4010 → jsr [0x4000] (secondary
  bootloader at CPU 0x4000, not in the .0pa). MPU at 0xFFF00000; flash cache probably 0xFFF80000;
  reset control 0xFB0000; a second CAN module at 0x00FA0000; no periodic watchdog service found
  in the app.
- **[agent, high]** "ecu_mode" (0x400A11 bits 7:5) is the level of an ASCII serial
  manufacturing/test protocol (0x076092), open for about 1.8 s after power-up. Level ≥ 3 runs a
  reduced cycle without control or monitoring; ≥ 4 also stops CAN. It is not a general state.
- **[verified]** Boot-mode / debug (detail `analysis/agents/bootmode/REPORT.md`): the **application writes
  NO JTAG/OnCE-disable or security/censorship register** — on M·CORE the debug port is fuse/TAP-gated, not
  CPU-pokeable, so any lock is mask-ROM/fuse and unknowable from the image (settle by probing). `0x0D5684`
  (jump-to-bootloader) requires `[0x4010]=='SBL!'` (0x53424C21) + `[0x4000]≠0xFFFFFFFF` + a bit of the
  reset-latched status word `0xFF0006` (app only reads it; no app GPIO boot-strap). Its **only caller is the
  reset dispatcher 0x06CFA6 case r2==45 (0x2D)**, invoked from the manufacturing/test serial protocol
  (sub_077080 ← sub_076092), not from any CAN/KWP SID — so CAN reflash is entered by the bootloader/mask-ROM
  at reset. Flash programming (0x34/0x36/0x37) lives entirely in the bootloader at CPU 0x4000.
- **[verified]** Mfg/test serial protocol decode (detail `analysis/agents/mfgproto/REPORT.md`): the serial
  engine is on the **0x00D80000 module** (ctrl 0xD80380, data 0xD80110; vector slots 44→0x42788→sub_07076C,
  52→0x42804→sub_0700E8; RX buffer 0x40331D) — **NOT 0xFC0000** (that address is referenced nowhere in code;
  corrects an earlier inference). 8-bit framing (8N1); baud unconfirmed (table 0xD78E0 → try 9600/10400).
  **No command reads/writes a caller-supplied address** — not a memory dumper. Commands: handshake (bytes
  0x40,0x01,0x02), digit cmds (0x30–0x3F), letters R/S/T/U/X/Z. **Bootloader entry** (fully decoded, no secret,
  ~1.8 s window): handshake → raise level≥3 via 'U' + "16" → **'Z'** with hex payload "2D" → `0x400A18=0x2D` →
  state7 → dispatcher 0x06CFA6 case 45 → jump_to_bootloader. It only transfers control to the bootloader; the
  bootloader's own services/auth are in the absent 0x0–0x47FFF image.

## Application structure (1M; detail in `analysis/agents/app/REPORT.md`, overview `ARCHITECTURE.md`)

- **[verified]** Runtime object 0xD7F14 → class 0xD81F4 → objects at 0xD81D0
  {0xD80AC, 0xD7FA8, 0xD816C, 0xD810C, 0xD8008}, object→task map 0xD7F08 {3,4,2,1,0}.
  Task bodies (class +40): T3 = 0x071040, T2 = 0x070CB4, T1 = 0x070C58. Runs per frame
  (class word 0, byte 2): 1, 10, 4.
- **[verified]** T3 0x071040 is the main cycle. In order: … 0x752B8 wheel speed, 0x8EE30
  per-wheel pass, 0x8F0A4, 0x8CAD8 control dispatcher, 0xB3DA8 monitoring, 0x71F2E, 0x7944C
  CAN stack, 0x6D084, 0x76092 or 0xAFEDC (diagnostics), NVM/error handlers, then 0x4009B4 bit2.
- **[verified]** The tables at 0xDB2D8 (8000), 0xDF158 (16000), 0xE6E58 (8000) and 0xEACD8
  (16000) are Q12 s16 sine/cosine values at 18° and 22.5° steps (e.g. 2896 = 4096·cos45°,
  3784 = 4096·cos22.5°, 3896 = 4096·cos18°). Used by a per-wheel module around 0xA6022.
  **Hypothesis:** RPA (indirect tyre-deflation detection via wheel-speed spectra); BMW ships
  `DSC8_RPA` coding for the E89 DSC.
- **[agent, med]** 10 ms frame (from CAN periods); T2 ≈ 1 ms SPI job engine; T1 ≈ 2.5 ms
  per-channel logic; main scalar calibration block probably 0xDA2F0–0xDB2FF.

## Calibration block sizes: 1M vs M3 (both decoded from each car's own directory)

- **[verified]** Directory header = {u32 ver=2, u32 count=12, u32 total_size}; records {tag[4], addr, len}.
  The blocks that differ in size between the two cars are exactly ABS, CSI, TCS; all others are
  byte-identical in length. 1M blocks are internal-format version 3 (TCS v4); M3 blocks are all v4.

  | Block | 1M len | M3 len | note |
  |---|---|---|---|
  | ABS | 0x666 | 0xB0A | M3 1.73× larger |
  | CSI | 0xB2 | 0x114 | M3 1.55× larger |
  | TCS | 0x932 | 0x1D4 | **M3 5× smaller** |
  | AYC | 0x58C | 0x5C6 | ~same |
  | BCO/COA/BFU/VAR/DDS/CSW/LVC/VMO | — | — | identical length |

  **[verified]** The size difference is NOT functional restructuring (an earlier inference, now
  disproven): the M3 TCS block shrank because its large curves were **relocated byte-identical into
  constant ROM at CPU 0xF61B4–~0xF6730** (outside the cal directory); 39/55 TCS curves and all six base
  slip curves match the 1M exactly. The M3 ABS growth is **12-way variant duplication** of three items
  (front speed-term, g-curve, floor tables), indexed by a 5-bit EEPROM coding field `0x4031AA+1` (read
  directly with `ld.b`), not present in the flash. See `analysis/agents/m3cal/REPORT.md`.
- **[verified]** M3 vs 1M slip/decel verdict: **base drive-slip threshold identical (Δ=0)**; ABS decel
  threshold identical for coding variants 1–9. Only variants **10/11** (= M3 GTS coupe / GTS sedan) are more permissive (high-speed
  ≥150 km/h by ≈3–5% at 200–300; <60 km/h floor −140 vs −132) and variant **0** (M3 sedan) differs <20 km/h
  (−127 vs −120). Active variant is in EEPROM (coding byte 1), not in the flash. TCS has two small opposing deltas
  (one cap +3000–3600 higher, one cap tighter) → no systematic motorsport lean in these blocks. **The
  M-car is not meaningfully more permissive in core slip/decel targets at the calibration-block level;**
  MDM-style permissiveness, if present, is more likely in DSC-mode logic / AYC / code constants.

## ABS calibration block (1M 0x4039C, ver 3, len 0x666; detail `analysis/agents/abs/REPORT.md`)

- **[verified]** Body = 39 piecewise-linear curves + scalar gaps. Curve reader `sub_071158`
  (0x7115C): record `s16 lo,hi,n; x[n-1]; c[n] intercept; k[n] slope Q10`;
  output `clamp(c[i] + (x*k[i])>>10, lo, hi)`. Confirmed in disasm.
- **[verified]** Readers are 49 fns in 0x44722–0x5B0EE — this **is the ABS controller** (dispatcher
  0x8CAD8 entries 0x44722/0x449E4), not merely an estimation layer (correcting an earlier note). The
  separate 0x8xxxx code is a pressure-request **arbiter + valve-pulse sequencer** (entry 0x840AC),
  calibrated by COA + the 0xDA2F0 scalar block, not by the ABS block.
- **[verified]** **ABS entry slip threshold = curve at ABS+0x576 (0x40912):** lo 0, hi 900, bp 5000,
  intercepts 150/115, slopes −4/+3 (Q10). **The curve input is vref (0x408D84), not slip** (corrects an
  earlier note); the resulting threshold is compared against slip = vref − wheel speed. Threshold evaluates
  to 150/130/144/158/173/202 ·0.01 km/h at vref 0/50/100/150/200/300 km/h ≈ **1.3–2.0 km/h of slip** as the
  ABS entry/continue condition (fn 0x54F9A). Closest thing to a "slip target"; it IS in the calibratable ABS
  block. There is **no slip-% target** — the controller works in a pressure-model domain (per-wheel levels,
  0.01 bar, −8000..25000, clamps hard-coded).
- **[verified]** **vref (0x408D84, 0.01 km/h) is a rate-limited integrator**, not a max-select (writer
  sub_044BF0, once/10 ms frame, floor 0.62 km/h). Rise +44/frame (1.25 g) toward fastest front wheel, +22
  (0.62 g) toward slowest valid wheel while ABS active, up to +282 ("snap") in init/modes 1/2/4; fall
  −22..−44 normal, −90 in modes 1–7, or decel-limited `−(|decel est|+margin)·0.36` capped −44 during ABS.
  Inputs are the 4 filtered wheel speeds `rec+0x1A` × the learned per-wheel tyre-tolerance factor (Q10, a ratio
  trim; circumference is already in `rec+0x1A` via K, see "Tyre-tolerance learning"). Full algorithm:
  `analysis/agents/absvref/REPORT.md`.
- **[verified]** Wheel accel **struct+0x20 in 0.01 g**: normal-mode writer is **sub_0D271C** (called from
  wheel-speed update 0x752B8 @0x754DE), `+0x20 = two-frame mean of Δv·2.833` (conv literal 0xE287 = 57991, ·2.8316),
  clamped to ±2032 (±20 g) by sub_0465B0; `w.39 = a/16` spans ±127. (sub_0B65DC's ±158 is only a glitch-
  recovery path.) **So the dump stages ARE reachable**: set A −62/−78/−94 ≈ −9.9/−12.5/−15 g, set B
  −25/−44/−62 ≈ −4/−7/−9.9 g (resolves the earlier "unreachable" conflict).
- **[verified]** Per-wheel ABS **phase state machine** (rec[0], sub_04FE3C): 0x80 armed-idle → 0xC0 pre-control
  / 0x84 rear-overspeed-hold → **0x21 DUMP → 0x09 HOLD → 0x11 REAPPLY → 0x15 reapply-hold** (bits: b0 in-cycle,
  b5 dump, b3 hold, b4 reapply, b6 pre-control). Global decision code **0x408DBA** (sub_051D54/054F9A):
  1=no-control/build, 64=rear-in-control, 32=yaw-limited(0..100%), 1024/16=reapply, 2=pair-hold-done, 128=special.
- **[verified]** Signal roadmap: decel threshold builder fn 0x47DFC → **0x4090C2** (bidirectional
  accel threshold, base −116/floor −240 in 0.01 g, front/rear speed curves +0x76/+0x9E). The ladder/dump
  summation (0x55D44/0x55EE8/0x56106) → **0x409110 = pressure-REDUCTION amount** (distinct from the 0x4090C2
  threshold; corrects an earlier conflation). Pressure-proportional dump %: front +0x154 (20→8%), rear +0x17C
  (30→6%).
- **[verified]** Apply ramp ABS+0x0C = 400/cycle (fn 0x44614). Dump stages (fn 0x5444C) compare filtered
  peak wheel-accel (struct+0x39 = accel/16 ±127) to ABS+0x61E/+0x65E; stage → pressure reduction
  ABS+0x624 = 1000/1500/2000 (= 10/15/20 bar). Speed-dependent caps live in **hard-coded ROM curves
  0xD713C–0xD7390 (outside any cal block → not tunable)**. Detail: `analysis/agents/control/REPORT.md`.
- **[verified]** Per-wheel deceleration-threshold builder (fn 0x47DFC): base +0xCC = −116,
  floor +0xCA = −240, low-speed floors +0xF0 = −120 (<20 km/h), +0xF2 = −132 (<60 km/h);
  front/rear speed-term curves +0x76/+0x9E; accumulator gains +0xC6 = 40 (front), +0xC8 = 25 (rear).
  **[agent, low]** unit ≈ 0.01 g (base ≈ −1.2 g, floor ≈ −2.4 g); not proven.
- **[verified]** Decel ladder +0x2C8..0x2D2 = −140,−90,−40,−210,−350,−490. Staged thresholds
  (fn 0x5444C): set A +0x61E = −62/−78/−94, set B +0x65E = −25/−44/−62, stage outputs 1000/1500/2000.
  Speed gates +0x458/+0x502/+0x508 = 70/70/100 km/h; +0x3A6/+0x3A8 = 60/20 km/h.

## TCS calibration block (1M 0x40AB8, ver 4, len 0x932; detail `analysis/agents/tcs/REPORT.md`)

- **[verified]** Same piecewise-linear format (`sub_071158`); 55 curves, replicated per **mode
  m=0,1,2** (stride 34/28/22 B). Controller is ~60 fns at 0xC7600..0xCFA00 off dispatcher 0x8CAD8.
  The 0xC79A0 region once guessed to be a "descriptor table" is just interleaved literal pools.
- **[verified]** Traction acts on the **rear (driven) wheels only** (state records 0x402FC4 init only
  for w=2,3). Reference speed `0x403066 = min(LF,RF)` (undriven front), 0.01 km/h. **Drive slip =
  rear wheel − same-side front**, absolute in 0.01 km/h (there is **no "target slip %"** field).
- **[verified]** Base slip-threshold curve: `thr = curve(vref)`, table +0x0EC+34·m (set A) or
  +0x086+34·m (set B, when 0x402F6C bit4 set); n=5, clamp 0..30000, breakpoints 15/25|50/80/100 km/h.
  Evaluated allowed rear−front slip (0.01 km/h) — verified: set-A mode 0 = {15.0, 2.7, 1.0, 2.3, 3.8,
  11.8, 28.4 km/h} at vref {0,15,25,50,80,100,150}; modes 1/2 keep a much higher low/mid floor
  (≈6–8 km/h). The m0→m1→m2 progression = increasingly permissive slip (DSC→DTC-like).
- **[verified]** Limit build (fn 0x0C78D0): entry `0x403014 = thr + extras + 500(5 km/h) − R`,
  exit `0x40300C = thr + extras/2 + 300(3 km/h) − R`; R = pct·0x40308E/100, pct +0x1D4.. = 10/10/2/10 %;
  extras curve +0x180+28·m (10 km/h@0 → 2 km/h@15). Entry gates +0x14.. = 16/10/20/30 km/h; gross-slip
  limit (fn 0x0C8384) max(15, 40 − vref) km/h; 5×8 hold-time map at +0x28E.
- **[agent, med]** No field confidently tied to engine-torque reduction; the torque-request writer
  was not traced. Mode byte (0x4031AA+7) physical meaning (DSC/DTC/surface?) unresolved.
  **[resolved 2026-10-26, M3]** The curves above are the *brake*-TCS thresholds; engine ASR uses separate targets and m
  is the DSC mode index (0 DSC on/off, 1/2 MDM). The tail words +0x8FE..+0x930 (37CE, 8B82, 0B3B, 9976, 6F9B) are
  disc thermal-model constants, not integrity/id words. See `analysis/TCS_7846816A.md`.

## Wheel-sensor type selection (resolved; detail `analysis/agents/sensortype/REPORT.md`)

- **SUPERSEDED 2026-10-06 → see `docs/E46_SENSOR_FIRMWARE_PATCH.md`.** The "no selector" finding below is true only for the MCU app code. The real selector is in the
  wheel-speed ASIC: register **0x28C** is a per-channel VDA/2-level mode mask, written once from the init table at
  file 0xDF22C (stock 0x00F = all VDA).
- **[verified]** There is **no per-axle/per-channel sensor-type selector** in the app. Both 1M and M3
  hard-configure all four channels for VDA active-encoded sensors; BFU front/rear values are identical
  in both cars `[100,72,2073,2073,48,48]`. The only coding bit in the wheel-speed chain (raw byte10
  bit6 → 0x4031F4 bit8 → invert mask 0xD79FC = 05/09) flips **direction polarity only**.
- **[verified]** Speed magnitude always comes from edge timing (0x0752B8), independent of VDA data —
  so edge timing is sensor-agnostic (would count toothed-ring edges), but VDA consumption is not
  switchable off per axle: direction mask (literal `60F2` @0x0B91AC) and the presence check
  (0x075E94: ASIC B-word popcount ≥3, else fault at cycle 100) both assume VDA on all four.
- **[verified]** 0x4031F4/F6 is the packed BMW coding block (module 0x0D0000; NVM block-7 reload
  checked vs 0x4030DC, mismatch → DTC 0xC0040). Air-gap quality bytes 0x400A3C/44/48 have no consumer (re-checked 2026-10-15: only `wss_ak_airgap_stats_init` 0x75B2C and `wss_ak_airgap_stats_update` 0x75B74 touch them; they hold the min/max/step of the AK air-gap gauge (AK b7:5) and a per-wheel "air-gap reserve error seen" flag, see symbols "Wheel direction").

### Missing-encoding fault gates (M3, byte-verified 2026-10-04) — for sensor-compatibility bench study

Two independent checks fault when the sensors don't deliver the VDA encoded stream:

- **[verified]** **Startup VDA presence check `wss_startup_presence_check` 0x75E38** (= 1M 0x75E94). Runs per wheel during the startup
  window ([0x400960] cycle counter ≤ 1000). The per-wheel sensor mode comes from `sub_075A44`, which returns
  **4 for all four wheels (hard-coded — confirms no per-wheel sensor-type field)**. Mode 4 → read the wheel's
  ASIC reply word 0x400F20+4·slot (slot via table 0xD7668) and **popcount it** (`sub_075DD8`, a 32-iter
  `lsrc`+`inct` bit-count); plus per-wheel presence bits in the ASIC status halfword 0x4009CA (= `lrw 0x4009C6` + `ld.h` offset 4; `wss_asic_present_bit` 0x75DEE:
  wheel0 bit1, wheel1 bit5, wheel2 bit7, wheel3 bit3). If popcount is **≥ 3** (`cmplti r2,3` at 0x75EB0; mode 2 uses
  0x75F1C) it sets the per-wheel **presence-OK** flag 0x4010CE[w] = 1 (corrected 2026-10-15: earlier text called it
  an error flag). At **cycle 100**, a wheel whose flag is still 0, which has no 5D90 electrical fault already
  (0x75D72) and is not inhibited by 0x400957 b5 && 0x40288C b6, latches **0x400952[w] |= 0x31** (bits 0/4/5) and
  raises **5D96/5DA6/5DB6/5DC6 "Drehrichtungserkennung"** via `wss_dir_fault_set(w)` 0x75D3E (fault id
  (2+w)<<16 | 0x40). Corrected 2026-10-15: earlier text said a "group 0x0C" sensor DTC. Controlling points: mode selector 0x75A44, popcount threshold
  `cmplti …,3` (0x75EB0 / 0x75F1C), status latch 0x400952[w].
- **[verified]** **Runtime direction-invalid fault `wheel_direction_update` 0xB9330**: per-wheel invalid-direction
  counter 0x4029DB[w]; at **≥175** (`movi r10,47; bseti r10,7` @0xB9448) → `fault_set` 0xB427C with the per-wheel
  DTC from table **0xF576C** (0x00020040/30040/40040/50040). Gated by the **direction-expected mask 0x4029D6**,
  loaded = **15 (all four wheels)** at **0xB93C4** (`movi r2,15`, bytes `60 F2`; → `validate_dir_cfg` 0x75A5E →
  st.b 0x4029D6). A mask value of 0 (`movi r2,0` = `60 02`) marks no wheel as direction-expected.
- **Context:** both are code checks (not cal fields). Speed magnitude (edge timing 0x7525C) is sensor-agnostic;
  what's lost without encoding is direction/reverse, standstill-direction, and air-gap/presence monitoring. Any
  image edit still needs re-signing (`tools/bmy_resign.py fix`). Static-derived → **bench-verify**. The sound
  reconfiguration path remains a sensor-matched factory flash (E85/GT4) — diff it if obtained.

#### `sub_075A44` mode value is a 3-way dispatch — a latent non-VDA path exists (byte-verified 2026-10-04)

- **[verified]** `sub_075A44` is a **pure constant map** of wheel index → mode: returns **4** for index 0..3,
  **0** otherwise. Reads no memory / no coding byte, so sensor type is a **compile-time constant baked in code**,
  not EEPROM. Only caller = dispatcher @0x75E9C in `sub_075E38`. Patch site for the constant: file offset
  **0x7DA56**, `60 43` (`movi r3,4`) — bytes confirmed.
- **[verified]** The caller **branches on the value three ways**, not just `==4`:
  `cmpnei r2,4; bt 0x75EC0` (`2A 42` @0x75E9E) then `cmpnei r2,2; bt 0x75F50` (`2A 22` @0x75EC0).
  - **mode 4** (current): VDA path — ASIC reply word 0x400F20+4·slot, presence = popcount ≥ 3.
  - **mode 2** (latent, never selected): a *different* algorithm @0x75EC4 — reads pair `u16[0x40339E+4·w]` and
    `u16[+2]`, plausible when `(w0−w1) ∈ [6..25]`, byte `[0x40339E+4·w+16] ≥ 2`, then confidence counters
    0x4010D2[w]/0x4010D6[w] (cap 254) and status via `sub_075DEE`, before the common fault tail.
    **Polarity (re-read 2026-10-15):** the mode-2 pass flag is 0x4010CE[w] = (0x4010D2[w] < 10 && 0x4010D6[w] < 3),
    and the fault fires at cycle 1000 when that flag is 0. So mode 2 **fails** a wheel that shows 10+ protocol-width
    pulses or 3+ ASIC-present cycles, and passes a plain pulse sensor (or a missing one; that is left to 5Dx0). This
    matches the bench reading 0x4010CE = 01 01 01 01 with no latch. Names: `analysis/7846816A_symbols.md`, "Wheel direction".
  - **anything else** (incl. mode 0 for a bad index): `bt 0x75F50` → immediate WSS fault latch 0x400952[w]|=0x31.
- **[verified]** **Mode-2 data source is live (hardware-fed), not dead.** Data chain:
  edge-capture hardware (timer/eTPU MMIO `0xF800xx` + `0xD800xx`, both above flash) → four per-wheel capture
  **ISRs** `sub_070CD0 / 070D56 / 070DE0 / 070E68` (all end `rfi`; each reads its channel's capture regs, converts
  via `jsri 0xD550C`, `lsri 2`) write the `0x40338A` struct → per-cycle **latch copy @0x73B5C** (`movi r1,10`
  halfword loop) copies `0x40338A[0..19] → 0x40339E[0..19]` → mode-2 branch reads `0x40339E[0..15]`. So mode 2 is
  the **raw edge-timing / period** presence scheme (no encoded protocol word), consistent with simple/passive
  (E46-style) sensors; mode 4 is the VDA-encoded active-sensor scheme (serial ASIC reply). This is the real
  type-4-vs-type-2 sensor distinction, selected solely by the `sub_075A44` constant.
- **Bench note:** forcing mode 2 (0x7DA56 `60 43`→`60 23`) reroutes presence onto the period path instead of the
  ASIC-popcount path; it is **not** a blind pass (mode 2 keeps its own plausibility window + confidence + status +
  0x400956 bit5 / 0x40288C bit6 gates before the fault latch). Period data is already produced every cycle, so the
  input is populated — but whether it resolves to "present" for a given physical sensor is a **bench-verify** item.
  Re-sign after any edit.

## Vehicle-model / coding-selected parameters (detail `analysis/agents/geom/REPORT.md`)

- **[verified]** The EEPROM **coding field `0x4031AA+1`** (5-bit, variant 0..11, read directly as `ld.b 0x4031AA+1`, not via `0x8E066`,
  unpacked at 0xD0418) selects a **vehicle-model parameter set**. M3: a 12-variant ROM table at
  ~0xD6E16..0xD70FF (each parameter = 12 contiguous s16, rows 24 B apart), loaded by 0x5DE44/0x5E424 into
  RAM 0x400AA4..0x400ABA. 1M: a single fixed scalar set at 0xD7458+ (no variant index). This confirms the
  user's hypothesis that unit coding selects geometry/mass.
- **[verified]** **Wheelbase** = l_f + l_r in 1/1024 m: 1M 1331+1393 = 2724 → **2660.2 mm** (exact 1M);
  M3 all variants sum 2826/2827 → **2760/2761 mm** (exact M3). Not stored as a scalar; only the CG split
  varies between M3 variants. Rows: l_f 0xD6F42, l_r 0xD6F5A, **mass 0xD6F72** (M3 1691–1947 kg; 1M 1739),
  yaw inertia Jz 0xD6F8A, stiffness 0xD6ECA/0xD6EE2. Roles fixed by the single-track model (next section); mass /
  inertia units consistent (J/m ≈ radius of gyration² ≈ l_f·l_r; 1M 1739 ≈ +4% over 1670 kg curb) but not proven
  absolutely; Cf / Cr units open.
- **[verified]** **Brake coding is separate**: fields `0x4031AA+3` (front) / `+4` (rear), 3-bit each,
  select COA pressure↔volume curves (front +0x1EA/+0x1FE, rear +0x212/+0x226; reader 0x81508), COA offset
  tables, and BCO threshold sets. **Rotor diameter and piston area are NOT stored as scalars** — folded
  into the p-V and gain curves.
- **[verified]** Correcting the earlier geometry-hunt caution: the "geometry-shaped" constants in
  COA/BCO/AYC are curve data / thresholds, not stored geometry (COA 2600–2750 = p-V points; BCO 300/358 =
  pressure compare thresholds; AYC 349/698 = ±20°/±40° angle clamps). VMO (0x42644) is a wheel-speed
  timing/plausibility monitor, not a vehicle model.
- **[needs-hw]** The car's actual coding bytes (+1/+3/+4) are not in flash; with +1 the 0xD6xxx row gives
  that unit's mass/CG. Variant→model mapping **[user-supplied]**: 0 M3 sedan, 1 Custom ESM
  (NCS: model from coding bytes 31–40; this image only non-zero-checks them and the loaders use ROM column 1), 3 coupe, 4 convertible, 5/8/9 Competition sedan/coupe/
  convertible, 10 GTS coupe, 11 GTS sedan; 2/6/7 not identified. All 12 rows are E9x M3 (same 2.76 m
  wheelbase).

## Yaw / single-track model + DSC mode (detail `analysis/agents/yawmodel/REPORT.md`)

- **[verified]** The vehicle-model scalars feed a real **single-track (bicycle) model**. Roles confirmed:
  l_f 1331 / l_r 1393 (Q10 m, front share 51.1%), **mass 1739 kg**, **Jz 3039 kg·m²** (Jz/m ≈ l_f·l_r
  confirms units), Cf 7186 / Cr 12857 (cornering stiffness). Two forms: a **dynamic observer** (AYC fn
  0x5ECB0, states β 0x400C42 / r 0x400C44, friction-clipped, 10 ms) producing the **target yaw rate B1A
  0x400B1A**; and a **closed-form reference** r_ref = δ·v/(L·(1+v²/v_ch²)) with **v_ch = 97.65 km/h** (CSI fn
  0x90C44 → 0x4020EC). Numerically validated (observer replica: v_ch 97.0 km/h, step ≈10 ms).
- **[verified]** Intervention: yaw error `e = measured(B46, from F-CAN 0x0CD) − target(B1A)`; entry |e|>B6C,
  hold |e|>B70=B6C−698, persistence ≥79; PD moment demand (fn 0x5F882) → brake (request ids 3/20) + engine
  torque (fn 0x6514C). Threshold base AYC+0x230=1396 (set A) / +0x232=2792 (set B).
- **[verified]** **DSC mode = 3-state index m∈{0,1,2}** (0xCF92A): `m=0 if 0x4030A4∈{1,4,5} or 0x4030A2≠3;
  else m=2 if coding bit (record byte 10 bit5) set, else 1`. Mode-indexed AYC tables: entry threshold B6C set A
  = {3490,3490,3013,2378,1952,1396}·0.01-units for m0/m1 vs {2420,1861,1396,…} for m2 (by speed); P-gain
  30→60% (m0/1) vs 73→100% (m2); torque ceiling @0.8 g m0=400/m1=2000/m2=330; feature-enable +0xF2 = [1,0,0].
  **m=1 is the most permissive** (loose yaw + largest TCS slip + highest torque ceiling); m=2 tightest; m=0
  tight-traction/loose-yaw. m ≠ 0 only in MDM (`tcs_mode` 0x4030A2 = 3); there one EEPROM coding bit picks m1 vs m2.
  **This is where the "motorsport permissiveness" lives — DSC-mode logic, not the ABS/TCS slip-target bytes.**
  M3 AYC block is byte-identical to the 1M (mode tables are not M-specific).
- **[verified, M3]** Driver mode → m: 0x4049B4 → 0x4030A2 (off → 2, on → 1, MDM → 3), so DSC on and DSC off run
  m = 0 and MDM runs m1 or m2 by coding byte 10 bit 5 ("DSC driver mode" near the end). **[needs-hw]** Which of m1 /
  m2 a stock M3 coding selects needs its EEPROM value.

## F-CAN (1M)

- **[verified]** Second CAN controller 0x00FA0000 (F-CAN), polled from 0x0C4B4C every 10 ms.
  Tables: header 0xF5CCB (14 TX / 18 RX), messages 0xF5CE5 (23 B, 4-byte ID), signals 0xF5FC5,
  variables 0xF61D8. TX IDs 0x080, 0x0CE, 0x11E, 0x130, 0x374, 0x790/791/797/798, 0x7D4–0x7D8;
  RX IDs 0x0CD, 0x0D1, 0x0D4 (DSC sensor cluster), 0x0C9 (steering angle), 0x118/0x11F (AFS),
  0x140, 0x0C8, 0x194, 0x1D6, 0x2A6, 0x1D9, 0x78E/78F, 0x7DC–0x7DF.

## Scope note

Stability-control calibration (the ABS/TCS slip & deceleration targets, and the AYC/BCO/COA
blocks) is **in scope** as of 2026-10-02 at the user's direction; see the "ABS calibration" and
"TCS calibration" sections below. Valve/pump actuation internals remain undocumented. All work is
static RE of the user's own ECU; images are research-only and cannot be flashed (ROM self-test +
BMY signature), as the XDF warns.

## CAN (1M, verified from flash tables + code)

- **[verified]** CAN config at 0xD82D5: 20 TX + 27 RX messages, 32 hardware mailboxes
  (TX 0–4, RX 5–31). Message records 23 B at 0xD82F5, signal descriptors 5 B at 0xD872E,
  variable table 8 B at 0xD8C34 (per-variable callback). Full dump:
  `analysis/7846411A_can_map.md` (`tools/can_map.py`).
- **[verified]** Cross-check against known E9x PT-CAN behavior: TX includes 0x0CE (wheel speeds,
  DLC 8, 20 ms, four 16-bit signals), 0x0C4 (DLC 7), 0x19E, 0x1A0 (20 ms), 0x1A6 (100 ms),
  0x4A9/0x5A9 (NM) and 0x629 (diag response) for diag address 0x29 (matches WinKFP "29").
  RX includes 0x0A8/0x0A9/0x0AA, 0x130, 0x1B4, 0x330, 0x380 (DLC 7), 0x3B0 (DLC 2),
  0x480/0x580 (mask 0x780), 0x6F1 (tester, mask 0x7F0).
- **[verified]** 0x0CE value = wheel speed (s16 at 0x0040BF1A + 0x40·w, 0.01 km/h) × 4/25,
  clamped to 4800 (300 km/h at 1/16 km/h), 0x8000 when the wheel is faulted (0x400952[w] b0 or 0x40288C b2), 0
  at or below the floor 0x4032D0 (≈0.6 km/h), and **negated when direction is valid and reverse** (direction bits
  update only below 55 km/h; above 70 km/h the latched bit is used unchecked). Order FL, FR, RL, RR. Decode: `analysis/CAN_TX_TABLE_7846816A.md`, "Frame 0x0CE".
- **[verified]** Direction state in 0x004029D9 (bits 0–3 valid, 4–7 forward). `wheel_direction_valid` needs
  0x004029DA bit 5 set, fewer than 2 direction-faulted wheels, 0x004029D6 (wheel mask) **non-zero** and the wheel
  not faulted. Then it returns 1 outright above 70.00 km/h, else the valid bit (corrected 2026-10-15: an earlier
  entry said direction is only reported ≤ 70 km/h). Sole writer: 1M `sub_0B9118` / M3 0xB9330. Full M3 decode:
  `analysis/7846816A_symbols.md`, "Wheel direction". (Corrected: an earlier entry said D6 == 0.)
- Named functions/variables: `analysis/7846411A_symbols.md`.

## Diagnostics / coding storage (1M)

- **[verified]** KWP2000 service table at 0xF33A8 (23 × 12 B): SIDs 0x14 10 20 18 17 1A 21 27 30
  31 3B 22 2E 3E 33 29 28 81 82 11 09 23 3D with handler addresses.
- **[verified]** NVM is a 2 KiB logical address space (0x000–0x7FF): 0x3D WriteMemoryByAddress
  rejects addresses ≥ 0x800 (NRC 0x31); 0x23 in state 3 reads it (≤ 4 bytes per request).
  Whether NCS coding uses this path or 0x2E/0x3B with a block id (NCS records contain a recurring
  `30 00` field, maybe block 0x3000) is still open.
- **[verified]** 0x23 cannot dump arbitrary RAM/flash: outside the logical EEPROM it only serves
  two fixed descriptor blocks (state 7, address 0 or 18).
- **[verified]** NVM reads go through 0x06EA74 → drivers 0x0D5400/0x0D5590 programming the
  0x00DB0000 block, which has a queue-RAM layout typical of a queued SPI controller. Inference
  (med): the coding EEPROM is an external SPI device.
- **[verified]** **No application/diagnostic path reads the bootloader region (0x0–0x47FFF).** Structural:
  no read primitive accepts a caller-supplied CPU address. 0x23 (handler 0x0B2EFA) serves only the logical
  NVM (format 3) or two fixed records (format 7, baseline state only); 0x31 (0x0B2904) is actuator/test
  routines with no memory-return; the mfg protocol reads no memory; there is no upload service (no
  0x34/35/36/37). Unlocking 0x27 does not create a read primitive. Getting the bootloader is therefore a
  hardware task (chip read-out / JTAG), or moot if a GT4/alternative signed image is obtained. Detail:
  `analysis/agents/btldread/REPORT.md`.
- **[verified / partial]** **SecurityAccess 0x27** (handler 0x0B12AA) is a fixed, image-derived seed→key
  with no per-unit secret (INPA/EDIABAS-reproducible), granting one coding-access level (0x409513=3), NOT a
  memory read. Seed `= (u16 @0x40095C counter) XOR 0x3008`, forced to 0x53A1 if zero (0x3008 = bytes at
  0xF6678/9, just after the "AZ2RAB00039" ID record) — **verified**. Key = `ROR16(seed,3)` → per-bit
  swap/complement network → XOR a constant from the same 0xF6674 record region; the **exact key-side XOR
  constant and bit-network are not yet verified** (an agent's "0x4241/0x4142 from ID bytes" reading was wrong)
  and the full algorithm needs validation against a live INPA 0x27 seed/key capture.

## Wheel-speed sensors

- **★ CURRENT STATUS [verified, bench 2026-10-06]: E46 (2-level, 7/14 mA) sensors run on the M3 MK60E5 with a
  firmware-only patch, on all four wheels.** Four byte patches plus a re-sign:
  - ASIC sensor-mode mask 0x28C → 0 (file 0xDF22C).
  - Both-edge timer capture, mode 0x91 → 0xA1 (file 0x77524).
  - Direction mask stored as 0 (file 0xC13C4).
  - Presence mode 2 (file 0x7DA57).
  - Exact bytes, rationale and procedure: **`docs/E46_SENSOR_FIRMWARE_PATCH.md`**.
  - For the stock firmware with an AK-emulating converter instead (no patches): the AK bits to send, plus the
    timing rules, are in **`docs/AK_BITS_EXPECTED.md`** (2026-10-15).
  - Older entries saying non-VDA sensors need hardware are superseded.
- **[user]** The 1M uses E9x wheel-speed sensors: active, with encoded data.
- **[user, corrected 2026-10-05]** The user does NOT own an E85 Z4 unit. E85 Z4 MK60E5 units work with
  E46 (2-level) sensors. (An earlier entry here wrongly said "the user's E85 unit".)
- **[source]** MK60E5 expects active Hall sensors with the VDA (AK) data stream: 28 mA speed
  pulse followed by 9 Manchester bits at 7/14 mA (magnetic strength, calibration, direction
  valid, direction, 3-bit air gap, parity). DF11i (7/14 mA PWM, direction + field strength,
  ~1.5 Hz standstill pulses) is a different active type
  ([MK60e5-Standalone](https://github.com/tomazcebul/MK60e5-Standalone), `MK60E5-Components/WheelSpeedSensors.md`).

## Wheel-speed chain (1M; full detail in `analysis/agents/wss/REPORT.md`)

- **[verified]** Capture config is hard-coded: 0x0D5CDC(ch, 0x91) for ch 0–3 at 0x06F5D4..EE.
- **[verified]** BFU calibration block at 0x41F04 (`BFU\x01`): u16 at 0x41F10..0x41F1A =
  100, 72, 2073, 2073, 48, 48. Agent reading (high use, med units): standstill threshold 72
  (0.01 km/h), circumference front/rear 2073 (mm), tooth count front/rear 48.
- **[verified]** 0x0B91AC `movi r2,15` → 0x075ABA → 0x004029D6 (direction-expected wheel mask).
  Agent reading: this literal is the only "direction expected" control found; 0 would disable
  direction checking.
- **[verified]** B9118 thresholds are literal-pool words used only inside B9118: 0xB9450 5500,
  0xB9484/88 401/5099, 0xB9504/08 2501/2999, 0xB950C 12000, 0xB9510 2500.
- **[agent, high]** VDA data bits are NOT decoded by the MCU. An external sensor-interface ASIC
  on QSPI (0x00DB0000 chip select 5; reader 0x0D52E8, poll 0x06FD70) returns per-wheel words
  with direction, direction-valid and 3-bit air gap. The edge ISRs only time speed pulses.
  Chip select 2 on the same QSPI looks like the EEPROM.
- **[agent, high]** Without direction-capable sensors the stock code counts invalid direction
  per wheel (4.01–55 km/h) and logs fault ids 0x000n0040 (table 0xF5A74) at 175 counts.
- **[agent, high]** Speed: 0x0752B8 → 0x0040094A[w] (raw), filtered by 0x0B65DC into
  0x0040BF1A + 0x40·w. Wheel index 0/1 = front, 2/3 = rear (via circumference choice).
  Index → ISR: 0 = 0x070D2C (F8+8E), 1 = 0x070E3C (D8+8E), 2 = 0x070EC6 (D8+9E),
  3 = 0x070DB2 (F8+9E).

## M3 (7846816A) decode — cycle 1 [verified 2026-10-04]

Byte-verified against the M3 image by the main session. Symbols: `analysis/7846816A_symbols.md`;
XDF: `xdf/MK60E5_7846816A.xdf` (vehicle-model + slip/decel categories); disasm `analysis/7846816A_main.lst`.

- **[verified]** M3 reset handler 0x6C906 (vs 1M 0x6C9B2). App CPU 0x40000–0xF6A23. Same M·CORE platform.
- **[verified]** **SRAM = 48 KB @ 0x400000–0x40C000.** Startup zero loop 0x6C9CC spans exactly
  [0x400000,0x40C000) (0x3000 words); topmost global struct ends at 0x40C000; same bound reused at
  0x6F7E6/0x737A8/0x77794. Separate peripheral RAM zeroed next: 0xFFF82000 (4 KB), 0xFFF84000 (16 KB),
  reg 0xFFF80000 (IPSBAR aperture, not CPU SRAM). MMC2114 relative has 8 KB → SC560002 ~6×.
- **[verified]** **Unallocated SRAM hole: [0x40959C, 0x40BF00) = 0x2564 = 9572 B (~9.3 KB), no refs.**
  Globals stack up from 0x400000 to 0x40959B (last = the `31 08` auth scratch: challenge [0x40957C,+16)
  + digest [0x40958C,+16), live only inside `sub_0B3F3E`); the lone top struct (wheel data, pinned by
  `sub_043DF0` via ptr 0x400978) sits at 0x40BF00 and grows up to 0x40C000. Hole confirmed 3 ways:
  Ghidra ref analysis (resolves computed bases), literal scan (zero lands inside), and M·CORE 4-bit
  scaled offsets (~60 B max, can't reach across 9 KB). **Zeroed every reset (0x6C9CC) → runtime scratch
  only, not NVM-backed; not stack-adjacent (stacks at bottom, top struct grows up), no heap.** 7846816A
  (M3) only. Doc: analysis/BOOTLOADER_SERVICES_7846816A.md §Unallocated SRAM hole.
- **[verified]** **BL allowlist (0x19BB4) permits sectors to 0x180000**, per full decode (19 sectors):
  one 16 KB @0x10000, eight 16 KB 0x20000–0x40000, two 128 KB 0x40000–0x80000, eight 128 KB
  0x80000–0x180000. **BUT [corrected 2026-10-14]** the allowlist is the BL firmware's permit table, not
  proof of silicon: the OEM .0pa uses only **bank 0 (~1 MB, phys 0x0–0xFFFFF)**, app fills it to phys
  0xFEA23 (CPU 0xF6A23); cal/EEPROM live in separate banks phys 0xDF0000/0xFF0000; **no OEM content at
  0x100000–0x180000**. Confirmed free & flashable = only ~5.6 KB (CPU 0xF6A24–0xF7FFF, end of bank 0,
  not in any stock segment) + reclaimable feature space. The ~544 KB CPU 0xF8000–0x180000 the allowlist
  implies is **[open/unconfirmed]** — bench test before use. (Earlier "~560 KB free to 0x180000" was an
  overstatement from the allowlist alone.)
- **[verified]** LOCK header 0x40200–0x40300 (fixed-offset, 0xFF-padded): ptr 0x40230→ID record 0xF68FC;
  ptr 0x40234→block/var table 0xD77C8; ptr 0x40238→MISR range table 0xD71EC (entries at 0xD71F4);
  ptr 0x402F4→BMY block 0xF6924; u32 0x402F8=stored checksum; 0x40300=cal directory. BMY & MISR ranges
  are image-located via these pointers. Appended code stays verifiable with no new secret: BMY RSA range
  = [0x40000:marker@0x402F4]; app MISR via in-image table 0xD71F4; SBL boot MISR (sub 0x4ce8) hardcoded
  to 0x180000. All recomputable via tools/bmy_resign.py + rsa-sig.json. Map:
  analysis/BOOTLOADER_SERVICES_7846816A.md.
- **[verified 2026-10-14, static]** Boot-time integrity enforcement = the lightweight **boot-descriptor
  MISR**, not the full image. Reset 0x2D8 MISRs the 0x200–0x248 descriptor vs [0x244]=0x42E5BD74
  (mismatch → params→0xFFFFFFFF); SBL driver 0x4690 MISRs the 0x8000 copy vs [0x802C]=0xF7C43DF9. Launch
  = validated descriptor → sub 0x4f2c → sub 0x4da6 (mtcr cr1; jmp). Live vectors route to 0x14000 (BL
  diag): [0x234]=0xFFEC, [0xFFEC]=0x66666666, [0xFFE8]=0x00014000, app slots [0x801C/20/24]=0xFFFFFFFF.
  Full 0x40000–0x180000 MISR engine (sub 0x4ce8/0x417e) exists + result read back (0x4B64), but **no
  RSA/BMY modexp on the reset→launch path** — supports "BMY not enforced at load." Likely: app runs only
  via a descriptor blessed after a programming-time verify; failure → fall back to BL diag (reroute, not
  brick). [open] whether the full scan runs unconditionally every boot vs. only on a flash/verify command
  (needs tracing SBL entry ptrs [0x400C]/[0x4004], or bench).
- **[verified]** M3 calibration directory at 0x40300 (ver 2, 12 blocks): ABS 0x4039C/0xB0A, CSI 0x40EA8/0x114,
  TCS 0x40FBC/0x1D4, AYC 0x41190/0x5C6, BCO 0x41758/0x220, COA 0x41978/0x36C, BFU 0x41CE4/0x1C,
  VAR 0x41D00/0xE, DDS 0x41D10/0x118, CSW 0x41E28/0x1A, LVC 0x41E44/0x5E0, VMO 0x42424/0x6C.
- **[verified]** **M3 vehicle-model variant table**: 12 s16 per parameter, stride 2, indexed by coding
  variant `0x4031AA+1` (0..11). Loaders `vehmodel_load_singletrack_coeffs` 0x5DE44 and
  `vehmodel_load_axle_derived` 0x5E424 → RAM 0x400AA4..0x400AF8. Only **7 distinct variants**: v0–4 == v5–9,
  v10/v11 unique. Meaning [user-supplied]: v0 sedan, v1 Custom ESM, v3 coupe, v4 convertible; v5/v8/v9 =
  Competition sedan/coupe/convertible (hence the duplication); **v10 GTS coupe, v11 GTS sedan**; v2/v6/v7
  not identified. Rows (v0..v11):
  - l_f 0xD6F42 Q10 m = {1413,1418,1439,1403,1501, ×dup, 1352,1362}; l_r 0xD6F5A Q10 m sums with l_f to
    2826/2827 (= 2.760 m wheelbase, exact E9x M3).
  - mass 0xD6F72 kg = {1787,1814,1845,1731,1947, ×dup, 1691,1674}.
  - Jz 0xD6F8A kg·m² = {2999,3203,2645,3006,3283, ×dup, 2671,3082} (Jz/m≈1.68 m² confirms units).
  - Cf 0xD6ECA / Cr 0xD6EE2 cornering stiffness (Cr·l_r−Cf·l_f understeer term in 0x5E424 fixes the roles;
    **units unresolved** — N/deg gives v_ch≈41 m/s (plausible), N/rad too low). Cr>Cf every variant → understeer.
  - track front 0xD6FA2 = **1.538 m** (Q10: 1575/1024; = the real M3 front track), track rear 0xD6FBA = 1.536 m
    (1573/1024). Q10 metres, not mm.
  - override-enable flag 0xD7032 = 0 for all 12 → the 0xD6E3A.. override rows are dead on this ROM.
- **[verified]** **M3 ABS entry/continue slip threshold** curve at 0x40DB6 (reader `curve_interp_s16` 0x710FC;
  `abs_entry_slip_eval` 0x54F4A/55062/552DA): lo0,hi900,n2,bp5000,c=150/115,k=−4/+3 (Q10). x = vref
  (0x408DA8). Evaluates 150/143/131/144/158/173/188/202 (0.01 km/h) at vref 0/20/50/100/150/200/250/300 km/h
  ≈ 1.3–2.0 km/h slip — same shape/values as the 1M. Debounce count at 0x40DB4 = 2.
- **[verified]** **M3 ABS decel scalars** (ABS=0x4039C): gain front +0x27E=40, rear +0x280=25, floor +0x282=−240,
  base +0x284=−116; floor<20 km/h +0x2A8 (12×: −127, then −120); floor<60 km/h +0x2C0 (12×: −132×10, −140×2);
  ladder +0x76C = {−140,−90,−40,−210,−350,−490}; staged A +0xAC2 {−62,−78,−94}, staged B +0xB02 {−25,−44,−62}.
  Front speed-term curve family 0x40412+0x28·m (m=0..11, n6), rear single 0x405F2 (n6), g-term family
  0x40674+0x40·m (n10). **Variants 0–9 identical; 10/11 more permissive at high speed** (confirms m3cal).
- **[verified]** **M3 TCS drive-slip** threshold: set B 0xF625C+0x22·mode (default), set A 0xF61F6+0x22·mode
  (set A when 0x402F6C bit4), mode = `0x4031AA+7` (0..2); reader `tcs_driveslip_curve` 0xC795E, x = vref 0x403066.
  B m0 evaluates {1500,270,101,226,379,1180,2842} (0.01 km/h) at vref {0,15,25,50,80,100,150} — matches 1M.
  **TCS caps**: 6 curves 0xF654C+0x22·j (j=0..5), reader `tcs_cap_eval` 0xCB576 (÷20). All relocated to const ROM.
- **[verified]** Interpolator `curve_interp_s16` 0x710FC: segment i = count of breakpoints **strictly** below x;
  `y = clamp(c[i] + trunc(x·k[i]/1024), lo, hi)` (truncate toward zero, not floor). Corrects the 1M floor note.
- **[verified]** **M3 known-input interface = 1M, relocated** (byte-pattern + opcode diff; `analysis/agents/m3can/`).
  Main-CAN config header 0xD7F45 (20 TX / 27 RX), messages 0xD7F65 (23 B), signals 0xD839E (5 B), variables
  0xD88C0 (8 B). F-CAN header **0xF59C3 (14 TX / 18 RX)**, messages 0xF59DD, signals 0xF5CBD, variables 0xF5ED0
  (shift −0x308 from 1M 0xF5CCB; **corrects cycle-1's erroneous 0xED9C3/20-24** — that address is not a table);
  poll fn 0xC4D64. **Every CAN id/DLC/period/mailbox is byte-identical to the 1M** (47 main + 32 F-CAN); only per-signal variable ids and
  callback addresses relocate. (F-CAN variable table not yet located.) KWP2000 service table 0xF30A0 (23×12 B);
  all 23 SID→handler entries recovered (e.g. 0x27→0xB14C2, 0x22→0xB23CC, 0x23→0xB3112, 0x3D→0xB324E). Full
  map in `analysis/7846816A_symbols.md`.
- **[verified]** **M3 SecurityAccess 0x27**: `seed = (u16 @0x40095C) XOR 0x1B09` (forced 0x53A1 if zero); the
  XOR const is ID-record bytes 0xF6910/11 = `09 1B` read little-endian (exactly the 1M scheme, whose const
  0x3008 = bytes `08 30`). M3 ID record 0xF690C = ECU **"AZ1RAE00008"** (1M "AZ2RAB00039"). Key network
  opcode-identical to 1M; granted coding level written to RAM 0x409537 = 3. The diag/security scratch-RAM
  block is shifted **+0x24** vs the 1M; coding/EEPROM-mirror RAM (0x4031xx, 0x40095C) is unshifted.
- **[verified]** **M3 coding/NVM path**: `coding_field_read` 0xCFC00 (= 1M 0xD0240, clean opcode diff) reads
  the packed coding block at unshifted RAM 0x4031F4/F6; `nvm_queue_job` 0x6E16C, `nvm_read_sync` 0x6E9C4; SPI
  drivers 0x0D4DC0/0x0D4F50 on the 0xDB0000 queued-SPI block (CS2 = coding EEPROM). 0x22 DIDs checked are the
  same 0x2501/0x1601/0x2502 as the 1M. Active coding variant is EEPROM/RAM state, not in the flash image.
- **[verified, static]** **EEPROM layout**: block table 0xD7424 (63 × {offset,len}; 1M 0xD77B4 identical), 27
  blocks tiling 0x000–0x7FF; job id = (blk<<4)|sub-id. Raw 48-byte coding = block 10 @ **0x400–0x42F**; the
  unpacked image the app runs from (0x4030DC / 0x4031AA / 0x4031B6) is block 7 @ 0x44B–0x4AF; ident data block 24
  @ 0x322–0x3FF; DTC memory block 5 @ 0x068; DDS data block 14 @ 0x510. Bytes are stored inverted on the chip.
  `0x409564` (w564) loads from 0x3BA–0x3BD (tail of the `1A 89` string), not 0x322. Full map:
  `analysis/EEPROM_MAP_7846816A.md`.
  There is no separate geometry accessor: M3 0x8E25E = 1M 0x8E066 is mid-function code,
  never called; the loaders read `0x4031AA+1` directly. M3 `0x8E066(id, sel)` is `state_nibble_get`, a 3-bit
  operating-state getter (0x401FAC for id 24) whose callers compare it with 2–4.)
- **[verified, static 2026-10-21]** **M3 coding write validator** `0xCF432 → 0xD02E6`: clears the active image,
  then five stages over the RX buffer 0x403320 (checksum 0xCFDB8, field unpack/limits 0xCFDD8 + 0xCFADC, flag
  words A/B 0xCFF1A, word array 0xD0064, feature row 0xD024C → 0xCF5D8). Any failure → fault 0xC0002, image
  zeroed, image check byte poisoned, NRC 0x31; pass → image resealed (check byte = XOR + 1). The raw bytes are not
  kept in RAM (reads go straight to the diag buffer 0x40943E). f+6 (feature row) is derived from c3 b2/b3 and
  c13 b5/b6; f+7 is the run-time DSC mode (`dsc_mode_select` 0xCF2E8). If `0x8E066(24,1)` = 4 the validator is
  skipped and the raw bytes are stored unchecked without updating the active image. Detail:
  `analysis/CODING_BYTES_7846816A.md`; symbols § Coding write validator.

### Cycle 2 [verified 2026-10-04] — control, wheel-speed, AYC/yaw (symbols in `analysis/7846816A_symbols.md`)

- **[verified]** The whole ABS controller (1M 0x44000–0x5E000, 196 fns) ports to the M3 by a constant shift
  (−0x220 below 0x4C000, −0x200 above); **all opcode-identical except `abs_decel_threshold_builder` 0x47BDC**
  (M3-rewritten: variant-indexed curves 0x40412/405F2/40674 by `0x4031AA+1`, vs the 1M's fixed curves). The
  `control_dispatcher` 0x8CCB8 is a **flat 41-call per-frame sequencer, not a jump table**. ABS/vref working RAM
  is shifted **+0x24** (vref 0x408DA8, decision code 0x408DDE). vref integrator + wheel-accel code and constants
  (literal 0xE287 = 57991, two-frame mean ·2.8316, 0.01 g) are unchanged — closes the 1M "wheel-accel ±158" conflict:
  normal range is ±16 g before clamp, so the dump stages (−62…) are reachable.
- **[verified]** M3 **tunable ABS control** scalars: apply ramp 0x403A8=400, dump reductions 0x40E64/66/68=1000/
  1500/2000, reapply nudge 0x40D90=80, decel set A/B enables 0x40E94/0x40E9C=1, cornering limits 0x40DCE=126/8/1748.
  Hard-coded speed-dependent ROM curves relocated to **0xD6AFC–0xD6D50, byte-identical to 1M 0xD713C–0xD7390**.
  Clamps 25000/−8000, delta clamp ±5714, accel scale 57991 (0xE287) and the vref rise/fall/snap values are code literals
  (patch-only, not calibratable). (The 1M 0xDA2F0 scalar block has matching *referenced* values but is not a clean
  contiguous relocation — left unverified.)
- **[verified]** M3 **wheel-speed chain**: edge ISRs vec 56/57/58/59 → handlers 0x70E6A/0x70D56/0x70DE0/0x70CD0
  (opcode-identical to 1M); `wheel_speed_update` 0x7525C, `wheel_speed_filter` 0xB67F4, `wheel_direction_update`
  0xB9330. **BFU geometry identical to the 1M** (standstill 72, circumference 2073 mm, 48 teeth front+rear) — the
  M3 is NOT configured for different wheels at the BFU level. VDA hard-configured on all 4 channels; direction mask
  15; invert pair 05/09 at 0xD766C. VMO monitor block 0x42424 (window threshold 2000, %-scales 85/75).
- **[verified]** M3 **AYC / yaw control**: `yaw_observer` 0x5EBC4 (variant-indexed via per-variant arrays
  0x415F8/0x41610/0x41628), `yaw_pd_moment` 0x5F7BA, `engine_torque_request` 0x65078, `yaw_ref_closedform` 0x90E5C,
  `dsc_mode_select` 0xCF2E8. AYC block 0x41190: entry base A/B = 1396/2792, per-mode entry/hold ceilings
  (10471/10471/8028 and 9773/9773/7330), speed-factor and P-gain % curves per mode, **torque ceiling per mode
  m0=150/400, m1=200/2000, m2=180/330** (feature-enable [1,0,0] relocated to 0xD6DA4). **m=1 is the most
  permissive (torque ceiling 2000)** — consistent with the 1M; AYC tables are not M-specific except three
  observer scalars that became 12-way variant arrays.
- **[verified]** **DSC mode** m∈{0,1,2} stored at 0x4031B1 (= coding 0x4031AA+7, shared with the TCS mode index):
  `m=0 if 0x4030A4∈{1,4,5} or 0x4030A2≠3; else m=2 if (0x4031F4 & 0x80) else 1`. The m→driver-mode (DSC/DTC/MDM/OFF)
  mapping needs live EEPROM/RAM state (not static).
- **[verified]** **M3 v_ch (characteristic speed) is variant-dependent** — runtime-derived by loader 0x5E424 from
  the variant vehicle model (not a stored constant). Per variant: {0/5:128.8, 1/6:109.1, 2/7:136.8, 3/8:109.0,
  4/9:121.8, 10:142.1, 11:105.5} km/h (replica matches the 1M's 97.65 exactly). The M3 reference yaw model is
  flatter in gain-vs-speed than the 1M (v_ch 8–45% higher). **[agent, med]** on the exact km/h (±1 LSB rounding).

### Cycle 3 [verified 2026-10-04] — CSI/steering, brake coding, DDS/RPA, LVC, fault manager

- **[verified]** **M3 CSI block 0x40EA8 (len 0x114) GREW +0x62 vs the 1M and its steering-ratio curve changed.**
  Steering ratio = y/1024 (:1): M3 ~15.9 at centre → 12.6 (vs 1M 14.6 → 12.5), 3 curve sets selected by coding
  `0x4031AA+5` (NCS: 0 = E90, 2 = E92/E93; set 1 is a copy of set 0); x = offset-corrected steering-wheel angle
  0x402132 in counts. Three former scalars became 12-way
  per-variant sign tables (all −1). The 144-byte tail is byte-identical to the 1M. `steer_ratio_convert` 0x9032E.
- **[verified]** **Steering input**: F-CAN RX **0x0C9** (DLC8, 1 ms, mailbox 16) sig 43 = angle → handler 0xC5C78
  (·1029/1024 → RAM 0x401644). Sensor cluster 0x0CD/0x0D1 → `cluster_sensor_get` idx0..5 (yaw/ay, 0x402F1C..26).
  Closed-form r_ref confirmed on the M3 (`yaw_ref_closedform` 0x90E5C): v_ch enters via RAM 0x400AE8/AEA (variant
  model), no CSI constant in the denominator; r·v clamp ≈1.24 g (hard-coded). Yaw-rate LSB = 1/20000 rad/s (derivation in
  Cycle 7); steering ≈ 0.044 deg/LSB **[unverified]**.
- **[verified]** **Brake COA 0x41978 (0x36C) and BCO 0x41758 (0x220) bodies are byte-identical to the 1M** — brake
  calibration is NOT retuned; coding only picks code 0 vs 1 per axle (`coding_unpack_block` 0xCFDD8: front +3 =
  (rec[2]>>3)&7, rear +4 = rec[2]&7; codes 2–7 undefined). COA p-V: shared pressure axis 0x41B4E (0..32700, 0.01
  bar), front volume sets 0x41B62/0x41B76, rear 0x41B8A/0x41B9E; gain curves 0x41A38/0x41AA4; BCO coded
  thresholds 0x41764. Rotor/piston geometry is folded into the p-V curves (confirms the 1M geom finding).
  `coa_vol_to_pressure` 0x819FE, `coa_pressure_to_vol` 0x816E8 (= 1M 0x81508), interpolator `interp_linear_xy` 0x7119E.
- **[verified]** **M3 DDS/RPA**: the Q12 sin/cos spectral tables (1M 0xDB2D8/0xDF158/0xE6E58/0xEACD8) are present,
  relocated −0x308 (M3 0xDAFD0/0xDEE50/0xE6B50/0xEA9D0), **byte-identical**. `rpa_correlate_step` 0xA623A (= 1M
  0xA6022) is a per-wheel 40-tap sin/cos quadrature correlator; `rpa_state_machine` 0xA7140 (per-wheel 400-step,
  hour counter ÷3600, coding-gated). DDS block 0x41D10 body byte-identical to the 1M (enable overrides 0x41D48/
  0x41D4A gate it against coding bits 0x4031F4/F6 bit4). The RPA indirect-tyre-deflation reading stays a hypothesis
  (correlator + tables are definite; no tyre-specific code confirmed).
- **[verified]** **LVC block 0x41E44 (len 0x5E0) body byte-identical to the 1M EXCEPT one scalar 0x4226A = 75 (1M
  50)** — the only M3-specific calibration difference in the DDS/LVC/FSF region (a hold/delay count, ~0.75 s vs 0.5 s
  if the cycle is 10 ms). `lvc_main` 0xBFB6C runs a 5-level speed ladder off max wheel speed; "LVC" expansion
  undetermined. **[2026-10-14] LVC is very likely the hill-start assist**: LVC code reads the HSA-level coding
  f+9 (0xC0D44) and gates on `coded_feature(11)` = hill-start (coding c13 b6) at 0xC0D5E. It drives CAN 0x19E
  byte 3 bit 2 via 0x402BE8 (see `analysis/CAN_TX_TABLE_7846816A.md`, "Frame 0x19E"). Per-coding-variant arrays at 0x422F8.. (indexed by 0x4031AA+9).
- **[verified]** **Fault manager** `fault_set` 0xB427C (= 1M 0xB4064): fault id = group<<16 | mask16, latched in the
  u16 array 0x402838[group], NVM-pending bits in 0x408CBC, NVM block id 0x31. `monitoring_main` 0xB3FC0 dispatches
  ~26 sub-monitors. Direction-fault id table 0xF576C = {0x00020040, 0x00030040, 0x00040040, 0x00050040} (per wheel).
  No fault-id→BMW-DTC-number translation table was found in these ranges. Mode/state table at 0xDA43C (12 records,
  id→callback: e.g. id 0x11→LVC, 0x0D→DDS, 0x01/0x16→TCS, 0x02/0x13→BCO).

### Cycle 4 [verified 2026-10-04] — OS/scheduler, ROM self-test, TCS torque path, actuation

- **[verified]** **M3 ROM self-test (MISR) — recompute path for re-signing edited calibrations.** Range table at
  **0xD71F4** = {[0x40000,0x402F8), [0x40300,**0x4249C**), [0x424A0,0xF691C)}. The MISR (poly 0x00400007, seed 0,
  big-endian u32 feed, per word `s=((s<<1)^poly·(s>>31))^w`) **recomputes byte-exact** (main session) to the words
  stored at each end: 0x402F8→0x66E81879, **0x4249C→0x310A99BD** (the calibration range), 0xF691C→0xC791DCD2.
  **So after editing any M3 calibration, the word at 0x4249C must be recomputed and written** (else error 0x10004).
  The calibration range end moved from the 1M's 0x426BC to the M3's 0x4249C (M3 cal blocks are larger). This is the
  in-ECU MISR only; the 512-bit BMY RSA signature (resolved earlier, key in `rsa-sig.json`) is a separate layer.
  **Tooling (2026-10-04):** `tools/bmy_resign.py` now auto-detects the MISR range table (0xD7584 1M / 0xD71F4 M3),
  so `bmy_resign.py fix <bin>` does the full M3 re-sign (MISR words then BMY signature); `verify` on the M3 reports all
  three MISR OK + BMY VALID (digest fd6642311227ac53b02d3a605627e034), and `selftest` reproduces the stock integrity
  data byte-exact on both images. `tools/rom_misr.py` is a key-free MISR-only checker. So editing the M3 XDF → re-sign
  is a complete, verified path at both integrity layers.
- **[verified]** **M3 OS** = OSEK-style, 5 tasks (shift −0x220). Config: entries 0x424E0 {0x7857E,8E,A6,0x7871C,
  0x78562}, priorities 0x424F4 {3,0,1,2,4}, autostart 0x42514 {1,0,0,0,1}; identical to the 1M bar the entry
  addresses. Time-base vec60 → `isr_timeslot` 0x70A2A, 13-slot jump table 0x70ACC, slot deltas sum 10000 → **10 ms
  frame** (1 µs tick, timer prescale 79 confirmed on the M3); T1 4×/T2 10×/T3 1× per frame. Reset 0x6C906 → RAM clear,
  PLL 0x6C6D8, VBR, INTC 0xE10000. Runtime obj 0xD7B84 → task bodies T3 0x70FE4 / T2 0x70C58 / T1 0x70BFC.
- **[CORRECTED 2026-10-26 → `analysis/TCS_7846816A.md`]** 0xCD1E8 is the **MSR** PID (torque increase), not the TCS
  reduction PI; the clamps are D (0x41068/6A) and integrator-input (0x4106E/70); 0x0B6 type 1 = increase (MSR), 2 =
  reduction. The ASR reduction is channel B (0xCAD00 / 0xCAB4E). Original entry, kept for reference:
  **[verified]** **M3 TCS engine-torque-reduction path (resolves the long-standing open TCS question).** TCS PI
  `tcs_torque_pi` 0xCD1E8 (P clamp 0x41068/6A=±2500, I clamp 0x4106E/70=±200, gains 0x41072-78=180/100/60/25,
  slip-target curve 0x41046) → arbiter `dme_torque_request_compose` 0xCC2C2 (merges TCS/ASR + MSR + AYC
  `engine_torque_request` + external limit) → **CAN TX 0x0B6** (DSC→DME, DLC5, 20 ms): sig19/sig18 torque values
  (scale 0x333/4096 ≈ ÷5, inverse of the DME torque LSB), sig20 request type (0 none / 1 single=ASR / 2 pair),
  0x800 = no request, negative = torque reduction. TCS gross-slip limit (min(1500, 4000−vref)) and entry gates are
  **hard-coded** on the M3 (the 1M had them as cal fields). `tcs_reduction_floor` 0xCD7FE is retuned vs the 1M.
- **[verified data, inferred roles]** **M3 hydraulic actuation layer** (previously undocumented): **12 solenoid
  channels** (mask table 0xD7634; test order 0xF2EF0 = [0,4,1,5,2,6,3,7,8,9,10,11]). ch0-3 inlet valves (analog
  current, driven over QSPI CS5 via `asic_reg_xfer32` 0xD4A30 to a combined sensor+valve ASIC), ch4-7 outlet
  (digital, CS4 latch via `spi_cs4_out16` 0xD4BF4), ch8-11 USV/HSV circuit valves — channel roles **inferred**.
  `valve_pulse_sequencer` 0x853A8 builds a 10-step current profile per wheel from inlet mode {hold/build/release};
  pump motor is a **timer-PWM** on module 0xF80000 (`pump_motor_control` 0x88EC0, 4000 ticks/level, level 0..15),
  not SPI. Actuation entry = dispatcher slot 32 `hydraulic_actuation_pipeline` 0x843BC. **Tunable (COA block):**
  valve start offsets 0x41A72/74 (40/20), build gains 0x41A76/78 (800/350), pump cal 0x419D4/D8/DA (0/100/50).
  Hold/boost currents (1100/1524/1532), ×51/400 scale and pump tick/level are **code literals** (patch-only). Current
  unit (~mA) and valve polarity are unverified. Dispatcher 0x8CCB8 = flat 41-slot sequencer; slots 0-39 named (med).

### Cycle 5 [verified 2026-10-04] — CAN signal dictionary, pressure/volume model, CSW/VAR/FSF, lamps

- **[verified backbone, inferred semantics]** **Full CAN signal dictionary** for both buses (`analysis/agents/m3cansig/`;
  signal-table layout re-walked byte-exact). **DME↔DSC engine-torque handshake:** RX **0x0A8** (→0x401146, "indicated
  torque"), **0x0AA** (→0x401144, "driver-demand", + pedal byte →0x401142), **0x0A9** (→0x401148 sign-flipped,
  engine-drag/MSR) — each a 12-bit signed field scaled ×5 into an internal unit (= raw LSB ÷5; absolute LSB unverified,
  ~0.1% ref torque). `S = 0x4030A0>>6` converts wheel-torque↔engine-%. DSC reply = **TX 0x0B6** (·0x333/4096 ≈ ÷5, the
  exact inverse). Engine RPM on 0x0AA bytes4-5 (→0x40113E), gear on **0x0BA** nibble (M-DCT 7-speed jump table 0x7C13C
  →0x4010F7). **All main-CAN TX carry a checksum** = low8(Σ payload + CAN-id) in the last signal (`can_tx_checksum8`
  0x7D24C) + a 0..14 alive counter. Steering relayed on TX 0x0C4 from F-CAN 0x0C9. Yaw/ay from F-CAN 0x0CD/0x0D1 are
  stored raw (sensor LSB not statically resolvable). No outside-temp message; no CAN brake-pressure RX.
- **[verified]** **DSC warning-lamp state is CAN-only** (TX **0x19E**), built by `indicator_lamp_output_update` 0x812FA
  from a 14-handler table 0xD9FB4 into a 3-byte lamp vector 0x40165E. **There is NO GPIO/brake-lamp output in the DSC.**
  Physical lamp↔bit mapping needs the cluster side (not statically resolvable).
- **[verified]** **The brake-pressure control is a VOLUME-DOMAIN hydraulic model** (`hydraulic_model_step` 0x82EF4,
  dispatcher slot 8, 10 ms), not a simple pressure integrator. Per wheel it tracks a modelled volume V (RAM 0x4016DA[w])
  and can derive pressure PM (0x4016E2[w]) through the COA p↔V curves; **in normal operation PM is overwritten each
  frame with the measured wheel-output pressure and V is re-synced to it** (`sub_082BC0`; see the pressure-sensing entry); valve flow Q = isqrt(|dp|)·open·k/4096 (clamp 2000),
  with a low-pressure accumulator per circuit. **The COA block carries the model coefficients** (byte-verified, tunable):
  k_in 0x41B26 (957/421), k_cross 0x41B2A (219/421), k_back 0x41B2E (705), k_out 0x41B30 (755/465), LPA pressure/volume
  curves 0x41B16/0x41B1E, pump supply-store cap 0x41B34 (1150) / fill rate 0x41B36 (100) (earlier misnamed "pump
  ramp/gain"; see "Pump volume model", 2026-10-16), pump flow curve 0x41B38, filter 0x41B4C (187), volume temp-comp 0x41AE4/F0.
  **Pressure unit = 0.01 bar**, pinned by CAN: 0x2B2 bytes 0–3 and 0x19E byte 6 transmit the internal values ÷100 as
  integer bar (consistent with LPA plateau 1.3-5.0 bar, pedal threshold 8 bar, request clamp 200 bar). Arbiter priority order (channel_owner_select 0x83720):
  18>5>4>6>8>1>2>3>14>13>0>11>12>17>20>16.
- **[verified]** **CSW** block 0x41E28: only +0x18 = 1562 has a code reader (a DDS/RPA per-wheel reference, 0x954E2
  region); the other six words are vestigial (no reader, 1M-identical). **VAR** 0x41D00: empty placeholder (payload 0,
  no reader). **FSF** 0xF57C4 (fault-memory config, outside the cal directory): NVM slot descriptors (ptr table 0xF57F8;
  blocks 0x31/0x1B1/0x1C1), a speed-dependent monitor (limit 0xF57D6/DA → fault 0x124000), per-mode clamp 0xF587E, a
  14-step speed ladder with no located consumer, and mask tables. FSF body byte-identical to the 1M. Fault history =
  14-entry ring at 0x4028E4 (`fault_history_push` 0xB4140).

### Cycle 6 [verified 2026-10-04] — ABS controller core, decision layer, inter-ECU inputs

- **[verified]** **ABS per-wheel pressure pipeline** (apply/hold/dump/reapply) fully named (~40 fns,
  `analysis/agents/m3abscore/`). Phase dispatch `abs_wheel_phase_dispatch` 0x504D0 switches on `rec[0]`:
  0xC0 pre-control 0x50894, 0x80 armed 0x50580, 0x09 hold 0x4CA3C (entry 0x57200), 0x11/0x15 reapply 0x4B680
  (step 0x581BA), 0x21 dump 0x4AAA8 (target 0x55F06). Pressure RAM per wheel: **PM 0x408F2A = copy of wheel
  pressure 0x4016E2[ch]** (measured wheel-output sensor; volume model during dump/sensor fault; writer `abs_pm_snapshot` 0x559CC), CMD 0x408F22 (commanded), LOCKEST 0x408FD0
  (lock-onset estimate, `abs_lockon_pressure_estimator` 0x5862C), PMMIN 0x408FC4. **Corrects cycle 5:** 0x408FD0
  is **min**-selected with PM, not max. Apply ramp (id 19) builds CMD +400/frame to 25000; **corrects cycle 2:**
  its vref gate (0x442AC) is **4 km/h** (0.01 km/h units), not 400 km/h. ABS never writes the volume model; it only
  submits CMD/RAMP/UP to the arbiter (`abs_emit_pressure_request` 0x446B6, id 1 or 11-rear).
- **[verified]** **ABS decision code 0x408DDE** (`abs_decision_classify` 0x51B54 → `abs_decision_resolve` 0x58B30):
  1 = no rear control; 16→8 = stepped/select-low rear build; 2 = pair-hold complete; 32 = yaw-limited build
  (0–100 % pressure lag during cornering, from sensor value between curves 0x40E26/0x40E0A — byte-verified);
  256 = cornering reapply; 64/128 transient within a cycle. Pair logic `abs_pair_logic` 0x54D9A (writes 32/1024/16/2).
- **[verified]** **ABS arming**: the real per-wheel arming threshold is the gross-slip curve at **0xD6CE2**
  (400 @0, ~599 @20-55 km/h, ~11 % of vref) with a persistence counter (≥5 counts; one cycle >50 km/h, three at
  20 km/h, never <10 km/h) — `abs_gross_slip_threshold` 0x52380. The small entry-slip curve 0x40DB6 (1.3-2.0 km/h)
  is used **only** inside the pair-logic partner test, not as the primary arming threshold. Phase SM `abs_phase_sm`
  0x4FC3C transitions re-verified. Event classifier 0x4D270 builds the per-wheel scratch via ~10 threshold helpers.
- **[verified]** **ABS pressure cal vs code**: tunable (ABS block, all = 1M) apply ramp 0x403A8=400, dump reductions
  0x40E64=1000/1500/2000, stage thresholds 0x40E5E/0x40E9E, reapply steps 0x40D5E/0x40D60=300/500. Hard-coded code
  literals (patch-only): clamps 25000 (0x61A8), −8000 (0xE0C0), 20000, 30000, 9000; hard-coded ROM dump-cap curves
  0xD6AFC/0xD6C76 (byte-identical to 1M). Pressure unit 0.01 bar.
- **[verified 2026-10-15]** **Full CAN RX decode: `analysis/CAN_RX_TABLE_7846816A.md`** (27 PT-CAN + 18 F-CAN
  frames, every signal, handler, timeout and the frame → DTC map). Key points: RX timeouts count in the 10 ms CAN
  task (50 = 500 ms; cluster/steering 100 ms). The CAN DTC id = 0x2000/0x3000 + 16·group + bit, with reason flags
  0x04 timeout / 0x02 alive / 0x08 checksum (e.g. D354–D357, D370–D373). **0x0BA (gear) is only processed with an
  automatic/DCT gearbox coded and 0x3B0 (reverse) only with a manual one** (`gearbox_type` 0x40114D from coding f+2).
  Dead frames: PT 0x0AC/0x0B4/0x0D5/0x1B4/0x388/0x2A6, F 0x118/0x11F (and F 0x194's payload).
  **PT-CAN message DTCs need ignition from 0x130**: every reporter checks 0x401163 b4, which `can_comm_state_update`
  0x794FC sets only 750 ms after `ignition_on` (0x400956 b6), plus ≈1.8 s after start-up. **[revised 2026-10-15]**
  `power_state_update` 0x72020 takes `ignition_on` from a valid 0x130 (byte 0 bits 2–3 = 1 → `terminal_state` 4).
  While 0x130 has never been received or has timed out (`ign_source_hw` 0x4009FF b0), it uses the hardware input
  0x400958 b5 = NOT bit 8 of the CS5 interface-chip status word 0x4009C8. **Bench:** with power only and no 0x130,
  an automatic-coded unit logs D35A + D354–D357, so that input reads "on" with power alone. So: valid 0x130 with
  ignition off → no CAN DTCs; no 0x130 → hardware input decides. The physical source of bit 8 is unknown.
  Detail: CAN_RX_TABLE "ignition gate".
- **[verified]** **DSC inputs (input-sources map, `analysis/agents/m3rx/`... text only)**: live powertrain RX = DME
  torque 0x0A8/0x0A9/0x0AA, gear 0x0BA, CAS 0x130; live chassis RX = steering 0x0C9, yaw/lat-g 0x0CD/0x0D1/0x0D4;
  NM node 0x29 on 0x480; tester 0x6F1. **Disabled**: the external torque-limit exchange (F-CAN 0x78F/0x78E) is gated
  by cal **0x4182A = 0** (verified; off in both M3 and 1M). **Dead**: RX 0x0AC/0x0B4/0x0D5/0x1B4/0x388 and F-CAN
  0x118/0x11F/0x194 have bare-return (`jmp r15`) setters — all signals discarded (**corrects the old FACTS note that
  0x118/0x11F were "AFS"**). The DSC also acts as a raw **F-CAN→PT-CAN gateway** for 0x0C8/0x194/0x1D6/0x2A6/0x1D9
  (`fcan_rx_queue_push` 0xC56D0 → `fcan_to_can_gateway_drain` 0x7A172).

### Cycle 7 [verified 2026-10-04] — sensor LSBs, AYC observer & distribution, RPA spectral algorithm

- **[verified]** **Internal sensor LSBs resolved.** Yaw-rate LSB = **1/20000 rad/s = 0.0028648 deg/s** (counts/deg·s⁻¹
  = 349.07); lateral-accel LSB = **1 mg** (g/1000); longitudinal from wheels 0x40200E = 0.01 g. Derivation: the
  wheel→yaw term 0x400AF4 = round(56888/track_Q10) = 36 gives R=20000 exactly, and the ay chain (0x90EE2:
  ay_int = r_int·V/70632, 88290=9.81·9000) closes to g/1000 only at R=20000. **Strong independent check: every AYC
  threshold is a round deg/s value** — entry base A/B 1396/2792 = **4.00 / 8.00 deg/s**, hold hysteresis 698 = 2.00,
  per-mode ceilings 10471/8028 = **30.0 / 23.0 deg/s**, entry-by-speed table 4.0–10.0 deg/s. Steering ≈ 0.044 deg/bit; the r·v friction
  clamp (0x4020EC ≤ 0x558C) = **1.27 g**. CAN output LSBs (sig63 ≈0.05 deg/s, sig62 ≈0.025 m/s²) are the only
  assumption-dependent items; the internal LSBs are not. Chains: `csi_cond_sensor0` 0x905E4 (yaw), 0x8FE70 (ay),
  both unity-gain (slew + LP + offset only). v_ch unchanged in km/h (V = 0.01 km/h confirmed).
- **[verified]** **Yaw observer `yaw_observer` 0x5EBC4** is a discrete nonlinear single-track observer (states β 0x400C42,
  r 0x400C44; 10 ms trapezoid integration). Per cycle: slip angles α_f/α_r (÷v), a per-variant front slip-angle lag
  (Q13 curve 0xD704A/0xD70AA, **variant-dependent — 10/11 differ**), a 3-regime front tyre force (linear → knee →
  saturated, knee from per-variant arrays 0x415F8 α_lim-base=1835 / 0x41610 F_k-scale=90 / 0x41628 μ-term=11905,
  17854 for v1/v6), linear rear force, β̇/ṙ EoM, and a μ·g/v friction clip. Target **B1A 0x400B1A** = the observer's
  own yaw rate, friction-clipped (= r_ref 0x4020EC only for the first 12 cycles). Coefficient formulas (RAM 0x400AA4..)
  match the 1M sim.
- **[verified]** **AYC yaw-moment → wheel distribution** (`ayc_moment_to_wheel_pressure` 0x616A4): PD moment M (0x400B1C)
  from yaw error (dead-zone P + D, gains B76/B78 0x413AA=47/47 × per-mode %); wheel select by sign of M, mode in
  0x400BB8[7:6]: **oversteer (s>0, mode 2) → brake outer FRONT only**; **understeer (s<0, mode 3) → same-side REAR**
  (rear share X = 0x4155E/256 = 256 → rear-only); small-yaw mode 1 → front 192/256 + rear 64/256 (0x413C4, doubled).
  Per-wheel demand 0x400B0C[w] ≈ 0.1 bar / M-count. Submitted as arbiter **id 3** (rate caps 0x41552/54 = 300/500)
  and **id 20** (front-outer 5-bar pre-fill, 0x411B4=500). **Engine-torque cap** `ayc_torque_cap_B30` 0x65494:
  0x400B30 = min(0x400D24, 0x400DB0), min-merged into the DME request at 0xCC388 (→ TX 0x0B6).
- **[verified]** **AYC→ABS link:** **0x408EB2 = driver brake pressure**
  (0.01 bar, dual-track ratiometric ADC sensor via 0x8F344, constants 0x5EE8=24296 / 0x97D=2429 / 0x556A=21866), NOT a
  yaw quantity. The real link is **B1A 0x400B1A** read directly by `abs_yaw_deviation_monitor` 0x4A254 (e = measured
  yaw ECC − B1A), and (corrected 2026-10-23) by 13 other ABS sites gated only on yaw-valid; see "ABS reads the
  steering-based yaw target". In `abs_sensor_input_gather` 0x5D82C: **0x408ECA = lateral accel** (coarse, the x for the ABS
  decision-32 yaw-limited-build curves 0x40E26/0x40E0A), **0x408ECC = measured yaw rate**, **0x408ECE = yaw accel**.
- **[verified]** **DDS/RPA is a resonance-frequency tyre-pressure monitor** (indirect TPM). Chain: tooth-period capture
  (`rpa_tooth_period_proc` 0xAA550, 48 teeth, learned per-tooth correction) → **uniform-time resample** to ~400 Hz
  (`rpa_resample_uniform_time` 0xAA758) → windowing (`rpa_window_dc` 0xAA812; flat-top 0xF26D0 fronts / bell 0xF29F0
  rears, Q13 peak 8192) → **40-bin direct DFT bank** (`rpa_correlate_step` 0xA623A over the sin/cos tables) →
  power spectrum (`rpa_power_spectrum` 0xA61D8). Band = **14–151 Hz** (1 Hz spacing to 64, then 3 Hz; bin0 = 14 Hz).
  Decision = **peak-frequency shift vs a context-learned baseline** (speed×load class) with persistence
  (`rpa_peak_shift_hyst` 0xAABDA, thresholds in ROM tables 0xDAC58/0xDACD0, 1.2× gate), not a wheel-to-wheel compare;
  verdict `rpa_verdict` 0x9D574 → fault 0x001B8000 / warning `rpa_warning_set` 0x97490. Coding-gated (0x4031F4 bit4,
  `coding_dds_rpa_enable` 0xCFC44); DDS-block enable overrides 0x41D48/0x41D4A = 0. The physical "tyre deflation" purpose
  is inferred; the DSP chain is byte-verified. (DDS-block scalars are mostly app-layer thresholds; the spectral decision
  constants are ROM tables, not the 0x41D10 block.)

## Open questions / hypotheses (not facts)

- **SUPERSEDED 2026-10-06 → see `docs/E46_SENSOR_FIRMWARE_PATCH.md`.** The ASIC mode mask 0x28C selects the sensor type, and the direction mask can be stored as 0 by
  bypassing `validate_dir_cfg`. Original note, kept for history: **Sensor type is hard-configured, not a
  flash/coding parameter** [verified on M3]. VDA active-encoded
  sensors are assumed on all four channels; the direction-expected mask 0x4029D6 is loaded = 15 (all four)
  in code at M3 0xB93C4 (1M 0xB91AC). Missing encoding therefore trips the per-wheel direction-invalid DTCs
  (table 0xF576C, via `wheel_direction_update` 0xB9330 → `fault_set` 0xB427C at ≥175 counts) and the VDA
  presence check `sub_075E38` (1M 0x75E94). *Note:* the earlier hypothesis "`60F2`→`6042` = mask 0" had a
  decode error — `6042` is `movi r2,4` (mask 4), not 0. **Reconfiguring for a different sensor type is
  properly a sensor-matched factory flash (the E85/GT4 motorsport application), not patching out the DSC's
  integrity checks** — defeating those fault gates is out of scope for this project (static RE only; and
  edited images still require re-signing). The high-value step remains obtaining the E85/GT4 flash to diff
  the sensor-path configuration by pattern (code layout differs, so compare by pattern not address).
- Who writes 0x004031F4 (bit 8 selects the direction invert mask 05/09)?
- **[2026-10-05] 2-level→VDA converter open items** (`docs/VDA_CONVERTER_DESIGN.md` §8). Moot since the
  2026-10-06 firmware patch; kept for reference:
  - **[user, measured 2026-10-05] Sensor-pin open-circuit voltage = 10.7 V** (between the two sensor wires,
    ECU on a 12 V bench supply). Still open: the sense R, and whether it tracks battery voltage (re-measure at 14 V).
  - The E90 frame bit values, DR polarity per side, and standstill frame content. Scope-capture them.
  - E46 ring teeth per rev. Expect 48, which gives 96 frames/rev to match BFU 48.
- **[user] E85 Z4 MK60E5 units work with E46 (2-level) sensors.** So some MK60E5 configuration reads
  2-level sensors.
  - **[user] The ASIC/firmware route was already pursued on the M3/1M images with no payoff.**
  - ~~Don't re-propose it. The external converter is the chosen path.~~ **RESOLVED 2026-10-06.** A renewed live
    ASIC sweep, with a precise ESP32 stimulus, found the mode mask 0x28C. The firmware patch is the path. The
    converter design is kept only as a fallback.

- Exact M·CORE derivative and memory map of SC560002 (custom part).
- ~~Hypothesis: 0x004029DA bit 5 reflects sensor type~~ Refuted by the agent: bit 5 is set at
  run time (vref < 55 km/h, init done, no controller active).
- ~~Hypothesis: capture mode selects sensor type~~ Refuted: mode is the constant 0x91 on all channels.
  **Update 2026-10-06:** the mode does select the capture EDGE. 0x91 = single edge, **0xA1 = both edges**
  (`sub_0D569C` sets bits 12:11 of 0x…8E). The E46 patch uses 0xA1.
  Find who sets the mode bits and whether that depends on coding/calibration.
- Mapping of ISR/channel to physical wheel (FL/FR/RL/RR). Partial (2026-10-06): FL = wheel idx 0 = ASIC 0x28C
  bit0 = capture on 0xF8008E. The other wheels' bits/channels are not individually mapped; the E46 patch clears
  all four.
- ~~Where sensor type (E46 vs E9x) is selected~~ **Resolved 2026-10-06: ASIC register 0x28C** (init table file
  0xDF22C). Older text, kept for history: no selector in the app; all four
  channels are hard-configured for VDA in both 1M and M3 (see "Wheel-sensor type selection"). Running
  passive would need HW + patches to 0x0B91AC and 0x075E94. The one wheel-chain coding bit only inverts
  direction polarity. (A real passive-rear variant, if it exists, would be a different flash/ASIC config.)
- Decode the **M3** ABS/TCS blocks field-by-field (M3 ABS 1.7× larger, TCS 5× smaller) to make the
  motorsport comparison field-level rather than structural.
- Follow the ABS slip/decel *estimation* outputs into the 0x8xxxx control code to find the actual
  hold/dump pressure targets (not in the ABS calibration block).
- Meaning of the 0xFFFF00 block (`00 01 … 07`); what the `BMY` u32 (0x000F59E0) is. **(Signature
  math resolved 2026-10-04: the 64 bytes verify as raw RSA e=7 under the `rsa-sig.json` key; the
  digest is reverse(MD5(image[0x48000:BMY_start])) — see the BMY key-verification entry above.)**
  Only remaining open item on BMY: whether the bootloader actually enforces the check at load (it is
  in the absent 0x0–0x47FFF region; 0x48000 being the hash start strongly implies the bootloader
  computes it).

## CAN flash / security protocol — WinKFP SGBD cross-check (verified 2026-10-04)

Source: BMW Standard Tools on this machine — SGBD `C:\EDIABAS\Ecu\DSC_87.prg`
(the E9x MK60E5 "DSC_MK60", confirmed by `JOBCOMMENT:Status Eingaenge E87 DSC_MK60`
and `IDENT_TEVES_ECU_SW_NR`) and WinKFP flash IPO `C:\EC-APPS\NFS\SGDAT\15DSC60.ipo`.

- **[verified]** The `.prg` string/symbol tables are **XOR-obfuscated with 0xF7** (0xF7 = encoded
  0x00). `bytes(b ^ 0xF7 ...)` yields ~18k clean strings (job/arg/result names, comments, the
  diagnose-mode table). This is the method to read any EDIABAS SGBD here.
- **[verified]** **Diagnostic session (DIAGNOSE_MODE table):** 0x81=default, **0x85 = ECUProgrammingMode
  (ECUPM)**, 0x86=ECUDevelopmentMode, 0x87=ECUAdjustmentMode/EOL. Flashing uses `StartDiagnosticSession
  0x10 0x85`. Matches the firmware 0x10 handler (0xB125C) accepting modes 0x81/0x85/0x87.
- **[verified]** **Security access for flash = KWP2000 `0x27` level `0x03`** (seed) / `0x04` (key);
  alt `0x07`/`0x08` (`JOBCOMMENT:KWP2000:$27,$03 oder $27,$07`; `$07 RequestForAuthentication`,
  `$08 ReleaseAuthentication`). Literal request bytes `27 03`, `27 07`, `27 08` each occur once in the
  SGBD bytecode. The key-computation local variable is literally named **`seedrev`** (plus `byteshift_2`,
  `wert_access`, `i`).
- **[HARDWARE-VERIFIED on the unit 2026-10-04]** **Flash/standard security key = `bitrev16(seed) XOR
  ROR16(seed, state+1)`**, no constant. `sub_0B1468` is NOT a plain bit-reverse: after the 16-bit reversal
  loop it XORs `ROR16(seed, state+1)` where `state` = 0x409534 at key-check (the 0x27 key sub-function).
  For level 0x03 → key sub-function 0x04 → state 4 → rotate 5; level 0x07 → state 8 → rotate 9.
  The other firmware transforms map to other levels: state 0xFE → `sub_0AFB10` (`afb10`), state 0xFC →
  `sub_0AFB9E` (`afb9e`). 16-bit seed/key (handler buffers 0x409489[2..3] seed, 0x409535/36 key).
- **[HARDWARE-VERIFIED]** **Working unlock sequence on the bench unit** (Kvaser, `tools/mk60_can.py`):
  `0x10 0x81` → `0x10 0x87` (ECUAdjustmentMode — 0x27 is granted here, NOT in default/0x85) → `0x27 0x03`
  (seed) → `0x27 0x04` key. Confirmed e.g. seed 0x60A1→key 0x8E03 accepted, seed 0xF32D→0xDB56 accepted
  (`67 04 ..` positive). NOTE: this ECU returns **NRC 0x10 (generalReject) for a WRONG key**, not 0x35.
- **[verified]** `0x10 0x85` (ECUProgrammingMode) returns **conditionsNotCorrect (0x22)** even after a
  successful 0x27 unlock in 0x87. The 0x10 handler (0xB125C) routes mode 0x85 to 0xB1304, which requires
  BOTH: (a) `sub_0AF78C(4,0,100) == 0`, and (b) **security level `0x409545 == 5`**. The 0x27 0x03 seed/key
  grants only level 2 (`0x409545 = state>>1 = 2`); no 0x27 sub-function reaches level 5.
- **[verified]** **Level 5 is granted only by a separate 128-bit "Authentisierung"** (handler ~0xB2FBE,
  the SGBD's AUTHENTISIERUNG / "Security Level B", KWP `$27,$07` RequestForAuthentication). On success it
  does `movi r6,5; st.b 0x409545` @0xB2FEC. The check `sub_0B3F3E` (0xB3F3E) computes an expected 16-byte
  response via `sub_0B3EE0` (setup) + **`sub_0B3F18`** (transform, using **flash key/table at 0xF56C8**)
  and byte-compares it to the tester's 16-byte response (from diag buffer 0x40331D); match → level 5.
  **This is the real gate to reflashing** — a 128-bit challenge-response, far stronger than the 16-bit
  seed/key. But the algorithm AND its key are entirely in the image (0xF56C8 is flash-resident).
- **[verified — algorithm identified]** The level-5 Authentisierung is a **keyed MD5**:
  `response16 = MD5( key16 || data16 || key16 )`, computed by `sub_0B3F18` =
  md5_init `sub_0B3D74` (IV 0x67452301/0xefcdab89/0x98badcfe/0x10325476 — confirmed MD5) →
  md5_update `sub_0B3C46` ×3 (key,16 / data,16 / key,16) → md5_final `sub_0B3C82`. `sub_0B3C46` buffers
  into a 64-byte block at 0x408C28 and compresses via `sub_0B3AFC` (MD5 block function).
  - **key16 = flash 0xF56C8[0:16] = `F1 CE 23 C6 CD 24 C8 B7 B8 B3 C6 53 D9 70 7B AC`** (extracted).
  - **data16** (`sub_0B3EE0`) = `0x408C0C[0:4] || 0x409564[0:4] || 0x408C04[0:8]`.
  - `0x408C04[0:8]` is produced by a **deterministic PRNG** `sub_0B3EAC`→`sub_0B3E6C` seeded from the ECU
    random `0x40956C` (16 B), and that random is **sent to the tester** (rearranged into the ZUFALLSZAHL
    response at 0x40943E). So the whole challenge is reproducible by anyone holding the firmware — no secret
    is withheld. **Crackable in principle; confirmed, not yet implemented end-to-end.**
  - Services (SGBD + firmware, LIVE-VERIFIED): **`0x31 0x07` = read random** (routine 7, RequestForAuthentication;
    requires LEVEL byte = 3 and a 4-byte USER_ID → telegram `31 07 03 <uid32>`). On the unit this returned
    `71 07` + **8-byte ZUFALLSZAHL** (e.g. `9F 6C 9C 35 73 B3 8B 93`). **`0x31 0x08` = send response**
    (routine 8, ReleaseAuthentication; BINAER_BUFFER with the 16-byte response at byte 21+). Routing:
    0x31 handler 0xB2B1C → jump table 0xB2B98 indexed by (routine−5) → routine 7 @0xB2C50, routine 8 @0xB2C56.
  - **data16 = USER_ID[4] (tester-chosen) || 0x409564[4] || ZUFALLSZAHL[8]**. The 8-byte part is the random
    the ECU returns (= 0x408C04, the PRNG output, sent directly — no LFSR reversal needed by the tester).
  - `0x409564` (4 bytes) is read from external **EEPROM** at logical NVM 0x0322 (table 0xD7424[24]) via
    `sub_06E41E`. **Read live from the bench unit with service 0x23 format 3: `23 00 03 22 03 04` →
    `63 D1 BB CD 33`, so 0x409564 = `D1 BB CD 33`** (per-unit AND dynamic — it changes between runs, so read it live each auth). The 0x23 request format is
    `23 00 <addrHi> <addrLo> 03 <len>` (format byte 3 = logical NVM, len ≤ 4).
- **[HARDWARE-VERIFIED — LEVEL-5 AUTHENTISIERUNG CRACKED 2026-10-04]** Full keyed-MD5 auth confirmed on the
  unit. Sequence: `0x10 0x81` → `0x10 0x87` → `0x31 07 03 <uid32>` (returns 8-byte ZUFALLSZAHL) →
  `0x31 08 <resp16>` where `resp = MD5(key16 || uid32 || 0x409564 || ZUFALLSZAHL || key16)`. Live example:
  uid=00000000, 0x409564=D1BBCD33, ZUFALLSZAHL=1d76ead8f2276b03 → resp=9c1a3704d2686c63625a69e8e76ee175 →
  **ECU replied `71 08 00` (ACCEPTED), level 5 granted.** The 8-byte ZUFALLSZAHL is used directly (it IS the
  0x408C04 PRNG output; no LFSR reversal needed by the tester). This fully solves the flash authentication.
- **[verified]** Even with level 5, `0x10 0x85` still returns conditionsNotCorrect: the remaining condition
  is `sub_0AF78C(4,0,100)` = funcptr table 0xF2EB8[4] = `sub_0AF8E8(0,100)`, which loops the 4 wheels and
  requires **every wheel's value `0x40094A[ wheel@0x40BF00+42 ]` ≤ 100** (a stationary/healthy-wheels gate).
  On the bench (no/faulted VDA wheel sensors) this exceeds 100 → blocks 0x85. It is a PHYSICAL precondition
  (vehicle stationary + working wheel-speed sensors), not a secret — passes on a car or a properly-fed bench.
  So: the entire crypto/auth chain is solved and verified; the only thing between here and a reflash is
  satisfying the stationary-wheels precondition (or neutralizing it, which ties back to the sensor work).
- **[hardware]** Bench unit identification (0x1A): part `P460927` (ASCII), HW refs `0678 9304` / `0678 5581`.
- **[verified]** **WinKFP flash job order** (15DSC60.ipo): SG_IDENT_LESEN → DIAGNOSE_MODE(ECUPM) →
  FLASH_PARAMETER_SETZEN → **FLASH_BLOCKLAENGE_LESEN** (block length is read *from* the ECU, not fixed) →
  FLASH_ZEITEN_LESEN (erase/signature/reset/auth wait times) → AUTHENTISIERUNG_ZUFALLSZAHL_LESEN +
  AUTHENTISIERUNG_START (0x27) → FLASH_LOESCHEN + status poll → FLASH_SCHREIBEN_ADRESSE → FLASH_SCHREIBEN
  (A/B double-buffered) → FLASH_SCHREIBEN_ENDE → **FLASH_SIGNATUR_PRUEFEN (Daten; Programm)** → AIF_SCHREIBEN
  → STEUERGERAETE_RESET → DIAGNOSE_ENDE.
- **[verified]** **The ECU enforces the signature after writing** (`FLASH_SIGNATUR_PRUEFEN`,
  `ERROR_FLASH_SIGNATURE_CHECK`) — so an edited image must pass `tools/bmy_resign.py fix` (MISR + BMY)
  or the flash is rejected. Confirms the BMY/MISR workstream is exactly what the module checks.
- **Not present in this install:** flash data (`.0da`/`.0pa`) for part numbers 7846816A/7846411A — so no
  factory signed image to diff here. The raw CAN service bytes per flash job are in compiled BEST/2
  bytecode (no `.b2s` source); the definitive capture is an EDIABAS IFH/API trace (set `IfhTrace=1`,
  `ApiTrace=1` in `C:\EDIABAS\bin\EDIABAS.ini`, TracePath `C:\EDIABAS\TRACE`) of a real tool session.
- Tooling: `tools/mk60_can.py` `unlock` walks 0x81→0x87 then 0x27 0x03/0x04 with algo `seedrev` (the
  verified transform) and unlocks the bench unit end-to-end. `flash` defaults to session 0x85 (still gated
  by the unmet programming-mode precondition above).

### Level-5 auth VALIDATED against real WinKFP M3 flash (2026-10-04)

- **[HARDWARE-GROUND-TRUTH]** Parsed the user's real WinKFP M3 flash CAN log
  (`analysis/mk60e5_flash_can_log.txt`, decimal format, tester 0x6F1 / ecu 0x629). Auth exchange:
  `31 07 03 32 37 33 63` → `71 07 c4eaf30aae361451` (ZUFALLSZAHL) → `31 08 bf59b8a05b7cc2f3b912872d68dc462a`
  → `71 08 **01**` (success; our bench had been getting `71 08 00` = FAIL — same reply shape for a wrong key).
- **[PROVEN by brute-force]** `MD5(KEY || UID || W564 || ZUFALLSZAHL || KEY)` (standard output) reproduces the
  logged response EXACTLY with **KEY = F1CE23C6CD24C8B7B8B3C653D9707BAC** (M3 0xF56C8), **UID = "273c"**
  (0x32373363), **W564 = "00B4"** (0x30304234). UID and W564 are FIXED ASCII constants WinKFP uses — NOT the
  per-unit NVM read my tool had been doing (that was the bug; corrected). Full flash auth for the M3 is solved.
- WinKFP sequence (log): `1a80… → 10 85 (ECUPM, succeeds sensorless) → 1a 89 → 31 07 → 31 08 → 10 85`.
  Confirms the wheel-speed gate passes sensorless on the M3 — the auth was always the real blocker.
- `tools/mk60_can.py auth5` now uses these validated constants and reproduces the logged response offline.

### DSC firmware inventory (BMW daten `C:\Users\cgrah\Downloads\E89_v74`)

- Flash payloads in `daten/` (WinKFP-COMPRESSED; key not present verbatim): **MK60_M3** (M3, ZB 7846816 =
  DSCM90), **MK60_87** (E9x non-M incl. **335**, DSC90 ZBs 4029563/6776067/6776069/6775389/6791524/6862873/
  6775387), **MK60_M82** (1M, DSCM80), plus DSC_84, DSC_89, DSC8_RPA. Repo has full dumps of M3 (7846816A) and
  1M (7846411A) only.
- **[verified on bench]** The M3 key does NOT authenticate a 335 (tested on the connected 335 unit: M3 key +
  273c/00B4 → 71 08 00, oracle 0x09 → NRC 0x33). Each MK60 variant has its own 0xF56C8 key + constants.
  Extracting the 335's requires decompressing the WinKFP MK60_87 flash data (format TBD).
- Oracle for level verification: service **0x09 requires security level >= 4** (service table 0xF30A0
  entry+9); NRC 0x33 = under-level, else level reached. (0x3B needs 2, 0x3D needs 127.)

### COMPLETE flash entry CRACKED & WORKING (M3 log + live 335, 2026-10-04)

**Full working sequence (validated end-to-end on the bench 335 → PROGRAMMING MODE OPEN; matches the real
WinKFP M3 flash log):**
1. `0x10 0x81` → `0x10 0x87` (ECUAdjustmentMode — where 0x31 auth is granted)
2. `0x1A 0x89` (ReadEcuId) → **`w564` = the LAST 4 BYTES of the response** (per-unit; e.g. M3 "61AB0**00B4**",
   bench-335 "691E0**009E**"). This is how WinKFP gets w564 — NOT an NVM read.
3. `0x31 0x07 0x03 <uid4>` → 8-byte ZUFALLSZAHL. **`uid` is tester-chosen/arbitrary** (WinKFP used "273c");
   the ECU stores whatever was sent and uses it.
4. `0x31 0x08 <resp16>` where **`resp = MD5(KEY || uid || w564 || ZUFALLSZAHL || KEY)`** (standard MD5).
   Success reply = **`71 08 01`** (01=granted; 00=failed).
5. `0x10 0x85` (ECUProgrammingMode) now succeeds — **sensorless** (the wheel-speed gate passes with no
   sensors; it was never the blocker — the auth/w564 was).
- **KEY = F1CE23C6CD24C8B7B8B3C653D9707BAC** is SHARED across M3 (DSCM90/7846816A), 1M (DSCM80/7846411A), and
  4 of 5 E9x-335 variants (DSC90: 6775387/6776067/6791524/6862873). Only DSC90/4029563A uses a different key.
- `tools/mk60_can.py auth5` implements this and opened 0x85 on the bench 335. `tools/parse_0pa.py` decodes any
  BMW `.0pa` (Intel HEX; addr = CPU+0x8000) to a raw image and extracts the key (`--scan <datendir>`).
- The `.0pa` firmware lives in the daten under `data/DSC*/<ZB>.0pa` (full Intel-HEX images, not compressed).

### COMPLETE flash WRITE protocol DECODED (from real WinKFP M3 log, 2026-10-04)

The full reflash — after the level-5 auth above opens `0x10 0x85` — is reconstructed byte-for-byte from
`analysis/mk60e5_flash_can_log.txt` (reassembled BMW byte-0 ISO-TP: tester 0x6F1, ECU 0x629). Every segment's
reconstructed data MATCHES our stock dump (`flash/bin/7846816A_*.bin`) exactly, confirming the log is genuine
7846816A firmware and that flash "addresses" are physical byte addresses into the 3 banks (main 0x000000, data
flash 0xDF0000, 0xFF0000). Sequence:

1. **Erase** — `31 02 <start:3> 06 <total:3>` (KWP StartRoutineByLocalId 0x02 = FLASH_LOESCHEN). M3 =
   `31 02 00 03 AC 06 0B 6E 6F` → erase 0x0003AC for 0x0B6E6F (749167) bytes = exactly the sum of all segment
   sizes. **Poll pattern**: resend until `71 02 01`; interim replies are `7F 31 23` (NRC 0x23 routineNotComplete).
2. **Quiet bus** — `28 02` then `29 02` (disable normal message tx). Fire-and-forget (no response).
3. **Per segment** (15 of them, in this order):
   - `34 <addr:3> 06 <size:4>` (RequestDownload) → `74 00 FC` → **max block = 0xFC** (252 incl. the 0x36
     service byte → **251 data bytes/frame**).
   - repeat `36 <≤251 data>` (TransferData; NO explicit counter in the request) → `76 <cnt:2> 01` where the ECU
     echoes a **2-byte block counter** that resets to 1 per segment.
   - `37 <addr:3> 06 <size:4>` (RequestTransferExit, echoes addr+size) → `77`.
4. **Finalize** — `31 0A` (status) → `71 0A 05` (written, verify pending); **`31 09 02` poll → `71 09 01`**
   (FLASH_SIGNATUR_PRUEFEN — the ECU verifies the BMY signature here; an unsigned edit is REJECTED); `31 0A` →
   `71 0A 01`; `29 02`; `11 01` (ECUReset) → `51 01`.

**M3 7846816A segment table** (addr / size, physical): 0x0003AC/0x544, 0x048000/0x210, 0x048230/0x10,
0x0482F0/0xC00, **0x048F20/0x99740 (628544 B main app)**, 0x0E2770/0x1C2B4 (115380 B), 0xDF812C/0x1F,
0xDF8160/0x22, 0xDF8281/0x4D, 0xDF83C0/0x1, 0xDF83C3/0x12, 0xDF83D6/0x3, 0xDF83E0/0x6, 0xDF844B/0x65,
**0xFFFF00/0x8 (signature)**.

**Tooling**: `tools/extract_flashplan.py <log>` rebuilds the stock plan (plan.json + data.bin) from the CAN log
(size-validated). `tools/mk60_can.py repack --plan <ref> --bank 0x0=main.bin --bank 0xDF0000=.. --bank
0xFF0000=.. --out <dir>` re-slices EDITED banks onto the fixed segment layout (byte-verified identical to the
extract for stock input). `tools/mk60_can.py flashplan <dir>` executes it — **DRY-RUN by default**, transmits
only with `--arm` + typed confirmation; reuses the verified `authenticate()` to reach 0x85, drives
erase/34/36/37/verify/reset with proper NRC-0x23/0x78 polling. Edited images must pass `bmy_resign.py fix`
first or they fail at step 4's `31 09` verify.

### LIVE: M3 firmware flashed onto a 335 unit — CROSS-FLASH SUCCESS (2026-10-04)

The M3 (DSCM90/7846816A) image was flashed onto a physical **E9x-335 (DSC90)** MK60E5 using
`tools/mk60_can.py flashplan` and **boots and runs** on the 335 hardware. Proven end-to-end on the bench.

**Outcome / proof:** after the flash + reset the unit runs the application: `10 81`→`50 81` (app session,
not bootloader), `1A 80`→`5A 80 00 00 07 84 68 16 02 08 05 B3 …` (real ident; the `00 00 07 84 68 16` prefix
matches the M3 capture, trailing bytes are the unit's own serial), `31 0A`→`71 0A 01` (status healthy). The
**M3 BMY signature verified on the 335 bootloader** (`31 09`→`71 09 01`) — the signature/auth scheme is
hardware-agnostic across MK60E5 variants (consistent with the shared key).

**Bootloader behaviour learned (important for any flash / recovery):**
- Entering `0x10 0x85` (ECUProgrammingMode) hands off to the **bootloader** and sets a "programming
  requested" flag that **survives power-cycle and `11 01` reset** — the ECU will NOT run the app again until a
  flash completes. An aborted flash therefore leaves the unit in the bootloader; this is recoverable, not a
  brick (re-flash to finish).
- **Fresh bootloader** (status `31 0A`→`71 0A 0C`): `0x85` opens with NO auth; app sessions `0x81/0x87` and
  `1A 89` return NRC 0x12.
- **After a partial write** (status `0x0B`, or `0x05` right after a full write): `0x85` is refused `7F 10 22`
  until the **level-5 auth is redone** — and in this state the auth routines ARE available even though
  `0x81/0x87` still return 0x12. So auth here is done WITHOUT the session prefix: `1A 89` (w564 = last 4 =
  e.g. this 335 = "009E") → `31 07 03 <uid>` → `31 08 MD5(KEY||uid||w564||ZUFALL||KEY)` → `71 08 01` →
  `0x10 0x85`→`50 85`. `authenticate()` now tolerates the `0x81/0x87` NRC 0x12 so the SAME path works in app
  and bootloader; `flashplan --no-auth` skips straight to `0x85` for a fresh bootloader.
- **335 verify is TWO-STEP** (differs from the M3's single `31 09 02`): `31 09 00` STARTS the verify, then
  `31 09 02` returns the result (`71 09 01`=pass). While computing it answers `7F 31 23` (busy) / nothing; if
  the result is requested before start it answers `7F 31 12` (= "(re)start"). `flashplan` now does start +
  poll and tolerates silence (the signature compute over ~749 KB runs >10 s with no interim frames).
- The erase and every `0x34/0x36/0x37` frame worked byte-identically to the M3 capture; the only
  cross-variant differences are the two-step verify and the bootloader auth-state handling above.

**Recovery note:** if a flash aborts, the unit sits in the bootloader (status 0x0B). Re-run
`flashplan <plan> --arm` (auth path auto-handles the bootloader) to finish; WinKFP + daten is the ultimate
fallback. Status codes seen: `0x0C`=bootloader ready, `0x05`=written/verify-pending, `0x0B`=written/
session-lost (needs re-auth), `0x01`=healthy app.

### Why the mode-2 flash read nothing — ASIC is the lever, not the mode byte (2026-10-04)

Two deep-dives (verified byte-exact; see `analysis/agents/asic_sensormode/REPORT.md`) explain the live
negative result:
- **The mode byte (file 0x7DA56) only selects the PRESENCE/fault check, not speed acquisition.** `sub_075A44`
  returns the mode for all wheels; the caller `sub_075E38` branches 4=ASIC-frame-popcount / 2=period-pair /
  else=fault. But the **speed magnitude** routine `sub_07525C` reads captured edges at `0x40339E` with NO
  mode dependence. So flipping 4→2 never affects whether a speed is produced. (Corrects the old "3-way mode
  dispatch in sub_075A44" framing — its arg is the wheel index.)
- **Edges reach the MCU via 4 timer input-capture ISRs** (`sub_070CD0/070DE0/070E6A/070D56` on timer modules
  0xF8xxxx/0xD8xxxx) → RAM 0x40339A–0x40339D (live) / 0x4033AE–0x4033B1 (snapshot via `sub_073B1C`). This path
  is mode-independent and IS initialized (it's the same path stock mode-4 uses).
- **SUPERSEDED 2026-10-06 → see `docs/E46_SENSOR_FIRMWARE_PATCH.md`.** The ASIC's VDA mode is switchable per channel via register 0x28C. Original text:
- **[likely] The sensor signal is conditioned by the ASIC**, which drives the digital pulse into the capture
  pin — a raw/passive signal at the input does NOT bypass the ASIC. The ASIC is hard-configured for VDA active
  (current-mode 7/14/28 mA) sensors, so a non-VDA stimulus gives no pulses → no edges → no speed. **That is
  why mode-2 read nothing.**
- **ASIC = the real lever.** Programmed over **hardware QSPI (base 0xDB0000, CS PCS5; driver `asic_reg_xfer32`
  @ 0xD4A30; 10-bit reg id + 10-bit data).** Config is 100% hardcoded constants (no coding/NVM/variant). M3
  tables at **CPU 0xD7210/0xD7242/0xD7276** (the old report's 0xD75A0/D75D2/D7607 were 1M addresses; M3 =
  1M−0x390). Per-channel config in `sub_073F74` (channel/input/row tables @ 0xD75E4/0xD75A4/0xD7614). Regs
  **0x154/15C/164/16C = 0x1B** (identical across channels) are the top suspect for a sensor-type/mode field.
- **BLOCKER: ASIC register semantics are not determinable from firmware.** Need the **ASIC part number +
  datasheet** (unit is cut open → read the chip). Candidate patch sites + the required direction-mask
  (0xC13C4) and presence-defeat (file 0x7DF2C `e0 1a`→`f0 1a`) patches are listed in the report.
- **Decisive bench test (no datasheet/flash):** stimulate FL, read RAM 0x40339A–0x40339D + 0x4033AE–0x4033B1.
  If they stay 0 → no pulses reach the MCU (ASIC gating confirmed); if >0 with CAN speed 0 → nulled downstream.

### Wheel-speed sensor ASIC identified + external VDA confirmation (2026-10-04)

- **[user, from the opened unit] The wheel-speed sensor-interface ASIC is a Texas Instruments custom part**,
  markings: `TI` / `5895-5120.1E` / `8BAHRFTB` / `P105070E2`. `5895-5120` is a custom/ASSP mask number (the
  other lines are lot/date codes) — **no public datasheet** (searched). This is the chip the firmware programs
  over QSPI (base 0xDB0000, CS5; driver `asic_reg_xfer32` @ 0xD4A30) per the asic_sensormode report.
- **[external, converges with our RE] MK60E5 requires active Hall VSS with a VDA-encoded data stream.** Passive
  VR sensors and even plain (non-VDA) Hall sensors are not decoded. Sources: BMW standalone-ABS community
  (lotustalk/miataturbo/rusefi threads) and the MK60e5-Standalone project
  (github.com/tomazcebul/MK60e5-Standalone, "MK60E5 requires active Hall effect VSS with VDA output data
  stream"). **No public success adapting non-VDA/passive sensors to MK60E5** — doing so would be novel.
- **Consequence for the E46-sensor goal:** enabling non-VDA sensors needs the TI ASIC to have a plain-edge/
  non-VDA input mode AND the right register value to select it. The firmware doesn't reveal the field meaning
  (regs 0x154/15C/164/16C=0x1B are the suspect), the datasheet is unavailable, and the reference motorsport
  flash is NLA. So this is presently blocked on ASIC register semantics — possibly a hardware limit, not just
  firmware. The pending RAM-counter bench test (0x40339A.. during FL stimulation) will confirm whether any
  pulses reach the MCU at all.

### [verified, bench 2026-10-05] Bare-I_H test: the gate is the 28 mA LEVEL, not VDA frame validity
**Corrects the 2026-10-04 conclusion below** that the ASIC "only emits capture pulses after decoding a valid VDA
frame".

**Setup:**
- Image `flash/plan/m3_probe_mode2`: mode-2 byte 0x7DA57=0x23 plus the 0x23 peek handler, re-signed. It is
  verified live: CPU 0x75A56 = `60 23`.
- The FL channel is driven by an ESP32-S3 + TIP120 sink, with no data bits at all:
  - R_L 1.5 kΩ gives 7 mA idle.
  - +21 mA through 91 Ω gives about 28 mA.

**Results.** CAN 0x0CE FL is raw/16 = km/h.
- **Pattern B** (50 µs 28 mA pulses, 300/s, 7 mA between): **0x016F = 22.9 km/h**, against 23.3 expected at
  96/rev and 2.073 m. Occasional 0x0154 (21.3) is ESP jitter. So the ASIC counts bare I_H pulses, and speed is
  correct.
- **Pattern A** (150 Hz 7/28 mA square, ms-long 28 mA dwells): **0x00B7/0x00AA = 11.4/10.6 km/h**, so one pulse
  per dwell (one per rising edge). A long I_H dwell is accepted, with no leakage/over-current DTC, but it counts
  once. A 7→7 / 14→28 in-loop scaler on a 48-tooth ring would therefore read HALF speed unless the front
  circumference or tooth count is recalibrated.

**DTCs read via KWP `18 02 FF FF`.** Texts are from `C:\ediabas\ecu\DSC_87.prg`, XOR 0xF7.
- **No FL electrical DTC.** Only the empty channels faulted: 5DA0 FR / 5DB0 RL / 5DC0 RR "Drehzahlfuehler …
  elektrisch defekt".
- **5D96 "Drehrichtungserkennung vorne links"** (status 0x60) was present. **CAVEAT:** DTCs were not cleared
  before this run, so it may be a stale entry from earlier tests. Not proven to come from patterns A/B.
- The others are bench artefacts:
  - D370–D372: F-CAN sensor-cluster messages 205/209/212 missing.
  - D358/D359: PT-CAN messages 784/816 missing.
  - 5E5D: brake-fluid switch.

**Consequences:**
- E46 sensors fail only because they never reach I_H.
- Presence (mode 2) and speed need no data bits. Only the direction check does: 5D96, fixed by the direction
  mask, or by real frames with GDR=1.
- See `docs/VDA_CONVERTER_DESIGN.md` §11–12.

### [verified 2026-10-05] Direction mask is ALL-OR-NOTHING through `validate_dir_cfg`; front-only needs a bypass
- `sub_075A5E` (validate_dir_cfg) returns **15 if the input is in {0,1,2,3,15}, else 0** (disasm verified).
  - So `movi r2,12` at 0xB93C4 (image `m3_probe_mode2_dirR`, flashed) stores **0x4029D6 = 0x00**: direction
    checking is off on ALL wheels. Verified live by peek: 0x4029D6 = 00 and counters 0x4029DB..DE = 0.
  - `movi r2,0..3` gives 15 (all on). Only values outside the set give 0 (all off).
- **Run on dirR:**
  - KWP `14 FF FF` cleared DTCs (`54 FF FF`). Then pattern A ~10 s and pattern B ~10 s.
  - Result: **no 5D96 and no 5D90** (FL electrical).
  - Caveat: the fault memory seems to hold ~10 entries; bench CAN-timeout codes refill it, and 5DA0 dropped out.
  - With mask 0 the check is disabled anyway, so this proves "no direction DTC with direction off", nothing
    more.
- **Front-only mask patch** (image `m3_probe_mode2_dirF`, re-signed, NOT yet flashed): file 0xC13C4 `60F2 7FB0` →
  `60C2 60C3` (`movi r2,12 ; movi r3,12`, skipping the validate call; `st.b r2` at 0xB93CC stores 0x0C).
  - That should give direction expected on wheel idx 2/3 (rears) only.
  - idx 0/1 = front is the agent's wheel-index reading [agent, high]. **Bench-verify: 0x4029D6 should read 0x0C.**

### [verified, bench 2026-10-05] Front-only direction mask works: `m3_probe_mode2_dirF` flashed
- **Patch:** file 0xC13C4 `60C2 60C3`, read back live.
- **Mask:** 0x4029D6 = **0x0C** live, i.e. direction is expected on idx 2/3 only.
- **Run:** DTCs cleared, then pattern B for about 50 s, with FL steady at 22.9 km/h on 0x0CE (dips to 21.25).
- **Counters 0x4029DB..DE stayed 00** throughout (peek polled every ~4 s), and no 5D96 appeared.
- **So FL is a masked wheel**, consistent with idx 0/1 = front.
- **Control NOT yet run:** the mask-15 image with counters polled under pattern B. Until then it isn't proven
  whether the mask is what stops counting, or whether a no-data-bit signal on mode 2 never counts anyway. That
  decides whether the direction patch is needed at all.
- **Other RAM seen:** 0x4029D3 = 0x02 and 0x4029DA = 0x24, constant, meaning unknown.
- **Bench working state:** a mode-2 + front-direction-masked image, plus bare 28 mA pulses on FL, gives correct
  speed and no FL DTCs.

### [verified disasm 2026-10-05] Where "2 pulses per tooth" lives: speed constant K = C·900 (not the tooth count)
- **`wheel_cal_prepare` 0x751A8:**
  - K_front = C_front(0x41CF4) × 900 → **0x4033CC**; K_rear = C_rear(0x41CF6) × 900 → **0x4033D0**.
  - floor 0x4032D0 = **max** over axles of 2·900·C/60000 (0x751D6 `cmplt r2,r3; movf r3,r2`: rear kept unless rear < front; an earlier note here said min).
  - The true circumferences are copied to 0x40935C.
  - The 900 folds in pulses/rev (96 = 48×2) and the capture clock. Bench check: 300 pulses/s → 22.94 km/h at
    C = 2073, i.e. ≈ 97 pulses/rev.
- **The speed routine `sub_07525C` uses ONLY K.** 0x7528C/0x75294 select 0x4033CC or 0x4033D0 from bit 7 of the
  wheel-struct pointer, i.e. idx 0/1 = front. No other code reads K.
- **The BFU tooth count is NOT in the speed path.**
  - 0x41CF8/0x41CFA (front/rear = 48) are read by `sub_075226`, a getter that copies them into a struct.
  - They are also read by `sub_06EC18`, which is called per wheel from the speed routine at 0x75464.
  - `sub_06EC18` is a speed/pulse plausibility check: teeth×200 and teeth×900 thresholds, a 5,000,000 constant,
    and a gate at > 20 km/h. Its exact semantics are not yet decoded.
- **Front-only ×2 patch (1 pulse per tooth).** Reorder at CPU 0x751C0 / file 0x7D1C0:
  - `9307 7722 3C13` → `3C13 9307 7722` (lsli r3,1 ; st.w r3,(r7,0) ; lrw r7,[0x7524C]).
  - The lrw encoding is unchanged at the new PC.
  - Result: K_front = 1800·C, while the floor and the 0x40935C circumference copy are unchanged.
- **Images** (built on dirF, re-signed, NOT yet flashed):
  - `m3_probe_mode2_dirF_k2`: speed patch only.
  - `m3_probe_mode2_dirF_k2t24`: plus BFU front teeth 48 → 24 at file 0x49CF8, so the `sub_06EC18` thresholds
    match 48 pulses/rev.
  - Expected effect on FL: pattern A at 150 Hz should read ≈ 23 km/h, and pattern B 300/s ≈ 46 km/h.

### [verified, bench 2026-10-05] Front ×2 speed patch WORKS with 48 teeth: image `m3_probe_mode2_dirF_k2` flashed
- **Readback:** code at 0x751C0 = `3C13 9307 7722`. **K_front 0x4033CC = 0x0038EFC8 = 2073×1800.** K_rear
  0x4033D0 = 0x001C77E4 = 2073×900 (unchanged). Mask 0x4029D6 = 0x0C.
- **Run:** DTCs cleared, then **pattern A** (150 Hz 7/28 mA square, i.e. the in-loop scaler's waveform) for
  about 60 s.
  - FL 0x0CE = **22.94 km/h** (was 11.4 before the patch), with recurring 21.25 dips. Those dips also appear
    on pattern B, so they're likely ECU quantisation.
  - Raw 0x40094A[0] = 0x08F6. So **FL = wheel idx 0**.
- **Health:**
  - FL sensor status 0x400952[0] = **0x08**, no fault bits; the empty channels show 0x99.
  - Direction counters 0x4029DB..DE = 0.
  - 0x4010CE[0..3] = 01 01 01 01 (presence error flag), but it is not latched into 0x400952 on mode 2.
  - DTC list: bench-only codes, but the list is capped at about 10 and evicts entries, so the RAM status is
    the authoritative check.
- **Result:** the plausibility check `sub_06EC18` (teeth-based thresholds) did NOT object to 48 pulses/rev
  with teeth=48 at 23 km/h. **No tooth-count change is needed.**
- **Bench-proven patch set for a 7→7/14→28 in-loop scaler on E46 front rings:**
  - mode 2 (0x7DA57 = 0x23)
  - front-only direction mask (0xC13C4 `60C2 60C3`)
  - front K×2 (0x7D1C0 `3C13 9307 7722`)
  - then re-sign.
- **Still to do:** a speed sweep (low end: the floor now corresponds to ~1.24 km/h real on the fronts; high
  end: plausibility at speed), and the actual scaler circuit with a real E46 sensor.

### [verified, bench 2026-10-05] TI 5895-5120: READ command found, full register dump, threshold hunt NEGATIVE
Context: the ECU was on `m3_probe_mode2_dirF_lvl13`. Stimulus was the ESP32 rig on FL, with a 7/14 mA square (E46-like,
Re 270 Ω) or a 7/28 mA square (Re 91 Ω, positive control: FL 11.44 km/h).

**Command field (verified):**
- The low 3 bits of the 10-bit ID are a command field: **xx100 = WRITE** (all firmware writes), **xx000 = READ**,
  101 = loopback (0x1A5).
- A read returns the current value in RX1 and changes nothing. Proven: reads of 0x158 between writes to 0x15C left it
  unchanged.
- A write returns the previous value in RX1. RX0 is always 0x0024.
- **Full read-only dump** of all 128 registers: `analysis/agents/asic_sensormode/asic_dump_ro.txt`
  (`asic_dump_ro.py`). Firmware-written registers read back their init values: 0x104 = 00F, 10C = 0FF, 174 = 200,
  21C = 1FF, 2FC/304 = 0E5, 30C/314 = 1FB, 26C = 1AA, 274 = 0C0, …

**Live registers** (12 samples while a 7/28 square ran):
- Steady with LSB jitter, likely supply/temperature ADCs: 0x030 ≈ 3F0, 0x090 ≈ 2A0, 0x098 ≈ 0C5, 0x0B0 ≈ 370,
  0x0F0 ≈ 1FE.
- Varying: 0x0A0, 0x0A8, 0x0C8, 0x0E8.
- **0x0A0 is bimodal**, about 0x013 or about 0x0C4, which may be FL's sensor-current ADC. To confirm, hold L and then H.

**Per-channel block 0x184–0x1DC**, three registers per channel at a stride of 0x18:
- ch0: 137 / 2C5 / 015
- ch1: 126 / 2CD / 015
- ch2: 1E5 / 22F / 01A
- ch3: 1E5 / 22F / 01A

**Threshold hunt — every candidate NEGATIVE.** None of these let a 7/14 mA square count, and none stopped a 7/28 mA
square from counting:
- (a) 0x154/15C/164/16C (stock 0x1B = 27): all values 0x00–0x3F, rewritten continuously, with the 7/14 stimulus.
  No edges.
- (b) 0x114–0x14C (they read **0x00A/0x00B**; the old report's 0xBF/0xC4/0xF2 was a mis-map): each register alone,
  0x000–0x3F0 in steps of 0x10, with 7/14. No edges.
- (c) 0x184–0x1DC pairs:
  - Lowered to (0x0A0, 0x15E) / (0x0A0, 0x120) / (0x080, 0x180) with 7/14: no edges.
  - **Raised to 0x3FF and zeroed to 0x000 with 7/28: FL kept counting** (19 distinct intervals per 1.5 s, unchanged).
- **Conclusion (registers above only):** the I_H level is not adjustable through THESE registers.
  **Superseded on the bottom line 2026-10-06:** the global register **0x28C** (sensor-mode mask) switches a channel
  to 2-level mode, so E46 sensors do NOT need external hardware. See `docs/E46_SENSOR_FIRMWARE_PATCH.md`.

**Side findings:**
- The `lvl13` flash patch to the global table (0xDF244..) did NOT reach 0x154/164/16C; something rewrites 0x1B.
  Only the runtime literal in `sub_07452A` (CPU 0x746FC, value at file 0x7C6FE) took effect, on 0x15C.
- **[user] Audible 1 Hz tick:** the bench unit normally ticks at 1 Hz. With 0x15C at 13 (runtime literal) the tick
  STOPPED, and it stayed stopped after a manual restore, because the firmware re-applies 0x0D.
  - So the 0x1B field is actuator-side, likely a valve-driver or test-pulse setting.
  - The bench unit has no hydraulic block, but the valve coils are in the ECU lid.
- Live pokes persist (no fast periodic rewrite seen for 0x154–0x16C or 0x184–0x1DC).
- **[verified 2026-10-06] DANGEROUS: writing 0x000 to ASIC reg 0x24C HANGS THE ECU.**
  - After the write: no diagnostic responses and no 0x0CE TX. A power-cycle recovers it.
  - 0x24C is from the 0xD7210 global table (init 0x090, reads 0x040). It is likely a supply/watchdog/reset control,
    in the TPIC7218-style power+sensor ASIC model.
  - **Do not sweep 0x24C–0x2F4, 0x00C or 0x2FC–0x314 blindly.**
- **More block tests (7/28 stimulus), each set to 0x000 and 0x3FF: no effect on counting.** Registers: 0x174 (0x200),
  0x17C, 0x21C (0x1FF), 0x104, 0x10C, 0x224, 0x194/1AC/1C4/1DC, 0x1E4–0x1FC, 0x23C. All were restored.
- **[user hypothesis, open] The I_H threshold may be set by an external per-channel sense resistor.** TPIC7218 analog:
  thresholds ∝ VREF/R_LOAD, with R_LOAD = 50 Ω giving 10/20 mA.
  - Doubling the front channels' R_LOAD would make E46's 14 mA count as I_H.
  - Next steps: measure signal-pin V at L/H to get the sense R, and find the 4 per-channel resistors on the PCB.
- **[verified 2026-10-06] Repeat on the clean `dirF` image** (0x1B restored), with a KWP `11 01` reset (`51 01`)
  between sections. All three 7/14 sweeps were negative again: (1) 0x154–16C, 0–63; (2) 0x184–1DC pairs lowered;
  (3) 0x114–14C, each register 0x000–0x3F0. The baseline and final checks showed no edges, and 7/28 positive
  controls counted.
  - So the `lvl13` state did not distort the earlier result.
  - **New: 0x114–0x14C self-adjust**, flickering between 0x00A and 0x00B from read to read. This is auto-tuning
    (offset or baseline trim), not a static config.
  - `11 01` works whenever all wheels read < 1 km/h.
- **Restored 2026-10-06:** the ECU is back on `m3_probe_mode2_dirF`, with 0x154–0x16C and the runtime literal at 0x1B,
  verified live.

### [verified, bench 2026-10-06] ★ ASIC reg 0x28C = per-channel SENSOR-MODE MASK. Clearing bit0 makes FL read 2-level (E46-type) signals
- **Stock:** 0x28C = **0x00F**, written once by the init table at CPU 0xD722C / **file 0xDF22C** (`028C 000F`).
  - It is the only ASIC writer of 0x28C. The literal 0x28C at CPU 0xBD4E8 is the number 652 in control logic,
    not a register ID.
- **Discovery:** the gentle sweep of the remaining global registers, with the ESP32 rig sending a **7/14 mA** square
  on FL.
  - 0x28C values with **bit0 = 0** (000/008/00E/010/016/080/200) all produced FL edges.
  - Values with bit0 = 1 (00B/00D/011/013/3FF/00F) produced none.
- **Confirmed by holding 0x28C = 0x00E** (bit0 cleared), on image `dirF` (mode 2 + front direction mask, no ×2):
  - A **7/14 mA** 150 Hz square reads **FL = 11.44 km/h, valid** on 0x0CE (raw 0x00B7); 0x40094A[0] = 0x047B.
  - **FL status 0x400952[0] = 0x08 (healthy)**, and the edge counters tick.
  - That is the same behaviour as a 7/28 square in stock mode (one count per dwell, so 48/rev on a 48-tooth ring).
- **Interpretation:** bit n = channel n in VDA/AK 3-level mode (I_H ≈ 20 mA). Clearing it gives a 2-level mode, where
  14 mA counts as an edge.
  - **FL = bit0.** Bits 1/2 cleared did not affect FL. The FR/RL/RR mapping is TBD.
  - This is the likely mechanism behind E85 Z4 MK60E5 units running E46 sensors.
- **★ [verified, bench 2026-10-06] A REAL E46 sensor reads on MK60E5** once 0x28C = 0x00E (live poke):
  - Hand-spinning the tone ring gives **FL 0x0CE valid, rising to 5–7 km/h per spin and decaying smoothly**
    (e.g. 0x70 = 7.00 → 0x0C = 0.75 km/h).
  - The same sensor read nothing at stock (2026-10-04 A/B).
  - The reading is half speed: one count per tooth, so 48/rev.
- **★ [verified 2026-10-06] FLASHED patch works.** Image `m3_probe_mode2_dirF_2lvlFL` (init table file 0xDF22C →
  `028C 000E`):
  - 0x28C reads 0x00E straight after boot, so no other writer overrides it.
  - The real E46 sensor reads on FL with no live poke.
- **Half-speed fix lead: MCU capture edge-select.**
  - `sub_0D569C(ch, mode)` (jump table + per-channel bodies) programs timer channel control 0x…8E bits 12:11 from
    the mode bits: 0x08 → 01, **0x10 → 00 (stock, mode 0x91)**, 0x20 → 10. Mode 0x80 enables capture setup,
    0x40 writes 0xF80340 = 1.
  - Speed channels are configured at CPU **0x6F524**: `611D 347D` (movi r13,17; bseti r13,7 → 0x91), then
    cfg(0..3, r13).
  - Live: 0xF8008E = 0xA007, 0xD8008E = 0x2007 (bits 12:11 = 00).
  - Test images: `…_2lvlFL_edgeA` (`609D` → 0x89, field 01) and `…_edgeB` (`621D` → 0xA1, field 10). Each applies to
    ALL channels, so a production patch must be front-only (rear VDA pulses would double-count with both edges).
- **★ [verified, bench 2026-10-06] Capture edge field 10 (mode 0xA1, image `…_2lvlFL_edgeB`) = BOTH EDGES.**
  Hand-spun real E46 on FL:
  - edgeB peaks **10–18 km/h**; `2lvlFL` and edgeA peak 5–7 km/h for similar spins. Live 0xF8008E = 0xB007.
  - At rest: CAN FL = 0.00 and 0x40094A[0] = 0x3E (the normal 0.62 floor). **No standstill/floor side effect**, because
    K is untouched.
  - edgeA (field 01, 0xA807) reads normally, single edge (likely falling).
  - So **0x28C bit0 cleared + capture both edges = native 96/rev from a 48-tooth E46 ring**.
  - Precise confirmation is still to do: the rig's 7/14 square at 150 Hz should read ≈ 22.9 km/h.
- **Production needs:**
  - (a) Both-edge capture on the FRONT channels only. Rear VDA pulses would double-count. The stock call sequence at
    0x6F524 uses one r13 for all 4 channels, so this needs a small code cave: ch0/1 = 0xA1, ch2/3 = 0x91, then
    r13 = 0x91 on exit.
  - (b) The FR bit in 0x28C (still TBD).
  - (c) Mode 2 + front direction mask (already in place).
  - (d) Bench-verify rears still read VDA correctly.
- **★ [2026-10-06] ALL-FOUR-WHEEL E46 image `m3_probe_e46all` (flashed and verified live).** Built on `…_2lvlFL_edgeB`:
  - 0x28C = **0x000** (file 0xDF22E), so all channels are 2-level.
  - Capture mode 0xA1 on all channels (file 0x77524 `621D`).
  - Direction mask stored directly as 0: file 0xC13C4 `6002 6003` (movi r2,0; movi r3,0), bypassing
    `validate_dir_cfg`, which maps 0 → 15.
  - Mode 2 (0x7DA57 = 0x23). The 0x23 peek handler is still present (bench-only).
  - Live readback: 0x28C = 000; 0x4029D6 = 00; 0xF8008E = 0xB007; 0xD8009E = 0x3007 (bit12 = both edges).
  - **★ [verified, bench 2026-10-06] ALL FOUR WHEELS read a real E46 sensor** (one sensor moved FL → FR → RL → RR, hand-spun):
    - Each reads valid on 0x0CE, peaking at 11–22 km/h (both-edge capture), and decays to the 0.62 floor then 0 at rest.
    - The rear per-channel registers (0x1B4.. = 1E5/22F/01A, which differ from the fronts' 137/2C5/015) do NOT matter.
      RL read with the originals (control test). An earlier 'RL no edges' was simply no spin.
    - Post-test DTCs: only 5D90/5DA0/5DB0 'electrically defective' on the channels left unplugged, plus bench CAN
      noise. **No 5D91 extrapolation, no 5D95 double-frequency, no 5D96 direction.**
    - Status bytes 0x400952[w] read 0x80 with a sensor connected at rest (0x08 when moving), and 0x99 when unplugged.
  - **Remaining before the car:**
    - Exact-scale check with the rig (7/14 mA, 150 Hz → expect ≈ 22.9 km/h).
    - A drive/high-speed sweep for plausibility.
    - Fault behaviour: unplugging or shorting an E46 at speed should give a DTC.
    - A car image WITHOUT the 0x23 peek handler.
- **Side note:** while sweeping, FL briefly went invalid (0x8000) as the mode toggled on and off. Held steady, it is
  clean.
- **Remaining:**
  - (1) Flash-patch 0xDF22C → 0x00E (FL), or the front bits once FR is identified, and verify the value survives init
    (other writers may exist, as with 0x154).
  - (2) Test a real E46 sensor plus tone ring.
  - (3) Speed is half on 48-tooth rings (one count per tooth). The fix is a front ×2 without the floor bug, OR switch
    the MCU timer capture to both edges if the ASIC output follows the sensor level in 2-level mode (capture config
    0x91, `0x0D5CDC`).
  - (4) The mode-2 + front direction mask is still needed (no direction info from 2-level sensors).
- **Earlier gentle-sweep results (7/14, no hits):** 0x2FC/0x304 (0E5), 0x30C/0x314 (1FB), 0x264, 0x26C, 0x274, 0x284,
  0x2CC, 0x2D4. The run was interrupted after 0x2D4. A later hang (no response, power-cycle) occurred around
  0x2E4/0x2F4/0x24C; the exact register is unknown.

### DEFINITIVE bench result: VDA encoding is the gate (2026-10-04)

**SUPERSEDED 2026-10-06 → see `docs/E46_SENSOR_FIRMWARE_PATCH.md`.** The A/B result is still true for STOCK firmware. The conclusion that this is "not firmware-configurable"
is wrong: ASIC register 0x28C switches the channel to 2-level mode.

Controlled A/B on the live unit (running the mode-2 image), same slow hand motion of a tone ring:
- **E46 active sensor (non-VDA): NO reading** on 0x0CE (FL stayed 0x0000, all channels static through 30 s of
  stimulation; the only "changing" CAN ids were alive-counters).
- **E90 active sensor (VDA-encoded): reads speed immediately**, even hand-moved at the same slow rate.

This is the empirical confirmation of the whole RE chain and **closes the non-VDA-sensor question**:
- The slow/irregular-rotation hypothesis is REFUTED — the E90 reads fine at the identical slow speed, so the
  blocker is purely the **VDA data encoding**, not speed/plausibility.
- ~~The TI ASIC (5895-5120) only emits capture pulses to the MCU **after decoding a valid VDA frame**.~~ **REFUTED 2026-10-05: it counts bare 28 mA (I_H) pulses with no data bits — see entry above.** A non-VDA
  sensor produces no decoded pulses → the capture counters never increment → no speed, at any rate.
  ~~**Hardware/ASIC gate, not firmware-configurable.**~~ (wrong; see 0x28C) No byte patch (mode, presence, direction, ASIC-reg guesses) can help,
  because the pulses never reach the capture path.
- **[user, 2026-10-05] The mode-2 image did NOT set a presence fault with E46 sensors connected.**
  So the mode-2 presence check passes without VDA data bits. Caveats:
  - The direction-invalid check (4.01–55 km/h, 175 counts) never ran, because no speed was read.
  - That check is still untested for a no-data-bit signal.
  - Relevance: a "dumb" in-loop 3·I−14 scaler (7→7, 14→28 mA, no data bits) only needs the ASIC to
    count bare I_H edges. Test patterns A/B are in `docs/VDA_CONVERTER_DESIGN.md`.
- Side-confirmation: the E90/VDA sensor reads even on the **mode-2** image → the speed-magnitude path is
  mode-independent (matches `sub_07525C` having no mode check), and the mode byte only ever affected the
  presence/fault logic.
- ~~**Practical conclusion:**~~ (superseded by the 0x28C firmware patch) use VDA sensors (E8x/E9x active Hall)
  with MK60E5 — they work natively. Non-VDA
  (E46 active or passive VR) would require a HARDWARE change (ASIC input reconfig via the unavailable TI
  datasheet, external VDA-synthesis circuitry, or JTAG-level probing), never a firmware edit.

## [verified 2026-10-05] Live ASIC/RAM peek-poke instrument (patched 0x23)
Repointed service-table 0x23 handler (file 0xFB1A0: 0x000B3112 -> 0x000D8F98) to a
128-byte M-CORE handler at CPU 0xD8F98/file 0xE0F98. Request = exactly 6 bytes
`23 <op> <arg:4>` (0x23 table len=0x06 is EXACT; the KWP dispatcher @0xB11B8 enforces
table[1] as exact length unless 0xFF). op=1 ASIC xfer (r2=arg; jsri 0xD4A30; return
4-byte readback (RX0<<16)|RX1); op=2 RAM peek (16 bytes from CPU addr). Reachable in
default session, no auth (flags[8]=0x94, seclvl=0). Handler = clean subroutine
(dispatcher calls `jsr r7`); frame MUST mirror a real handler (subi r0,16/stm r13-r15
.. ldm r13-r15/addi r0,16/jmp r15) — a single-reg stm/ldm r15 hard-hangs the ECU.
Response: data@0x40948A, len@0x409537=databytes+1, ready@0x409435=1 (TX prepends 0x63).
Build: tools/build_asic_probe.py; drive: `mk60_can.py asic {xfer|dump|ram}`.
PROVEN: RAM peek @0xF56C8 returns the auth key byte-exact; ASIC reg 0x008->RX1=0x00AE,
0x1A5->RX1=0x02CD (RX0=0x0024 const). Both paths validated; ECU stays healthy.
This is an owner-authorized bench-only instrument on the cut-open test unit.

## [research 2026-10-05] Cross-OEM tooth-reading AK/VDA front-sensor candidates (E46-front retrofit)
**Not needed since 2026-10-06:** E46 sensors run directly with the firmware patch
(`docs/E46_SENSOR_FIRMWARE_PATCH.md`). Kept for reference.
Goal: a sensor that reads a ferromagnetic TOOTHED ring AND emits the AK/VDA directional
telegram MK60E5 decodes (7/14/28 mA, direction bit), to run E46 front reluctors.
- No off-the-shelf part is gear-tooth + AK + E46-bolt-in. Every gear-tooth+AK device is a
  bare IC (Allegro ATS604 [best: integrated back-bias magnet, native AK, 7/14/28mA, 5.2-24V,
  EEPROM-config], NXP KMI25/4 [AK, <=16V, fixed map], Infineon TLE4943C [needs ext magnet]).
  Bosch Motorsport DF11S is housed but only 2-level current (NOT directional AK) -> won't pass gate.
- Best buyable cross-OEM candidate: VW Touareg(7L/7P)/Audi Q7(4L)/Porsche Cayenne FRONT sensor
  (WHT005651A, 7L0927807x, 7P0927807x, Porsche 95860640500/1/2, ATE 24.0711-series). Reads a
  steel toothed ring on the outer CV joint, cylindrical bolt-in (same concept as E46 front),
  ~66mm long. Favor 7P/958 (2011+) for full directional AK. Secondary: MB W220/R230/W211 front.
- Fitment: sensor-tip OD is unpublished everywhere (TecDoc has no OD field) -> must caliper.
  Rough bracket ~12-15mm. E46 front = bolt-in 5mm-hex (M6) slip-fit tip. CRUCIAL: E9x REAR
  sensor (34526870077, the kind that solved the user's rears, tooth+VDA) is the SAME BMW bolt-in
  active-Hall 5mm-hex flange family as E46 front -> test the existing rear sensor in the E46 front
  bore FIRST (may drop in / light shave). Aftermarket sensors commonly run oversize -> shaving/sleeving routine.
- Two unknowns both bench-resolvable: (1) tip OD vs bore = calipers; (2) directional-AK decode =
  patched-0x23 peek tool (watch 0x40339E while spinning). No datasheet needed to decide.

## [verified 2026-10-05] M3 (7846816A) ABS algorithm — full characterization (5-agent pass)

Consolidated doc: `analysis/ABS_ALGORITHM_M3_7846816A.md`; per-domain detail in
`analysis/agents/abs_full/0{1..5}_*.md`. CPU addrs; file = CPU+0x8000. Frame 10 ms.
Units: speed/slip 0.01 km/h, accel/decel 0.01 g, pressure 0.01 bar (pinned by CAN 0x2B2/0x19E ÷100 = bar). Core architecture is opcode-identical to the 1M; RAM/cal addrs differ.

- **Two triggers.** (1) Slip = plain `vref−wheelspeed` in 0.01 km/h (NOT a ratio): entry gate 0x40DB6
  ~1.5 km/h arms; gross-slip limit 0xD6CE2 = flat ~6 km/h to 55 km/h then **11.04 % of vref** (k=113/1024).
  (2) Wheel-decel crossing a speed/g-dependent threshold. Interlocked in per-wheel phase machine
  `abs_phase_sm` 0x4FC3C (armed 0x80→DUMP 0x21→HOLD 0x09→REAPPLY 0x11). [verified]
- **vref 0x408DA8** = rate-limited integrator (`vref_update` 0x449D0), not max-select; rises +44/frame
  (+1.25 g) toward fastest front, falls decel-limited −44/frame during ABS. [verified]
- **Decel threshold** (0.01 g, builder 0x47BDC): `thr = −1.16g − speed_term(vref) − g_term(|decel|)`,
  then floors max(−2.40g); <60 km/h max(−1.32g); <20 km/h max(−1.27g). speed_term 0x48412 (var), g_term
  0x48674 (var). 100 km/h@1g→−1.61g, 300 km/h→−2.26g. Re-apply on positive spin-up threshold. [verified]
- **LATERAL G AFFECTS ABS — YES, in ABS-only.** ABS has its own sensor latch (lat accel 0x408ECA, yaw
  0x408ECC). (a) code-32 cornering handling (`abs_decision_classify` 0x51B54 + exec 0x58FF4). (b) Pair
  cornering gate 0x54D9A. (c) Inside/outside rear select-low 0x5184C. [verified]
  The cal curves 0x40E0A/0x40E26 are a lateral-g pressure term that **rises** with |lat g| (26→49 / 14→40 bar), not a
  knockdown. The code-32 rear reduction uses a separate pct byte 0x408DE0 (the position of driver pressure between
  the two curves, "ABS with and without the SZL"), plus rear select-low.
- **Steering reaches ABS** via the getters and sets the yaw-stable flag `0x408E5F` b4; see "ABS with and without the SZL". **Vehicle model (mass/l_f/l_r/Cf/Cr/Jz) feeds ONLY DSC**
  — zero reads in the ABS region; it is NOT an ABS tuning lever. [verified] **EBD is decel-driven** (front
  0x40412/rear 0x405F2), not model-based. [verified]
- **HARDWARE: the MK60E5 has FIVE integrated brake-pressure transducers** — 1 on the input/master side
  plus 1 per hydraulic output (one per wheel circuit) — all built into the valve block; the board also
  carries a longitudinal-accel sensor. The **"E5" designation denotes this 5-pressure-sensor configuration**
  (vs the single-sensor MK60E). Supplier Continental Teves. [source: BMW DSC MK60E5 training doc;
  tomazcebul/MK60e5-Standalone README; multiple standalone-swap forums] [user: confirmed 5 transducers on
  the physical PCB contacting the block]
- **CAN pressure broadcast [verified]:** the DSC transmits all five measured pressures, matching the
  external DBC (commaai/opendbc `bmw_e9x_e8x.dbc`). Detail: `analysis/agents/abs_full/07_pressure_on_can.md`.
  - `0x2B2 WheelPressure` (DLC8, 20 ms): **bytes 0–3 = wheel pressures LF, RF, LR, RR** (wheel index 0..3;
    front=0/1, rear=2/3). Getters 0x7B490/4DE/51C/566 → `sub_08D030(idx)` read staging `0x40499A + 4·idx`
    (value@+0, flags@+2), `clamp(s16/100, 0..254)` → bar, 0xFF=invalid. Writer `sub_08CFCC` copies PM
    `0x4016E2[w]` and sets flags: b6 = wheel-sensor system enabled, **b5 = PM is measured** (`0x401719`
    b7 front / b6 rear), b7 = valid. Bytes 4.4–5.7 = a ×939 yaw/accel value (not pressure); 6–7 = flags.
  - `0x19E StatusDSC` byte 6 = master/input pressure: getter 0x7AD2A → `sub_093F00(2)` → `0x401FF8`
    (validated, offset-corrected, filtered master sensor), same ÷100 → bar.
  - `0x1A0 Speed`: VehicleSpeed 0.0/12, drive direction 1.4/3, AccX 2.0/12, AccY 3.4/12, YawRate 5.0/12,
    alive 6.4/4, checksum 7. Full decode: `analysis/CAN_TX_TABLE_7846816A.md`, "Frame 0x1A0".
- **Pressure sensing: all five transducers are sampled AND used for control [verified].** Detail:
  `analysis/agents/abs_full/06_pressure_sensors_recheck.md`.
  - **Master sensor** (ASIC ch 6/7, raw 0x402954, `pressure_adc_track` 0x8F344) → validated `0x401FF8`.
    Driver pressure `0x404994` (slot 0, 0x8CE5E, sole store 0x8CE9E) = `0x401FF8` when the master sensor
    is valid; else the mean of valid wheel pressures (`sub_08CDC4` → `0x404996`, if ≥ 1 bar); else
    modelled circuit pressure `0x40171A`.
  - **Four wheel-output sensors**, each dual-element. Primary element: fast SPI burst `sub_06FD90`
    (several samples per 10 ms frame) → `sub_08FA00` (zero offset `0x40218C[w]`/16, 4-sample average) →
    **measured wheel pressure `0x402198 + 4·w`** `{value, flags}`, 0.01 bar. Redundant element (raw
    `0x4029B6..BC`, filtered `0x402096[w]`, offset `0x40209E[w]`) is plausibility-only. Control getter
    `sub_091A50(w)` — 16 call sites.
  - **PM `0x4016E2[w]` is measurement-primary.** `sub_082BC0` (in `hydraulic_model_step`, 0x82F36, 10 ms):
    normal → **PM = measured** (store 0x82E9C) and volume `0x4016DA[w]` re-synced via `coa_pressure_to_vol`;
    outlet/dump active (valve state `0x401A16[w]` < 0, latched `0x401715[w]`) → COA volume model until the
    state goes positive, then the volume error is reconciled into `0x4016F2[circuit]`; inlet fully open
    (state 20) with recent pump flow → min(p(V(PM) + 500), measured), so PM may rise by at most 500 volume
    units per frame (store 0x82E06; detail in `analysis/7846816A_symbols.md`, "Circuit volume model"); **gate closed → pure model for
    all four wheels**. Gate = `0x402888` b5 clear, fault ids 35/57/59/61/63 `<<15` not latched, and all
    four sensors valid (one invalid sensor drops all four).
  - **Other direct consumers of measured wheel pressure:** ABS `sub_046ADC` (per-wheel filters
    `0x408E20 + 14·w`, referenced by ~15 ABS routines), `sub_055A84` (7-deep history `0x403296`),
    `abs_hold_entry_sync` 0x57200, `abs_decision_resolve` 0x58B30, `valve_pulse_sequencer` via `sub_084620`
    (cell `0x40206A[w]`), `coa_wheel_gain_apply` 0x84E38, 0x69992/0x89D8A/0x8A90C/0x8B9E0 (role open),
    KWP 0x21 via `sub_0946D0`. How the ABS routines use the value in their decisions is open.
  - `supply_pressure` 0x84D42 = clamp(max(partner PMs, driver pressure 0x404994), 0, 200 bar) — both
    terms measured in normal operation. The return pump still injects volume into the model
    (`circuit_volume_update` 0x826C0), which matters for PM only in model phases.
  - **Consequence for datalogs:** 0x2B2 is real per-wheel output pressure and 0x19E byte 6 is the input
    side — different transducers. Front/rear circuits are separate (wheel→circuit ROM 0xDA1B4 = 0,0,1,1),
    so on a dual-master/bias-bar car 0x2B2 shows the true front/rear split, and rear above master is
    physical. During an ABS dump the affected wheel's byte is the model estimate until re-sync.
  - **Bench unit:** if the wheel sensors are faulted or disconnected the gate closes and PM/0x2B2
    become pure model; otherwise they read the (zero) block pressure. [inferred] Watch `0x401719` b7/b6 and
    `0x402198 + 4·w` vs `0x4016E2 + 2·w` over the 0x23 RAM peek.
- **Owner's sluggish-brakes concern:** under braking the dominant loop is measured slip + wheel-accel
  (10 ms), and pressure metering is closed on measured wheel pressure, so a P-V error mis-sizes single
  pulses rather than accumulating. Onset "bite" is the apply-ramp/slew constants (apply +400/frame, dump
  −8000, slew 0x584CC). P-V accuracy dominates only in dump phases and in sensor-fault fallback. COA
  tables are 1M-identical (not M3-retuned). [verified/inferred]
- **Variants:** ABS = two flavors only, 0–9 (M3 / Competition, all bodies) vs 10/11 (GTS coupe / GTS sedan;
  tolerate deeper decel at speed, floor −1.40g <60 km/h). Only front speed-term/g-term families are variant-indexed; rest global. M3 index in EEPROM
  (coding byte[1]&0x1F), default 0. [verified]
- **µ-split/GMA** = decision code 32 (0x54D9A→0x58FF4), **gated by lateral g**. **Low-µ** = deep-slip flag
  (0x40902E b4), no continuous µ estimator / no µ-indexed slip remap / no NVM learning. Rough-road
  suppressor 0x5567C. Standstill 0x41CF2=72; apply cut <4 km/h; **ABS runs in reverse**. [verified]
- **BENCH UNIT:** no wheel edges ⇒ group-1 plausibility faults ⇒ global inhibit 0x4009BC clears master
  gate 0x401FF2 b7 ⇒ **ABS never arms without plausible wheel signals** (does NOT degrade gracefully). [verified]
- **Track tuning levers (ranked) [REVISED 2026-10-05]:** (1) the code-32 cornering rear-knockdown — the real
  mid-corner pressure cut (exec 0x58FF4: CMD = max(1 bar, PM − pct·G/100), 09 §2.1 item 7), driven by pct byte 0x408DE0
  (producer: 0x51F42, "ABS with and without the SZL") + rear select-low 0x5184C; this is the lever for trail-brake authority, NOT the
  0x48E0A/26 curves (those ADD pressure with g). (2) apply-ramp/slew onset. (3) decel floors / variant 10/11. (4) gross-slip
  slope 0xD6CE2 (smallest; stock ~11 % already near peak-µ). NOT levers: vehicle model, COA P-V.
- **Unmapped global cal to add to XDF:** 0x40C40, 0x40C5A, 0x40D24, 0x40D40(=50), 0x40D42(=7000),
  0x40DD2(=1748)+0x40DD8, rough-road 0x40D66..0x40D7E (CPU; file +0x8000).

## [verified 2026-10-05] ST_CLCTR control-state bitfield

- **ST_CLCTR = CAN 0x19E (StatusDSC) byte 0** — a BITFIELD (getter `can_tx_19E_status_flags` 0x7AEAA),
  assembled from the ABS control-state block 0x408DA0/0x408DA2 + intervention flags:
  - **[verified 2026-10-14] bit0 (1) = a FRONT wheel is in an ABS cycle** ← 0x408DA2 b7. Not a general "ABS
    engaged" flag. `abs_state_aggregate` 0x45808 (called from 0x45EC4) clears DA2 b0/b5/b6/b7 every pass
    (0x45858–0x45864), then loops over the wheel records 0x40BF00+0x40·w (0x4596C–0x45A32). For each wheel
    with `rec[0]` b0 (in cycle: DUMP 0x21 / HOLD 0x09 / REAPPLY 0x11 / 0x15) it sets DA2 b0+b6 and 0x408DA1
    b4, then DA2 **b5 for a rear** (record address b7 set, w = 2/3) or DA2 **b7 for a front** (w = 0/1,
    0x45994). 0x45994 is the only instruction that sets DA2 b7 (the other writers 0x51160 / 0x51226 /
    0xB5D40 never do). So rear-only ABS leaves bit0 = 0, and pre-control (0xC0) or armed (0x80) don't set it.
    (At front engagement the phase machine DUMPS first, so front pressures drop when this sets.)
  - bit1 (2) = TCS/ASR ← 0x402FC0 b4 (brake TCS active) or (0x402F6C b7 ASR active ∧ 0x402F6D b3) [2026-10-26]; bit2 (4) = AYC/torque ← 0x400B0A&0xC0; bit3 (8) = DSC ← 0x400DF4 b7;
    bit4 (16) = **MSR (engine drag torque control)** ← 0x402F6C+1 b2 [user-confirmed 2026-10].
  - **[verified 2026-10-14] bit5 (32) = rear axle controlled without the front** ← 0x408DA0 b1. The only
    writer is 0x45A62 in `abs_state_aggregate`, right after the wheel loop (0x45A34–0x45A62). The other DA0
    writers (0x5184C, 0x51A5C, 0x58B30, 0x5CAF4, 0x5DC08) touch only b4/b5/b7:
    ```
    if DA2.b5 (a rear in an ABS cycle):  bit5 = !DA2.b7          # rear in ABS, no front in ABS
    else:                                bit5 = 0x409049[4*2].b3 | 0x409049[4*3].b3   # rear decel-gate latch
    ```
    **No lateral or yaw input feeds this bit.** The earlier "lateral-limited / decision-code 32" label was
    inferred from bit position only and is **wrong**. The cornering latch (0x409049 b2+b5, set at 0x4E908) is
    not read here; only b3 is.
    - **Rear decel-gate latch 0x409049[4w] b3** (rears only), set at 0x4DF9E. Every condition must hold:
      - 0x408E1C b7.
      - One trigger path: ax 0x408E80 < −0.55 g (cal 0x40C94 = 70, +15) with 0x40902E[3w] & 0x12; or
        0x408E94 < −700 raw with 3 ≤ 0x408E6A ≤ 24. 0x408E94 is a second ax-type signal from
        `abs_sensor_gather` (getter 0x938E2: 0x404A00 − 0x404A04/10; fallback 10·0x408DAF). Units 1 mg/bit
        [inferred, see "The accelerometer IS broadcast"], so −700 = −0.70 g.
        0x408E6A is a frame counter in 0x471A4 that runs while 0x401FF2 b5 is set.
      - `rec+6` < 0.
      - Counter 0x409014[w] ≥ 2.
      - `rec[0] & 0x41` = 0 (not in a cycle or pre-control).
      - No EV0.b6 this frame.
      - No WSS fault (0x400952[w] b0 clear).
      - 0x401FF2 b7.
      - Driver pressure 0x408EB2 > 0.
      - 0x408E6D b6.

      On set it snapshots 0x408EB2 → 0x408E72.

      **Release** at 0x4ECA0 (any one):
      - ax > −0.55 g with 0x408E1C b7 set.
      - With 0x408E6D b6: driver pressure < snapshot − 4 bar AND < 0.8·snapshot.
      - EV0.b5 (dump trigger) on that wheel.

      While latched, 0x4ECA4 forces EV0.b6, which puts the rear into pre-control.
    - Open: meaning of 0x408E1C b7, 0x408E6D b6, 0x40902E b1/b4, 0x401FF2 b5; which of w = 2/3 is RL vs RR.
  - **The getter sets only bits 0–5 (≤63); it NEVER emits bit6=64.** The `64 = rear-control` value exists
    only in the *internal* decision code 0x408DDE, which is NOT broadcast (0 CAN getters read it). A logged
    ST_CLCTR=64 ⇒ the DBC byte/bit offset is wrong.
- **[verified code 2026-10-14] Rest of 0x19E decoded.** Full table in `analysis/CAN_TX_TABLE_7846816A.md`,
  "Frame 0x19E".
  - 1.0/2 ABS status (2 = off/failed).
  - 1.2/3 DSC status enum: 0 normal, 1 DSC-off lamp, 2 failed, 3 steering angle not valid, 4 mode lamp,
    6 start-up.
  - 2.4/4 event counter. Its trigger bit 0x4046D4 b4 has no setter, so it likely never changes.
  - 3.0/2 torque-intervention flag 0x402F6E b5.
  - 3.2/2 hill-start (LVC) flag 0x402BE8.
  - 5.0/2 brake-light switch state. The BLS is GPIO 0xDE0018 b0 (`bls_input_get` 0x6FE92), plausibility-checked
    against master pressure by 0xB7ABC.
  - 5.4/2 coded-feature-5 status.
  - 5.6/2 brake applied (BLS or any wheel > 6 bar).
  - 6.0/8 driver pressure (`can_tx_19E_driver_pressure` 0x7AD2A).
  - 1.6, 2.0, 2.2, 3.4, 3.6, 4.4, 4.6 are constant 3, 4.0/4 is constant 14, 5.2 is constant 0.
- **"ST_CLCTR=0 (ABS off), rear 0x2B2 > master 0x19E" is physical.** 0x2B2 rear bytes are the measured
  rear wheel-output pressures; 0x19E byte 6 is the master/input sensor. On a car with independent
  front/rear master cylinders they are different circuits. [verified sources; plumbing inferred]
- **Pump is NOT gated by the slip-control state.** `pump_motor_control` 0x88EC0 is gated by 0x401981 bit5,
  set in the actuation/arbiter pipeline (0x8428C/0x843BC), so the pump CAN run while ST_CLCTR=0 (precharge/
  autonomous build). [verified]

## [verified 2026-10-05] Cornering lateral-g pressure-term curves 0x40E0A/0x40E26 (decoded + in XDF/cal)

- Both curves (file 0x48E0A, 0x48E26; CPU 0x40E0A/0x40E26) are standard piecewise [lo,hi,n,xs,cs,ks] s16,
  n=4, 28 bytes each. Byte-verified:
  - 0x48E0A: lo0 hi100 xs[50,100,115] cs[26,20,7,-3] ks[82,205,341,427]
  - 0x48E26: lo0 hi50  xs[30,60,100]  cs[14,13,8,-7] ks[102,137,230,379]
- **BOTH take x = |lateral accel|** (signed byte 0x408ECA; ld.b/sextb/abs at 0x51C2C/40/54), **~0.01 g/count**
  (xs 50/100/115 = 0.5/1.0/1.15 g; byte ±127 ≈ ±1.27 g). NEITHER is yaw rate. [addr CONFIRMED; LSB inferred]
- **Output is PRESSURE (0.01 bar), and RISES with lateral g** — classify multiplies each curve ×100
  (0x51C3A/0x51C4E): 0x40E0A = 26→49 bar over 0→1.27 g, +5 bar hard-coded when |ay|>0.8 g (500 @0x51C62);
  0x40E26 = 14→40 bar. A lateral-LOAD (outside-wheel) pressure term that GROWS with cornering — **NOT a
  knockdown.** [CONFIRMED scaling]. Two curves → separate regs (0x40E0A→r8+boost primary, 0x40E26→r11
  companion); not multiplied/min'd. Exact store role (per-wheel ceiling vs reference) UNCONFIRMED.
- **The code-32 REAR KNOCKDOWN is separate:** exec 0x58FF4 (0x59222) sets a rear's `CMD(0x408F22)` = max(1 bar,
  PM − pct·G/100), G = the source wheel's dump depth LOCKEST − CMD (wheel roles open, 09 §2.1 item 7), where `pct` = small byte 0x408DE0 **(producer traced 2026-10-15: pct = 100·(P_drv − P_lo)/(P_hi − P_lo) with
  P_lo/P_hi from these two curves; "ABS with and without the SZL")**; plus rear select-low 0x5184C. This —
  not the 0x40E0A/26 curves — is what pulls rear pressure at turn-in. (The user logged a "big rear reduction"
  with ST_CLCTR=32. That CAN bit is NOT code 32: it means a rear-only ABS cycle or the rear decel-gate latch,
  see the ST_CLCTR entry. A rear dump or pre-control can explain the drop without code 32.) **The real trail-brake-authority lever is the 0x408DE0 pct producer (now traced: the two curves set it, so they are the lever. Higher curve values give a smaller pct for the same
  pedal, so less rear knockdown [I]).**
- Yaw rate (0x408ECC) is used separately at 0x51B88: curve 0x40E42 (x=peak-decel) sets a threshold |yaw|
  must exceed to latch the cornering flag 0x409024. 0x40C5A = the yaw-deviation monitor 0x4A254 (runs every
  ABS frame, not AYC-gated: 2026-10-25), does NOT factor into code-32. [CONFIRMED]
- TOOLING: added to xdf/MK60E5_7846816A.xdf (uniqueid 0x2A0–0x2A9, labelled bar / |lat g|) and
  tools/cal_yaml.py (`lat_g_press_a`/`lat_g_press_b`, round-trip byte-identical); tools/cal_plot.py plots the
  bar-vs-|lat g| panel. Re-sign MISR 0x4249C + BMY after any edit.

## [research 2026-10-05] AK/VDA protocol spec, ECU interface analogs, E46 sensor (→ 2-level→VDA converter)
**The converter is not needed since 2026-10-06.** The protocol and ECU facts below remain valid as reference.
Design doc: `docs/VDA_CONVERTER_DESIGN.md` (1-channel PoC converter, design only, not built).
- **[source] Why E46 sensors don't read, protocol-level:** an AK speed pulse is the 28 mA level (I_H).
  Pulse width is measured at (I_H+I_L)/2 ≈ 17.5 mA (Allegro A19302 fn.8). E46 sensors only switch 7↔14 mA
  (BMW ST034 p.33), so they never make a speed pulse. Their ms-long 14 mA dwell is also invalid Manchester
  ("a data bit without current edge in the middle is invalid", NXP KMI25 §5.3.1). This matches the
  2026-10-04 A/B.
- **[source] AK frame consensus** (NXP KMI25, Infineon TLE4943C, Allegro A19351/A19302/ATS604; the VDA
  AK-Protokoll v4.0 itself is NDA-only):
  - **Levels:** I_L 7 (5.88–8.4), I_M 14 (11.76–16.8), I_H 28 (23.52–33.6) mA. tp = 50 µs (40–60).
  - **Frame:** I_L ½tp → speed pulse I_H 1tp → I_L ½tp → 9 Manchester cells (low→mid = 1). 550 µs total.
  - **Trigger:** one frame per magnetic zero crossing, so 2 per period. MK60e5-Standalone: 96/rev.
  - **Bits b0..b8:** LR, M/SLM, unused, GDR, DR, LM0..2, even parity XOR(b0..b7).
  - **High speed:** last bits are cut (TLE4943C Table 2: 9 bits <1818 Hz … 2 bits <5000 Hz electrical).
  - **Standstill:** after 150 ms (105–195) with no edge, the frame repeats with the speed pulse at I_M.
  - **Vendor disagreements:** b2, DR polarity, standstill bit content. Settle these by scoping a real
    E90 sensor.
- **[source] ECU-side analogs (TI TPIC7218-Q1, ST L9396; the real TI 5895-5120 is not public):**
  - Sensing is low side, through ~50 Ω R_LOAD on the signal pin.
  - Thresholds: L/M ≈ 10 mA, M/H ≈ 20 mA. Open circuit is 1.0–3.5 mA (L9396). Overcurrent ≈ 31–40 mA.
  - Supply: BMW says "12V" (~10 V at the sensor). TPIC clamps at 8/12/15 V; L9396 runs at 6.5/7.2 V.
- **[source] E46 MK60 sensors are magnetoresistive, 7/14 mA, fed 12 V by the MK60** (BMW ST034 p.32–33).
  - **[user] All four E46 sensors are 2-wire.** ST034's "front sensors are three wire" doesn't match the
    user's car.
  - The IC inside is not public.
  - Representative 2-level parts: TLE4941plusC (≥ 4.5 V), A1684 (≥ 4.0 V).

## [disasm 2026-10-06] vref during all-wheel slip, the longitudinal-accel path into ABS, and the CAN speed source

Read directly from `analysis/7846816A_main.lst` (M3) in a single pass. **Not bench-verified.** Items marked
[inferred] are interpretation. CPU addresses; speeds 0.01 km/h; accel 0.01 g; one vref count per 10 ms frame
= 0.0283 g (so 0.36 count/frame per 0.01 g).

### `vref_update` 0x449D0 — what happens when every wheel is below vref
- **Wheel picks.** Cmax = fastest tyre-compensated wheel; Fmax = fastest compensated front; Vmin = slowest
  valid raw wheel. Skipped: fault bit `0x400952[w]` b0, `rec+0x19 & 0xC0`; Vmin also skips `0x40905E[2w]` b7.
  A wheel with `rec[0]` bit2 set cannot become Cmax/Fmax (looks like an overspeed mark [inferred]).
  Compensation factor = `(0x301 + byte)/1024`, byte from `0x403214[w]` or `rec+53` (learned tyre-tolerance trim,
  applied inline to `rec+0x1A`; fronts take the smaller byte, rears the larger).
- **Regime bit = `0x408DA1` bit4** (with bits 7:5 clear). Set: rise +44 while vref < Fmax, and the
  decel-limited fall below applies. Clear: rise only +22 (or +282 snap in controller modes 1/2/4) while
  vref < Vmin; fall −32. Bits 7:5 ≠ 0: −90 while Vmin < vref. **The earlier "+22 while ABS active" label looks
  wrong**: bit4 is grouped with the TCS/AYC/DSC active flags in `sub_092C26`, so bit4-set reads as the
  braking/ABS regime [inferred].
- **vref only falls when vref > Cmax**, i.e. above every wheel. In that state it is an open-loop
  extrapolation; wheel speeds do not enter the step. A wheel that recovers above vref pulls it back up
  (+44/frame).
- **Fixed-step fall (fallback path), per frame:** −22 or −44 chosen by phase flags (both fronts in
  dump/hold, a rear in control, vref ≥ 100 km/h, `0x408DA2` b5, front `rec+12` b2); −11 for one flag
  combination (`0x408DEE` b6 / `0x408DEB` b5 with `0x408E7A` < 140; meaning not established); −23 or −32
  plus `(75 + decel)/3` when the decel estimate `0x408DAF` < −80, reaching about −49 (1.4 g) — so −44 is
  not a hard cap on this path.
- **Inline decel limiter:** step = max(step, `(0x408DAF − margin)·360/1000`), margin **50** (or **30** when a
  front has `rec+12` b2), and at least `margin·0.36`. Skipped when an invalid wheel was seen, in controller
  modes 1/2/4, or when `0x400966` b6. (Earlier docs said margin 20…30; that is the helper's margin.)
- **Decel estimate `0x408DAF`** (s8, writer 0x534E6) = `0x408EE8 / 21`, or `0x408DB4` in one state. Writer of
  `0x408EE8` not found. `0x408DB8` (writer 0x532F0) is a vref slope: `(0x408DBA − vref)·453/16/(10n−10)`,
  clamp ±127. Both are speed-derived, so the fallback path is self-referential once all four wheels slip.
- Shadow integrator `0x408E7E` takes the same step and is kept ≤ vref. Floor `0x4032D0` applied after.

### Longitudinal accel IS used by ABS — from the F-CAN cluster, not an on-board ADC
- **Chain:** F-CAN RX `0x0D1` bytes 4–5 (sig 36) → `0x402F26` → `cluster_sensor_get(5)` 0xC583C →
  × sign cal `0x40F2C` (=1) → `0x404A00` (`sub_092B98`) → IIR low-pass `(10x + 7y)/8` (or `(10x+23y)/24`
  when `0x408DB5` b7; DC gain 10, so 0.1 mg) → `0x404A02` → minus zero offset `0x404A04` (= learned
  `0x4049FD` ×20), ÷100, clamp ±127 → **`0x4049FC`** (s8, 0.01 g, saturates ±1.27 g) (`0x92BBC`).
- Getter **`0x93828`** returns `0x4049FC` plus a status byte; "present" comes from ROM table `0xF6756[9]`
  (= 1 in this image); faults from `0x404A2E` b7:6 and `0x402888` b1.
- ABS sensor gather `0x5D82C` writes **`0x408E80`** (s16): default = wheel-derived `0x408DAF`; overwritten
  with the getter value when valid, which also sets **`0x408E6D` bit3** ("ax valid").
- **That signal 5 is longitudinal is [inferred]** (docs label the cluster "yaw/ay"): its offset is learned
  against the wheel-derived longitudinal decel (`sub_092C26`: accumulates `0x4049FC − 0x408DAF·37/32` over
  distance while no ABS/TCS/AYC/DSC flag is set; not fully traced), and ABS substitutes it for `0x408DAF`.
- **vref helper `0x50FF4`** (called from `vref_update` at 0x451F2). The b3 entry is dead (b3 is cleared again in the
  gather); the live route needs lat, yaw, steering and pressure valid ("Steering-sensor loss", "ABS with and without
  the SZL"). Coded conditions of the b3 entry: `0x408E6D` b3 set,
  `0x408DA1 & 0xE0` = 0, and — if `0x408E6D` b7 — |lat `0x408ECA`| ≤ 70; if a front has `rec+16` b2 it
  also needs `0x408E80` ≥ 0. (A second entry route exists without b3; conditions at 0x45142–0x45196.)
  - decel = −|`0x408E80`| in the bit4 regime (sign ignored). With bit4 clear it may pick the wheel estimate.
  - margin 20, or 30 when decel ≤ −50; +10 or −10 by phase flags; minimum 10.
  - when Cmax < vref: **step = max(−44, (decel − margin)·360/1000)**, and this *replaces* the fixed step.
  - So with a healthy cluster the all-wheel-slip extrapolation is accelerometer-driven, capped at 1.25 g.
- `0x408E80` has 59 references in the ABS region (0x45xxx–0x59xxx), including the decel-threshold builder
  (0x47AFE, 0x47CEA). Only the vref path was traced.
- **Standalone / no-cluster consequence:** ABS falls back silently to the wheel-derived estimate.
- The on-board longitudinal sensor mentioned in the 5-transducer entry is not used on this path; no
  evidence for or against it elsewhere.

### CAN `0x1A0` vehicle speed = mean of the two FRONT wheels, not vref
- `can_tx_1A0_vspeed` 0x7B1F2 loops over wheel records 0 and 1 only (fronts). Per wheel: skipped and
  counted as faulted if `0x400952[w]` b0 or `0x40288C` b2; else adds `min(rec+0x1A, 30000)` if above the
  floor `0x4032D0` (a wheel at or below the floor adds 0).
- 0 faults: sum/20 (front mean, 0.1 km/h). 1 fault: sum/10 (the other front). 2 faults: `0xFFF` and
  `0x4015E8` b7 set. Clamp 3000 (300.0 km/h). Stored to `0x404720`.
- Uses raw filtered wheel speed (no tyre-compensation factor) and never reads vref `0x408DA8`. It
  therefore dips with front slip under ABS, reads 0 with both fronts locked, and ignores rear wheelspin.
- **[verified 2026-10-14] AccX on 0x1A0 (2.0/12) is also front-wheel-derived, not the accelerometer.** Getter
  0x7B0AC → `ax_signal_get(1)` 0x9390E → 0x40200E (writer 0x8F2B0) = mean of the unfaulted fronts' wheel accel
  (rec+0x20, 0.01 g), clamp ±1.00 g, IIR α = 1/32 (`iir_blend_q8` 0x712FC, k 248); ×4 on CAN (0.0025 g/bit). 0x800 only when both fronts are faulted.
  So it shows front-wheel deceleration under braking and ABS, not body decel. AccY and YawRate are the conditioned,
  offset-corrected cluster signals (0x4020DA, 0x4020F4), scaled to 0.025 m/s² and 0.05 °/s per bit.
- **[verified] The accelerometer IS broadcast, in 0x1A3 and 0x2B3, not 0x1A0.**
  No caller uses `ax_signal_get(0)` (the offset-corrected 0x4049FC). 0x1A3 0.0/12 (0x7B906) and 0x2B3 1.4/12
  (0x7B7F4) send idx3 = raw 0x404A00 (unfiltered, no offset correction). 0x1A3 1.4/12 (0x7B96E) and 0x2B3 3.0/12
  (0x7B83C) send idx2 = 0x4049FD, which is the **learned zero offset**, not a filtered accel (0x93A52 is only one of
  several writers, and the ax filter has a DC gain of 10).
  - 0x4049FD is the s8 offset-learner state: seeded from 0x404A02/20 (0x93A52) or from EEPROM (0x92186), stepped
    by at most ±5 (0x92DF2–0x92E24), clamped ±119, and stored ×20 as the subtracted offset 0x404A04 (0x92E2A).
  - Units: `(10x + 7y)/8` settles at 10x, so 0x404A02 and 0x404A04 are 0.1 mg and 0x4049FD is 2 mg (±0.238 g).
    0x404A00 is **1 mg/bit [inferred]**: it matches 0x4049FC = (0x404A02 − 0x404A04)/100 being 0.01 g, and the
    lateral channel from the same cluster (0x8FE70, unity gain) is 1 mg at 0x4020D6.
  - On the bus both signals of a frame share one scale, so corrected ax = raw − offset. 0x1A3: ×251/256 and
    ×251/128 → 0.01 m/s²/bit, signed, clamp ±2047, 0x800 invalid. 0x2B3: ×201/512 and ×201/256 →
    0.025 m/s²/bit, offset binary +2048, clamp 0..4095, 0xFFF invalid. `MK60e5_CAN.dbc` carries both: 0x1A3 (`AccelLongSensor`, preferred on M3) and 0x2B3 (`AccelLongSensorLowRes`), because non-M 6862873A never sends 0x1A3 (its counter-zeroing function 0x850DE clears the 0x1A3 slot unconditionally at 0x85264).
  So BMW's split is: 0x1A0 AccX = kinematic dv/dt matching the 0x1A0 speed; 0x1A3/0x2B3 = measured specific
  force (includes road gradient), sent uncorrected together with the DSC's learned offset so the receiver can
  correct it [design intent inferred].
- **0x1A0 1.4/3 drive direction:** 0 standstill (0x40328C b7, `vehicle_standstill_update` 0xD381C), 1 forward /
  2 reverse when both fronts' direction-sensing wheel speed sensors agree (0x4029D9 b4/b5), 3 when they
  disagree or no direction is known, 7 when the standstill detector is invalid. Without valid direction-sensing
  fronts it falls back to the AYC reverse flag 0x400B09 b3 (2) or 3.

### Motorsport consequence: a ~1.25–1.27 g ceiling runs through the ABS estimation [inferred]
vref fall cap −44/frame (1.25 g, code literal); ax byte `0x4049FC` and lateral byte `0x408ECA` both
saturate at ±1.27 g; decel estimate `0x408DAF` is a signed byte; the g-term (curve `0x40674`, breakpoints to 1.83 g) sees a
byte without ax trust and wraps above 1.27 g with it (see "The decel-threshold g-term wraps above 1.27 g").
A car that really decelerates above ~1.25 g outruns the vref fall, apparent slip grows, and ABS
over-releases. Raising it means code patches (literals 44 at 0x44DE2/0x44FEA and the −44 clamp at 0x51100)
plus rescaling the byte signals — not a calibration edit.

**Size of the effect (2026-10-25, point-mass model, not car-verified).** The error builds through the stop, not at
its start. While vref falls at the 1.25 g cap, the apparent slip grows until it reaches the gross-slip limit (~11 %
of vref). Model: tyre linear up to 1.5 g at 8 % true slip, flat beyond that; a perfect ABS holds apparent slip at
11 % once it is reached.
- **After the hold starts, chassis decel settles at 1.25 g / r, where r = vref/v ≈ 1.05.** That is ≈ 1.19 g
  (6.3 % true slip) whatever the tyre grip. The cap then acts as a decel limit for the rest of the stop.
- **Stopping-distance penalty, 0.5 s apply ramp:** +2 % (1.4 g), +6 % (1.5 g), +11 % (1.6 g), +22 % (1.8 g)
  from 200 km/h. It is slightly smaller from 100 km/h. With the cap raised to 2 g, none of these trigger.
- **An instant apply is worse:** +15 % at 1.5 g. vref starts at chassis speed with the wheels already 8 % below
  it, so only 3 % more is needed.
- **Wheel decel, not chassis decel, has to exceed the cap.** With steady slip s, wheel decel = a(1 − s), so the
  effective chassis ceiling is ≈ 1.25/(1 − s) g. Wheels that recover to chassis speed between cycles pull it
  back toward 1.25 g.
- **With no slip,** the time to reach 11 % is t = 0.11·v0 / (g·(a − 1.1125)). That gives 1.6 s from 200 km/h
  at 1.5 g, and t scales with v0.

### Doc inconsistency noted
`docs/HANDBOOK.md` and the TL;DR/§2(a)/§6 of `analysis/agents/abs_full/03_lateral_g_influence.md` described
the `0x40E0A`/`0x40E26` curves as the code-32 knockdown / source of `pct`. The 2026-10-05 correction above
stands: they are a pressure term that rises with |lat g|. (2026-10-15: they are the P_lo / P_hi thresholds that set
`pct`; see "ABS with and without the SZL".)
Both files now carry a correction note.

## [disasm 2026-10-12] Pressure-model coding (byte 2) and friction radius (byte 17): M3, 1M, non-M

Detail: `analysis/CODING_BYTES_7846816A.md` (M3 / 1M) and `analysis/CODING_BYTES_6862873A.md` (non-M).

- **[verified]** M3 pressure model is 0/1 per axle (NCS: M3 / M3 GTS). It changes the COA p-V curve on
  both axles and, for the front code only, the BCO prefill tuning (0xD7156, 0x4176C, 0x41770, 0x41774,
  0x417A8, 0x417B4). Every other code-indexed table holds the same value for 0 and 1.
- **[verified]** The 1M (7846411A) has the same two codes and the same p-V values as the M3 (image
  bytes rebuilt from the listing's hex column). It is not representative of the non-M cars.
- **[verified]** Non-M image `fw/6862873A.0pa` (DSC90) is now disassembled: `analysis/6862873A_main.lst`.
  Coding image at 0x40323C; limit table 0xE1710 allows front codes 0–5, rear 0–4, 22 variants.
- **[verified]** Non-M stores a caliper piston diameter per code (0xE17C8: front 54/54/57/57/57/57 mm,
  rear 40/40/42/44/44 mm) and computes the torque↔pressure factors from it and from coding byte 17.
  The M3 uses constants (front 1762, rear 1016, set at 0xD2888) and does not read byte 17.
- **[verified]** Non-M coding byte 17: low nibble front, high nibble rear, signed 4-bit `n`, value
  `139 + 3·n` (115–160). **[inferred]** unit is mm (NCS: "effective friction radius"). It feeds the
  general torque↔pressure converters (26 call sites), not only yaw moment compensation.
- **[from NCS rules, not firmware]** Front 5 / rear 4 are the sport-brake (fixed caliper) packages,
  standard on the 135i. The firmware has no fixed-caliper switch; those codes only select table rows.
- **Open:** purpose of the three undecoded code-indexed clusters in the non-M image; why front 4/5 and
  rear 4 use the small-caliper coefficient at 0xD90F0/0xD90FC; the non-M path from EEPROM to 0xD1C74;
  why the M3 constants are lower than the non-M formula gives for its smallest caliper.

## [disasm 2026-10-16] Pump volume model, and M3 vs 335 hydraulic calibration

Symbols: `analysis/7846816A_symbols.md`, "Pump volume model". Overview and ABS-only simulation: `analysis/HYDRAULIC_MODEL_7846816A.md`. Circuit c = 0 is wheels 0/1 and c = 1 is wheels 2/3
(ROM 0xDA1B8).

- **[verified] 0x41B34 / 0x41B36 are not a pump ramp and gain.** Both are read by two functions:
  - `pump_supply_store_update` 0x82824 (called by `hydraulic_model_step` at 0x82F24) loops c = 0, 1. While
    circuit c is pumped, the store 0x401702[c] goes up each frame by 0x401A1A[c] × r / 20, doubled when the
    store is empty. Here r = 0x41B36 × the ROM factor 0xDA5F8 / 100. The store is clamped to **0x41B34**. The
    same function then reduces the store by the volume the pump delivered: interp(pump flow 0x40170C,
    0x41B3C → 0x41B44) × 0x401A1A[c] / 20.
  - `pump_circuit_demand(c)` 0x88A18 is called for c = 0 and c = 1 by `hydraulic_actuation_pipeline` (at
    0x843CE / 0x843D2). It acts when the shortfall 0x401D32[c] is more than store + 125 and 0x401E4E = 1.
    demand = (0x401D32[c] − min(store + 0x41B36, 0x41B34)) × 10 / interp(0x40170C, 0x41B3C → 0x41B48),
    clamped to 0–10. The rate is doubled when the store is empty.
- **[verified] The cap is a volume, not a pressure.** `circuit_volume_shortfall(c)` 0x86054 handles the
  circuit's two wheels.
  - For each wheel it takes the target pressure: max(0x401A20[w] when 0x40199C[w] is set, 0x401D28[c]).
  - It converts that pressure to a volume with the coded p-V curve. The axis is 0x41B4E; the front curve is
    0x41B62 + 20 × coding byte 3, and the rear is 0x41B8A + 20 × byte 4.
  - It subtracts the modelled volume V 0x4016DA[w].
  - The result is stored to 0x401D32[c] at 0x86288.

  How the two wheels are combined is not traced. 0x401D32 and the 0x41B34 cap are both in the p-V curve's
  volume unit, which has not been identified.
- **[verified, main path]** `pump_flow_estimate_update` 0x81782 is called by `hydraulic_model_step` at 0x82F22.
  - x = the sum of circuit pressure 0x4016EA[c] / 2 over circuits with 0x4016FA[c] ≠ 0.
  - target = interp(x, ROM axis 0xDA604 {0, 25000}, **0x41B38 {4300, 2600}**).
  - 0x40170C += (target − 0x40170C) × 0x41B4C / 256.

  The curve has pump flow falling as delivery pressure rises from 0 to 250 bar, which is a pump characteristic.
- **[verified] M3 vs 335 COA block.** This compares the M3 block (0x41978, 0x36C bytes) with the 6862873A block
  (0x415A0, 0x514 bytes), word by word.
  - **Identical:** k_in, k_cross, k_back, k_out, the LPA curves, pump level cal 0x419D4–DA, valve start
    offsets and build gains 0x41A72–78, the store fill rate 0x41B36, the pump flow curve 0x41B38, the curves
    0x41B3C / 0x41B44 / 0x41B48, and the filter 0x41B4C.
  - **Different:** the store cap 0x41B34 (M3 1150, 335 650), the p-V curves, front volume temp-comp y2 0x41AE8
    (−2500 vs −2250), and the unidentified words 0x4197E–82, 0x41996, 0x419B8, 0x419C8, 0x419D2 and 0x41C48.
  - **The cap in each image:** 7846816A 1150, 7846411A 1150, 6862873A 650, 6791524A 650. The cap follows the M
    brake package: the 1M has the M3's p-V curves.
- **[inferred]** The pump characteristic and the valve-flow coefficients are identical, which suggests the same
  pump and valve block. Whether the cap is brake tuning or reflects supply-side hardware is open.

## [estimate 2026-10-16] Hydraulic-model volume unit: about 0.1–0.3 mm³ per count

The firmware never states the unit of the p-V curves, the LPA curve or the valve-flow gains. They are
consistent with each other (all calibration), and no code constant ties them to a physical unit. The flow law is a bare
orifice equation, Q = isqrt(|Δp in 0.01 bar|) × opening (max 80) × k / 4096 per 10 ms, so k absorbs
Cd·A·√(2/ρ) and the unit scaling. Three independent bounds:

- **[inferred] Master cylinder capacity.** At 120 bar the M3 front circuit is 2 × 13300 counts. A tandem master
  supplies roughly 8–9 cm³ per circuit over its whole stroke, so 1 mm³/count is impossible and the unit
  must be well below about 0.3 mm³.
- **[inferred] Caliper compliance.** At 0.1–0.25 mm³/count, a 57 mm front piston comes to 0.5–1.3 mm of
  equivalent travel at 120 bar and 0.06–0.14 mm at 4 bar (pad clearance). Both are plausible.
- **[user + inferred] Orifice flow.** u ≈ 707 × Cd × A[mm²] / k mm³/count. The user sectioned an MK100 body:
  its inlet valve is a sprung-open needle with a seat of about 0.5–0.8 mm, and flow toward the caliper
  pushes the needle off the seat. With k_in front = 957 and Cd ≈ 0.65 this gives about 0.09–0.24 mm³/count.

**Working value: about 0.1–0.3 mm³/count, probably 0.1 (a round decimal, like 0.01 bar).** On that basis the "full"
LPA (15000) is about 1.5–4.5 cm³. For scale, the user measured an MK100 LPA bore of 24 mm × 30 mm. The LPA curve
then implies a spring preload of about 59 N (1.3 bar on 452 mm²) and a spring rate of about 15–50 N/mm. The
needle-valve geometry supports the inlet-valve model: current sets the Δp at which the valve cracks open
(F_mag = F_spring + Δp × A_seat; 2–5 N at 100 bar). A return flow cannot pass the inlet valve itself, which is
why the model's backflow path (k_back) depends on the USV level rather than the inlet level.
At 0.1 mm³/count, a `valve_flow` result of 1 count/frame is 0.1 mm³ per 10 ms, or 10 mm³/s. So the 2000 clamp is
20 cm³/s. At full opening (80) and Δp = 100 bar, the flows are: front inlet (k 957) about 18.7 cm³/s, rear inlet
(k 421) 8.2, front outlet (k 755) 14.7 and rear outlet (k 465) 9.1. A 0.6 mm sharp orifice at Cd 0.7 passes about 30 cm³/s
at 100 bar, which is the same order.
- **[source, user 2026-10-16] A BMW-published hydraulic diagram shows a check valve antiparallel to each inlet
  valve**, so fluid can leave the caliper back toward the master side while the inlet valve is closed. This
  matches `wheel_volume_delta` 0x8216E. When p_wheel > driver pressure (and the circuit is not pump-fed), the
  backflow is -valve_flow(Δp, k_back 0x41B2E, (10 - `usv_close_level`/2) × 8). That path does not use the inlet
  opening, uses one shared coefficient (705) for all four wheels, and is throttled only by the USV
  in series with it.
- **[source, user 2026-10-16] The same diagram shows two more check valves**, and the model matches both:
  - **Around the USV (master -> circuit).** The master can always add fluid, even with the USV closed. In the
    model, inflow to a wheel is valve_flow(driver pressure - p_wheel, k_in, inlet opening), with no USV term.
    The circuit pressure is floored at `driver_pressure` in both branches of `circuit_feed_pressure_update`
    0x8236C, including the pump-fed one. `circuit_supply_pressure` 0x81AF4 adds driver pressure on top of the
    pump-side term.
  - **LPA / outlet side -> pump inlet.** The LPA drains only through the pump (`lpa_pump_draw` 0x825B6). While
    the pump is drawing from the master side (HSV open, `pump_circuit_active`), it takes 250 per frame from the
    LPA only if `lpa_pressure`[c] >= `driver_pressure`, else 0. That is, the check valve only opens when the LPA
    is above the pump-inlet (master) pressure. Otherwise the draw is `pump_volume_frame`[c].
- **[user, MK100 section 2026-10-16] Outlet valve = normally closed ball-on-seat.** A spring holds a small ball on
  the seat. Wheel pressure pushes the ball onto the seat, so the seal gets tighter as pressure rises, and the
  solenoid is strong enough to lift the ball against the full wheel pressure. This matches the firmware's treatment of
  outlets as digital (on/off through the CS4 latch, `spi_cs4_out16` 0xD4BF4), with no current scheduling and no
  calibration. The outlet "level" (`outlet_valve_level`, from `valve_cmd` < 0) is an open-time fraction of the
  10 ms frame set by `outlet_dump_time_calc` / `valve_pulse_set`, not a partial lift. The model has no leak term
  for a closed outlet, and only lets the LPA flow back into a wheel while the outlet is commanded open
  (`wheel_dump_volume` returns 0 at level 0). Normally closed outlets plus normally open inlets mean an unpowered
  unit keeps conventional braking and cannot dump.
- **[source/user 2026-10-16] Pump outlet "damper chamber".** In the MK100 section it is a rubber diaphragm with almost no
  volume behind it, so it is a small, stiff compliance: a high-frequency filter for piston ripple (NVH and pedal
  feel), not a store. [inferred] So the model's one-frame "line charge" release (`supply_charge_state_update`
  0x82108 + `supply_inflow_split` 0x81BC8) more likely stands for the compliance of the whole pump-to-inlet
  passage (bores, the diaphragm, trapped fluid) than for a damper volume. The pump-flow low-pass (0x41B4C =
  187/256 per frame) is about 30 ms, which is far slower than piston ripple, so it more likely models motor
  spin-up and flow averaging than the damper.

## [disasm 2026-10-15] DSC driver mode: button, CAN 0x398, and the DME-timeout fault reaction

Symbols: `analysis/7846816A_symbols.md`, "DSC button / driver mode". How to use this on a car:
`docs/PTCAN_FRAMES_EXPECTED.md`, "Turning DSC off".

- **[verified]** Driver mode lives in `driver_mode_state` 0x4049B4[0]: 0 = DSC off, 1 = on, 2 = button stuck,
  4 = MDM. Param 0x4049BC[0]. Power-up always sets mode 1, param 0 (`driver_mode_init` 0x8D1BE). Nothing stores it.
- **[verified] Hardwired button.** `dsc_button_input_get` 0x6FEE4 reads latch 0x4009F4 b1 (BLS is b0), active-low.
  `button_mode_sm` 0x8D214 runs every 10 ms frame with table 0xDA1BC:
  - From on (or MDM), held for 50 frames (≈ 0.5 s) → off.
  - From off, held for 15 frames → on.
  - Held for 1000 frames (10 s) → mode 2 and fault 0x91000 = 5E5B. The mode later returns to 1.
  - No button rule enters MDM (4). The button code ignores the input until the start-up flag 0x400966 clears.
- **[verified] CAN 0x398 sets the same state.** Byte 1 bits 2–4 (sig 209, `can_rx_398_dsc_mode` 0x7C3DC):
  **0 → mode 1 (on), 1 → mode 0 (off), 4 → mode 4 (MDM)**; other values are flagged invalid and ignored. The frame
  is DLC 2 with no checksum, alive counter or timeout DTC. Its "received" bits (0x40113B) are cleared at the
  start of every 10 ms CAN task (0x78CE2 from 0x793F0), so each received frame is one request. `can_mode_request_apply`
  0x8D70A applies it when:
  - the button is idle (press counter 0x4049C4[0] = 0),
  - enable 0x4049CC[0] b7 is set (`driver_mode_can_update` 0x8D7FE sets it every frame, except when 0xC7818 ∈
    {2, 5} and `dsc_function_state` 0x4049EF = 1), and
  - `mode_transition_valid` 0x8D570 accepts it. On → off and on → MDM need 0x400B0A b2 = NOT 0x400B0A b7 (no AYC
    intervention running). Off → on and off → MDM need 0x402F6A b7 and 0x400B0A b3 (= 0x400B50 & 0xC0 = 0).
    A rejected request leaves the mode unchanged and is retried by the next frame.
  A CAN request sets mode 0 with param 1. That is the same steady state a button press reaches (the button sets
  param 2, then 1 on release). The DSC-off lamp (`0x80CFE`) needs mode 0 and a param other than 0, so both light it.
  While 0x398 keeps sending "off", CAN overrides the button: a press back to on is undone by the next frame after
  release. Byte 0 bits 4–5 (sig 208) drive a second slot (0x4049B4[1], states 8–11). Its meaning is not identified.
  0x399 (needs terminal 15) writes the same request bytes through toggle logic that is not fully traced.
- **[verified] What mode 0 does.**
  - Traction control mode: `tcs_mode_from_driver_mode` 0x8DA30 sets 0x4030A2 = 2 (mode 4 → 3, modes 1/2/5 → 1).
    0x4030A2 is read only by the traction code (0xC7xxx–0xCFxxx).
  - Yaw control: `driver_mode_is_on` 0x8D060 (modes 1/2/5) is false. The yaw state select 0x68E5E then picks state 2
    for 0x400DF5, unless DSC has been active for more than 2000 cycles (`dsc_active_cycles` 0x400E24). 0x69F6E sets
    the DSC-inhibit flag 0x400DF4 b6.
  - **[verified 2026-10-15]** Traction channels A and B go to state 7 (off); channel C (MSR-like) stays enabled. See
    "DSC-off and the traction channels".
- **[verified] DME torque timeout reaction.**
  - All three timeouts (0x0A8/0x0A9/0x0AA → D354/D355/D356) report group fault **0xA0008**. It latches 0x40284C
    (`0x402838[10]`) b3. The timeouts also set 0x401151/0x401154 b2. They never start the 5E1B timers, which only run
    on 0x800 values in frames that do arrive.
  - `fault_reaction_matrix` 0xB567E: group A & 0x2F (also & 0x3F at 0xB5B38), through the follow-on rules at
    0xB5BDE and 0xB5C2E, sets:
    - 0x402880 b2–b5. b2 blocks and aborts AYC intervention (0xB5CD0) and is tested by the traction code
      (0xCE3D0/0xCE638). b3–b5 are read by the AYC code (0x5FEE0, 0x6028E, 0x66E7A).
    - 0x402881 b7 and 0x402882 b4/b6. 0x402882 b4 → DSC inhibit 0x400DF4 b6 (0x6A03A).
    - 0x40288E b0, b2–b5 and 0x40288F b5. 0x40288E b2 forces `dsc_function_state` (0x8DA8E); the lamp shows DSC failed.
  - **ABS is not disabled.** The ABS-off bits 0x402880 b6/b7 and 0x40288E b6/b7 are not set. So `abs_function_state`
    0x8D8C0 stays OK, ABS enable 0x408DC6 b6 (built by 0x5DAA2) stays enabled, and 0x19E reports ABS OK.
  - The accelerometer stays valid: `ax_signal_get` 0x9390E checks only ignition, cluster status 0x402E50/51 and
    0x402888/0x402890 b1, none of which group A sets.
  - **[open]** 0x402880 b2 also clears 0x408DC6 b5, which gates two ABS-side hooks: a per-wheel branch at 0x46050
    (only when 0x40905E[w] b6; looks like the hand-off from active pressure) and 0x59BF2 → 0x408E68 b1. Both look
    like the interface to active braking, not the slip loop. Not traced.
- So **0x130 alone, without the torque frames**, gives ignition-on ABS with DSC failed, and DTCs D354–D356.
  **0x130 + torque frames + 0x398 "off"** gives the same ABS, DSC in the normal driver-off state, and no DTCs.

### [disasm 2026-10-15] What constant ("fake") DME values affect

- **[verified] No DME DTC checks the torque values against anything.** Every DME DTC is raised by an invalid
  marker or by a DME status bit, after a 50-cycle timer. The timer loop in `can_dme_iface_update` 0x7E7A4
  (0x7F2D6–0x7F354) reports:
  - pedal 0xFF (timer 0x4046EA) or rpm invalid (0x4046ED; 0xFFFF or 0x0AA 6.0–6.1 ≠ 0) → **5E1A**;
  - 0x0A8 3.0–3.3 = 3 (0x4046EB) → **5E19** "Motormoment nicht einstellbar" (fault 0xB0040);
  - 0x0A8 6.4–6.5 ≠ 0 (0x4046EC) → **5E18** "Botschaft unplausibel" (fault 0xB0010);
  - any torque 0x800 (0x4046EE/EF/F0) → **5E1B**.

  So 5E19 is the DME's own "torque not adjustable" flag; the DSC does not compare its 0x0B6 request with the torque
  it receives. All-zero torques/pedal with status fields 0 and a valid rpm raise nothing.
- **[verified] ABS does not read engine torque, rpm or pedal.** In 0x40000–0x5DFFF there are no references to
  0x401144/46/48 or 0x40113E/3C, and no calls to the torque getters. The pedal is read once, through
  `pedal_at_most` 0x7D16A(13) at 0x4EDD6, on a path taken only when 0x408DC6 b6 is clear (0x402880 b6, ABS degraded).
  The validity byte 0x401150 is read on the same path.
- Readers that do use the DME values:
  - **AYC** (0x5E936, 0x5FA2A, 0x65078, 0x66E7A, 0x68096, rpm 0x6339E) and **TCS/MSR** (0xC95B8–0xD09A4):
    torque, drag, demand, rpm and pedal.
  - **Hill-start assist / LVC** (0xC0DAE–0xC4116): `lvc_driveoff_torque_model` 0xC2CB8 uses rpm and engine torque.
    Release logic with zero torque not traced; coding byte 13 bit 6 turns the feature off.
  - **BCO**: pedal gradient (0x6C31C, from 0x401142 and the 0x401157 b3:2 time base) for mode A (ready-alert, 0x6B280) and the
    throttle test of mode B (disc drying, 0x6BCFE). Constant pedal 0 → mode A never triggers; mode B needs pedal > 25. Mode A
    also needs DSC mode on; mode B does not. Both are inhibited while steering / lateral / yaw are invalid. See
    `analysis/BCO_PREFILL_7846816A.md`.
  - **RPA/DDS** (0x9EDE0, 0x9FF9E, 0xA8FC8, 0xAA196): torque and rpm.
  - **Supervisor**: 0xB5E3C sets `engine_running` 0x4028A5 b7 = rpm ≥ 720 (internal rpm units; ≈ 360 rpm if the raw
    is 0.25 rpm/bit). It is read in the lamp/supervisor code 0xB5458 / 0xB616A. **[open]** Its exact role; it looks
    like start-up lamp-check logic.
  - 0x91070 sets an output bit only for pedal ≥ 26 while accelerating above a speed threshold. Its purpose is
    unknown; it never fires with pedal 0.

## [disasm 2026-10-15] Steering-sensor loss: sensor validity, DSC and TCS reaction

Symbols: `analysis/7846816A_symbols.md`, "Sensor validity, steering-loss reaction, TCS inhibit". Question behind it: a
swap with the yaw/lat cluster on F-CAN but no steering sensor (0x0C9) and no DME. Read from code, not bench-tested.

- **[verified] Getter validity.** Every ABS/CAN sensor getter fills `sensor_sig_t {s16 value; u8 st; u8 st2}`;
  valid ⇔ `(st & 0x78) == 0x60`. Fault inputs per signal:

  | Signal | Getter | `0x402888` bit | `0x402884` bit |
  |---|---|---|---|
  | steering (3 getters) | 0x9403C / 0x94120 / 0x940AE | b0 | b3 |
  | ax | 0x93828 | b1 | (0x404A2E b7:6) |
  | lateral | 0x93AC0 (+ 0x93B3A / 0x93C22) | b2 | b5 |
  | yaw, yaw accel | 0x94308 / 0x94376 | b3 | b7 |
  | brake pressure | 0x93E1C / 0x93E8E | b5 | b4 |

  The ABS lat-valid bit `0x408E6D` b7 additionally needs `0x402888 & 0x09` = 0 (steering and yaw OK).
- **[verified] Missing 0x0C9 marks steering, lateral and yaw invalid.**
  1. `fcan_rx_0C9_timeout` 0xC6E18 (100 ms) reports D373 with fault id 0xA0040, only while F-CAN reporting is
     enabled (`0x402F35` b4, built in 0xC4F0E; no ignition term). It also sets `0x402E6D` b7/b5 ("missing now").
  2. 0xBFA2A → `fcan_fault_flag_set` 0xB481E → `0x4028B1` b7 → `fcan_fault_commit` 0xB484A → `fault_set(0xA0040)`
     (group A b6) and `0x402893` b6 (held 255 cycles by 0x4028BC).
  3. `sensor_reaction_build` 0xB4A74 rebuilds `0x402888` every cycle. Group A b6 **and** `0x402E6D` b5 (0xB4C66), or
     `0x402893` b6 (0xB4C06) → `0x402888` b0 | b2 | b3.
  4. Result in the ABS gather: steering `0x408E6D` b5 = 0, lateral b7 = 0, yaw b4 = 0 with `0x408ECC` = 0 and
     `0x408ECE` = 0. `0x408ECA` is still written every cycle, with the wheel-speed substitute `0x408D64`
     (`ay_wheel_estimate_update` 0xD21C4, formula not fully decoded). **ax stays valid** (only `0x402888` b1).
  5. ABS lateral users test b7 first (rear select-low 0x5197E, classifier lateral curves 0x51BF2 with b6, many
     more). The yaw-stable flag `0x408E5F` b4 (0x530E4) needs b7, b4 and b5, so it stays 0. Net: plain ABS
     without the cornering logic. It recovers when 0x0C9 returns.
- **[verified] The 0x1A0 AccY / YawRate fields do not show this.** The TX encoders 0x7B06A / 0x7B104 send 0x800 only
  on `st2 & 0x60` (`0x402890`, `0x402884`, cluster status). `0x402888` sets only `st2` b4, which they ignore. So with
  0x0C9 missing, 0x1A0 carries live ay/yaw while the ABS treats them as invalid. Tell from outside: D373 active and
  no 0x0C9 traffic.
- **[verified] DSC reaction.** `fault_reaction_matrix` 0xB567E: `0x402888 & 0x0D` → `0x402880` b2 (0xB596C);
  `& 0x0C` → `0x402881` b7 (0xB5AF2); follow-on 0xB5BDE → 0xB5BFC → `0x402880` b2–b5 and `0x402882` b4 (DSC
  inhibit `0x400DF4` b6). That is the same `0x402880` pattern as the DME timeout. `0x40288E` is not set by this rule.
- **[verified] TCS reaction: all three traction channels are inhibited.** `0x402880` b4 → `0x403004` b7
  (0xCE3D0, latched until `0x402F86` b2), b5 → `0x403048` b6 (0xCE638, same latch), b3 → `0x402F84` b1 (0xCE7A4).
  The channel state functions `tcs_state_a/b/c` 0xC779A / 0xC7818 / 0xC789C return 6 (5) = inhibited when their
  fault word is non-zero and the channel is not already active (active flags `0x402FC0` b4 / `0x402F6C` b7 /
  `0x40303C` b7). Summary `0x402F6A` b6/b4/b5. So with steering **or** DME missing there is no traction control
  of any kind, brake-only included. **[resolved 2026-10-26]** A = brake TCS, B = engine ASR, C = MSR
  (`analysis/TCS_7846816A.md`).
- **Not affected by DSC-off or the DME timeout:** neither sets `0x402884` / `0x402888` / `0x402890`, so with
  steering present the ABS keeps using lateral and yaw. (The yaw-deviation monitor 0x4A254 is not AYC-gated either;
  it runs every ABS frame.)
- **[verified] `0x408E6D` b3 is always 0 for consumers.** `abs_sensor_gather`
  sets b3 from the ax getter at 0x5D868, then clears b3 and b7 at 0x5D914 in the same pass. No other writer of
  0x408E6D exists (also checked through nearby base addresses). So the `0x50FF4` entry "when `0x408E6D` b3 is set"
  is never taken; only the second route (0x45142–0x45196) can reach it. ax validity survives in `0x408E1B` b4 and
  `0x408DEC` b2 (ax invalid). Route 2 calls `vref_fall_from_ax` only with lat, yaw, steering and pressure valid
  and \|lat\| < 0.3 g ("ABS with and without the SZL"). Bench check: does vref fall faster than −22/−44 per frame
  under hard straight-line braking with the SZL connected, and not without it.

## [disasm 2026-10-15] ABS with and without the SZL (steering-angle sensor)

Detail: `analysis/agents/abs_full/09_chassis_sensor_use.md`. Symbols: `analysis/7846816A_symbols.md`, "ABS and TCS use
of the chassis sensors". Question: in a swap with the yaw/lateral cluster present, what does the ABS lose when the
SZL (F-CAN 0x0C9) is dead? Read from code, not bench-tested. With the SZL dead, lateral, yaw and steering are all
invalid ("Steering-sensor loss"): `abs_ay` = wheel-speed estimate, `abs_yaw` = `abs_yaw_accel` = steering = 0, and the
yaw-stable flag `0x408E5F` b4 never sets.

- **[verified] The pct producer.** `abs_decision_classify` 0x51B54 writes `abs_decision_t` at 0x408DDE (code u16, pct
  u8 at 0x408DE0). With lat + pressure valid (`0x408E6D & 0xC0`), the wheel's `0x40903C` b7 or rear cornering latch
  `0x409049` b5, and `0x408DC4` b4 clear: P_lo = 100·curve 0x40E26(\|lat\|), P_hi = 100·curve 0x40E0A(\|lat\|), +500
  above \|lat\| 80. Then driver pressure `0x408EB2` < P_lo → **code 1**; a dumping wheel with P_drv > P_lo (and
  P_drv < P_hi or latch b5) → **code 32**, pct = 100·(P_drv − P_lo)/(P_hi − P_lo) (0x51F32–0x51F42). Without these
  conditions P_lo = P_hi = 0.
- **[verified] Straight-line shortcut → code 1** (0x51E00–0x51E94): \|lat\| < 9 (< 15 after code 1), front pressures
  `0x408FF0/F2` within 50 %, yaw-stable, `0x409024` b0 clear, yaw valid, `0x408DBE` b7 clear, plus a rear condition.
  The default is code 1 if both rears are only armed, else **64** (select-low). So without the SZL a controlling rear is
  always select-low.
- **[verified] Yaw cornering flag** `abs_yaw_corner_flags` 0x409024 b0+b6: \|yaw\| > curve 0x40E42(−decel) during ABS.
  Never set without yaw.
- **[verified] Rear cornering latch** (event classifier 0x4E908): needs `0x408E6D & 0xF0` = 0xF0 (lat, pressure,
  steering, yaw) at 0x4E8B6. Sets `0x409049` b2+b5 and `0x408E1B` b1, which enable the code-32 / code-1 branch above
  and the yaw-limited dump flag (classifier block 14). **Triggers (2026-10-26):** yaw − DSC target ≥ 1 count in the
  turn direction, or \|lat\| > T, or the yaw-limited / yaw-recovery flags. T = cal 0x40B06 (0.80 g) lowered by turn-in
  yaw accel, then **max(T, cal 0x403E4 = 0.40 g)**. Only the yaw-target triggers need steering; with
  `abs_cluster_without_szl` the latch sets on \|lat\| > T alone. Releases when driver pressure < P_lo; b5 holds while a
  rear is cycling. Detail: 09 §2.2.
- **[verified] pct 0x408DE0 is not clamped and wraps.** 0x51F42 stores 100·(P_drv − P_lo)/(P_hi − P_lo) with `st.b`;
  the exec reads it with `ld.b` (0x59272). With the latch the code-32 branch runs above P_hi, so pct passes 100 and
  wraps to near 0 at P_lo + 2.56·(P_hi − P_lo) (about 46 bar of pedal at 0.4 g lateral, 68 bar at 1.0 g). Effect on
  the rears [I].
- **[verified] µ-split pair logic needs yaw.** `abs_pair_logic` 0x54D9A exits at once (0x553BE) while `abs_pair_gate`
  0x54B70 (state `0x408E5F` b6:5) is 0. 0 → 1 needs `abs_pair_gate_split_yaw` 0x547D8: an axle pressure split,
  \|yaw\| > cal 0x40DD4 with the side's sign, and `0x408E5F & 0x14` = 0x14 (yaw-stable + b2). So the partner-dump code
  32 and the 1024 / 16 rebuild codes never run without yaw. The front staged dump (0x53940) and the low-µ coupling
  (0x48EB0) do not need it; `abs_front_stage_cancel` 0x540D4 cancels the staged dump in a corner (\|lat\| > 35) only
  with lat valid.
- **[verified] vref only uses ax with every chassis sensor valid.** Route 2 into `vref_fall_from_ax` 0x50FF4
  (0x45142–0x451F2) needs `0x408E1C` b7, `0x408E6D` b7 + b4 + b5 + b6, \|lat\| < 30, `0x408DA1 & 0xE0` = 0, no
  `0x400B09` b6, and `0x408DB5` b7 or (ax > −0.3 g, `0x408E6A` ≥ 21, regime) (code `cmplti r7,21; bt skip`).
  Route 1 (b3) is dead. Without the SZL vref falls on the fixed slopes bounded by the wheel-derived `0x408DAF`.
  The clamp that holds `0x408DAF` within ±0.2 g of measured ax during ABS (`abs_decel_est_clamp_ax` 0x538E8) needs
  ax trust, which also needs the SZL (next bullet), so without the SZL ax does not shape vref.
- **[verified] Other SZL-dependent paths.** Dump cornering flags b28/b27 (\|lat\| > 50 / 80, ½ / ⅓ steps) need b7.
  `abs_rear_lead_select` 0x5184C needs b7; `abs_side_select` 0x5AEEE falls back to the rear wheel-speed difference.
  `abs_countersteer_check` 0x5CAF4 needs steering (road-wheel angle opposite to yaw). `abs_ax_decel_estimator`
  0x49572 updates only straight and stable with lat (+ yaw) valid. `abs_chassis_frame_init` 0x5A21C flags "all four
  valid" and otherwise clears `0x40903C[3w]` b4.
- **[verified] Without the SZL the cluster's longitudinal accel is valid but never trusted.** `0x408E1C` b7 = "ax
  trusted" is first set at 0x49AE0–0x49CB8, which needs lateral + pressure valid and the yaw-stable flag. The
  re-trust path 0x49AC6 (deviation `0x408E8E` < 50, counter `0x408E8C` ≥ 16; cleared above 500) reads no lateral,
  yaw or steering but runs only after a trusted ax went stale ("ax trust needs the SZL"). With trust: the decel-threshold g-term uses measured decel (0x47BE0), `0x408DAF` is clamped to ax ± 0.2 g in ABS
  (0x538E8), the classifier uses ax, and the rear decel-gate latch can fire. Without trust, ax still reaches the
  readers of `0x408E80` that skip the flag (0x47CEA, 0x48584, 0x492F6, 0x4A530, 0x4EC36, 0x50E14, …). Detail: 09 §2.10.
- **Unaffected:** slip / decel thresholds, phase machine, dump / hold / reapply, EBD, front staged dump, low-µ flag.
  (The rear decel-gate latch needs ax trust, so it is off without the SZL.)
- **[inferred] Net effect of a dead SZL:** rears always select-low, no cornering-specific rear handling or dump-step
  reduction, no yaw-triggered µ-split limiting, and the accelerometer does not reach vref at all. A few readers use the raw
  lateral byte without the valid bit and so see the wheel-speed estimate (classifier block 14, the rear dump clause
  0x4EF72, parts of `abs_front_split_detect` 0x53D3C).
- **[open]** Writer of `0x40903C` b7 and of `0x408DF0` b7/b6; the rest of `abs_chassis_frame` 0x5A0DC; pair-gate
  helpers 0x54954 / 0x54AF8; consumers of the 0x49572 outputs.

## [disasm 2026-10-15] Steering calibrations that affect ABS (SZL working)

Question: with a working SZL, which calibrations decide how steering changes ABS behaviour, how sensitive are they,
and which are physical versus to-taste? Read from code, not bench-tested. Detail and tables:
`analysis/agents/abs_full/09_chassis_sensor_use.md` §7. Steering LSB ≈ 0.044°/count is still unverified, so the
degree figures below are [inferred].

- **[verified] Signals.** `0x402132` (getter `steer_angle_get` 0x94120 → ABS `abs_steer_angle` `0x408EDE`) is the
  **offset-corrected steering-wheel angle** (raw `0x4020D0` − offset `0x4020A6`/64). Road-wheel angle `0x408EE4` = 29360·angle / ratio; rate `0x408EE6` from `steer_rate_update`
  0x90408 (raw angle, so offset-free; units not confirmed).
- **[verified] Steering mostly acts as a validity switch.** `0x408E6D` b5 enables yaw-stable, the rear cornering latch,
  the straight latch, GMA (via yaw-stable), the countersteer test, vref route 2 and `abs_chassis_frame_init`.
  Magnitude is used in only two places:
  1. `abs_yaw_stable_update` 0x530E4: \|angle\| > cal **0x4040E = 2971** (≈ 130°) zeroes the yaw-stable counter
     (other cals: 0x40404 = 1047 calm yaw, 0x4040C = 63 frames, 0x40406 = 28 hysteresis, 0x40408 / 0x4040A = 1571 /
     3002 decay).
  2. `abs_gma_hold_frames` 0x54BE8 (GMA rebuild pacing in `abs_pair_logic`; the high-µ wheel gets +0x40DB0 = 3 bar
     every 0x40D8E (7) + score frames). Steering terms: rears + \|rate\|/**0x40D86 (457)** when rate is past
     **0x40D88 (1143)** toward that side; all wheels + **0x40D92 (14)**·(\|angle\| − min)/(**0x40D8A (2286)** − min),
     min = `0x408EF2` = smallest \|angle\| since the gate opened; score 248 (rebuild stops) when \|angle\| > 2286 and
     the wheel is > 5 bar above its partner. Other terms: slip, speed above 40 km/h, decel, predicted yaw (rears).
- **[verified] Sign / zero only:** `abs_countersteer_check` uses the road-wheel angle sign against lat / yaw and peak
  `0x408EE2` (0x5A4E4); no magnitude cal. The front staged-dump steering peak `0x400A92` feeds outputs with no readers.
- **[inferred] Physical vs to-taste.** Physical: sensor scale (LSB, ·1029/1024), sign convention, zero offset (learned
  by `steer_offset_learn`), steer-ratio curve 0x40EB4 / 0x40ECC. To-taste: 0x4040E, the GMA steering terms
  0x40D86 / 0x40D88 / 0x40D8A / 0x40D92 and pacing 0x40D8E / 0x40DB0, the yaw-stable yaw thresholds.
- **[inferred] Sensitivity for ABS:** valid status ≫ sign > offset > scale > ratio (≈ none; the ratio only matters for
  the DSC yaw reference). The to-taste thresholds are generous (130°, 100°, ≈ 50 °/s); the GMA steering terms are the
  only ones that noticeably change behaviour (split-µ rebuild speed versus pull).
- `abs_gma_hold_frames` 0x54BE8 uses predicted yaw (yaw `0x408ECC` + yaw accel `0x408ECE`/2), not lateral accel.
- **[open]** Steering LSB and rate units; what `steering_angle_init_monitor` 0xB97D4 needs before steering is valid;
  whether the CSI sign tables 0x40EE4 / 0x40F14 reach anything ABS reads.

## [disasm 2026-10-15] DSC-off and the traction channels

Symbols: "Sensor validity, steering-loss reaction, TCS inhibit" and "ABS and TCS use of the chassis sensors".

- **[verified] DSC off (`tcs_mode` 0x4030A2 = 2) switches off channels A and B.** `tcs_a_inhibit_update` 0xCE3D0
  sets `tcs_a_fault_word` 0x403004 byte 3 b2 while the mode is 2 (0xCE584); `tcs_b_inhibit_update` 0xCE7A4 sets
  0x402F84 byte 1 b2 (0xCE7F0). Both stay set until the mode is no longer 2 **and** 0x402F86 b2 is set. With the bit
  set, `tcs_state_a` / `tcs_state_b` return **7** unless the channel is already active (a running intervention
  finishes).
- **[verified] Channel C has no DSC-off bit and stays enabled.** `tcs_c_inhibit_update` 0xCE638 builds 0x403048
  from: fault reaction 0x402880 b5 (b6), 0x40288C b5 (b7), channel A / B / AYC active (b5), 0x403056 ≥ 15 (b4),
  0x403047 b7 or 0x6FF0E() (b3), **pedal > 13 %** (b2), 0x403046 b2 (b1), 0x4030A4 = 3 (byte 1 b0).
- **[verified 2026-10-26] Channel C is MSR** (the arbiter turns its flag into 0x402F6D b2 = 0x19E MSR bit; TCS doc §6). Its controller `msr_pid` (was `tcs_torque_pi`) 0xCD1E8 only requests positive torque (the
  integrator 0x40304A is floored at 0), only while the wheel-derived decel `0x408DAF` is negative, and only with the
  pedal at ≤ 13 %. In mode 2 its output is capped and then forced to 0 (0xCD33A–0xCD350), but only when
  `dme_0A8_flags` 0x40114F b4 (0x0A8 byte 5 bits 0–1 = 1, meaning unknown) is set and the DME frames are valid. So
  whether MSR acts in DSC off depends on that DME bit. It reads no yaw, lateral or steering.
- **[verified] The traction code's own sensor copy.** `tcs_sensor_latch` 0xCC89C → `tcs_sensor_valid` 0x403064
  (b7 ax, b6 lat, b5 pressure, b4 road-wheel angle, b3 yaw) and 0x40306C–0x403074. Lateral comes from
  `abs_ay_aux2_get` 0x93C22, not `abs_ay_get`. Users: `tcs_straight_detect` 0xCB43E (no valid-bit test),
  `tcs_yaw_slip_term` 0xC9450 (yaw when valid, else 0x4030A8), `tcs_reduction_floor` 0xCD7FE (needs lat valid).
- **Summary of the swap combinations** (with "Steering-sensor loss" and "DSC driver mode"): yaw cluster only, or
  cluster + DME frames → plain ABS, AYC and all traction channels inhibited; cluster + SZL without DME → full ABS
  (above), AYC and all traction channels inhibited by the DME rule; everything present → full function. DSC off then
  changes nothing in the ABS and leaves only channel C of traction control.
- **[open]** ~~Which of channels A / B is engine ASR and which is brake TCS~~ (resolved 2026-10-26: A brake, B engine); the meaning of 0x0A8 byte 5 bits 0–1;
  0x402F86 b2 (the release condition of the fault and DSC-off latches).

## [disasm 2026-10-15] D364 "Operator_Key_Tempo" has no reporter

- D364 is the F-CAN cruise/ACC stalk frame **0x194** from the SZL (DSC_87.prg job `STATUS_F_CAN_TEMPOMAT_ACC`
  reads $0194). The prg text says "PT-CAN", but its `dtc_table` ids are F-CAN: 0x3046 timeout, 0x3047 checksum,
  0x3048 alive (mask 0x40040 / 0x40100 / 0x40080).
- **Nothing in 7846816A can raise it.** The 0x194 timeout handler (F-CAN var 5, 60 × 10 ms) at 0xC69F4 is a bare
  return. The payload handler 0xC69EA only jumps to `fcan_rx_queue_push` 0xC56D0 (gateway to PT-CAN), and the
  signal handlers are stubs. A raw scan of the whole image finds eight F-CAN report calls (all through 0xBFA2A,
  0xC624A–0xC6E9A), and none can produce group 4 bits 6–8. The SZL fault-forward switch at 0xC5F46 stops at id
  0x3045.
- So a D364 on a bench unit is most likely stored from the car the unit came from. Not bench-checked.
- Same scan: the 0x0C9 timeout 0xC6E18 also reports **9502 / 9503** (SZL steering sensor under / over voltage,
  ids 0x304A / 0x304B) when 0x402F53 b2–3 = 1 / 2. Those bits are written by the signal handler 0xC62EC, whose
  frame was not traced; they are probably 0 with no SZL on the bus.

## [disasm 2026-10-18] vref fall paths, ax trust, decel-threshold build order, low-µ flags

Full detail: `analysis/agents/abs_full/10_vref_and_ax.md` (vref) and `02_decel_threshold.md` §2 (threshold).
Not bench-verified.
- **[verified] vref fall step selection** (`vref_update` 0x44DE4–0x45138), only with vref > Cmax and controller
  mode 0. Steps −11 / −22 / −23 / −32 / −44, plus `(75 + DAF)/3` below DAF −0.80 g on the −23 and reapply-flag −32
  branches (down to −40 / −49). Then the DAF limiter `max(s, min((DAF − m)·0.36, −m·0.36))`, m 50 or 30. The limiter
  is skipped in several states, notably when a wheel in control re-accelerates with PM > 40 bar (`hiP`, 0x44A4A).
- **[verified] Cmax excludes the rears** while a front is in an ABS cycle (0x408DA2 b7) with 0x408DB5 b5 clear and
  0x408DC4 b5 set (0x44BD0), unless a wheel was invalid.
- **[verified] `vref_fall_from_ax` 0x50FF4** replaces the step (not a max) with `max(−44, (d − m)·0.36)`, d = −|ax| in
  the regime, m 20/30 ±10 (min 10). Route 2 needs trust, lat + yaw + steering + pressure valid, |lat| < 0.3 g, and
  0x408DB5 b7 or (ax > −0.3 g, 0x408E6A ≥ 21, regime). So it is dead without the SZL and rarely taken in a hard stop.
- **[verified] Effect of ax trust on vref:** only through `abs_decel_est_clamp_ax` (DAF to ax ± 0.2 g in the regime),
  which anchors the limiter to measured ax. With ax valid but untrusted, vref behaves exactly as with no cluster.
- **[verified] Curve reader 0x710FC** picks segment i = number of breakpoints strictly below x. Speed term at
  200 / 250 / 300 km/h = 0.29 / 0.47 / 0.80 g (var 0); g-term at 0.5 / 1.0 / 1.27 g = 0.04 / 0.35 / 0.60 g.
- **[verified] Decel-threshold pre-trim** (0x47C1A–0x47C8C): `rec+0x10` bits 7:5 < 2 → speed trims −25…−8; ≥ 2 →
  `thr −= 60 − 2·0x408E6A`, then ≤ −121. The 60 km/h floor is skipped only with ax ≤ −127, DAF < −110 and trust.
- **[verified] Low-µ flags `0x40902E + 3w`** (stride 3): b1 below 80 km/h, b4 from 60 km/h; set only outside a cycle;
  front depth gate uses own **or partner** 0x409010 > 50, rear own > 30. Detail in `05_edge_cases_variants.md` §2.

## [disasm + bench log 2026-10-21] ax trust needs the SZL

- `0x408E1C` b7 (ax trusted) has two writers in `abs_ax_decel_estimator` 0x49572. **Initial set** 0x49AE0–0x49CB8:
  driver pressure 0x408EB2 > 5 bar (cal 0x40CC6), 0x401FF2 b7, not in the ABS regime, 0x408E68 b7 clear,
  0x408E6D b7 + b6 (lateral + pressure valid), 0x408E5F b4 (yaw-stable), DAF < 0, \|lat\| < 0.20 g (cal 0x40C9A);
  agreement counter 0x408EA7 ≥ 5 and deviation 0x408E8E < 20. **Re-trust** 0x49AC6 needs b2, set at 0x49614 only
  after a trusted ax went stale. So without lateral / yaw (no SZL) ax is never trusted.
- Bench log (MR2, 7846816A + CAN debug patches, 740 s drive, stops to 1.0 g): lat / yaw / steering invalid
  throughout, b7 = 0, b2 = 0, b3 = 1, ax valid, alive counter 25.
- Same log: ax lags the wheel-speed derivative by ~120 ms and reads 0.07–0.09 g more negative (also at standstill);
  DAF 0x408DAF is unbiased (−0.002 g), lags ~200 ms, gain 0.88.

## [disasm 2026-10-21] Tyre-tolerance learning and wheel-ratio plausibility DTCs

Detail: `analysis/TYRE_TOLERANCE_LEARNING_7846816A.md`. Not bench-verified. M3 only.
- **[verified]** The per-wheel factor in vref (`(0x301 + byte)/1024`) is a learned tyre-tolerance correction
  (`tyre_tol_learn` 0xD144A). The bytes are normalised so the slowest wheel is 1.0 (`0xD0480`), range 0.746–1.0. They
  are stepped every 11th pass with vref > 5 km/h, no wheel fault, outside the braking regime and with the rear wheel
  accels near the vehicle decel. Fronts step −1.5 %/+0.1 % per step within 5 %; rears and larger front corrections
  step +1.5 %/−0.1 %.
- **[verified]** Stored in EEPROM block 22 (0x403255). At start-up each axle gets the larger factor of its two wheels,
  **floored at 225 (0.970)**, so only about 3 % is applied before relearning.
- **[verified]** `rec+0x1C` is the corrected speed. The main ABS slip (vref − `rec+0x1A`), the wheel accel `rec+0x20`
  and the excess speed loss `rec+6` use **raw** speed; the corrected speed only feeds vref, slip2 (overspeed / pause
  tests), front slip under `0x408DF1` b7 (factory-stagger switch, below), and the left/right comparisons. **[inferred]** So a learned front/rear
  mismatch m becomes a −m slip offset on the faster-reading axle (late ABS there); unlearned it is a +m phantom slip
  on the slower axle (the MR2 track log case).
- **[verified]** `wss_ratio_plausibility` 0xB6A08: sorted-speed ratios ≥ 1.25 above 40 km/h (≥ 1.50 below 20 km/h),
  held for a counter of 1000 (3000 at low speed), raise 5Dx5 on the fast wheel(s) or 5Dx3 on a single slow wheel,
  and mark the wheel faulted.
- **[inferred]** One wheel 8–20 % fast with the other three matched is handled as a space-saver spare (0xD10EC):
  factors are loaded at once.
- **[verified, 2026-10-23] It is a ratio trim, not a size calibration.** Only ratios between wheels are learned, so an
  error common to all four (wrong BFU circumference or tooth count) is invisible to it and stays in every speed, slip
  threshold and acceleration. For a standalone or swapped installation it cannot fix wrong tyre sizes; set C per
  axle (`WHEEL_SPEED_CHAIN_7846816A.md` §6.3).
- **[verified, 2026-10-23] Factory-stagger switch.** `abs_wheel_signal_frame` 0x461C0 sets `0x408DF1` b7 (front main
  slip on `rec+0x1C`) when each axle's factors match within 5 counts and rear − front axle sums D satisfy
  2·cal − 20 < D < 2·cal + 10, cal = ABS+0x66 (0x40402) = **25** (fronts ≈ 1.5–3.0 % fast), plus learner status
  0x403210 b0 and (0x403212 & 31) ≥ 9. The stock M3 (245/40R18 ≈ 2052 mm, 265/40R18 ≈ 2102 mm on a matched 2073 mm
  cal: fronts ≈ 2.4 % fast, factors ≈ 231 / 255, D ≈ 48) falls in the window, so the calibration is built around the
  factory stagger. The start-up restore floor (225, 2.9 %) also covers it. **[inferred]** With correct per-axle C the
  factors stay ≈ 255, D ≈ 0 and the switch stays off. Above ≈ 3 % (to 25 %) the learner still corrects vref but the
  switch is off, so the fronts read −m slip (late front ABS). **Non-M 6862873A has no switch** (equivalent function
  0x462F4 lacks the block); its front main slip is always raw.

## [disasm 2026-10-22] Steering data flow, offset learning and fitting DSC to another car

Detail: `analysis/DSC_STEERING_AND_VEHICLE_MODEL_7846816A.md`. Read from code, not bench-tested. Degree figures assume
≈ 0.044°/count (unverified; a non-M coding cross-check gives 0.04374°/count).
- **[verified] Chain.** 0x0C9 → `canrx_steer_angle_0C9` 0xC5C78 (·1029/1024) → 0x401644 → `steer_task` 0x91008:
  `steer_capture` 0x901D4 (raw 0x4020D0, IIR 0x4020D2), then `steer_offset_learn` 0x9020C (corrected angle 0x402132 =
  raw − 0x4020A6/64 every call) and `steer_ratio_convert` 0x9032E (road-wheel 0x40212E = 29360·a / R). Readers of
  0x40212E: the yaw reference (0x90E8A → r_ref 0x4020EC), state flags 0x91070, the ABS getter 0x9403C.
- **[verified] Offset limits.** The learner clamps its target to offset ± 228
  counts; it is a step clamp, not a window. Hard clamp ±0x7249 Q6 (457 counts ≈ 20°). `steer_offset_fault_monitor`
  0xBF868 sets **0x120001** when \|offset\| > 14628 Q6 (228.6 counts ≈ 10°) or \|raw\| > 16457. So about ±10° is usable.
  Update `offset += (target·64 − offset)/D`, D = min(lateral curve 0xDA8FA, residual curve 0xDA906)·1200/[0x400B2C],
  every 100 calls with 0x4020FD b7 + 0x402147 b7.
- **[verified] The offset is saved.** EEPROM block 8 (0x160) = record 0x4020AE: XOR checksum + steering, lateral and
  two master-pressure offsets, clamped by 0xDA974 on restore (`sensor_offset_record_sm` 0x92104; bad checksum → fault
  0x81000). A bad learned offset survives power cycles; re-zero with `31 21 00` after moving the sensor.
- **[verified] Steering-ratio sets.** f+5 picks one of 3 four-point curves (x 0x40EB4, y 0x40ECC, y = secant ratio
  × 1024). NCS **[user-supplied]**: 0 = E90, 2 = E92/E93, 1 unused (ROM copy of 0). A set 3 would overlap y set 0 and
  the sign tables; the field limit (3) rejects it. Non-M 6862873A: 5 sets, limit 5, and f+5 = 1 builds the curve from
  coding words w22–w28.
- **[inferred] The curve is geometry plus tuning.** Set 0 gives ≈ 38° road wheel at lock, local ratio 15.4 → 10.8;
  the rack is constant-ratio **[user-supplied]**, so this is linkage geometry. Sets 0 and 2 differ by up to 3.4 % on
  identical hardware, so they are calibration fits, not drawings.
- **[verified] No coding route to custom geometry.** Variant 1 (Custom ESM) reads ROM column 1. To fit another car,
  patch the coded variant's column (keep 0–9; ABS decel curves are variant-indexed too): l_f / l_r / track in Q10 m,
  mass kg, Jz kg·m², Cf / Cr (units open; they set v_ch). Also tyre circumference (BFU 0x41CF4 / 0x41CF6) and the
  ratio curve. Validate by overlaying target yaw 0x400B1A on measured 0x402100 in steady cornering.

## [disasm 2026-10-22] BCO pre-fill: two modes (summary; full detail `analysis/BCO_PREFILL_7846816A.md`)

Static analysis only; nothing bench-confirmed.

- **Two independent generators, both arbiter id 17.** Mode A `bco_main_state_machine` 0x6B85E (pedal-lift ready-alert) and
  mode B `bco_dry_main` 0x6C090 (wiper-driven brake-disc drying).
- **[verified in code] Mode A trigger.** Pedal-release path: A.10 coded ∧ `driver_mode_is_on` ∧ front code 0 ∧ pedal gradient
  `0x400F0C` (= previous − current, positive on lift) above the pedal curve 0x4177A. Residual path: A.9 coded ∧
  `|0x402126|` (model-based axle lateral acceleration, 0.01 g: roughly ay) at or above 0.60 g for 0.5 s, then at or below 0.20 g for 0.4 s (front code 1: 0.87 g / 0.76 g for 0.1 s), i.e. a hard-cornering detector. Needs vref 60–500 km/h, master pressure < 3 bar
  with pedal switch clear, no ABS/AYC/TCS/DSC intervention, DME pedal valid. DSC off (mode 0) kills the pedal-release path.
- **[verified in code] DME status nibble.** `bco_dme_status_monitor` 0x6B51A watches 0x0AA byte 6 bits 7:4 (0x40470C): outside {8, 9, 11} for
  about a second pulses `0x400ECE` = 1 and `bco_main_state_machine` resets mode A. Send 8. Only the 0x0AA frame feeds mode A's DME inputs.
- **[verified in code] Inhibit gate** `0x6B490` → `0x400E9D` (**1 = inhibited**): `0x402888 & 0x0D` (steering/lateral/yaw),
  `0x404605 == 3` (meaning open), WSS faults, fault ids 35/57/59/61/63. So no SZL/yaw/lateral sensors → no BCO unless patched.
- **[verified in code] Mode A request.** All four wheels, target `0x400E9E`/`0x400E9F` = 20 (hard-coded) × scale 100 (hard-coded;
  `0x417B4` = 50/150 on the residual path), no divide → 2000 = 20 bar in one 10 ms frame (rate literal 10000 = jump to
  target; `req_slot_step` 0x83F26). **Suspect:** mode B uses explicit `/100 /10` and gives 1.0–1.4 bar in the same units.
- **[verified in code] Mode B.** Wiper state from F-CAN 0x2A6 byte 0 (3-bit, `0x402E4C` b7:5) and PT-CAN 0x226 byte 0
  (0xAA / 0xFD / 0x55 = level 1/2/3). Exposure accumulator `0x400ED0` (above 70 km/h; due after about 36–72 s at 100 km/h, halved
  when outside temperature `0x4046E0` is above about 18 °C). Fires at 82–500 km/h with throttle on, no braking, no intervention.
  Front wheels only, 1.0 bar at 82 km/h up to 1.4 bar from 150 km/h, shaped over at most 3 s (0 at start, peak at 1.5–1.8 s, fade to 0 at 3 s). No DSC-mode check.
- **[verified] Arbiter slot format** (`req_arbiter_submit` 0x833DA, slot at 0x401728 + 56·w + 8 + 12·k): +0 id, +4 current, +6 rate,
  +8 target (s16, 0.01 bar), +10 flag. Rate 10000 / ±8000 / 9000 jump to target; other rates are 0.01 bar per 10 ms frame.
- **[verified in code]** Mode B runs only if `coded_feature(18) == 1` (`bco_dry_init` 0x6BB82 → `0x400EE7`), the NCS
  "brake-disc drying" bit (c13 b5; verified through `coding_feature_combo_check` and `coded_feature` case 18), and cal 0x417C2 ≠ 0.
  The flag-word-A bit 11 getter 0xCFD0A is A.11 (GMB, c14 b5), unrelated (read only by `abs_front_split_detect`). A.9 (c13 b3) is
  read only by `bco_init`; the NCS "soft-stop assist" label does not match (soft-stop, id 18, is gated by cal 0x4182A).

## [disasm 2026-10-23] ABS reads the steering-based yaw target

Question: without an SZL, can ABS use lateral and yaw if they are made valid, or does it still need the steering
angle? Read from code, not bench-tested. Patch: `mk60e5_patcher` `patches/performance/abs_cluster_without_szl`.

- **[verified] Direct steering-value users in ABS** (0x408EDE / 0x408EE4 / 0x408EE6): `abs_yaw_stable_update` (\|angle\|
  > 0x4040E kill), `abs_gma_hold_frames` (angle, rate), `abs_countersteer_check` / `abs_corner_peak_track` (road-wheel
  sign and peak), and the dead outputs of 0x53940 / 0x5971C. Nothing else.
- **[verified] Indirect users: the DSC yaw target.** Besides 0x4A254, these ABS literal words hold 0x400B1A:
  0x4E444, 0x4E900, 0x4ED60 (`sub_04D270`), 0x50E88, 0x571E0, 0x59980 (0x5971C), 0x5ABF0 (0x5A4E4), and 0x5B828,
  0x5BBAC, 0x5BEAC, 0x5C2CC, 0x5C594, 0x5C8B8 (`abs_side_select`). 0x55560 (0x55420) holds the closed-form reference
  0x4020EC. Every lrw is followed by a plain `ld.h (rN,0)`. Most sites compute yaw − target or compare signs, and are
  gated on 0x408E6D b4, on `0x40493A` b5 (always set by init 0x81584) or on other ABS state. None is gated on
  steering-valid (b5) or AYC. Earlier notes said "ABS reads B1A only in 0x4A254"; that is wrong. Per-site uses
  (filtered error 0x408ED8, forced-dump halving, side-select thresholds): `09_chassis_sensor_use.md` §7.6.
- **[verified] The b5 (steering-valid) users of 0x408E6D**: 0x4518C (vref route 2, mask 0x60), 0x468A2 / 0x469A6
  (0x4688C → 0x408E69 b6/b7, also 0x400B09), 0x47856 (0x477E8, also 0x400B09 b6), 0x4A276 (yaw-deviation monitor),
  0x4B556 (`abs_reapply_special_rate`), 0x4E8B6 (rear cornering latch), 0x500F0 (`abs_event_prefilter_flags`, 0xB0),
  0x521EC / 0x522A4 (straight latch), 0x530EA (yaw-stable), 0x59898 (dead), 0x5A230 (`abs_chassis_frame_init`),
  0x5CE36 / 0x5CECE (countersteer).
- **[verified] Validity coupling.** The lateral / yaw getters (0x93AC0, 0x93B3A, 0x93C22, 0x94308, 0x94376) fail on
  `sensor_reaction_word` b2 / b3 with st b3|b4 set and skip the `sensor_reaction_aux` test on that path. In
  `sensor_reaction_build` every rule that sets b0 also sets b2 | b3. The steering-timeout rules are 0xB4C66 (group A b6
  + 0x402E6D b5) and 0xB4C0E (0x402893 b6, sharing its set-site with 0x4028B6 b1). The only caller is the jsri at
  0xB5D6A, just before 0xB4D40 and `fault_reaction_matrix`. The only reader of 0x402881 b7 is 0x9AE96 (`sub_09ADE4`
  → 0x4022FA b0).
- **[inferred] Consequence.** Making yaw valid without the SZL, without also neutralising these targets, would make
  every corner look like a yaw error of the full measured yaw in those ABS paths.
- **[bench 2026-10-23, MR2 without SZL] More rules than the 0x0C9 timeout invalidate lateral / yaw.** Read:
  0x402009 = 0x40 (steering monitor fault state b6, b7 clear), group A = 0x0040 (0xA0040), group 11 = 0x0402,
  0x402890 b0 = 1. Group 11 b10 = fault **0xB0400**, raised only by `fcan_rx_2A6_byte0` 0xC630A (F-CAN 0x2A6, an SZL
  frame the DSC gateways). It trips rule 0xB4C2E (group 11 & 0xE00 → 0x402888 b0|b2|b3 and 0x402890 b0). Rule
  0xB4BF4 (0x402009 b6 + b7) is the next one to watch. The "Steering-sensor loss" chain above lists only the 0x0C9
  path.
- **[disasm 2026-10-23] The ax plausibility check is blind during ABS.** The deviation integrator 0x408E8E
  (`abs_ax_decel_estimator`, trust drops above 500) compares ax with DAF using tolerance cal 0x40D46 = 0.20 g. That
  is the same width as `abs_decel_est_clamp_ax`, which pins DAF to ax ± 0.20 g in the ABS regime once trusted, so
  inside ABS the integrator can only decay. Outside ABS it rises at up to +5 per frame (about 1 s to drop trust at
  e > 0.5 g). Detail: `analysis/agents/abs_full/10_vref_and_ax.md` §1.1.
- **[disasm 2026-10-23] Correction: one ax check does act inside ABS, and nothing overflows.** `sub_0935E8` sets
  ax invalid (0x404A2E b7, which drops trust) after 30 ABS frames in which 0x408DB5 b6 is set (reference wheel slip ≥
  ¼ of the gross-slip curve, [I]) and both rears decelerate uniformly. That is, vref held above the wheels. DAF is
  clamped (0x408EE8 ±2667 → ±127) and ax is the clamped byte, so a stop above 1.27 g pegs both together and the
  deviation stays 0. The alive counter uses the 1 mg raw signal. Detail: `10_vref_and_ax.md` §1.1.
- **[disasm 2026-10-23] The decel-threshold g-term wraps above 1.27 g, but only with ax trusted.** In
  `abs_decel_threshold_builder` 0x47BDC the trusted path takes x = 0x408E92 (1 mg, s16) / 10 at full width
  (0x47BF6). 0x47CB6 `sextb r3` then truncates it, so a 1.28–2.55 g decel wraps positive, is negated to x ≤ 0, and
  gives g-term 0: about −1.85 g at 1.27 g jumps back to the zero-decel value, about −1.25 g, at 1.28 g (100 km/h, var 0). The untrusted path
  (0x408DB8 / DAF bytes) can't wrap. Curve 0x40674 has breakpoints at 1.55 / 1.83 g that only a full-width input
  reaches. The fix is `sextb` → `mov r3,r3` (mk60-patcher `research/abs_decel_thr_ax_wrap`, branch
  vesrah/Lotus-GT3). The output stays bounded by curve hi = 250 and the absolute floor 0x4061E (−2.40 g). The 60 km/h
  floor skip (0x47CEA) uses the clamped byte 0x408E80 and is not affected. A car without the SZL only hits this
  with `abs_cluster_without_szl`, which makes trust possible.

## [disasm 2026-10-26] Traction control: brake TCS, engine ASR, MSR

Doc: `analysis/TCS_7846816A.md`. Symbols: "Traction control (TCS / ASR / MSR)" and the corrected cycle-4 section.

- **[verified] Channel roles.**
  - A = brake TCS on the rears: `req_arbiter_submit` id 2, target 0x402FEC[w], active 0x402FC0 b4.
  - B = engine ASR: torque limit 0x402F7A, active 0x402F6C b7, slot 16 0xCBF58.
  - C = MSR: 0x40304C, active 0x40303C b7, slot 17.
  - `dme_torque_request_compose` 0xCC2C2 (replayed 400/400) sets 0x402F6D b3 for reduction (ASR / ABS 0x408D58 /
    AYC 0x400B30 / dormant external) or b2 for increase (MSR).
  - 0x0B6 sig20 = 2 reduction pair, 1 increase, 0 none.
- **[verified, replayed] Brake-TCS limits.** entry = curve(0xF625C + 34m, vref_tcs) + 0x4030B6/4 + extras
  0xF62EE + 28m − rate/10 + 5 km/h, exit = … + extras/2 + 3 km/h. m0: 20 / 16.5 / 8.0 / 9.3 / 18.8 km/h at
  0 / 10 / 25 / 50 / 100 km/h.
- **[verified] Brake-TCS pressure law.**
  - fast fill ≤ 0.4 s;
  - +5 bar every N frames from map 0xF643A; release −max(15 %, 3 bar) every N from map 0xF63B8;
  - target ≤ 130 bar (literal);
  - no new entry above 120 km/h ABS vref; inhibited in DSC off and by disc overheat (0x402FC0 b1);
  - in MDM, capped to 0 from 80 km/h (0xF635E) and exits when both rears spin.
- **[verified, replayed] Engine-bog gate 0x403024** (< 20 km/h: (n_ref(pedal) − rpm)/16 …). It blocks brake-TCS entry
  above 80, holds above 110 and exits above 150.
- **[verified] Gearbox bit.** 0x402F6C b4 = gearbox type ∈ {1, 3} is never set on a valid M3 coding, so the alternate
  threshold set 0xF61F6 and the pedal-scaled ASR term are dead on the M3.
- **[verified] ASR allowed slip.** Targets 0xF66E0 / 0xF669E + 22m: m0 ≈ 1.5 km/h (6.5 at standstill), MDM 3–5
  km/h. ASR exits in DSC off (0xCA074).
- **[verified] Disc model.** The rear-disc thermal model 0x402FF4 (0xCEEDC) inhibits brake TCS. Thresholds
  0x9976 / 0x6F9B ≈ 550 / 400 at 0.014 per count [I °C].
- **[verified] Brake TCS ↔ ASR coupling** (doc §8.1):
  - the two run in parallel and nothing arbitrates brake against engine;
  - ASR's lower targets make it act first, and brake TCS exits on symmetric spin (0xC7D48, MDM pair exit);
  - ASR active slows the front-tracker fall (0.05 vs 0.11 km/h per frame) and shortens the hold;
  - split-µ (0xC9A22) is detected from brake-TCS pressures plus the ASR limit and changes both channels;
  - ASR cancels the brake-TCS freeze (0xC846A), and ASR's request hold (0xCA1E0) reads the brake-TCS entry limit;
  - 0x402F6C b5 latches the brake-TCS inhibit.
- **[verified] Replayer bug fixed.** `tools/mcore_replay.py` treated `clrt rx` / `clrf rx` as flag operations; they
  clear rx when C = 1 / 0. Replays through code containing them should be re-run (e.g. the AYC range 0x5E936–0x5FA2A
  has three).

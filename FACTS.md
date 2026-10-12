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
- **[verified]** 0xDF83C0–0xDF83E5 holds the ZB number 7846411 three times as BCD
  (`00 07 84 64 11`). The surrounding 0xDF8xxx ranges are all zero, so this is a
  programming/identification record, not code.
- **[verified]** E85 MK60E5 (`dsc_85.prg`, KWP2000) has no programming jobs in its SGBD and no
  WinKFP family in any pack on this machine.

## Hardware

- **[user]** MK60E5 main MCU marking: `0994.8500 4` / `SC560002MVF92 M98A` / `DCTNP0842B`,
  Freescale with ATE logo.
- **[source]** SC560002MVF92 is a customer-specific Freescale automotive ABS IC; no public
  datasheet ([NXP community](https://community.nxp.com/t5/Other-NXP-Products/Freescale-SC560002MVF92/td-p/1768891),
  [Octopart](https://octopart.com/sc560002mvf92-freescale+semiconductor-84653843)).

## CPU / code (1M image 7846411A; M3 not yet examined)

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
- **[verified]** File 0x3AC–0x8EF is a position-independent routine (addresses via r8) that
  dispatches on a command code, masks with 0x000FFFFF, references 0x00F60000.
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
  (front speed-term, g-curve, floor tables), indexed by a 5-bit EEPROM coding field `0x4031AA+1` (read via
  `0x8E066(24,1)`), not present in the flash. See `analysis/agents/m3cal/REPORT.md`.
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
  Inputs are the 4 filtered wheel speeds × a per-wheel tyre-circumference factor (Q10). Full algorithm:
  `analysis/agents/absvref/REPORT.md`.
- **[verified]** Wheel accel **struct+0x20 in 0.01 g**: normal-mode writer is **sub_0D271C** (called from
  wheel-speed update 0x752B8 @0x754DE), `+0x20 = two-frame mean of Δv·2.833` (conv literal 0xE287=58023),
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
  checked vs 0x4030DC, mismatch → DTC 0xC0040). Air-gap quality bytes 0x400A3C/44/48 have no consumer.

### Missing-encoding fault gates (M3, byte-verified 2026-10-04) — for sensor-compatibility bench study

Two independent checks fault when the sensors don't deliver the VDA encoded stream:

- **[verified]** **Startup VDA presence check `sub_075E38`** (= 1M 0x75E94). Runs per wheel during the startup
  window ([0x400960] cycle counter ≤ 1000). The per-wheel sensor mode comes from `sub_075A44`, which returns
  **4 for all four wheels (hard-coded — confirms no per-wheel sensor-type field)**. Mode 4 → read the wheel's
  ASIC reply word 0x400F20+4·slot (slot via table 0xD7668) and **popcount it** (`sub_075DD8`, a 32-iter
  `lsrc`+`inct` bit-count); plus per-wheel presence bits in the ASIC status word 0x4009C6 (`sub_075DEE`:
  wheel0 bit1, wheel1 bit5, wheel2 bit7, wheel3 bit3). If popcount **< 3** (`cmplti r2,3` at 0x75EB0; also
  0x75F1C) it sets the per-wheel error flag 0x4010CE[w]; at **cycle 100** the failure latches into the
  per-wheel status byte **0x400952[w] |= 0x31** (bits 0/4/5) → WSS sensor DTC (group 0x0C, the 0xC01xx/02xx/
  08xx per-wheel ids from the 0x95526 loop). Controlling points: mode selector 0x75A44, popcount threshold
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

- **[verified]** The EEPROM **coding field `0x4031AA+1`** (5-bit, variant 0..11, read via `0x8E066(24,1)`,
  unpacked at 0xD0418) selects a **vehicle-model parameter set**. M3: a 12-variant ROM table at
  ~0xD6E16..0xD70FF (each parameter = 12 contiguous s16, rows 24 B apart), loaded by 0x5DE44/0x5E424 into
  RAM 0x400AA4..0x400ABA. 1M: a single fixed scalar set at 0xD7458+ (no variant index). This confirms the
  user's hypothesis that unit coding selects geometry/mass.
- **[verified]** **Wheelbase** = l_f + l_r in 1/1024 m: 1M 1331+1393 = 2724 → **2660.2 mm** (exact 1M);
  M3 all variants sum 2826/2827 → **2760/2761 mm** (exact M3). Not stored as a scalar; only the CG split
  varies between M3 variants. Rows: l_f 0xD6F42, l_r 0xD6F5A, **mass 0xD6F72** (M3 1691–1947 kg; 1M 1739),
  yaw inertia Jz 0xD6F8A, stiffness 0xD6ECA/0xD6EE2. Mass/inertia units **[agent, med-low]** (J/m ≈ radius
  of gyration² supports it; 1M 1739 ≈ +4% over 1670 kg curb).
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
  (model parameters from coding bytes 31–40), 3 coupe, 4 convertible, 5/8/9 Competition sedan/coupe/
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
  tight-traction/loose-yaw. The car selects m=1 vs m=2 via one EEPROM coding bit while TCS state is 2/3.
  **This is where the "motorsport permissiveness" lives — DSC-mode logic, not the ABS/TCS slip-target bytes.**
  M3 AYC block is byte-identical to the 1M (mode tables are not M-specific).
- **[needs-hw]** Which driver-visible mode (DSC / DTC / MDM / OFF) maps to each m needs live values while
  cycling the DSC button + coding byte 10 bit5. Sensor LSB scales need a bench/CAN capture.

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
  clamped to 4800 (300 km/h at 1/16 km/h), 0x8000 when the wheel is faulted, and **negated when
  direction is valid and reverse**.
- **[verified]** Direction state in 0x004029D9 (bits 0–3 valid, 4–7 direction). It is only
  reported when 0x004029DA bit 5 is set, 0x004029D6 (wheel mask) is **non-zero**, and wheel
  speed ≤ 70.00 km/h. Sole writer: `sub_0B9118`. (Corrected: an earlier entry said D6 == 0.)
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
    (1573/1024). **Corrected cycle 7: these are Q10 metres, not mm** as first read.
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
  (The geometry/variant field accessor used by the vehicle-model loaders is a separate fn `coding_field_read_geom`
  M3 0x8E25E = 1M 0x8E066.)

### Cycle 2 [verified 2026-10-04] — control, wheel-speed, AYC/yaw (symbols in `analysis/7846816A_symbols.md`)

- **[verified]** The whole ABS controller (1M 0x44000–0x5E000, 196 fns) ports to the M3 by a constant shift
  (−0x220 below 0x4C000, −0x200 above); **all opcode-identical except `abs_decel_threshold_builder` 0x47BDC**
  (M3-rewritten: variant-indexed curves 0x40412/405F2/40674 by `0x4031AA+1`, vs the 1M's fixed curves). The
  `control_dispatcher` 0x8CCB8 is a **flat 41-call per-frame sequencer, not a jump table**. ABS/vref working RAM
  is shifted **+0x24** (vref 0x408DA8, decision code 0x408DDE). vref integrator + wheel-accel code and constants
  (literal 0xE287=58023, two-frame mean ·2.833, 0.01 g) are unchanged — closes the 1M "wheel-accel ±158" conflict:
  normal range is ±16 g before clamp, so the dump stages (−62…) are reachable.
- **[verified]** M3 **tunable ABS control** scalars: apply ramp 0x403A8=400, dump reductions 0x40E64/66/68=1000/
  1500/2000, reapply nudge 0x40D90=80, decel set A/B enables 0x40E94/0x40E9C=1, cornering limits 0x40DCE=126/8/1748.
  Hard-coded speed-dependent ROM curves relocated to **0xD6AFC–0xD6D50, byte-identical to 1M 0xD713C–0xD7390**.
  Clamps 25000/−8000, delta clamp ±5714, accel scale 58023 and the vref rise/fall/snap values are code literals
  (patch-only, not calibratable). (The 1M 0xDA2F0 scalar block has matching *referenced* values but is not a clean
  contiguous relocation — left unverified.)
- **[verified]** M3 **wheel-speed chain**: edge ISRs vec 56/57/58/59 → handlers 0x70E6A/0x70D56/0x70DE0/0x70CD0
  (opcode-identical to 1M); `wheel_speed_update` 0x7525C, `wheel_speed_filter` 0xB67F4, `wheel_direction_update`
  0xB9330. **BFU geometry identical to the 1M** (standstill 72, circumference 2073 mm, 48 teeth front+rear) — the
  M3 is NOT configured for different wheels at the BFU level. VDA hard-configured on all 4 channels; direction mask
  15; invert pair 05/09 at 0xD766C. VMO monitor block 0x42424 (window threshold 2000, %-scales 85/75).
- **[verified]** M3 **AYC / yaw control**: `yaw_observer` 0x5EBC4 (variant-indexed via per-variant arrays
  0x415F8/0x41610/0x41628), `yaw_pd_moment` 0x5F7BA, `engine_torque_request` 0x65078, `yaw_ref_closedform` 0x90E5C,
  `dsc_mode_select` 0xCF2EA. AYC block 0x41190: entry base A/B = 1396/2792, per-mode entry/hold ceilings
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
  `0x4031AA+5` (sets 0/1 identical, set 2 differs); x = raw steering counts. Three former scalars became 12-way
  per-variant sign tables (all −1). The 144-byte tail is byte-identical to the 1M. `steer_ratio_convert` 0x9032E.
- **[verified]** **Steering input**: F-CAN RX **0x0C9** (DLC8, 1 ms, mailbox 16) sig 43 = angle → handler 0xC5C78
  (·1029/1024 → RAM 0x401644). Sensor cluster 0x0CD/0x0D1 → `cluster_sensor_get` idx0..5 (yaw/ay, 0x402F1C..26).
  Closed-form r_ref confirmed on the M3 (`yaw_ref_closedform` 0x90E5C): v_ch enters via RAM 0x400AE8/AEA (variant
  model), no CSI constant in the denominator; r·v clamp ≈1.24 g (hard-coded). Yaw-rate LSB ≈1/20480 rad/s and
  steering ≈0.043 deg/LSB are **[agent, med / unverified units]**.
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
  undetermined. Per-coding-variant arrays at 0x422F8.. (indexed by 0x4031AA+9).
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
- **[verified]** **M3 TCS engine-torque-reduction path (resolves the long-standing open TCS question).** TCS PI
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
  curves 0x41B16/0x41B1E, pump ramp 0x41B34 (1150)/gain 0x41B36 (100)/filter 0x41B4C (187), volume temp-comp 0x41AE4/F0.
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
  per-mode ceilings 10471/8028 = **30.0 / 23.0 deg/s**, entry-by-speed table 4.0–10.0 deg/s. (**Refines the cycle-3
  "1/20480" hypothesis, which came from misreading the track table as mm.**) Steering ≈ 0.044 deg/bit; the r·v friction
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
- **[verified]** **AYC→ABS link resolved (corrects the cycle-6 EB2 note):** **0x408EB2 = driver brake pressure**
  (0.01 bar, dual-track ratiometric ADC sensor via 0x8F344, constants 0x5EE8=24296 / 0x97D=2429 / 0x556A=21866), NOT a
  yaw quantity. The real link is **B1A 0x400B1A** read directly by `abs_yaw_deviation_monitor` 0x4A254 (e = measured
  yaw ECC − B1A). In `abs_sensor_input_gather` 0x5D82C: **0x408ECA = lateral accel** (coarse, the x for the ABS
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
  - floor 0x4032D0 = min(2·900·C/60000).
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
Units: speed/slip 0.01 km/h, accel/decel 0.01 g, pressure ~0.01 bar (absolute scale [open],
needs bench gauge). Core architecture is opcode-identical to the 1M; RAM/cal addrs differ.

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
  **⚠ DIRECTION CORRECTED 2026-10-05 (see "cornering lat-g pressure term" entry below): the cal curves
  0x40E0A/0x40E26 are a lateral-g pressure term that RISES with |lat g| (26→49 / 14→40 bar), NOT a
  knockdown. The actual code-32 rear reduction uses a SEPARATE pct byte 0x408DE0 (producer untraced), plus
  rear select-low.** Earlier "scales ABS pressure down the harder you corner / the curves soften braking"
  was wrong on direction.
- **Steering angle never reaches ABS** (DSC-only). **Vehicle model (mass/l_f/l_r/Cf/Cr/Jz) feeds ONLY DSC**
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
  - `0x1A0 Speed`: AccX/AccY/YawRate/VehicleSpeed.
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
    (state 20) with recent pump flow → min(model, measured) (store 0x82E06); **gate closed → pure model for
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
  mid-corner pressure cut (exec 0x58FF4: CMD = PM − pct·(LOCKEST−CMD)/100), driven by pct byte 0x408DE0
  (PRODUCER UNTRACED) + rear select-low 0x5184C; this is the lever for trail-brake authority, NOT the
  0x48E0A/26 curves (those ADD pressure with g). (2) apply-ramp/slew onset. (3) decel floors / variant 10/11. (4) gross-slip
  slope 0xD6CE2 (smallest; stock ~11 % already near peak-µ). NOT levers: vehicle model, COA P-V.
- **Unmapped global cal to add to XDF:** 0x40C40, 0x40C5A, 0x40D24, 0x40D40(=50), 0x40D42(=7000),
  0x40DD2(=1748)+0x40DD8, rough-road 0x40D66..0x40D7E (CPU; file +0x8000).

## [verified 2026-10-05] ST_CLCTR control-state bitfield

- **ST_CLCTR = CAN 0x19E (StatusDSC) byte 0** — a BITFIELD (getter `can_tx_19E_status_flags` 0x7AEAA),
  assembled from the ABS control-state block 0x408DA0/0x408DA2 + intervention flags:
  - bit0 (1) = brake/slip-control active (ABS engaged) ← 0x408DA2 b7. (At engagement the phase machine
    DUMPS first, so pressures DROP when this sets — consistent with a datalog showing all four fall, fronts
    first, on a front-biased car.)
  - bit1 (2) = TCS/ASR ← 0x402FC0 b4; bit2 (4) = AYC/torque ← 0x400B0A&0xC0; bit3 (8) = DSC ← 0x400DF4 b7;
    bit4 (16) = TCS mode ← 0x402F6C+1 b2.
  - **bit5 (32) = lateral-limited (cornering handling active)** ← 0x408DA0 b1. CONFIRMED tie to decision
    code 32 (`abs_pair_logic` 0x54D9A → exec `abs_decision_pressure_exec` 0x58FF4). The exec REDUCES
    commanded pressure: CMD = PM − pct·(LOCKEST−CMD)/100 (pct byte 0x408DE0, producer untraced), and the
    rear-biased reduction is the separate select-low 0x5184C. (The cal curves 0x40E0A/0x40E26 are a lat-g
    pressure term that RISES with g — a separate thing, see the dedicated entry; do not conflate them with
    the knockdown.) [verified byte+bits; decision-code tie inferred]
  - **The getter sets only bits 0–5 (≤63); it NEVER emits bit6=64.** The `64 = rear-control` value exists
    only in the *internal* decision code 0x408DDE, which is NOT broadcast (0 CAN getters read it). A logged
    ST_CLCTR=64 ⇒ the DBC byte/bit offset is wrong.
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
- **The code-32 REAR KNOCKDOWN is separate:** exec 0x58FF4 (0x59222) `CMD(0x408F22) = PM − pct·(LOCKEST−CMD)/100`,
  floored, where `pct` = small byte 0x408DE0 **(producer NOT traced)**; plus rear select-low 0x5184C. This —
  not the 0x40E0A/26 curves — is what pulls rear pressure at turn-in (the ST_CLCTR=32 "big rear reduction"
  the user logged). **The real trail-brake-authority lever is the 0x408DE0 pct producer; TRACE IT NEXT.**
- Yaw rate (0x408ECC) is used separately at 0x51B88: curve 0x40E42 (x=peak-decel) sets a threshold |yaw|
  must exceed to latch the cornering flag 0x409024. 0x40C5A = AYC-gated yaw-deviation monitor (0x4A254),
  a separate DSC path, does NOT factor into code-32. [CONFIRMED]
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

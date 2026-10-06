# Phase-1 recon: ASIC/RAM peek-poke diagnostic patch (M3 7846816A)

All verified against `analysis/7846816A_main.lst` + `flash/bin/7846816A_00000000.bin` (file = CPU+0x8000).
This is a bench-only RE instrument for the cut-open test unit — NOT for a vehicle.

## Hook: repoint a dead 0x21 local-id
Service 0x21 (ReadDataByLocalId) handler `sub_0B184A` dispatches via a 12-entry jump table at CPU **0xB18F4**
(file 0xBB8F4). Valid ids = {2,4,5,6,7,9,11}; **ids 0,1,3,8,10 are dead → all point to the error stub 0xB2086.**
→ Repoint **id 0**: patch the 4-byte table entry at **file 0xBB8F4** from `00 0B 20 86` to `00 0D 8F 98`.
No bounds-check change (id 0 < 12 already indexes the table). Request `21 00 ...` now runs our handler.

## Handler location (free code space)
CPU **0xD8F98** / file **0xE0F98** — ~4 KB of zero-fill, **no `lrw`/data references**, inside the BMY-signed
app segment [4] (0x48F20–0xE265F), so it flashes + is covered by the signature with no segment/erase change.

## Request buffer
Raw KWP request at RAM **0x40331D**: `[0]=SID(0x21) [1]=localid(0x00) [2]=op [3..]=args`. (Confirmed: the 0x23
handler reads its format at 0x40331D+4 and len at +5, i.e. SID at +0.) We read `op` at 0x40331D+2, args at +3…

## Response emit (from id-5/id-7 handlers)
- Payload buffer base **0x409489**; **data is written starting at +2 (0x40948B)** — the dispatcher prepends
  `61 <id>` (so our reply is `61 00 <payload>`).
- **Length byte at 0x409537** = payload length (tune on bench; id-7 used 0x0F).
- **Ready flag at 0x409435 = 1.**
- Then run the id-handler epilogue to unwind `sub_0B184A`'s frame and `jmp r15`. Frame: prologue was
  `subi r0,24; stm r10-r15,(r0); movi r1,40; subu r0,r1`; epilogue = `addi r0,40; ldm r10-r15,(r0);
  addi r0,24; jmp r15` (copy the exact bytes from a real id handler's return to be safe).

## ASIC primitive: asic_reg_xfer32 @ 0xD4A30 [verified]
- Input in **r2 = (regfield<<16) | data** (each masked to 10 bits: TX word0 = (r2>>16)&0x3FF = reg/command
  field; TX word1 = r2&0x3FF = data). Return in **r2 = (RX0<<16)|RX1** (readback).
- Self-brackets irq_disable/restore (0x6C6A8/0x6C6B8); safe to call from the handler. QSPI base 0xDB0000, CS5.
- Reg id low bits encode R/W (init writes use ids like 0x154 with low bits `100`; the loopback READ used
  regfield 0x008 / data 0). Our op passes the tester-supplied 32-bit arg straight through, so we can
  experiment with any regfield/data from the bench.

## Ops to implement (build #1 first, validate, then add #2)
1. **RAM peek**: `21 00 01 <addr:4> <len:1>` → read `len` bytes from CPU addr, return them. (Validates the
   whole hook+flash loop against a known value, e.g. read the ident region.)
2. **ASIC xfer**: `21 00 02 <arg:4>` → `r2=arg; jsri 0xD4A30`; return the 4-byte readback. (Dump ASIC regs;
   later poke candidates.)

## M·CORE encoding cribs (verified from the listing)
`subi r0,imm`=24Fx · `stm r10-r15,(r0)`=007A · `ldm r10-r15,(r0)`=006A · `mov rd,rs`=0x1200|(rs<<4)|rd
(122D=mov r13,r2) · `movi rd,imm7`=0x6000|(imm<<4)|rd (60F2=movi r2,15) · `lrw rd,[pool]`=0x7000|(rd<<8)|...
· `ld.w rd,(rs,off)`=0x8000|(off4<<4?) (8703=ld.w r7,(r3,0)) · `st.w`=9703 · `ld.b`=A30E(r3,(r14,0)) ·
`st.b`=B70E · `ld.h`=C701 · `st.h`=D701 · `and rd,rs`=0x1600 (1672=and r2,r7) · `or`=0x1E00 (1E67) ·
`lsli rd,imm`=0x3C00 (3CC2=lsli r2,12) · `lsri`=0x3F00 (3F06=lsri r6,16) · `bmaski rd,n`=0x2C00 (2CA5=r5,10→0x3FF)
· `cmpnei rd,imm`=0x2A00 (2A31=cmpnei r1,3) · `bt`=0xE000 · `bf`=0xE800 · `br`=0xF000 · `jsri [pool]`=0x7F00 ·
`jmp r15`=00CF. Literal pools (lrw/jsri targets) are 32-bit words placed near the code; our handler needs its
own pool for 0xD4A30, 0x40331D, 0x409489, 0x409537, 0x409435.

## UPDATE (2026-10-05): switched hook from 0x21 to 0x23 (parametric) — BUILT
**Why 0x21 failed for params:** the KWP dispatcher enforces the service table's
length byte (`0xF30A0`, entry[1]) as an **EXACT** request length, unless it is
`0xFF` (= variable). 0x21's entry is len=0x02, so any `21 00 ..` >2 bytes → NRC 0x12.
Length check is at CPU 0xB11B8–0xB11CA (`ld.b r4,(r3,1)` vs `*0x409537`, `!=0xFF`).
Marker hook on 0x21 proved code-exec works, but 0x21 can't carry an address.

**New hook = service 0x23** (entry 21: len=0x06 EXACT, flags[8]=0x94 == 0x21's,
seclvl[9]=0x00 → reachable in the same session as the 0x21 hook, no auth).
Repoint the handler pointer (table entry+4) at **file 0xFB1A0**: `00 0B 31 12 -> 00 0D 8F 98`.
Request is exactly 6 bytes: **`23 <op> <arg:4>`**.
- op=0x01 ASIC xfer: `r2=(arg)`; `jsri 0xD4A30`; return 4-byte readback `(RX0<<16)|RX1` big-endian.
  arg = `(regfield<<16)|data` (peek with data=0; poke by supplying data).
- op=0x02 RAM peek: `addr=arg`; read 32 bytes from CPU addr (raw `ld.b`), return them.

**Response convention (mimics stock 0x23 @ 0xB3178):** data → **0x40948A**, length
`0x409537` = databytes+1, ready `0x409435`=1; dispatcher prepends `0x63`.
**Calling convention:** dispatcher does `ld.w r7,(r3,4); jsr r7` → clean subroutine;
handler saves r15 (op=1 calls the ASIC driver), balanced stack, `jmp r15`.
Handler body @ CPU 0xD8F98 / file 0xE0F98 (128 bytes). Builder: `tools/build_asic_probe.py`.
Both edits are covered by BMY (app region [0x48000,0xFE924)); `bmy_resign fix` re-signs.

**Client:** `tools/mk60_can.py asic {xfer|dump|ram} ...` (sends `23 op arg`, decodes reply).
Flash: `flashplan flash/plan/m3_probe --arm`. First validate the pipe with a known
value: `asic ram 0x000F56C8` must return the auth key `F1 CE 23 C6 CD 24 C8 B7 ...`.

## RESULT (2026-10-05): WORKING — proven on the live module
First build crashed the ECU (hard hang, dead until power-cycle) on BOTH ops. Root
cause: the prologue/epilogue saved/restored r15 with a **single-register** `stm r15`
/`ldm r15` (0x007F/0x006F) — a form the firmware never uses; it mis-restored r15 so
the final `jmp r15` jumped wild. **Fix:** mirror the stock 0x23 frame exactly —
`subi r0,16; stm r13-r15,(r0)` ... `ldm r13-r15,(r0); addi r0,16; jmp r15`
(0x24F0/0x007D ... 0x006D/0x20F0/0x00CF). We only clobber r1-r7, so r13/r14
round-trip. Also shrank the RAM-peek to 16 B (the KWP response buffer is ~31 B;
a 33-B response overran it — a second, independent hazard now avoided).

Proven live (M3 fw on the bench unit):
- `asic ram 0x000F56C8` → `f1 ce 23 c6 cd 24 c8 b7 b8 b3 c6 53 d9 70 7b ac` (auth key — exact). Memory peek validated.
- `asic xfer 0x008` → RX0=0x0024 RX1=0x00AE (deterministic on repeat).
- `asic xfer 0x1A5` → RX0=0x0024 RX1=0x02CD. RX0 = constant status word; RX1 = per-command data.
ECU stays healthy across calls. Capability = arbitrary RAM/flash peek + ASIC QSPI xfer (read+write) over D-CAN.

## Safety / rollback
Dormant unless `21 00 ...` is sent (normal operation untouched). A buggy handler only faults on our request
(recoverable by reset/reflash). A bad ASIC poke is wiped by boot-time re-init. Stock-M3 reflash always recovers.
Re-sign with `bmy_resign fix` (MISR+BMY) before flashing; repack onto the segment layout; flashplan --arm.

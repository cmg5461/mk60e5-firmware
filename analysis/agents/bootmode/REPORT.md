# Boot-mode / debug-lock / bootloader-entry (app image only; bootloader 0x0–0x3FFFF absent)

Agent-derived (Sonnet), **key claims re-verified by main session**: `'SBL!'`=0x53424C21 in the 0x0D5684
literal pool; 0x0D5684 calls sys-status read 0x0D58B0; reset dispatcher 0x06CFA6 has `movi r7,45; cmpne r2,r7`
and reaches `jsri 0x0D5684` in that case — all byte-exact. CPU addresses.

## 1. Headline — NO JTAG/OnCE disable in the application [agent, med-high]
Full disassembly of the reset handler (0x06C9B2) and its boot-time callees — register/CR clear, INTC
(0xE10000), PLL (0xDC0000), port dirs (0xD5/F5), MPU (0xFFF00000 via 0x0D5654/0xD7648), flash-cache clear
(0xFFF80000/82000/84000), sys-status bit clear (0xFF0000 bit5) — writes **no register outside the already-
catalogued peripheral clusters**, and nothing resembling a debug-control / censorship / security bit. On this
M·CORE family OnCE/JTAG is gated by a **factory fuse / TAP hardware**, not a CPU-addressable register, so an
app-level disable would be unusual in principle. **Good news for probing: the application gives no evidence of
locking the debug port; any lock would be mask-ROM/fuse, invisible here and settleable only by probing [needs-hw].**

## 2. Boot-mode detection
- `sys_status_read` (0x0D58B0) only **reads** `0xFF0006` (byte-swapped u16); the app never writes it.
  `jump_to_bootloader` (0x0D5684) requires a bit of that status word set, **plus** `[0x4010]=='SBL!'` and
  `[0x4000] != 0xFFFFFFFF` [verified]. (On our image 0x4000/0x4010 are in the absent bootloader region, so the
  'SBL!' marker is present only on a real unit — the check is app code, the data is bootloader-written.)
- The status word must be latched by the **reset controller / mask-ROM before the app runs** — plausibly a
  reset-cause or a sampled boot-mode pin. **No app-level GPIO boot-strap read exists** [agent, med]. Any
  connector/pad boot-mode strap lives in the bootloader/hardware [needs-hw].

## 3. Bootloader-entry / programming trigger
- Single call site to `jump_to_bootloader`: `ecu_reset_dispatcher` (0x06CFA6), **case r2 == 45 (0x2D)**
  [verified]. That path quiesces both CAN modules (0xDD0000/0xFA0000), re-runs MPU setup (0x6C754/0xD5624/
  0xD55EC), touches timers and the signature unit 0xD50200, then jumps to the secondary bootloader at 0x4000.
  Other dispatcher cases (123, 0x81/0x84) do a normal soft reset, not the SBL jump.
- The literal 45 is supplied by `sub_077080`, inside the **ASCII manufacturing/test serial protocol**
  (`sub_076092`, fed from serial buffer 0x40331D, open ~1.8 s at power-up), loaded dynamically from protocol
  state 0x400A18 — the exact serial command byte wasn't pinned [agent, med]. **No CAN/KWP SID in the app
  forwards 45.** So CAN-triggered reflash is almost certainly handled by the **bootloader/mask-ROM at reset**
  (checking 0xFF0006 before handing to the app), which is why bench flashing over CAN doesn't involve the app.
- App vs bootloader split [verified]: RequestDownload 0x34 / TransferData 0x36 / TransferExit 0x37 are ABSENT
  from the app KWP table (0xF33A8 = 0x10/0x11/0x27/0x31…). Flash programming lives entirely in the bootloader
  at CPU 0x4000, reached only via the 'SBL!' / jsr[0x4000] hand-off.

## Open / needs-hw
- Whether OnCE/JTAG is fused off — settleable only by probing the pads.
- Exact serial command that resolves to reset-code 45 in sub_076092 (dynamic from 0x400A18) — not fully traced.
- Whether 0xFF0006 bit reflects a physical pin, reset-cause, or bootloader-written flag — needs bootloader/bench.

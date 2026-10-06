# Manufacturing/test serial protocol (sub_076092) — decode

Agent-derived (Sonnet), **key claims re-verified by main session**: vec44→0x42788 / vec52→0x42804;
**0x00FC0000 referenced nowhere in code** (serial is on the 0xD80000 module, not 0xFC0000); the 'Z' gate
(`ld.b (r9,1); lsri r7,5; cmplti r7,3` then `st.b top-byte → 0x400A18`, 123 override) byte-exact. CPU addresses.

## Answer: no memory-read primitive; it only triggers the bootloader jump
**No command takes a caller-supplied address** to read/write arbitrary RAM/flash (corroborates the btldread
finding). The protocol's only "write" is one fixed byte — the reset/dispatch code at `0x400A18`. So this is
NOT a bootloader dumper; it just hands control to the (absent) bootloader.

## Serial engine — corrects the prior FACTS "0xFC0000" claim [verified]
- `0x00FC0000` appears in **no** code literal → the "serial unit 0xFC0000" entry was wrong.
- The real engine is on the **0x00D80000 module** (same TPU-style multi-channel base as the WSS timer/capture;
  one channel runs a UART function): control reg **0xD80380**, data **0xD80110** (64-byte channel stride).
  Vector slots **44** (handler 0x42788 → sub_07076C) and **52** (0x42804 → sub_0700E8) are the RX/TX ISRs,
  feeding the RAM driver struct **0x403368–0x403390**, incl. RX buffer **0x40331D** and TX byte ~0x4032D1/D2.
  (The vector#→physical-IRQ# mapping is unproven, so "44/52" as literal IRQ numbers stays unconfirmed.)
- **Framing**: plain 8-bit bytes, consistent with **8N1**. **Baud**: not pinned to a divider in code; table
  0xD78E0 (16×u16, sysclk/5 MHz) yields standard rates incl. 9600 (521) and K-line 10400 (481). **Probe TX
  within ~1.8 s of power-up and try 9600 / 10400 8N1 first** [needs-hw].

## Command set (jump table 0x076134, 13 states; state var 0x400A28)
- **State1 handshake**: requires exactly bytes `0x40 ('@'), 0x01, 0x02`; timing-gated to the power-up window.
- **State2**: byte-at-a-time digit commands 0x30–0x3F via sub-table 0x076210; ACKs each byte with 'c'/'j'/'n'.
- **State4** sets ecu_mode bit5 (level 1 / handshake); **State6** aborts the session to ecu_mode 0xE0 on failure.
- **Letter dispatcher** (byte at RX-frame +2): **R** (local scratch r/w), **S** (string echo ≤24), **T**
  (hex-ASCII-pair number parser, sub_0773C4), **U** (level-raise, §auth), **X** (internal block copy), **Z**
  (bootloader trigger, below). **None takes a CPU address** — all pointers are fixed/local.

## Bootloader-entry sequence [mechanism verified; exact payload offsets agent, med]
Within ~1.8 s of power-up: handshake (`@`,01,02) → raise level to ≥3 via **'U'** command + confirmation
**"16"** (0x31,0x36) → **'Z'** command with a hex-ASCII payload whose first pair is **"2D"** →
`0x400A18 = 0x2D (45)` → state7 (0x077078) → sub_077080 → `ecu_reset_dispatcher` 0x06CFA6 case 45 →
`jump_to_bootloader` 0x0D5684 → `jsr [0x4000]` (needs `[0x4010]=='SBL!'`). The 'Z' write is **gated by
ecu_mode level ≥3** (0x76C1C–0x76C2E); below that it's a no-op. No per-unit secret — a scripted byte sequence,
fully ROM-visible (like the 0x27 algorithm).

## Gating / auth — soft, no secret
Timing window ~1.8 s / 179 frames; fixed sync bytes; 'U' level-raise needs "16" for level 3 (writes raw
field = 2). Level 4 ("stops CAN") path not located this pass (look for a "33" confirmation) [open].

## Open / needs-hw
1. UART baud index actually used (try 9600/10400 8N1). 2. Exact 'Z' payload byte offsets/lengths (live
capture). 3. Level-4 path ("33"?). 4. **Physical TX/RX pin identity for the 0xD80000 serial lines — a
package/schematic question, needs-hw.**

## Note
Forcing bootloader entry via this serial sequence only transfers control to the bootloader; whatever the
bootloader then exposes (a read/upload service, its own auth) is in the absent 0x0–0x47FFF image — so this is
a route to *interact with* the bootloader on the bench, not to read it from the app.

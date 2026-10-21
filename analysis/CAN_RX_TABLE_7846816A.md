# CAN RX frame table — 7846816A (M3)

Companion to `CAN_TX_TABLE_7846816A.md`. Decoded 2026-10-15 from the same config tables (image
`flash/bin/7846816A_00000000.bin`, CPU = file − 0x8000) and checked against the RX code. RX messages follow the TX
messages in the message table: PT-CAN header 0xD7F45 has 20 TX + **27 RX**; F-CAN header 0xF59C3 has 14 TX + **18 RX**.

## Record layout (RX side)

- **Message** (23 B, same table as TX): +2 u16 CAN id · +4 low nibble DLC · +5 b6 = masked id (then +16 u16 =
  acceptance mask) · +10 n_signals · +11 u16 first signal · +13 mailbox. F-CAN only: +20 u16 = PT-CAN id the frame
  is gatewayed to (0x0C8/0x194/0x1D6/0x2A6/0x1D9). +6/+7/+9 are not used by the RX code paths decoded here.
- **Signal** (5 B): +0 b0..4 length · b5 "signed" flag (informational; handlers sign-extend themselves) · b6 pack
  mode (never set on RX, so every RX signal is Intel) · +1 start byte (low nibble) / bit (high nibble) · +3 u16 variable.
- **Variable** (8 B): +0 b0..2 type · +1 default · +4 u32 handler (or RAM address for type 1).

## How a frame is processed

`can_rx_dispatch` 0x79D3A (PT, in the 10 ms CAN task 0x793F0) walks every RX mailbox that has new data:

1. **DLC check.** A frame shorter than the configured DLC is rejected (0x40163C bit set, frame status 0x401174[i]
   b7 cleared) and none of its signals run.
2. **Signals in table order** via `can_rx_signal` 0x79CC8, stopping as soon as 0x401174[i] b7 is cleared (a
   payload handler that fails its checksum, or an alive handler that sees a stale counter, clears it):
   - **type 0**: `v = can_unpack_bits` 0x79FE0(&payload[byte], bit, len, mode); `handler(v)` (zero-extended).
     Same mask table and byte order as the TX packer.
   - **type 2**: `handler(payload)` (checksums, multi-byte fields, gateway copies).
   - **type 4**: no call on receive; reloads the timeout counter 0x40161C[var] with the default (unless 0xFF).
3. **Timeouts.** `can_rx_timeout_task` 0x796CC (same 10 ms task) decrements each type-4 counter (PT vars 0..10).
   At 0 it calls the handler **every cycle** until the frame returns. Counts are in 10 ms units: 50 = 500 ms,
   10 = 100 ms, 30 = 300 ms, 250 = 2.5 s. Frames without a type-4 variable use software counters in
   `can_dme_iface_update` 0x7E7A4 instead (0x4046F2..0x4046FA, reloaded by the signal handler).
- F-CAN works the same way (`fcan_rx_signal` 0xC5284, counters 0x402F05[var], `comms2_state_machine` 0xC4D64,
  10 ms). F-CAN also has **type 1**: store the field directly to the RAM address in +4. Var +1 low nibble = width − 1,
  high nibble = bit position in the destination; a wider field is right-shifted to keep its top bits (0xC54DA inserts).

## Common patterns

- **Checksum** (payload handler): zeroes its own byte or nibble, recomputes with `can_checksum` 0x7D24C(mode, id,
  n = received DLC, buf), and compares. F-CAN cluster frames use 0xC72B8 on byte 7.
  - `s = Σ buf[0..n−1] + id`, then `c8 = (s + ((s & 0xFFFF) >> 8)) & 0xFF`. **Mode 8** (0x0A8/0x0A9/0x0AA byte 0,
    0x0BA byte 5) returns c8.
  - **Mode 4** (0x130 byte 4 high nibble, 0x308/0x399 nibble) returns `(c8 + (c8 >> 4)) & 0xF`.
  - Example 0x130: zero byte 4's high nibble, sum all DLC bytes + 0x130, fold to 4 bits, put the result in byte 4's
    high nibble.
- **Alive counter** (4-bit): 15 or the same value as last frame → frame dropped. A per-frame 2-bit error counter
  (saturating at 3) is kept for checksum and alive errors.
- **Timeout handler** picks the reason from those counters (checksum ≥ 3 → checksum fault, alive ≥ 3 → alive fault,
  else timeout) and reports it with `0xBF994(mask, …)` (PT) or `0xBFA2A(mask, …)` (F-CAN). PT reports are
  suppressed while fault 0xA0002 (PT-CAN bus-off, D347) is latched, and only made when 0x401163 b4 is set.
- **Invalid values**: 12-bit fields use 0x800, bytes 0xFF, words 0xFFFF; 2-bit status fields usually reserve 2/3.
  Invalid sets per-signal flags in 0x401150–0x401155 and, for the DME torques/pedal/rpm, starts a 50-cycle timer
  (0x4046EA–0x4046F0). Expired torque timers report **5E1B** "CAN DME Motormoment Signal Fehler" (0x7CCC8/0x7CCE2/0x7CD00).
  The other DME timers are checked in the same loop (0x7F2D6–0x7F354 in 0x7E7A4): pedal 0x4046EA and rpm 0x4046ED
  → **5E1A**; 0x0A8 state = 3 (0x4046EB) → **5E19** "Motormoment nicht einstellbar"; 0x0A8 6.4–6.5 ≠ 0
  (0x4046EC) → **5E18** "Botschaft unplausibel". No DME DTC compares the torque values with anything else.

## Fault id → DTC

The reporters take a bitmask: DTC-table internal id = 0x2000 (PT) or 0x3000 (F-CAN) + 16·(mask >> 16) +
bit index of (mask & 0xFFFF). Records are in `dtc_table` 0xF367C (`{u16 id, u16 DTC, u32 flags, u32}`); the
flags byte gives the reason: 0x04 timeout, 0x02 alive, 0x08 checksum. Texts from `DSC_87.prg`.

| Frame | DTC | Ids (timeout / alive / checksum) |
|---|---|---|
| 0x0A8 | D354 DME/DDE_1 Drehmoment 1 | 0x2000 / 0x2001 / 0x2002 |
| 0x0A9 | D355 DME/DDE_2 Drehmoment 2 | 0x2003 / 0x2004 / 0x2005 |
| 0x0AA | D356 DME/DDE_3 Drehmoment 3 | 0x2006 / 0x2007 / 0x2008 |
| 0x0BA | D357 Getriebe 1 | 0x2009 / 0x200A / 0x200B |
| 0x310 | D358 Instrumentcluster_1 (outside temp / relative time) | 0x200C |
| 0x330 | D359 Instrumentcluster_2 (odometer) | 0x200D |
| 0x130 | D35A Gateway_1 Klemmenstatus | 0x200E / 0x200F / 0x2010 |
| 0x2E4 | D377 Status_Anhaenger | 0x2011 (no reporter found) |
| 0x0D5 | D35B LDM wheel-torque request | 0x2012–0x2014 (frame is dead) |
| 0x380 | D361 VIN timeout, 5E1F VIN wrong, 5E1D VIN invalid | 0x201C / 0x201D / 0x201E (reporters not traced) |
| 0x1A3 | D35D ACC long-term timeout | 0x201F (reporter not traced; the timeout handler only sets 0x4046D8 b3) |
| 0x3B0 | D378 Status_Gang_Rueckwaerts | 0x2021 |
| 0x308 | D379 Status MSA | 0x2033 / 0x2035 / 0x2034 |
| F 0x0CD | D370 Sensorcluster_1 | 0x3000 / 0x3001 / 0x3002 |
| F 0x0D1 | D371 Sensorcluster_2 | 0x3003 / 0x3004 / 0x3005 |
| F 0x0D4 | D372 Sensorcluster_3 | 0x3006 / 0x3007 / 0x3008 |
| F 0x0C9 | D373 SWA-Top-Sensor 200/201 | 0x3009 / 0x300A / 0x300B |
| F 0x118 / 0x11F | D375 / D376 AFS | 0x300F–0x3014 (frames are dead) |
| F 0x194 | D364 Operator_Key_Tempo (cruise stalk) | 0x3046 / 0x3048 / 0x3047 (**no reporter**; timeout handler is a stub) |
| F SZL status | 5E50 / 5E51 SZL serial wrong / invalid, 5E3F SZL coding, 94B0–9520 and C987–C99C forwarded SZL faults | 0x3015 / 0x3016 / 0x3017, 0x3018–0x3045 (0xC5E7A / 0xC6354) |
| F 0x0C9 timeout | 9502 / 9503 SZL steering sensor under- / over-voltage | 0x304A / 0x304B, from 0x402F53 b2–3 = 1 / 2 (0xC6E70) |

Other CAN DTCs in the table, not traced to a frame here: D35C ACC_2, D360 Motronic_4, D362 Motronic_5,
D363 Instrument_cluster_3, 5E18–5E1C, 5E60–5E68. (D364 is F-CAN 0x194, above. The DSC_87.prg text says
"PT-CAN", but the id is in the F-CAN namespace.)

## When CAN DTCs are reported at all (ignition gate)

Every PT-CAN timeout/alive/checksum reporter above checks **0x401163 b4** (`can_dtc_enable`) before calling
0xBF994. `can_comm_state_update` 0x794FC sets that bit only when **all** of these hold, and clears it otherwise:

1. **0x4015E8 b4 clear.** `can_dme_iface_update` 0x7E7A4 sets b4 = (0x40471C ≠ 0) or (0x4046C0 ≤ 178).
   - 0x4046C0 counts 10 ms cycles since start, so the first ≈ 1.8 s are always suppressed.
   - **0x40471C is reloaded to 75 every cycle while 0x400956 b6 ("ignition on") is clear**, and counts down to 0
     once it is set. So reporting starts only **750 ms after ignition-on**.
2. **0x400956 b5 and b7 clear** for 75 cycles (second delay counter 0x401629). b5 = 0x4009BC & 0x60 ≠ 0, the same
   inhibit the BLS input uses (likely supply voltage out of range; not confirmed). No writer of b7 was found.
3. **0x400966 b6 clear** (start-up flag; clears by itself after about 180 cycles, 0x70F68).
4. **0x401163 b7 clear.** This is set and cleared from the diagnostic-routine dispatcher 0x8E144 / 0x8E6E2 (via 0x78FCA),
   so a tester can switch CAN fault monitoring off.

**Where ignition comes from (revised 2026-10-15).** 0x400956 b6 is written by the power state machine
`power_state_update` 0x72020 (state 0x4009C0: 4 = on, 5 = off, 1/2 transitional; debounce counter 0x4009BE, 0–7).
Its source is picked by **`ign_source_hw` 0x4009FF b0**, recomputed at the end of every pass:
b0 = 0x401134 b7 (`terminal_state` invalid), or (0x401162 b7 and the previous b0). 0x401134 b7 is set at CAN init
(0x78B7C) and by the 0x130 timeout (0x7CE44), and cleared by a valid 0x130 (0x7C37E). So:

- **0x130 valid** (b0 = 0): ignition = `terminal_state` 0x401130 ∈ {4, 5}. 0x401130 = 4 comes from **0x130 byte 0
  bits 2–3 = 1** (`can_rx_130_kl_b`, inferred terminal 15). A valid 0x130 reporting ignition off turns it off.
- **0x130 never received, or timed out** (b0 = 1): ignition = **`hw_ign_input` 0x400958 b5**, which 0x72224 sets to
  NOT bit 8 of `wss_asic_status_rx`[1] (0x4009C8), from the 4-word QSPI CS5 status read. While the input is on,
  the counter counts up to 7; when it goes off, the counter counts down and ignition goes off at 0 (≈ 70 ms if
  this runs every 10 ms). Off → on also follows the input.

**[bench, 2026-10-15]** On an automatic-coded unit with only power applied (no 0x130; 0x310/0x330 sent), the DSC
logs **D35A, D354, D355, D356, D357**. D35A can only be reported with `ignition_on` set, so the hardware input
reads "on" with power alone on that unit. Which pin or chip state drives bit 8 is not known. An earlier note
(no D354 until 0x130 was sent) came from a setup that was not recorded; a valid 0x130 with ignition off would
explain it.

**Consequence.** With a valid 0x130 reporting ignition off, the DSC raises **no** PT-CAN message DTCs, not even
D35A. With no 0x130 at all, it depends on the hardware input. Either way, once ignition is on, monitoring starts
after about 0.75 s and every missing frame gets its timeout DTC.

F-CAN has a similar but separate gate in `fcan_comm_state_update` 0xC4DD0 (flags 0x402EE0 b3/b1: uses 0x400956 &
0xA0, a 75-cycle delay 0x402EDD, and the 0x40095C uptime counter). I did not establish whether it needs ignition.

## Dead frames

Every handler of these frames is a bare `jmp r15`, so their data is discarded and their DTCs cannot be raised:
PT 0x0AC, 0x0B4, 0x0D5, 0x1B4, 0x388, 0x2A6 (PT); F 0x118, 0x11F, and the signals of F 0x194 (its payload is only gatewayed to PT-CAN).
Many single signals in live frames are stubs too (marked "(stub)" below).

## Not identified

PT 0x226, 0x316, 0x319 carry 2–4-bit states into 0x401108 / 0x401111 / 0x40482E–0x404830. I could not tie
them to a BMW message name. 0x398 and 0x399 are now known to carry driver-mode requests into 0x401139–0x40113B
(0x398 byte 1 bits 2–4: 0 = DSC on, 1 = DSC off, 4 = MDM; see FACTS "DSC driver mode"). The BMW message names are
still unknown, and so is the meaning of the 0x398 byte 0 slot. 0x797, NM (0x480/0x580) and tester (0x6F1)
handlers are summarised only. "Probably terminal R/15/50" for 0x130 is inferred from use (the BLS state on 0x19E
needs sig 164 = 1), not confirmed.

## PT-CAN RX (27 frames)

#### PT-CAN 0x0A8  DLC 8 · mailbox 5 · timeout 50 × 10 ms

DME torque 1 (D354). Engine torque, state bits

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 108 | — | — | Intel | 0x0CF | 2 payload | 0x07D6CE | `can_rx_0A8_checksum` | checksum: byte = low8(Σ payload + id) as `can_tx_checksum8` (byte zeroed first). Mismatch → frame dropped (0x401174[i] b7 cleared), error counter +1 (sat 3), signals marked invalid; counter 0x4046C8 b5:4 |
| 109 | 1.0 | 4 | Intel | 0x07D | 0 value | 0x07BA42 | `can_rx_0A8_alive` | 4-bit alive counter: 15 or unchanged → frame dropped, error counter +1 (sat 3); else step (mod 15, max 3) saved; last 0x4046CC hi nibble, counter 0x4046C8 b7:6 |
| 110 | 1.4 | 12 | Intel · signed | 0x0B4 | 0 value | 0x07BB0A | `can_rx_0A8_torque_set` | 12-bit signed torque ×5 → **0x401146** ("indicated engine torque", internal unit = raw/5). 0x800 = invalid → 0x401150/53 b2 + 50-cycle timer 0x4046EF (→ 5E1B on expiry) |
| 111 | 3.0 | 4 | Intel | 0x0B0 | 0 value | 0x07BB5A | `can_rx_0A8_state` | 0/1 → 0x40114F b6:5 = 00, 2 → 10, 3 → 01 (+ timer 0x4046EB = 50, on expiry 0x7CC7A → **5E19** "Motormoment nicht einstellbar", fault 0xB0040); ≥ 4 invalid (0x401151/54 b5:4) |
| 112 | 5.0 | 2 | Intel | 0x0AF | 0 value | 0x07BBDE | `can_rx_0A8_flag` | 0/1 → 0x40114F b4; 2/3 invalid (0x401151/54 b2) |
| 113 | 6.4 | 2 | Intel | 0x0AC | 0 value | 0x07BC1A | `can_rx_0A8_event` | ≠ 0 starts 50-cycle timer 0x4046EC (on expiry 0x7CC94 → **5E18** "Botschaft unplausibel", fault 0xB0010); 0 clears it (0xFF) |
| 114 | 7.5 | 3 | Intel | 0x099 | 0 value | 0x07BC30 | (stub) | bare return: signal discarded |
| 115 | — | — | Intel | 0x008 | 4 timeout | 0x07CEE8 | `can_rx_0A8_timeout` | after 50 × 10 ms: DTC **D354** via 0xBF994: checksum errors ≥ 3 → 0x2002, alive errors ≥ 3 → 0x2001, else (unless PT bus-off 0xA0002) 0x2000 timeout. Reported only if 0x401163 b4. Also sets 0x401151/0x401154 b2 and reports group fault **0xA0008** (latch 0x40284C b3), shared by D354–D356; its reaction disables DSC/AYC/TCS but not ABS (FACTS: DME torque timeout reaction). No 5E1B |

#### PT-CAN 0x0A9  DLC 8 · mailbox 6 · timeout 50 × 10 ms

DME torque 2 (D355). Engine drag / MSR torque; other 12-bit fields are stubs

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 116 | — | — | Intel | 0x0D0 | 2 payload | 0x07D656 | `can_rx_0A9_checksum` | checksum: byte = low8(Σ payload + id) as `can_tx_checksum8` (byte zeroed first). Mismatch → frame dropped (0x401174[i] b7 cleared), error counter +1 (sat 3), signals marked invalid; counter 0x4046C8 b1:0 |
| 117 | 1.0 | 4 | Intel | 0x07E | 0 value | 0x07BC32 | `can_rx_0A9_alive` | 4-bit alive counter: 15 or unchanged → frame dropped, error counter +1 (sat 3); else step (mod 15, max 3) saved; counter 0x4046C8 b3:2 |
| 118 | 2.0 | 12 | Intel · signed | 0x0B6 | 0 value | 0x07BCDC | `can_rx_0A9_torque_set` | 12-bit signed, **negated**, ×5 → **0x401148** (engine drag / minimum torque, MSR reference). 0x800 invalid → 0x401150/53 b1 + timer 0x4046F0 (→ 5E1B) |
| 119 | 3.4 | 12 | Intel · signed | 0x0B5 | 0 value | 0x07BD3C | (stub) | bare return: signal discarded |
| 120 | 5.0 | 12 | Intel · signed | 0x0B7 | 0 value | 0x07BD3E | (stub) | bare return: signal discarded |
| 121 | 6.4 | 12 | Intel · signed | 0x0B8 | 0 value | 0x07BD40 | (stub) | bare return: signal discarded |
| 122 | 1.6 | 2 | Intel | 0x09F | 0 value | 0x07BD42 | (stub) | bare return: signal discarded |
| 123 | — | — | Intel | 0x009 | 4 timeout | 0x07CF3E | `can_rx_0A9_timeout` | after 500 ms: **D355** (0x2005 checksum / 0x2004 alive / 0x2003 timeout); group fault 0xA0008 as 0x0A8 |

#### PT-CAN 0x0AA  DLC 8 · mailbox 7 · timeout 50 × 10 ms

DME torque 3 (D356). Driver-demand torque, pedal, rpm

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 124 | — | — | Intel | 0x0D1 | 2 payload | 0x07D562 | `can_rx_0AA_checksum` | checksum: byte = low8(Σ payload + id) as `can_tx_checksum8` (byte zeroed first). Mismatch → frame dropped (0x401174[i] b7 cleared), error counter +1 (sat 3), signals marked invalid; counter 0x4046C9 b5:4 |
| 125 | 1.0 | 4 | Intel | 0x07F | 0 value | 0x07BD44 | `can_rx_0AA_alive` | 4-bit alive counter: 15 or unchanged → frame dropped, error counter +1 (sat 3); else step (mod 15, max 3) saved; counter 0x4046C9 b7:6 |
| 126 | 1.4 | 12 | Intel · signed | 0x0B9 | 0 value | 0x07BE3C | `can_rx_0AA_torque_set` | 12-bit signed ×5 → **0x401144** (driver-demand torque). 0x800 invalid → 0x401150/53 b3 + timer 0x4046EE (→ 5E1B) |
| 127 | 3.0 | 8 | Intel | 0x082 | 0 value | 0x07BE90 | `can_rx_0AA_pedal_u8` | u8 → **0x401142** (accelerator pedal); 0xFF invalid → 0x401150/53 b5:4 + timer 0x4046EA (on expiry 0x7CC58 → **5E1A**, fault 0xA0020) |
| 128 | 6.0 | 2 | Intel | 0x093 | 0 value | 0x07BEEA | `can_rx_0AA_rpm_error` | 0x4046D8 b4 = (value ≠ 0); when set, the rpm signal is treated as invalid |
| 129 | 4.0 | 16 | Intel | 0x092 | 0 value | 0x07BEFC | `can_rx_0AA_rpm` | u16 >> 1 → **0x40113E** (engine speed; raw/2, BMW raw is 0.25 rpm so 0.5 rpm/bit, not confirmed). 0xFFFF or 0x4046D8 b4 → invalid (0x401150/53 b7:6, timer 0x4046ED → 0x7CCAE → **5E1A**). Also builds a low-passed rpm gradient **0x40113C** and keeps the previous value in 0x401168 |
| 130 | 6.4 | 4 | Intel | 0x098 | 0 value | 0x07BFD8 | `can_rx_0AA_nibble` | 4-bit value → u32 0x40470C (15 → stored as 8) |
| 131 | 6.2 | 2 | Intel | 0x09D | 0 value | 0x07BFF6 | (stub) | bare return: signal discarded |
| 132 | — | — | Intel | 0x00A | 4 timeout | 0x07CF94 | `can_rx_0AA_timeout` | after 500 ms: **D356** (0x2008 / 0x2007 / 0x2006); group fault 0xA0008 as 0x0A8 |

#### PT-CAN 0x0AC  DLC 8 · mailbox 8 · timeout 10 × 10 ms

**dead**: every handler is a bare return

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 133 | — | — | Intel | 0x0D3 | 2 payload | 0x07F9C2 | (stub) | bare return: signal discarded |
| 134 | 1.0 | 4 | Intel | 0x081 | 0 value | 0x07F9C4 | (stub) | bare return: signal discarded |
| 135 | 4.0 | 16 | Intel | 0x0C7 | 0 value | 0x07F9C6 | (stub) | bare return: signal discarded |
| 136 | 6.0 | 16 | Intel | 0x0C6 | 0 value | 0x07F9C8 | (stub) | bare return: signal discarded |
| 137 | — | — | Intel | 0x004 | 4 timeout | 0x07F9CC | (stub) | bare return: signal discarded |

#### PT-CAN 0x0B4  DLC 8 · mailbox 9 · timeout 10 × 10 ms

**dead**

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 138 | — | — | Intel | 0x0D2 | 2 payload | 0x07F9B4 | (stub) | bare return: signal discarded |
| 139 | 1.0 | 4 | Intel | 0x080 | 0 value | 0x07F9B6 | (stub) | bare return: signal discarded |
| 140 | 1.4 | 12 | Intel | 0x083 | 0 value | 0x07F9B8 | (stub) | bare return: signal discarded |
| 141 | 3.0 | 16 | Intel | 0x0C5 | 0 value | 0x07F9BA | (stub) | bare return: signal discarded |
| 142 | 5.0 | 12 | Intel | 0x084 | 0 value | 0x07F9BC | (stub) | bare return: signal discarded |
| 143 | 7.0 | 3 | Intel | 0x0AA | 0 value | 0x07F9BE | (stub) | bare return: signal discarded |
| 144 | 7.3 | 5 | Intel | 0x0A1 | 0 value | 0x07F9C0 | (stub) | bare return: signal discarded |
| 145 | — | — | Intel | 0x003 | 4 timeout | 0x07F9CA | (stub) | bare return: signal discarded |

#### PT-CAN 0x0BA  DLC 8 · mailbox 10 · timeout 50 × 10 ms

gearbox data (D357). Processed only when the gearbox is coded automatic/DCT (0x40114D ≠ 0)

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 146 | — | — | Intel | 0x0C9 | 2 payload | 0x07D4A6 | `can_rx_0BA_checksum` | checksum in byte 5 (same scheme). Only when 0x40114D ≠ 0 (automatic/DCT coded) and 0x401151 b7 clear |
| 147 | 6.0 | 4 | Intel | 0x079 | 0 value | 0x07BFF8 | `can_rx_0BA_alive` | 4-bit alive counter: 15 or unchanged → frame dropped, error counter +1 (sat 3); else step (mod 15, max 3) saved |
| 148 | 0.4 | 2 | Intel | 0x09C | 0 value | 0x07C08A | `can_rx_0BA_flag` | value < 2 → 0x4010FA b7; else invalid (0x4010FB/FC b5). Gated like the gear |
| 149 | 0.0 | 4 | Intel | 0x09B | 0 value | 0x07C0CC | `can_rx_0BA_gear` | gear nibble via jump table 0x7C13C: 1 → 0 (N), 2 → 8 (R), 3 → 11 (P), 5..11 → 1..7, others → 0xFF invalid. Debounced (two equal frames) into **0x4010F7** (current gear), raw in 0x4010F6. Gated: only when 0x40114D ≠ 0 (gearbox coded automatic/DCT) |
| 150 | 0.6 | 2 | Intel | 0x097 | 0 value | 0x07C220 | (stub) | bare return: signal discarded |
| 151 | 1.0 | 12 | Intel | 0x086 | 0 value | 0x07C222 | (stub) | bare return: signal discarded |
| 152 | 3.0 | 16 | Intel | 0x094 | 0 value | 0x07C224 | (stub) | bare return: signal discarded |
| 153 | 7.6 | 2 | Intel | 0x0AD | 0 value | 0x07C226 | `can_rx_0BA_flag2` | value < 2 → 0x4046D9 b2; else 0x4046D9 b1 (invalid) |
| 154 | — | — | Intel | 0x001 | 4 timeout | 0x07CDD8 | `can_rx_0BA_timeout` | after 500 ms: **D357** (0x200B / 0x200A / 0x2009) |

#### PT-CAN 0x0D5  DLC 6 · mailbox 11 · timeout 10 × 10 ms

**dead** (LDM wheel-torque request; D35B text exists but cannot be raised)

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 155 | — | — | Intel | 0x0CC | 2 payload | 0x07CBD4 | (stub) | bare return: signal discarded |
| 156 | 1.0 | 4 | Intel | 0x07B | 0 value | 0x07CBD6 | (stub) | bare return: signal discarded |
| 157 | 1.4 | 12 | Intel | 0x0C2 | 0 value | 0x07CBD8 | (stub) | bare return: signal discarded |
| 158 | 3.0 | 16 | Intel | 0x0C3 | 0 value | 0x07CBDA | (stub) | bare return: signal discarded |
| 159 | 5.0 | 2 | Intel | 0x0C4 | 0 value | 0x07CBDC | (stub) | bare return: signal discarded |
| 160 | — | — | Intel | 0x000 | 4 timeout | 0x07CFF8 | (stub) | bare return: signal discarded |

#### PT-CAN 0x130  DLC 5 · mailbox 12 · timeout 50 × 10 ms

terminal status (D35A). Also relayed onward

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 161 | — | — | Intel | 0x0D5 | 2 payload | 0x07C24C | `can_rx_130_gateway` | copies the 8 payload bytes and passes them to 0x7A3A8 (re-sent; F-CAN TX 0x130 exists) |
| 162 | — | — | Intel | 0x0CB | 2 payload | 0x07D404 | `can_rx_130_checksum` | checksum compared with byte 4 high nibble (0x7D24C mode 4 over all received bytes, with byte 4 high nibble zeroed and the alive nibble kept in the sum). Mismatch → frame dropped, counter 0x4046CA b5:4, 0x4046D4 b2/b0 (terminals invalid) |
| 163 | 4.0 | 4 | Intel | 0x07A | 0 value | 0x07C282 | `can_rx_130_alive` | 4-bit alive counter: 15 or unchanged → frame dropped, error counter +1 (sat 3); else step (mod 15, max 3) saved |
| 164 | 0.0 | 2 | Intel | 0x0A2 | 0 value | 0x07C2F6 | `can_rx_130_kl_a` | 2-bit: 1 → 0x4046D4 b1 = 1, 0 → 0; 2/3 → 0x4046D4 b0 (invalid). Used by 0x19E byte 5 (BLS state valid only when this = 1). Probably terminal R (inferred) |
| 165 | 0.2 | 2 | Intel | 0x0A3 | 0 value | 0x07C328 | `can_rx_130_kl_b` | 2-bit: 1 → 0x4046D4 b3, 2/3 → b2 invalid. Then **0x401130** = 4 if this is on, 3 if sig 164 is on, else 0; 0x401134 b7 = invalid. Probably terminal 15 (inferred) |
| 166 | 0.4 | 2 | Intel | 0x0A4 | 0 value | 0x07C38E | `can_rx_130_kl_c` | 2-bit: 1 → 0x40114F b2; ≥ 2 → invalid (0x401152/55 b3). Probably terminal 50 / crank (inferred) |
| 167 | — | — | Intel | 0x002 | 4 timeout | 0x07CE44 | `can_rx_130_timeout` | after 500 ms: **D35A** (0x2010 checksum / 0x200F alive / 0x200E timeout); terminal state invalid |

#### PT-CAN 0x1A3  DLC 2 · mailbox 13 · timeout 10 × 10 ms

ACC (D35D text). Signal is a stub; only the timeout sets a flag

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 168 | 0.0 | 12 | Intel | 0x096 | 0 value | 0x07C99A | (stub) | bare return: signal discarded |
| 169 | — | — | Intel | 0x005 | 4 timeout | 0x07CFFC | `can_rx_1A3_timeout` | after 100 ms: sets 0x4046D8 b3 only. The signal itself is a stub (ACC not used) |

#### PT-CAN 0x1B4  DLC 8 · mailbox 14 · timeout 30 × 10 ms

**dead**

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 170 | — | — | Intel | 0x0CA | 2 payload | 0x07F9A6 | (stub) | bare return: signal discarded |
| 171 | 3.0 | 4 | Intel | 0x077 | 0 value | 0x07F9A8 | (stub) | bare return: signal discarded |
| 172 | 0.0 | 12 | Intel | 0x0C0 | 0 value | 0x07F9AA | (stub) | bare return: signal discarded |
| 173 | 1.4 | 2 | Intel | 0x0B2 | 0 value | 0x07F9AC | (stub) | bare return: signal discarded |
| 174 | 2.0 | 2 | Intel | 0x091 | 0 value | 0x07F9AE | (stub) | bare return: signal discarded |
| 175 | 2.2 | 3 | Intel | 0x0A0 | 0 value | 0x07F9B0 | (stub) | bare return: signal discarded |
| 176 | 6.0 | 7 | Intel | 0x09E | 0 value | 0x07F9B2 | (stub) | bare return: signal discarded |
| 177 | — | — | Intel | 0x006 | 4 timeout | 0x07F9CE | (stub) | bare return: signal discarded |

#### PT-CAN 0x226  DLC 5 · mailbox 15

not identified. Software timeout 0x4046F8 = 4000 (handler 0x7D116 sets invalid flags only)

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 178 | 3.0 | 4 | Intel | 0x0C1 | 0 value | 0x07C904 | `can_rx_226_nibble` | 4-bit → 0x404709 (15 = invalid → 0x4046D8 b7). Reloads the software timeout 0x4046F8 = 4000 |
| 179 | 1.0 | 16 | Intel | 0x087 | 0 value | 0x07C932 | `can_rx_226_state` | u16 combined with 0x404709 into 0x401111 b7:5: 0 if either is 0, 2 if 0x404709 < 5, else 3; b1 = invalid |
| 180 | 0.0 | 8 | Intel | 0x088 | 0 value | 0x07C974 | `can_rx_226_byte0` | u8 → u32 0x404714; 0xFF → invalid (0x404718 b5) |

#### PT-CAN 0x2A6  DLC 2 · mailbox 16

**dead** on PT-CAN (the DSC sends its own 0x2A6 via the F→PT gateway)

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 181 | 0.0 | 8 | Intel | 0x08E | 0 value | 0x07C996 | (stub) | bare return: signal discarded |
| 182 | 1.0 | 3 | Intel | 0x08D | 0 value | 0x07C998 | (stub) | bare return: signal discarded |

#### PT-CAN 0x2E4  DLC 2 · mailbox 17

trailer status (D377 text)

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 183 | 0.0 | 2 | Intel | 0x0B1 | 0 value | 0x07C85A | `can_rx_2E4_trailer` | 2-bit trailer status (D377 text: "Status_Anhaenger"): 3 = invalid (0x401116/18 b7); else 0x401115 b7 = bit 0. Reloads software timeout 0x4046F4 = 2500; on expiry 0x7D0D4 only sets the invalid flags (no fault call found) |

#### PT-CAN 0x308  DLC 3 · mailbox 18 · timeout 250 × 10 ms

MSA / auto start-stop status (D379). Most fields stored only when MSA is coded

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 184 | — | — | Intel | 0x0CE | 2 payload | 0x07D2B4 | `can_rx_308_checksum` | 4-bit checksum in byte 0 low nibble. Status MSA (D379) |
| 185 | 0.4 | 4 | Intel | 0x078 | 0 value | 0x07C99C | `can_rx_308_alive` | 4-bit alive counter: 15 or unchanged → frame dropped, error counter +1 (sat 3); else step (mod 15, max 3) saved |
| 186 | 1.0 | 2 | Intel | 0x0A7 | 0 value | 0x07CB26 | `can_rx_308_s1_0` | 2-bit; stored only if 0xCFD8C ≠ 0 (coding flag word 0x4031F6 bit 7, likely MSA coded): 1/2 → u32 0x404744; else invalid (0x404748 b5) |
| 187 | 1.2 | 2 | Intel | 0x0A8 | 0 value | 0x07CAD6 | `can_rx_308_s1_2` | 2-bit, MSA-gated: 0..2 → 0x40473C; 3 invalid |
| 188 | 1.4 | 2 | Intel | 0x095 | 0 value | 0x07CAAC | `can_rx_308_s1_4` | 2-bit, MSA-gated: 1/2 → 0x404734; else invalid |
| 189 | 1.6 | 2 | Intel | 0x085 | 0 value | 0x07CA7E | `can_rx_308_s1_6` | 2-bit, MSA-gated: 0..2 → 0x40472C; 3 invalid |
| 190 | 2.0 | 2 | Intel | 0x0AB | 0 value | 0x07CA5A | `can_rx_308_s2_0` | 2-bit: 1 → 0x404724 = 0, 2 → 1; else invalid (0x404728 b5) |
| 191 | 2.2 | 2 | Intel | 0x0AE | 0 value | 0x07CB50 | `can_rx_308_s2_2` | 2-bit, MSA-gated: 0..2 → 0x40474C; 3 invalid |
| 192 | 2.4 | 4 | Intel | 0x0A9 | 0 value | 0x07CB7E | `can_rx_308_s2_4` | 4-bit, MSA-gated: → 0x404754; 15 invalid |
| 193 | — | — | Intel | 0x007 | 4 timeout | 0x07D006 | `can_rx_308_timeout` | after 2.5 s: **D379** (0x2033 timeout / 0x2034 / 0x2035) plus resets of the MSA records; large handler, not fully traced |

#### PT-CAN 0x310  DLC 7 · mailbox 19

outside temperature + relative time (D358)

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 194 | 0.0 | 8 | Intel | 0x0B3 | 0 value | 0x07C824 | `can_rx_310_outside_temp` | u8 → **0x4046E0** (outside temperature, raw); 0xFF invalid (0x4046D8 b1, 0x401137 b6) |
| 195 | — | — | Intel | 0x0D9 | 2 payload | 0x07C7C8 | `can_rx_310_rel_time` | bytes 1–4 → u32 **0x401128** (relative time); all 0xFF invalid (0x40112C b7). Reloads software timeout 0x4046F2 = 500; on expiry 0x7D09C raises **D358** (0x200C) |

#### PT-CAN 0x316  DLC 2 · mailbox 20

2-bit status; not identified

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 196 | 0.0 | 2 | Intel | 0x08A | 0 value | 0x07C75E | `can_rx_316_state` | 2-bit → 0x401108 b7:5: 0 → 000, 1 → 001, else 011 + b1 invalid (same encoding as 0x3B0) |

#### PT-CAN 0x319  DLC 2 · mailbox 21

2-bit status; not identified

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 197 | 0.0 | 2 | Intel | 0x08B | 0 value | 0x07C79A | `can_rx_319_state` | 2-bit → 0x404830 b7:6, also passed through the 0x398 handler |

#### PT-CAN 0x330  DLC 8 · mailbox 22

odometer (D359)

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 198 | — | — | Intel | 0x0D6 | 2 payload | 0x07C89A | `can_rx_330_mileage` | bytes 0–2 (24-bit) → **0x4046DC** (odometer); 0xFFFFFF invalid (0x4046D4 b7, 0x401137 b7). Reloads software timeout 0x4046F6 = 5000; on expiry 0x7D0E6 raises **D359** (0x200D) |

#### PT-CAN 0x380  DLC 7 · mailbox 23

VIN (D361, 5E1F, 5E1D)

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 199 | — | — | Intel | 0x0D8 | 2 payload | 0x07C636 | `can_rx_380_vin` | 7 VIN bytes: all 0xFF → invalid (0x4046D6 b3, 0x4046D7 b7). Else compared with the stored copy 0x4047FD[7] (mismatch → 0x4046D5 b0) and copied to 0x4047F6[7]. VIN DTCs D361 / 5E1F / 5E1D |

#### PT-CAN 0x388  DLC 7 · mailbox 24

**dead**

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 200 | 0.0 | 8 | Intel | 0x0BF | 0 value | 0x07C7B8 | (stub) | bare return: signal discarded |
| 201 | 1.0 | 8 | Intel | 0x0BA | 0 value | 0x07C7BA | (stub) | bare return: signal discarded |
| 202 | 2.0 | 4 | Intel | 0x08F | 0 value | 0x07C7BC | (stub) | bare return: signal discarded |
| 203 | 2.4 | 4 | Intel | 0x090 | 0 value | 0x07C7BE | (stub) | bare return: signal discarded |
| 204 | 3.0 | 4 | Intel | 0x0BD | 0 value | 0x07C7C0 | (stub) | bare return: signal discarded |
| 205 | 4.0 | 4 | Intel | 0x0BE | 0 value | 0x07C7C2 | (stub) | bare return: signal discarded |
| 206 | 5.0 | 8 | Intel | 0x0BC | 0 value | 0x07C7C4 | (stub) | bare return: signal discarded |
| 207 | 6.0 | 8 | Intel | 0x0BB | 0 value | 0x07C7C6 | (stub) | bare return: signal discarded |

#### PT-CAN 0x398  DLC 2 · mailbox 25

DSC driver-mode request (on / off / MDM). No checksum, alive or timeout. See FACTS "DSC driver mode"

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 208 | 0.4 | 2 | Intel | 0x08C | 0 value | 0x07C450 | `can_rx_398_s0_4` | 2-bit request for driver-mode slot 1 (meaning not identified): 1 → 0x401139 b3:2 = 2 and 0x40113B b3:2 = 1 (received), so `can_mode_request_apply` 0x8D70A requests slot-1 state 10; other non-zero values → invalid (0x40113A b5); 0 → no request. Also edge logic on 0x40482E |
| 209 | 1.2 | 3 | Intel | 0x089 | 0 value | 0x07C3DC | `can_rx_398_dsc_mode` | **DSC driver-mode request.** 0 → x = 1, 1 → x = 0, 4 → x = 2, written to 0x401139 b7:6 and b5:4; other values → invalid (0x40113A b6). Sets 0x40113B b5:4 = 1 (received; cleared every 10 ms by 0x78CE2). `can_mode_request_apply` 0x8D70A turns x into `driver_mode_state` 0x4049B4[0]: **sig 0 → mode 1 (DSC on), 1 → mode 0 (DSC off), 4 → mode 4 (MDM)**. Same validity check as the button (0x8D570) |

#### PT-CAN 0x399  DLC 5 · mailbox 26

second driver-mode request path (has checksum + alive; needs terminal 15). Not fully traced

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 210 | — | — | Intel | 0x0CD | 2 payload | 0x07D3BE | `can_rx_399_checksum` | 4-bit checksum (byte 0 low nibble) |
| 211 | 0.4 | 4 | Intel | 0x07C | 0 value | 0x07C4E6 | `can_rx_399_alive` | 4-bit alive counter: 15 or unchanged → frame dropped, error counter +1 (sat 3); else step (mod 15, max 3) saved |
| 212 | 1.0 | 2 | Intel | 0x0A5 | 0 value | 0x07C51E | `can_rx_399_s1_0` | 2-bit → 0x40483B |
| 213 | 1.2 | 3 | Intel | 0x0A6 | 0 value | 0x07C524 | `can_rx_399_s1_2` | 3-bit; only when 0x130 reports terminal 15 (0x4046D4 & 0x0C = 8). Combined with 0x40483B and the toggle state 0x4046BC, it writes the same driver-mode request bytes 0x401139–0x40113B as 0x398. Toggle logic not fully traced |

#### PT-CAN 0x3B0  DLC 2 · mailbox 27

reverse gear (D378). Processed only when the gearbox is coded manual (0x40114D = 0)

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 214 | 0.0 | 2 | Intel | 0x09A | 0 value | 0x07C712 | `can_rx_3B0_reverse_gear` | reverse gear (D378: "Status_Gang_Rueckwaerts"): 1 → 0x401112 b7:5 = 0 (not engaged), 2 → 1 (engaged), 0/3 → 3 + b1 (invalid). Only when 0x40114D = 0 (manual gearbox coded); reloads timeout 0x4046FA = 500 → **D378** (0x2021) via 0x7D130 |

#### PT-CAN 0x797  DLC 1 · mailbox 28

special / manufacturing frame, DLC 1

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 215 | — | — | Intel | 0x0C8 | 2 payload | 0x07AB08 | `can_rx_797_payload` | DLC 1. 0x401164 = 0xFFFF; if 0xAF78C(1,0,0) = 4 → 0x7A686(payload). Not traced further |

#### PT-CAN 0x480  DLC 1 · mailbox 29 · id mask 0x780

network management

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 216 | — | — | Intel | 0x0D7 | 2 payload | 0x07CBE4 | `can_rx_480_nm` | OSEK NM (id 0x480 + node, mask 0x780). Ignores its own 0x4A9; stores the sender node in 0x404841 and runs 0x7FB8A |

#### PT-CAN 0x580  DLC 1 · mailbox 30 · id mask 0x780

network management / node frames

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 217 | — | — | Intel | 0x0DA | 2 payload | 0x07E4D6 | `can_rx_580_nm` | NM / node messages 0x580–0x5FF (mask 0x780); large handler 0x7E4D6, not traced |

#### PT-CAN 0x6F1  DLC 1 · mailbox 31 · id mask 0x7F0

diagnostic tester

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 218 | — | — | Intel | 0x0D4 | 2 payload | 0x07CC02 | `can_rx_6F1_tester_cb` | diagnostic tester requests 0x6F0–0x6FF (mask 0x7F0) → KWP/UDS dispatcher. See SERVICE_ROUTINES / symbols |


## F-CAN RX (18 frames)

#### F-CAN 0x0CD  DLC 8 · mailbox 14 · timeout 10 × 10 ms

sensor cluster 1 (D370): yaw + lateral accel

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 22 | — | — | Intel | 0x02D | 2 payload | 0x0C5948 | `fcan_rx_cluster_checksum` | checksum in byte 7 (0xC72B8). Mismatch → frame invalid (0x402EE5[i] b7), per-frame error counter in 0x402F39/0x402F3A, sat 3. Shared by 0x0CD / 0x0D1 / 0x0D4 |
| 23 | 6.4 | 4 | Intel | 0x02C | 0 value | 0x0C59FE | `fcan_rx_0CD_alive` | 4-bit alive; unchanged → invalid + counter 0x402F39 b5:4. Ignored during start-up (0x400966 b6). Last value 0x402F28 |
| 24 | 6.2 | 2 | Intel | 0x02B | 0 value | 0x0C5A5E | `fcan_rx_0CD_q1` | 2-bit → 0x402E4E b5:4 (qualifier) |
| 25 | 6.0 | 2 | Intel | 0x02A | 0 value | 0x0C5A4C | `fcan_rx_0CD_q0` | 2-bit → 0x402E4E b7:6 (qualifier) |
| 26 | 0.0 | 16 | Intel | 0x027 | 1 RAM store | → 0x402F1C | (direct) | u16 → **0x402F1C** = `cluster_sensor_get(0)` = **yaw rate** (raw, read by `csi_cond_sensor0` 0x905E4) |
| 27 | 2.0 | 16 | Intel | 0x028 | 1 RAM store | → 0x402F20 | (direct) | u16 → 0x402F20 = `cluster_sensor_get(1)`; only the cluster monitor 0xC6354 reads it (redundant channel, inferred) |
| 28 | 4.0 | 16 | Intel | 0x029 | 1 RAM store | → 0x402F24 | (direct) | u16 → **0x402F24** = `cluster_sensor_get(2)` = **lateral accel** (raw, read by `csi_cond_sensor2` 0x8FE70) |
| 29 | — | — | Intel | 0x000 | 4 timeout | 0x0C6D8E | `fcan_rx_0CD_timeout` | after 100 ms: **D370** via 0xBFA2A(reason, 0xA1000): 4 checksum → 0x3002, 2 alive → 0x3001, 1 timeout → 0x3000 |

#### F-CAN 0x0D1  DLC 8 · mailbox 15 · timeout 10 × 10 ms

sensor cluster 2 (D371): longitudinal accel

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 30 | — | — | Intel | 0x02D | 2 payload | 0x0C5948 | `fcan_rx_cluster_checksum` | as sig 22 |
| 31 | 6.4 | 4 | Intel | 0x033 | 0 value | 0x0C5A72 | `fcan_rx_0D1_alive` | 4-bit alive, counter 0x402F39 b1:0; last 0x402F29 |
| 32 | 6.2 | 2 | Intel | 0x031 | 0 value | 0x0C5AD0 | `fcan_rx_0D1_q1` | 2-bit → 0x402E4E b1:0 |
| 33 | 6.0 | 2 | Intel | 0x032 | 0 value | 0x0C5ABC | `fcan_rx_0D1_q0` | 2-bit → 0x402E4E b3:2 |
| 34 | 0.0 | 16 | Intel | 0x02E | 1 RAM store | → 0x402F1E | (direct) | u16 → 0x402F1E = `cluster_sensor_get(3)`; only the cluster monitor reads it |
| 35 | 2.0 | 16 | Intel | 0x02F | 1 RAM store | → 0x402F22 | (direct) | u16 → 0x402F22 = `cluster_sensor_get(4)`; only the cluster monitor reads it |
| 36 | 4.0 | 16 | Intel | 0x030 | 1 RAM store | → 0x402F26 | (direct) | u16 → **0x402F26** = `cluster_sensor_get(5)` = **longitudinal accel** (→ 0x404A00 → 0x4049FC, FACTS) |
| 37 | — | — | Intel | 0x001 | 4 timeout | 0x0C6DBA | `fcan_rx_0D1_timeout` | after 100 ms: **D371** (0x3005 / 0x3004 / 0x3003) |

#### F-CAN 0x0C9  DLC 8 · mailbox 16 · timeout 10 × 10 ms

steering angle sensor (D373)

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 38 | 2.4 | 4 | Intel | 0x024 | 0 value | 0x0C5B9C | `fcan_rx_0C9_alive` | 4-bit alive (15 invalid) with error counter; status into 0x402E6D / 0x40164E |
| 39 | 5.0 | 2 | Intel | 0x023 | 0 value | 0x0C5E4A | `fcan_rx_0C9_q5` | 2-bit → 0x402F36 b5:4 |
| 40 | 5.4 | 4 | Intel | 0x025 | 0 value | 0x0C5E74 | `fcan_rx_0C9_mux` | 4-bit multiplexer index → 0x402F3D; selects how sig 41 is read |
| 41 | 6.0 | 16 | Intel | 0x026 | 0 value | 0x0C5E7A | `fcan_rx_0C9_mux_data` | 16-bit multiplexed payload; 13-way jump table 0xC5EC8 on the mux index. Includes the steering-sensor error codes that map to DTCs 94B0–94C9; not traced further |
| 42 | 3.0 | 16 | Intel | 0x022 | 0 value | 0x0C5C18 | `fcan_rx_0C9_angle_rate` | 16-bit: bits 13..0 sign-folded and scaled → u32 **0x402E70** (steering angle rate, inferred); bits 15:14 → 0x402F54 b4:3 (status) |
| 43 | 0.0 | 16 | Intel | 0x020 | 0 value | 0x0C5C78 | `canrx_steer_angle_0C9` | 16-bit steering angle, valid window, ·1029/1024 → **0x401644** (relayed on PT-CAN TX 0x0C4). Status 0x40164D / 0x40164E |
| 44 | 2.0 | 2 | Intel | 0x021 | 0 value | 0x0C5E20 | `fcan_rx_0C9_angle_status` | 2-bit: 0/1 mapped through table 0xF58C0, ≥ 2 → 3; → 0x40164D b7:6 (angle status read by `steering_angle_init_monitor`) |
| 45 | 2.2 | 2 | Intel | 0x050 | 0 value | 0x0C62EC | `fcan_rx_0C9_q2` | 2-bit → 0x402F53 b3:2 |
| 46 | — | — | Intel | 0x002 | 4 timeout | 0x0C6E18 | `fcan_rx_0C9_timeout` | after 100 ms: **D373** ("SWA-Top-Sensor 200 or 201"; 0x300B / 0x300A / 0x3009), only while 0x402F35 b4. Carries fault **0xA0040** (group A b6, via 0xB484A); sets 0x402E6D b7/b5. While the frame stays missing, `sensor_reaction_build` sets 0x402888 b0/b2/b3: **steering, lateral and yaw invalid** for ABS, AYC and all TCS channels inhibited (FACTS "Steering-sensor loss") |

#### F-CAN 0x118  DLC 8 · mailbox 17 · timeout 10 × 10 ms

**dead** (AFS)

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 47 | — | — | Intel | 0x04C | 2 payload | 0x0C5B76 | (stub) | AFS 0x118: all handlers are bare returns, so D375 is never raised |
| 48 | 2.4 | 4 | Intel | 0x04D | 0 value | 0x0C5B78 | (stub) | bare return: signal discarded |
| 49 | 0.0 | 16 | Intel | 0x01D | 0 value | 0x0C5B7A | (stub) | bare return: signal discarded |
| 50 | 3.0 | 16 | Intel | 0x01E | 0 value | 0x0C5B7C | (stub) | bare return: signal discarded |
| 51 | 2.0 | 2 | Intel | 0x01F | 0 value | 0x0C5B7E | (stub) | bare return: signal discarded |
| 52 | 5.0 | 16 | Intel | 0x04B | 0 value | 0x0C5B80 | (stub) | bare return: signal discarded |
| 53 | — | — | Intel | 0x003 | 4 timeout | 0x0C6EB2 | (stub) | bare return: signal discarded |

#### F-CAN 0x0D4  DLC 8 · mailbox 18 · timeout 10 × 10 ms

sensor cluster 3 (D372): status + identity

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 54 | — | — | Intel | 0x02D | 2 payload | 0x0C5948 | `fcan_rx_cluster_checksum` | as sig 22 |
| 55 | 6.4 | 4 | Intel | 0x03D | 0 value | 0x0C5AE2 | `fcan_rx_0D4_alive` | 4-bit alive, counter 0x402F3A; last 0x402F2A |
| 56 | 0.0 | 4 | Intel | 0x034 | 1 RAM store | → 0x402F2B | (direct) | 4-bit → 0x402F2B (read by 0xC5886) |
| 57 | 0.4 | 4 | Intel | 0x036 | 1 RAM store | → 0x402F2D | (direct) | 4-bit → 0x402F2D |
| 58 | 1.0 | 4 | Intel | 0x037 | 1 RAM store | → 0x402F2E | (direct) | 4-bit → 0x402F2E |
| 59 | 1.4 | 4 | Intel | 0x035 | 1 RAM store | → 0x402F2C | (direct) | 4-bit → 0x402F2C |
| 60 | 2.0 | 8 | Intel | 0x038 | 1 RAM store | → 0x402F30 | (direct) | u8 → 0x402F30 (cluster identity/serial check 0xC70A0, inferred) |
| 61 | 3.0 | 8 | Intel | 0x039 | 1 RAM store | → 0x402F32 | (direct) | u8 → 0x402F32 (same) |
| 62 | 4.0 | 8 | Intel | 0x03A | 1 RAM store | → 0x402F34 | (direct) | u8 → 0x402F34 (same) |
| 63 | 5.0 | 8 | Intel | 0x03B | 1 RAM store | → 0x400973 | (direct) | u8 → 0x400973 (same) |
| 64 | 6.0 | 4 | Intel | 0x03C | 0 value | 0x0C5B30 | `fcan_rx_0D4_status` | 4-bit cluster status → **0x402E50**: b7 = bit 0, b3 = bit 3, b2 = bit 1. 0x402E50 & 0x0C ≠ 0 makes yaw / lateral accel invalid (see 0x1A0 decode) |
| 65 | — | — | Intel | 0x004 | 4 timeout | 0x0C6DEC | `fcan_rx_0D4_timeout` | after 100 ms: **D372** (0x3008 / 0x3007 / 0x3006) |

#### F-CAN 0x140  DLC 2 · mailbox 19

cluster-related u16

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 66 | 0.0 | 16 | Intel | 0x043 | 0 value | 0x0C5B60 | `fcan_rx_140` | u16 → 0x402E52; sets 0x402EDE b4 and 0x402E51 b6. Read by the cluster identity check 0xC70A0 |

#### F-CAN 0x0C8  DLC 8 · mailbox 20 · gateway → PT-CAN 0x0C8

gatewayed to PT-CAN (one-shot)

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 67 | — | — | Intel | 0x045 | 2 payload | 0x0C5B82 | `fcan_rx_0C8_gateway` | when 0x402F49 b2 is set (one-shot): push to the F→PT gateway 0xC56D0 |

#### F-CAN 0x194  DLC 4 · mailbox 21 · gateway → PT-CAN 0x194 · timeout 60 × 10 ms

Cruise-control / ACC stalk frame (`STATUS_F_CAN_TEMPOMAT_ACC` in DSC_87.prg), from the SZL. The payload is only
gatewayed to PT-CAN; nothing is decoded. Its DTC **D364** "Operator_Key_Tempo" (ids 0x3046 timeout / 0x3047
checksum / 0x3048 alive, F-CAN mask 0x40040/0x40100/0x40080) has **no reporter**: the timeout handler is a bare
return, and none of the eight F-CAN report sites (all via 0xBFA2A) can produce group 4 bits 6–8 (re-checked
2026-10-15).

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 68 | — | — | Intel | 0x03E | 2 payload | 0x0C69EA | → `fcan_rx_queue_push` | `jmpi` to the F→PT gateway 0xC56D0 (queues the frame for PT-CAN). No checksum or alive check |
| 69 | 1.0 | 4 | Intel | 0x03F | 0 value | 0x0C69EC | (stub) | bare return: signal discarded |
| 70 | 2.0 | 8 | Intel | 0x040 | 0 value | 0x0C69EE | (stub) | bare return: signal discarded |
| 71 | 3.0 | 2 | Intel | 0x041 | 0 value | 0x0C69F0 | (stub) | bare return: signal discarded |
| 72 | 3.2 | 2 | Intel | 0x042 | 0 value | 0x0C69F2 | (stub) | bare return: signal discarded |
| 73 | — | — | Intel | 0x005 | 4 timeout | 0x0C69F4 | (stub) | bare return: a missing 0x194 is never reported (D364 unreachable) |

#### F-CAN 0x1D6  DLC 2 · mailbox 22 · gateway → PT-CAN 0x1D6

gatewayed to PT-CAN

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 74 | — | — | Intel | 0x044 | 2 payload | 0x0C56D0 | `fcan_rx_queue_push` | F-CAN → PT-CAN gateway (0xC56D0): queues the frame for `fcan_to_can_gateway_drain` 0x7A172 |

#### F-CAN 0x2A6  DLC 2 · mailbox 23 · gateway → PT-CAN 0x2A6

gatewayed to PT-CAN + byte-0 state machine

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 75 | — | — | Intel | 0x044 | 2 payload | 0x0C56D0 | `fcan_rx_queue_push` | gateway, as 0x1D6 |
| 76 | 0.0 | 8 | Intel | 0x04E | 0 value | 0x0C630A | `fcan_rx_2A6_byte0` | u8 with a large state machine (0xC630A, 3-bit field, faults incl. 0xB0400); not traced |

#### F-CAN 0x1D9  DLC 3 · mailbox 24 · gateway → PT-CAN 0x1D9

gatewayed to PT-CAN

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 77 | — | — | Intel | 0x044 | 2 payload | 0x0C56D0 | `fcan_rx_queue_push` | gateway, as 0x1D6 |

#### F-CAN 0x11F  DLC 8 · mailbox 25 · timeout 10 × 10 ms

**dead** (AFS)

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 78 | — | — | Intel | 0x04A | 2 payload | 0x0C6300 | (stub) | AFS 0x11F: all handlers are bare returns, so D376 is never raised |
| 79 | 1.0 | 4 | Intel | 0x049 | 0 value | 0x0C6302 | (stub) | bare return: signal discarded |
| 80 | 2.0 | 16 | Intel | 0x047 | 0 value | 0x0C6306 | (stub) | bare return: signal discarded |
| 81 | 4.0 | 16 | Intel | 0x046 | 0 value | 0x0C6304 | (stub) | bare return: signal discarded |
| 82 | 0.0 | 8 | Intel | 0x048 | 0 value | 0x0C6308 | (stub) | bare return: signal discarded |
| 83 | — | — | Intel | 0x006 | 4 timeout | 0x0C6EB6 | (stub) | bare return: signal discarded |

#### F-CAN 0x78F  DLC 8 · mailbox 26

external torque-limit exchange (gated off by cal 0x4182A = 0, FACTS)

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 84 | — | — | Intel | 0x04F | 2 payload | 0x0C6D78 | `fcan_rx_78x_7Dx_flag` | sets 0x408D2C[frame index − 26] = 1 ("received" flag). Same handler for 0x78F/0x78E/0x7DC–0x7DF |

#### F-CAN 0x78E  DLC 8 · mailbox 27

same as 0x78F

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 85 | — | — | Intel | 0x04F | 2 payload | 0x0C6D78 |  |  |

#### F-CAN 0x7DC  DLC 8 · mailbox 28

received flag only

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 86 | — | — | Intel | 0x04F | 2 payload | 0x0C6D78 |  |  |

#### F-CAN 0x7DD  DLC 8 · mailbox 29

received flag only

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 87 | — | — | Intel | 0x04F | 2 payload | 0x0C6D78 |  |  |

#### F-CAN 0x7DE  DLC 8 · mailbox 30

received flag only

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 88 | — | — | Intel | 0x04F | 2 payload | 0x0C6D78 |  |  |

#### F-CAN 0x7DF  DLC 8 · mailbox 31

received flag only

| sig | pos | len | pack | var | var type | handler | symbol | notes |
|---|---|---|---|---|---|---|---|---|
| 89 | — | — | Intel | 0x04F | 2 payload | 0x0C6D78 |  |  |

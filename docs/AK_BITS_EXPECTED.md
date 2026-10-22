# AK protocol bits the stock firmware expects (7846816A, M3)

What a VDA/AK sensor, or a converter that emulates one, has to send so the **stock** firmware raises no
direction or presence DTC. Derived from the disassembly. Function and RAM names are in
`analysis/7846816A_symbols.md`, section "Wheel direction".

## How the firmware sees AK frames

The wheel-speed interface chip decodes each AK frame. `wss_asic_spi_poll` 0x6FCC0 reads it over QSPI CS5 into
`wss_asic_reply` 0x400F1C. For each slot it gives two words:

- `data`: bit n = value of AK bit n.
- `qual`: bit n = AK bit n was received. Frames get clipped at speed, so a full 9-bit frame gives 0x1FF.

`wss_dir_protocol_update` 0x75C6C keeps only the low byte of each (`wss_dir_proto` 0x400A34), so parity
(bit 8) never reaches the firmware.

## What to send

| AK bit | Meaning | Send | What reads it |
|---|---|---|---|
| 0 | air-gap reserve error | 0 | air-gap stats only (`wss_ak_airgap_stats_update` 0x75B74); nothing reads the stats |
| 1 | amplitude-measurement validity | 0 | gates those stats only. The firmware treats 0 as valid |
| 2 | unused | 0 | accessor 0x75B10 has no callers |
| **3** | **direction valid (GDR)** | **1, always** | direction is used only if b3 was received and = 1 |
| **4** | **direction (DR)** | **constant "forward" for that wheel** (next table) | `wss_dir_raw_get` 0x75A94 → `wheel_direction_update` 0xB9330 |
| 5–7 | air-gap gauge | 0 (any value works) | stats only |
| 8 | parity | correct per the AK spec | not visible to the firmware. The interface chip may check it (unverified), so send it correctly |

### "Forward" per wheel

The firmware XORs DR with a per-wheel flip mask, then reads 1 as forward. Coding byte 10 bit 6 (flag word
0x4031F4 bit 8, read by 0xCFCAE) picks the mask from 0xD766C:

| Coding byte 10 bit 6 | Flipped wheels (mask) | DR to send FL / FR / RL / RR |
|---|---|---|
| 0 | FL, RL (0x05) | 0 / 1 / 0 / 1 |
| 1 | FL, RR (0x09) | 0 / 1 / 1 / 0 |

A wheel sent backwards reads as reversing: its 0x0CE speed goes negative below 70 km/h, and a stored reverse
above 120 km/h raises 5Dx6.

## Timing

1. **Send standstill frames when the car is powered up.** `wss_startup_presence_check` 0x75E38 needs at least
   one frame with ≥ 3 AK bits received (popcount of `qual` ≥ 3) before main cycle 100. That is about 1 s if a
   cycle is 10 ms; the cycle length is not confirmed. A wheel that misses the window gets **5Dx6**, and its
   sensor status byte 0x400952[w] is marked faulted (|= 0x31), so its speed reads 0x8000. This lasts at least
   until the next power-up. VR and plain Hall sensors give no edges on a stationary car, so a converter has to
   generate these frames itself.
2. **Between 4 and 55 km/h, frames must include bits 0–4.** `dir_missing_cnt[w]` 0x4029DB counts +1 for each
   cycle without direction and −1 for each cycle with it. At 175 → **5Dx6**. The odd lost frame is harmless.
   Above 55 km/h the direction bits are ignored, so clipping is fine. Simplest: always send all 9 bits.
3. **Never use GDR = 0 to mean "unknown".** That is the "no direction" case that counts toward 5Dx6.
4. **Never change DR.** A change between 25 and 55 km/h, once all wheels have reported, raises **5Dx6**.

## What a constant "forward" costs

When reversing, the DSC still thinks the car is moving forward:
- 0x0CE wheel speeds stay positive.
- The 0x1A0 drive-direction field says forward.
- ABS sees forward.

This raises no DTC. The flip check only fires when DR changes, and the 120 km/h check only fires on a stored
reverse.

## Out of scope

The other per-wheel DTCs depend on the speed pulses and current levels, not on the data bits:
- 5Dx0 electrical
- 5Dx1 extrapolation
- 5Dx2 tone-ring periodic
- 5Dx3 start-up speed comparison
- 5Dx4 long-term
- 5Dx5 double frequency

Here x = 9 / A / B / C for FL / FR / RL / RR. The mapping from fault id to DTC is in `analysis/7846816A_symbols.md`
(`dtc_table` 0xF367C).

## Unverified

- **Polarity of bit 1.** The firmware treats 0 as "amplitude valid". Either way it only affects the unused stats.
- **Parity.** Whether the interface chip rejects frames with bad parity.
- **Cycle length.** How long a main cycle is, and so the real start-up window.

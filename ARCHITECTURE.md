# MK60E5 (E82 1M, 7846411A) firmware architecture

A top-down map of the application image. Confidence follows FACTS.md: anything not stated there
as **[verified]** is an inference. Details: `analysis/agents/*/REPORT.md`,
`analysis/7846411A_symbols.md`, `analysis/7846411A_can_map.md`. CPU addresses (file offset =
CPU + 0x8000).

## Hardware view
```
                    +--------------------------------------------------+
  wheel sensors --> | sensor-interface ASIC  (VDA decode: dir, airgap) |--QSPI CS5--+
  (VDA, 7/14/28mA)  +--------------------------------------------------+            |
           speed pulses -> timer/capture D8 (w1,w2) + F8 (w0,w3) --IRQ 56-59        |
                                                                                    v
  PT-CAN <--> CAN module 0xDD0000 (32 mailboxes, IRQ 40) <--> M-CORE MCU (Freescale SC560002, custom)
  ext. EEPROM (2 KiB logical, coding/NVM) <--QSPI CS2-- QSPI 0xDB0000 ---+   INTC 0xE10000, VBR 0x40000
  mfg/test serial on the 0xD80000 module (regs +0x380/+0x110; vec44/52), GPIO 0xDE0000, ports 0xD5/0xF5  RAM 0x400000..
  valves / pump: probably driven through SPI output images (unconfirmed)
```

**Update 2026-10-06:** the sensor-interface ASIC also has a 2-level (7/14 mA) mode, selected per channel by ASIC register
0x28C (M3 init table, file 0xDF22C). With both-edge timer capture, E46-type sensors work. See
`docs/E46_SENSOR_FIRMWARE_PATCH.md`.

## Software layers
```
 +------------------------------------------------------------------------------------+
 | Control & monitoring (once per 10 ms frame, task T3 body 0x071040)                 |
 |  wheel speed 0x752B8 -> per-wheel pass 0x8EE30 -> control dispatcher 0x8CAD8      |
 |  (~620 fns: ABS/ASC/DSC logic; DDS/RPA spectral module ~0x96666-0xAE2A0)        |
 |  -> monitoring 0xB3DA8 (plausibility, wheel direction, fault manager 0xB4064)     |
 |  -> CAN stack 0x7944C -> diagnostics 0xAFEDC / ECU state 0x76092 -> NVM           |
 | Fast loops: T1 0x070C58 (4/frame, per-channel 0x850A2, outputs)                   |
 |             T2 0x070CB4 (10/frame, SPI job engine 0x74F42)                        |
 +------------------------------------------------------------------------------------+
 | Services: CAN signal tables (0xD82D5..), KWP2000 dispatcher (0xF33A8), NVM queue  |
 |  (0x6E21C), fault manager, interp/sat math helpers (0x6D17C.., 0x711FA)          |
 +------------------------------------------------------------------------------------+
 | Runtime wrapper 0x77C00-0x78B60: ROM object 0xD7F14 maps 5 objects -> OS tasks,   |
 |  runs-per-frame supervision (error 0xA010), T3 overrun check (error 0x10001)     |
 +------------------------------------------------------------------------------------+
 | OSEK-style OS 0x42000-0x44000: 5 tasks, events, dispatcher (IRQ 32), canaries     |
 | Time base: IRQ 60 0x70A86, 13-slot frame (inferred 10 ms), jump table 0x70B28     |
 +------------------------------------------------------------------------------------+
 | HW drivers 0xD4000-0xD7000: CAN, QSPI, timers D8/F8, serial, irq lock             |
 | Startup: reset 0x6C9B2 -> RAM clear, PLL, VBR, INTC, timers -> app_main -> OS     |
 +------------------------------------------------------------------------------------+
 | Bootloader (file 0x0-0x47FFF): NOT in the .0pa; signature check presumably there  |
 +------------------------------------------------------------------------------------+
```

## Frame schedule (13 slots)
| Slot | ISR work | Tasks |
|---|---|---|
| 0 | overrun check, wheel buffer swap, runtime supervision | T1, T2, T3 |
| 1, 2 | | T2 |
| 3 | | T1 |
| 4 | SPI command | – |
| 5 | 0x75690 | T2 |
| 6 | SPI read, CAN module service | T2 |
| 7 | SPI command | T1, T2 |
| 8, 9 | | T2 |
| 10 | | T1 |
| 11 | SetEvent(T0) | T2 |
| 12 | | T2 |

T0 does a once-per-frame port toggle (watchdog? unconfirmed). T4 is a background stack monitor.

## Image layout (CPU)
| Range | Content |
|---|---|
| 0x40000-0x401FF | vector table |
| 0x42000-0xD7000 | code (module map in analysis/agents/app/REPORT.md §4) |
| 0x41F04 | BFU wheel calibration block |
| 0xD7000-0xF678B | const data: OS objects, CAN config, calibration (0xDA2F0..), Q12 sin/cos tables (0xDB2D8..0xF29D8), maps (0xF3000..), KWP + NVM tables |
| file 0xFE68C | `BMY` block with 64-byte probable signature |

## Second CAN bus
F-CAN controller 0x00FA0000 (stack 0x0C4B4C, tables 0xF5CCB). It carries the DSC sensor cluster
(0x0CD/0x0D1/0x0D4) and steering angle (0x0C9). See FACTS.md.

## Out of scope
Brake actuation (valves/pump) and the internals/calibration of the stability-control blocks
(ABS/TCS/AYC/BCO/COA) are deliberately not documented here.

## Biggest unknowns
1. Bootloader behaviour: signature verification, and whether a programming path accepts modified images.
2. The exact MCU part's peripheral map (custom chip; everything above is inferred from code).

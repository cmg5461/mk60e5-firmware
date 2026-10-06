# MK60E5 (M3 7846816A): firmware changes to run E46 wheel-speed sensors

Status: **bench-verified 2026-10-06, not yet car-tested.** Applies to the E9x M3 DSC image **7846816A** (DSCM90).
File offsets are into the 1 MB bank-0 image `flash/bin/7846816A_00000000.bin`; **CPU address = file offset − 0x8000**.

## Summary

Four byte patches let a stock MK60E5 read **E46-type 2-level (7 / 14 mA) active wheel-speed sensors on all four
wheels**. No external hardware and no PCB changes are needed. They:
- switch the wheel-speed ASIC into 2-level sensor mode;
- capture both edges of each tooth, so a 48-tooth ring gives the native 96 pulses/rev;
- turn off the direction check, since E46 sensors carry no direction;
- relax the startup presence check.

On the bench, a real E46 sensor on each of FL, FR, RL and RR reads valid speed and returns to 0 at rest. No
plausibility, direction or extrapolation DTCs were set.

## Background: why a stock MK60E5 rejects E46 sensors

- The ECU's wheel-speed interface ASIC (TI **5895-5120**, custom, no public datasheet) is programmed by default for
  **VDA / AK-protocol** sensors. Those output 7 mA idle, a **28 mA speed pulse**, and Manchester data bits at
  7 / 14 mA.
- In that mode the ASIC only produces a speed edge when the loop current crosses the high level (about 20 mA). An E46
  sensor only switches 7 ↔ 14 mA, so it never produces an edge, and the wheel reads 0.
- The ASIC has a **per-channel sensor-mode mask** (register 0x28C). Clearing a channel's bit puts that channel in
  2-level mode, where the 14 mA level counts as an edge (patch 1).
- In 2-level mode each tooth gives one edge on the MCU's timer capture pin. Stock capture counts **one edge**, so a
  48-tooth ring would read 48 pulses/rev and **half speed**. Capturing **both edges** restores the 96 pulses/rev that
  the speed constant assumes (patch 2).
- E46 sensors carry no direction information or VDA data bits. The direction check and the VDA-data presence check
  must therefore be relaxed (patches 3 and 4).

## Required patches

| # | Purpose | File offset | CPU addr | Stock bytes | Patched bytes |
|---|---|---|---|---|---|
| 1 | ASIC sensor-mode mask: all 4 channels to 2-level | 0xDF22C | 0xD722C | `02 8C 00 0F` | `02 8C 00 00` |
| 2 | Timer capture on both edges, all 4 speed channels | 0x77524 | 0x6F524 | `61 1D` | `62 1D` |
| 3 | Direction-expected mask = 0 (no wheel) | 0xC13C4 | 0xB93C4 | `60 F2 7F B0` | `60 02 60 03` |
| 4 | Wheel-sensor presence mode 4 (VDA) → 2 | 0x7DA56 | 0x75A56 | `60 43` | `60 23` |
| — | Re-sign: MISR checksum + BMY RSA signature | 0xFE91C, 0xFE930 | — | — | `tools/bmy_resign.py fix` |

The only changed bytes are 0xDF22F, 0x77524, 0xC13C5–0xC13C7 and 0x7DA57, plus the MISR/BMY words written by the
re-sign. **Do not** include the bench-only 0x23 peek handler in a car image. That is file 0xE0F98–0xE1017 and the
service-table pointer at 0xFB1A0, both present in the `m3_probe_*` test images.

## Patch details

### 1. ASIC register 0x28C: sensor-mode mask (file 0xDF22C)

- At boot, the ASIC init loop (CPU 0x6F5EC–0x6F5FA) walks the 12-word global table at **CPU 0xD7210**. Each word is
  `(reg << 16) | value`, written via `asic_reg_xfer32` (0xD4A30).
- The word at 0xD722C is `0x028C000F`: register **0x28C = 0x00F**, which means all four channels are in VDA mode.
- **Bit n = channel n.** Bit 0 is FL; the other wheels' bits were not individually mapped, because the patch clears
  all four.
  - 0 = 2-level mode (14 mA counts as an edge).
  - 1 = VDA / AK mode (only about 28 mA counts).
- This table entry is the **only** writer of 0x28C. The literal 0x28C at CPU 0xBD4E8 is the number 652 in unrelated
  control logic. The value was verified to survive boot: register 0x28C reads 0x000 after reset.
- ASIC access, for reference: 10-bit register ID + 10-bit data over QSPI. The ID's low 3 bits are a command field:
  `100` = write (0x28C), `000` = read (0x288).

### 2. Capture both edges (file 0x77524)

The speed-capture channels are configured at CPU 0x6F524:

```
06F524  611D  movi  r13,17
06F526  347D  bseti r13,7          ; r13 = 0x91  (stock mode)
06F528  6002  movi  r2,0 ; 12D3 mov r3,r13 ; 7F9C jsri cfg(0, 0x91)
06F52E  6012  movi  r2,1 ; ...             ; cfg(1, 0x91)
06F534  6022  movi  r2,2 ; ...             ; cfg(2, 0x91)
06F53A  6032  movi  r2,3 ; ...             ; cfg(3, 0x91)
```

`cfg` is `sub_0D569C(ch, mode)`. Its mode bits program bits 12:11 of the timer channel control register
(0xF8008E, 0xD8008E, …):

| Mode bit | Bits 12:11 | Capture |
|---|---|---|
| 0x08 | 01 | single edge (bench: reads like stock; likely falling) |
| **0x10** | **00** | **single edge, stock (mode 0x91)** |
| **0x20** | **10** | **both edges (mode 0xA1)** |

Mode 0x80 enables the capture setup, and 0x01 continues to the remaining setup. Patching `611D` → `621D`
(`movi r13,33`) gives **0xA1** for all four channels. Live readback after the patch: 0xF8008E 0xA007 → **0xB007**.

The speed formula's constant K = circumference × 900 (`wheel_cal_prepare` 0x751A8) is **not** changed. The minimum
speed floor and the standstill behaviour therefore stay stock.

### 3. Direction mask = 0 (file 0xC13C4)

```
0B93C4  60F2  movi r2,15          ; patched: 6002 movi r2,0
0B93C6  7FB0  jsri validate_dir_cfg (0x75A5E)   ; patched: 6003 movi r3,0
0B93C8  77AE  lrw  r7,[..] = 0x4029D6
0B93CA  6049  movi r9,4
0B93CC  B207  st.b r2,(r7,0)      ; direction-expected wheel mask
```

- `validate_dir_cfg` returns **15 for an input in {0,1,2,3,15}, else 0**, so the mask can only be all-on or all-off
  through it. A plain `movi r2,0` would give 15. The patch **bypasses the call** and stores 0 directly. `r3` is set
  the same way the routine would leave it.
- With mask 0 no wheel accumulates invalid-direction counts (0x4029DB[w]), so the direction DTCs (5D96 and the
  others) can't set.
- Front-only variant, if the rears keep VDA sensors: `60 C2 60 C3` (mask 0x0C = rears only).

### 4. Presence check mode 2 (file 0x7DA56)

- `sub_075A44` returns the per-wheel presence mode (`movi r3,4` at CPU 0x75A56) used by the startup check
  `sub_075E38`.
- **Mode 4** expects the ASIC VDA reply word: popcount ≥ 3, else a fault at cycle 100.
- **Mode 2** uses a period-based check that passes without VDA data.
- This mode byte does not affect speed acquisition; `sub_07525C` doesn't check it.

### What is NOT needed

These were investigated and ruled out:

| Idea | Why not |
|---|---|
| Changing the BFU tooth count (48) | It isn't in the speed path |
| Doubling the speed constant K | Doubles the standstill floor to ~1.2 km/h, so a stopped wheel never reads 0, and it blocks reset/programming |
| ASIC level registers 0x114–0x14C, 0x154–0x16C, 0x184–0x1FC, etc. | They don't change detection |
| An external converter | Unnecessary |

## Applying the patch

1. Start from the stock bank-0 image (`flash/bin/7846816A_00000000.bin`) and apply the four byte changes above. The
   bench image `flash/bin/7846816A_probe_e46all.bin` has them plus the peek handler.
2. Re-sign and verify:
   ```
   python tools/bmy_resign.py fix <image.bin>
   python tools/bmy_resign.py verify <image.bin>      # MISR OK, BMY VALID
   ```
3. Repack onto the stock segment layout:
   ```
   python tools/mk60_can.py repack --plan flash/plan/m3_7846816A_stock \
     --bank 0x000000=<image.bin> --bank 0xDF0000=flash/bin/7846816A_00DF0000.bin \
     --bank 0xFF0000=flash/bin/7846816A_00FF0000.bin --out flash/plan/<name>
   ```
4. Flash with a Kvaser on D-CAN. Run a dry run first, then `--arm` and type the confirmation:
   ```
   python tools/mk60_can.py flashplan flash/plan/<name>
   python tools/mk60_can.py flashplan flash/plan/<name> --arm
   ```
   **Precondition:** every wheel must read below 1 km/h. The ECU refuses programming (NRC 0x22) otherwise. Keep the
   wheels still.
5. Confirm `SIGNATURE VERIFIED (71 09 01)` and `31 0A → 71 0A 01`.

## Verification (bench, 2026-10-06)

| Test | Result |
|---|---|
| Stock firmware, real E46 sensor (2026-10-04) | No reading at any speed |
| ESP32 rig, 7 / 14 mA square, register 0x28C = 0x00E (live) | FL 11.44 km/h valid, status healthy. Stock 0x00F: no edges |
| Real E46 on FL, 0x28C patch flashed | Reads; hand spins 5–7 km/h (single edge) |
| Capture mode 0xA1 (both edges) | Same spins read 10–18 km/h (≈ 2×). At rest: 0.00 km/h, normal 0.62 km/h internal floor |
| All-four image `m3_probe_e46all`, sensor moved FL → FR → RL → RR | **Every wheel reads valid**, peaks 11–22 km/h, decays to 0 |
| Live readbacks | 0x28C = 0x000; 0x4029D6 = 0x00; 0xF8008E = 0xB007; 0xD8009E = 0x3007 |
| Fault memory after testing | Only "electrically defective" on unplugged channels plus bench CAN noise. **No 5D91 / 5D95 / 5D96** |

## Limitations and open items before car use

- [ ] **Exact scale check.** The ESP32 rig at 7 / 14 mA, 150 Hz should read ≈ 22.9 km/h. Hand spins only show the
  doubling.
- [ ] **High-speed plausibility.** Ramp the rig to about 1200–1800 Hz (≈ 92–138 km/h) **with a ramp**. An instant step
  trips 5D91 (extrapolation), as a real wheel never steps.
- [ ] **Fault behaviour.** Unplug or short a sensor while "moving" and confirm a sensor DTC rather than a stale or
  zero speed.
- [ ] **Car image.** Build from stock plus the four patches only (no 0x23 peek handler), then re-sign.
- **No direction / reverse detection on any wheel.** E46 sensors never provided it. Functions relying on wheel
  direction (rollback or reverse logic) lose it.
- The minimum readable speed is unchanged from stock, about 0.6 km/h at 96 pulses/rev.
- The patch assumes **48-tooth rings** on all four wheels, matching BFU tooth count 48. A different tooth count needs a
  BFU circumference/teeth calibration change.

## References

| Item | Where |
|---|---|
| Full findings and bench log | `FACTS.md`, entries dated 2026-10-04 → 2026-10-06 (ASIC sensor-mode mask, capture edge-select, all-four-wheel test) |
| Commits | `bc02085` (0x28C discovery), `abef471` (real E46 on FL), `e12de4b` (both-edge capture), `243d5bb` / `3ae5744` (all four wheels) |
| Bench images and plans | `flash/bin/7846816A_probe_e46all.bin`, `flash/plan/m3_probe_e46all` (includes the 0x23 peek handler) |
| ASIC scripts and register dump | `analysis/agents/asic_sensormode/` (`asic_dump_ro.txt`, sweep scripts) |
| ESP32 test rig sketch | `C:\Users\cgrah\Documents\Arduino\sketch_oct5a` |
| Earlier converter design (now not needed) | `docs/VDA_CONVERTER_DESIGN.md` |

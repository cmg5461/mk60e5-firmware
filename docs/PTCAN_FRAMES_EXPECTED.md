# PT-CAN frames the stock firmware expects (7846816A, M3)

What to send on PT-CAN so the **stock** DSC firmware, running without the rest of its car, raises no CAN DTCs,
thinks the ignition is on, and (optionally) runs ABS with DSC switched off. It covers a bench, or a different car
with an emulator in front of the DSC.

This document is derived from the disassembly and has not been checked on a unit yet. The firmware
detail behind each statement is in `FACTS.md`, sections "CAN RX handlers" and "DSC driver mode", and in
`analysis/CAN_RX_TABLE_7846816A.md`.

Bit positions are `byte.bit`, Intel (little-endian), LSB first. "Coding byte n" is byte n of the coding payload
read and written with `22/2E 30 00` (see `analysis/CODING_BYTES_7846816A.md`).

## Quick recipe: ABS on, DSC off, no DTCs

1. Send **0x130** with ignition on (below).
2. Send the three DME frames **0x0A8 / 0x0A9 / 0x0AA** with the "idle engine" values in "Faking the DME frames".
3. Send the gearbox frame that matches the coding: **0x3B0** (manual) or **0x0BA** (DCT).
4. Send **0x310** and **0x330** (instrument cluster).
5. Send **0x398 `00 04`** (DSC off) about every 100 ms.
6. Code **hill-start assist off** and, if you don't want it, **RPA off** (see "Coding").
7. Check the DSC's own **0x19E**. Byte 1 bits 2–4 should be 1 (DSC off lamp), and byte 1 bits 0–1 should be 0
   (ABS OK).

## Send 0x130 first

0x130 is the terminal status (Klemmenstatus). The DSC decides "ignition on" in one of two ways:

- **While it receives a valid 0x130**, the terminal-15 bits in that frame decide. A valid 0x130 that reports
  ignition off turns ignition off, whatever the hardware says.
- **While 0x130 has never been received, or has stopped arriving**, a hardware input decides. On a bench unit with
  only power applied, this input reads "on": that unit logs D35A (0x130 missing) plus the DME and gearbox timeouts.
  Which pin drives it is not known, so another unit or harness may behave differently.

So a unit like that one has ignition on without 0x130, but stores D35A. **Send 0x130 with ignition on**: it
removes D35A and makes the ignition state independent of the hardware input. Never send it with ignition off
unless you want the DSC switched off.

With ignition off:

- **No PT-CAN message DTC is raised at all.** Monitoring is off, so a bus that is missing frames *looks* clean.
- **Many functions change behaviour.** ABS still runs, but:
  - The longitudinal acceleration from the sensor cluster is marked invalid, so ABS falls back to a
    wheel-speed estimate.
  - The ignition-off path writes to the valve/pump driver chip. This may be a power-down; not confirmed.
  - The scheduler, fault manager, fault reactions, lamps and hill-start code also change behaviour.

With ignition on, CAN fault monitoring switches on after about 750 ms (and never in the first ≈ 1.8 s after
power-up). From then on, every frame below that has a timeout DTC must be present.

**Tell which state you are in:** D35A or other timeout DTCs appearing means ignition is on. No CAN frame from the
DSC carries the ignition state directly.

## Rules for every frame

- **DLC.** Send at least the DLC in the table. Shorter frames are dropped whole.
- **Alive counter.** 4 bits. Count 0, 1, …, 14, 0, …. It must change on every frame. A value of 15, or the same
  value twice in a row, drops the frame. Three such errors turn the timeout DTC into an "alive" DTC.
- **Checksum.** See "Checksum" below. A mismatch drops the frame. Three mismatches give a "checksum" DTC.
- **Invalid values.** 12-bit fields reserve 0x800, bytes 0xFF and words 0xFFFF. Never send these in the DME
  frames (see the DTC table in "Faking the DME frames").

## What to send

| Frame | DLC | Send every | Timeout → DTC | Contents |
|---|---|---|---|---|
| **0x130** terminal status | 5 | 100 ms | 500 ms → D35A | see below |
| **0x0A8** DME torque 1 | 8 | 10–100 ms | 500 ms → D354 | see below |
| **0x0A9** DME torque 2 | 8 | 10–100 ms | 500 ms → D355 | see below |
| **0x0AA** DME torque 3 | 8 | 10–100 ms | 500 ms → D356 | see below |
| **0x3B0** reverse gear, *manual gearbox coded* | 2 | ≤ 1 s | 5 s → D378 | byte 0 bits 0–1 = **1** (not in reverse). 2 = reverse, 0/3 = invalid |
| **0x0BA** gearbox, *DCT coded* | 8 | 10–100 ms | 500 ms → D357 | see below |
| **0x310** instrument cluster 1 | 7 | ≤ 1 s | 5 s → D358 | byte 0 (outside temperature) ≠ 0xFF; bytes 1–4 (relative time, u32) not all 0xFF |
| **0x330** instrument cluster 2 | 8 | ≤ 1 s | 50 s → D359 | bytes 0–2 (odometer, 24-bit) ≠ 0xFFFFFF |
| **0x398** DSC mode request | 2 | ≈ 100 ms | none | optional; `00 04` = DSC off. See "Turning DSC off" |

The gearbox type is coding byte 2 bits 6–7 (0 = manual, 2 = DCT). With manual, only 0x3B0 is read; otherwise
only 0x0BA. Send the one that matches the coding; sending both does no harm.

### 0x130 terminal status

| Bits | Value | Meaning |
|---|---|---|
| 0.0–0.1 | 1 | probably terminal R. Must be 1 for the brake-light-switch state on TX 0x19E to be valid |
| 0.2–0.3 | 1 | probably terminal 15. 1 = **ignition on** |
| 0.4–0.5 | 0 | probably terminal 50 (crank). 1 = cranking |
| 0.6–0.7 | any | not read. A real E9x sends byte 0 = **0x45** with ignition on, which fits this table |
| bytes 1–3 | any | not read by the DSC |
| 4.0–4.3 | alive | alive counter |
| 4.4–4.7 | c4 | checksum (mode 4) |

The DSC relays this frame unchanged to F-CAN. The terminal meanings are inferred from how the bits are used,
not confirmed.

### 0x0A8 DME torque 1

| Bits | Send | Notes |
|---|---|---|
| byte 0 | c8 | checksum (mode 8) |
| 1.0–1.3 | alive | |
| 1.4–2.7 | 0 | 12-bit signed engine torque. Never 0x800 |
| 3.0–3.3 | **0** | DME status. 0–2 valid. **3 = "torque not adjustable"** (→ 5E19), ≥ 4 invalid |
| 5.0–5.1 | 0 | flag. 2/3 invalid |
| 6.4–6.5 | **0** | anything else means "message implausible" (→ 5E18) |
| rest | any | not read |

### 0x0A9 DME torque 2

| Bits | Send | Notes |
|---|---|---|
| byte 0 | c8 | checksum (mode 8) |
| 1.0–1.3 | alive | |
| 2.0–3.3 | 0 | 12-bit signed engine drag torque (the DSC negates it). Never 0x800 |
| rest | any | not read |

### 0x0AA DME torque 3

| Bits | Send | Notes |
|---|---|---|
| byte 0 | c8 | checksum (mode 8) |
| 1.0–1.3 | alive | |
| 1.4–2.7 | 0 | 12-bit signed driver-demand torque. Never 0x800 |
| byte 3 | 0 | accelerator pedal. Never 0xFF |
| bytes 4–5 | **≈ 3200** (0x0C80) | u16 engine speed. Probably 0.25 rpm/bit as on other BMWs, so 3200 ≈ 800 rpm (scaling not confirmed). Never 0xFFFF. **Don't send 0** (see below) |
| 6.0–6.1 | **0** | rpm error. Any other value makes rpm invalid |
| 6.4–6.7 | ≠ 15 | 4-bit value, purpose unknown |
| rest | any | not read |

### 0x0BA gearbox (DCT coding only)

| Bits | Send | Notes |
|---|---|---|
| 0.0–0.3 | 1 | gear: 1 = N, 2 = R, 3 = P, 5–11 = gears 1–7. Others invalid. A change needs two equal frames in a row |
| 0.4–0.5 | 0 | flag. ≥ 2 invalid |
| byte 5 | c8 | checksum (mode 8) |
| 6.0–6.3 | alive | |
| 7.6–7.7 | 0 | flag. ≥ 2 invalid |

## Faking the DME frames

Constant "idle engine" values are fine. The DSC never compares the DME torques with anything else (wheel
acceleration, pedal, rpm). Every DME DTC comes from either a value marked invalid or the DME's own status bits,
held for 50 cycles (≈ 0.5 s):

| DTC | Text | Raised by | Avoid by |
|---|---|---|---|
| 5E1B | CAN DME/DDE Motormoment Signal Fehler | any of the three torques = 0x800 | torque ≠ 0x800 (0 is fine) |
| 5E1A | CAN DME/DDE Signal Fehler | pedal = 0xFF, rpm = 0xFFFF, or 0x0AA 6.0–6.1 ≠ 0 | pedal 0, rpm ≈ 3200, 6.0–6.1 = 0 |
| 5E19 | CAN DME/DDE, Motormoment nicht einstellbar | 0x0A8 3.0–3.3 = 3 | send 0 |
| 5E18 | CAN DME/DDE Botschaft unplausibel | 0x0A8 6.4–6.5 ≠ 0 | send 0 |
| D354 / D355 / D356 | DME/DDE_1/2/3 | frame missing for 500 ms, or 3 alive / checksum errors | send on time with a correct alive counter and checksum |

**ABS does not use the DME values.** The ABS controller never reads engine torque or rpm. It reads the pedal only
in a fallback mode, and there 0 means "pedal released". What the fake values do affect:

- **Traction control, yaw control and engine drag-torque control (MSR)** see an idling engine. That is wrong data,
  which is one more reason to switch DSC off. Their torque requests go out on 0x0B6 and nothing on your car acts on
  them; the DSC only notices if the DME sets "torque not adjustable" itself, which you don't send.
- **Hill-start assist** detects drive-off from rpm and engine torque. With torque stuck at 0 it may never see the
  car pulling away and could hold brake pressure for longer. How it releases has not been traced. **Code it off.**
- **Ready-alert brake** (brake pre-fill on a fast throttle lift) never triggers with the pedal stuck at 0. You just
  lose it.
- **Soft-stop assist** also reads these values (not traced). Code it off if you want to be safe.
- **RPA** (tyre-pressure warning) uses torque and rpm to decide when it compares wheels. Fake values may give
  false warnings. Code it off if you don't use it.
- **Engine speed.** Below roughly 360 rpm (if the scaling is right) the DSC treats the engine as not running. Its
  start-up lamp logic reads that state (not fully traced). Send a plausible idle, not 0.

## Turning DSC off (keeping ABS)

With all the frames above present, the DSC is fully functional, including traction and yaw control. To get ABS
without DSC, use one of the methods below.

### Recommended: 0x398 "DSC off"

| Frame | DLC | Send every | Contents |
|---|---|---|---|
| **0x398** | 2 | ≈ 100 ms | `00 04`: byte 1 bits 2–4 = **1**. Byte 0 bits 4–5 = 0. Everything else 0 |

Byte 1 bits 2–4 is the driver-mode request:

| Value | Mode |
|---|---|
| 0 | DSC on |
| **1** | **DSC off**: the same state as holding the DSC button, lamp included |
| 4 | M Dynamic Mode |
| other | ignored |

Byte 0 bits 4–5 is a second request whose meaning is unknown. Keep it at 0. Don't send 0x399; it writes the same
request through logic that was not fully traced.

- **No checksum, no alive counter, no timeout DTC.** Each received frame is one request. Keep sending it: the mode
  resets to "on" at every power-up, and a request that is not accepted is retried by the next frame.
- **When it is accepted.** The switch from on to off is accepted only while no yaw-control intervention is running
  (always true at a standstill). It is also ignored while the DSC button is pressed. Leave the button input in its
  released state: a stuck button (5E5B after 10 s) blocks CAN requests.
- **CAN overrides the button.** While you keep sending "off", a button press back to on is undone by the next frame
  after release.
- **What off does.** Yaw control drops to its passive state and the DSC is flagged as inhibited. Two of the three
  traction-control channels switch off (a running intervention is allowed to finish). The third, an MSR-like
  engine-drag controller that only asks the DME for *more* torque with the pedal at ≤ 13 %, stays enabled; in DSC
  off its request is forced to 0 only when the DME sends 0x0A8 byte 5 bits 0–1 = 1. ABS, EBD and the ABS use of the
  yaw cluster and steering sensor are unaffected (FACTS "DSC-off and the traction channels").
- **Check it** on 0x19E: byte 1 bits 2–4 = **1** (DSC off lamp), bits 0–1 = **0** (ABS OK).

The hardwired DSC button does the same. It is active-low (pressed = pulled low). Hold it for more than 0.5 s but
less than 10 s, about 2 s or more after power-up, once at every power-up. Its connector pin is not known from the
firmware; take it from the E9x wiring diagram.

### Alternative: 0x130 but no DME frames

Leave out 0x0A8, 0x0A9 and 0x0AA, and keep 0x130 reporting ignition. (Leaving out 0x130 as well also works when
the hardware ignition input reads "on", at the cost of D35A.)

- **ABS still runs in its ignition-on mode**, including the longitudinal-accel sensor.
- **DTCs: D354, D355, D356** (timeout), about 1.25 s after ignition on. **No 5E1B**, because that one comes only
  from 0x800 values in torque frames that do arrive.
- **DSC goes to "failed" through its fault reaction.** All three timeouts raise one internal fault. Its reaction
  blocks and aborts yaw-control intervention, flags DSC as inhibited, and affects traction control.
- **ABS is not switched off.** None of the ABS-off reactions are triggered, so the ABS function state stays OK.
  Two small ABS-side functions that hand over from active (DSC) braking are switched off with yaw control; what they
  do was not traced.
- **Check it** on 0x19E: byte 1 bits 2–4 = **2** (DSC failed), bits 0–1 = **0** (ABS OK).

You can combine both methods. The fault route also stops DSC at function level, at the cost of DTCs and the
warning lamp.

## Coding

| Coding byte | Bit | Feature | Recommendation |
|---|---|---|---|
| 13 | 6 | hill-start assist | **0** (off) with fake DME data |
| 13 | 3 | soft-stop assist | 0 if unsure |
| 13 | 4 | ready-alert brake | either; it can't trigger with pedal 0 |
| 3 | 3 | RPA tyre-puncture warning | 0 if not used (DDS Plus, byte 10 bit 4, requires it) |
| 1 | 0–4 | vehicle-model variant | mass and geometry only feed DSC; for ABS this picks the deceleration curves: 0–9 standard, 10/11 (GTS) allow deeper wheel decel (−1.40 g floor below 60 km/h, more above 150 km/h). Avoid 1 (needs bytes 31–40 non-zero) |
| 2 | 6–7 | gearbox | must match the gearbox frame you send (0 = manual → 0x3B0, 2 = DCT → 0x0BA) |

Coding byte 0 is a checksum: `c[0] = (c[1] ^ … ^ c[47]) + 1`. The DSC also runs a feature-combination check over
the fan, RPA, disc-drying and hill-start bits that has not been decoded. A rejected coding raises a coding fault.

## Checksum

```
s  = sum of all received bytes (the checksum byte, or nibble, set to 0 first) + CAN id
c8 = (s + ((s & 0xFFFF) >> 8)) & 0xFF          # mode 8: 0x0A8/0x0A9/0x0AA byte 0, 0x0BA byte 5
c4 = (c8 + (c8 >> 4)) & 0x0F                    # mode 4: 0x130 byte 4 high nibble
```

For 0x130, the alive nibble stays in the sum. Only the high nibble is zeroed.

Examples:
- 0x130 `45 FF FF FF 0a`, where a is the alive counter: byte 4 = 0xD0 (a = 0), 0xE1 (a = 1), 0xF2 (a = 2).
- 0x0A8 with all other bytes 0: byte 0 = 0xA8.

```python
def can_c8(can_id, data):
    s = sum(data) + can_id
    return (s + ((s & 0xFFFF) >> 8)) & 0xFF

def can_c4(can_id, data):
    c = can_c8(can_id, data)
    return (c + (c >> 4)) & 0x0F

def frame_130(alive):                     # alive 0..14
    d = [0x45, 0xFF, 0xFF, 0xFF, alive]
    d[4] |= can_c4(0x130, d) << 4
    return bytes(d)

def frame_0a8(alive, torque=0):           # idle engine, all status fields 0
    d = [0] * 8
    d[1] = (alive & 0xF) | ((torque & 0xF) << 4)
    d[2] = (torque >> 4) & 0xFF
    d[0] = can_c8(0x0A8, d)
    return bytes(d)

def frame_0a9(alive, drag=0):
    d = [0] * 8
    d[1] = alive & 0xF
    d[2] = drag & 0xFF
    d[3] = (drag >> 8) & 0x0F
    d[0] = can_c8(0x0A9, d)
    return bytes(d)

def frame_0aa(alive, demand=0, pedal=0, rpm_raw=3200):
    d = [0] * 8
    d[1] = (alive & 0xF) | ((demand & 0xF) << 4)
    d[2] = (demand >> 4) & 0xFF
    d[3] = pedal
    d[4] = rpm_raw & 0xFF
    d[5] = rpm_raw >> 8
    # d[6] = 0: rpm error bits 0-1 = 0, upper nibble 0 (anything but 15)
    d[0] = can_c8(0x0AA, d)
    return bytes(d)

def frame_398_dsc_off():
    return bytes([0x00, 0x04])            # no checksum, no alive counter
```

## Optional

- **0x380 VIN** (DLC 7). DTCs D361 (missing), 5E1F (wrong) and 5E1D (invalid) exist, but the code that raises them
  was not traced. The 7 bytes are compared with the VIN stored in the DSC, and all 0xFF means invalid. If any of
  those DTCs appear, send the stored VIN about every 1 s. On BMWs 0x380 normally carries the last 7 VIN characters;
  the stored format was not checked.
- **0x308 MSA** (auto start/stop, D379, 2.5 s timeout). The M3 has no auto start/stop, and the timeout handling was
  not fully traced. Add it only if D379 appears.

## Not needed

- **No timeout DTC found:** 0x2E4, 0x226, 0x316, 0x319, 0x398, 0x399, 0x1A3. The 0x1A3 timeout only sets a flag.
  (0x398 is still useful for DSC off, see above.)
- **Ignored entirely:** 0x0AC, 0x0B4, 0x0D5, 0x1B4, 0x388, 0x2A6. The DSC discards their contents.

## Out of scope: F-CAN

The yaw/acceleration sensor cluster (0x0CD/0x0D1/0x0D4 → D370–D372) and the steering-angle sensor
(0x0C9 → D373) are on F-CAN. F-CAN has its own monitoring gate; whether it needs ignition was not established.

**Without 0x0C9 the DSC marks lateral acceleration and yaw rate invalid too**, and switches off yaw control and all
traction control (FACTS "Steering-sensor loss"). So the cluster is only useful together with the steering sensor.
What the ABS does with both of them that it cannot do without (FACTS "ABS with and without the SZL"):

- **Rear axle.** Straight and stable, the rears can be controlled individually; without the sensors a rear in
  control always pulls the other rear to the lower pressure (select-low).
- **Cornering.** A rear cornering latch, a rear pressure cut set by driver pressure and lateral g (code 32), and
  ½ / ⅓ release steps in corners. None of these run without the sensors.
- **Split-µ.** The yaw-triggered limiting of the high-grip wheel. A pressure-based front coupling remains without it.
- **Hard braking.** The vehicle-speed estimate follows the measured deceleration (straight only). Without the
  steering sensor it falls at fixed rates, but those are still bounded by the cluster's accelerometer.

Without the steering sensor the cluster still contributes its **longitudinal accelerometer**: the ABS checks it
against the wheels, then uses it for its deceleration thresholds and to keep its vehicle-deceleration estimate
honest. The cluster also keeps D370–D372 away, and 0x1A0 keeps carrying its lateral and yaw values.

| You have | ABS | Yaw control | Traction control |
|---|---|---|---|
| cluster only | plain | off | off |
| cluster + DME frames | plain | off | off |
| cluster + steering sensor | full (above) | off (DME missing) | off (DME missing) |
| cluster + steering sensor + DME frames | full | on (off with 0x398) | on (with 0x398 "off": only the MSR-like channel) |

**D364 "PT-CAN Operator_Key_Tempo"** is really the F-CAN cruise-control stalk frame **0x194** (from the steering
column switch cluster, SZL). In 7846816A nothing can raise it: the 0x194 timeout handler is a bare return and no
F-CAN report site produces its ids. If it shows up, it is most likely an old entry stored before the unit was
removed from its car. Clear the fault memory and check whether it comes back. If your tester shows the entry's
mileage stamp, a donor-car mileage (rather than the odometer you send on 0x330) also marks it as old.

## Unverified

- **Everything here** comes from the code and has not yet been tried on a unit.
- **Terminal meanings** of the 0x130 bits (R / 15 / 50) are inferred from use.
- **rpm scaling** of 0x0AA bytes 4–5, and so the "engine running" threshold.
- **Hill-start assist** behaviour with zero engine torque.
- **The effect of ignition off** on the valve/pump driver chip.
- **VIN DTC reporters** for 0x380, and **D379 behaviour** of 0x308.
- **DSC off:** the BMW name of 0x398, the meaning of its byte 0 field, which of the two switched-off traction
  channels is the brake-based one, and the meaning of 0x0A8 byte 5 bits 0–1.
- **F-CAN sensors:** the ABS behaviour with and without the steering sensor is read from code only.
- **Hardware ignition input.** Which connector pin (or internal state) drives it, and whether every unit reads it
  as "on" with power alone. One bench unit does.

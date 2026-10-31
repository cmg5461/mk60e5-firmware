# MK60E5 (7846816A) — Scan-tool service-routine spec

How a diagnostic tester drives the DSC's actuator / calibration / bleed routines, derived
from the firmware KWP2000 dispatcher (`0xF30A0`) and handlers, cross-checked against the
EDIABAS SGBD `DSC_87.prg` (XOR-`0xF7`). Byte layouts are given as **KWP payloads** (SID +
data); the transport wrapper (§1) is applied once around every payload.

Confidence tags: **[fw]** proven in the firmware image, **[sgbd]** from the SGBD job table,
**[cap]** needs a bus capture to pin exactly. RAM addresses are CPU addresses in this image.

---

## 1. Transport & addressing  [fw/sgbd]

| | |
|---|---|
| Bus | PT-CAN, 500 kbit/s |
| DSC diagnostic address | `0x29` (WinKFP "29") |
| Tester → DSC request CAN-ID | **`0x6F1`** (mask `0x7F0`), handler `can_rx_6F1_tester_cb` `0x7CC02`, mailbox 31 |
| DSC → tester response CAN-ID | **`0x629`** (= `0x600 + addr`) |
| Framing | BMW "byte-0" ISO-TP: **data byte 0 = address** (request `0x29`, response `0xF1`), byte 1 = ISO-TP PCI, then KWP data. 6 payload bytes per single/consecutive frame. |

So a single-frame request of a KWP payload `P0 P1 …` (n ≤ 6 bytes) is sent as:

```
ID 0x6F1  D = [29] [0n] [P0 P1 … Pn-1]      ; 29=target, 0n = SF, len=n
```

Multi-frame uses standard ISO-TP (FF `1L LL…`, CF `2x…`, tester sends FC `30 …`), still
with the address byte in D0. Response mirror: `ID 0x629 D=[F1][PCI]…`.

**TesterPresent:** send `3E` (`DIAGNOSE_AUFRECHT`) at least every **~2 s** while any non-default
session is held, or the ECU drops back to the default session and aborts a running routine.
Positive response `7E`.

---

## 2. Diagnostic session model  [fw: `kwp_10` `0xB125C`]

`10 <mode>` → `50 <mode>`. Modes accepted by this image:

| Mode | Name | Use |
|------|------|-----|
| `81` | StartCommunication / default | always first after connect |
| `85` | ECUProgrammingMode (ECUPM) | flash only; **needs level-5 auth first** (else NRC `22`). Hands off to bootloader, forces a reset — wait the reset time before re-querying. |
| `86` | ECUDevelopmentMode | n/a for service |
| `87` | **ECUAdjustmentMode / EOL** | **required for all actuation, calibration and bleed routines**, and the only session where SecurityAccess `27` is granted |

Teardown: `20` StopDiagnosticSession (`DIAGNOSE_ENDE`) → `60`, or let TesterPresent lapse.
Always stop a routine (§5) **before** leaving the adjustment session.

Minimum connect sequence for any service routine:

```
10 81            -> 50 81        ; StartCommunication
10 87            -> 50 87        ; ECUAdjustmentMode
(…routine…)
20               -> 60
```

**SecurityAccess `27` is not required for the `31` service routines, the `30` valve drive or the
coding write.** [fw-verified, capture-verified] None of these handlers checks a security level. A
live bus capture shows `31 22 00` succeeding straight after `10 87 05` with no `27` in the session.

---

## 3. Request-length check — `0x409537`  [fw-verified]

`0x409537` holds the **length of the current KWP message** (SID + data bytes, without the address
byte or ISO-TP PCI). It is not an access token or a security level.

- **Receive:** the diag RX copier writes the received request length there before dispatch
  (`0xB041A`; also `0xB045C` from `0x4094D6`), next to `0x409533`.
- **Transmit:** each handler overwrites it with the **response** length when it builds its reply.
  For example, `kwp_30` writes 3 for `70 10 07`, the `22 30 00` read writes 51 for
  `62 30 00` + 48 bytes, and StartCommunication `81` writes 3 for `C1 KB1 KB2`.

Two layers check it. A wrong length gives **NRC `0x12`**, not `0x13`.

**Dispatcher layer** (`0xB11B8`): before calling a handler, it requires
`0x409537 == serviceTable[SID].lenByte`, unless that byte is `0xFF` (variable length; the handler
checks). Service table `0xF30A0`, 12-byte records `[SID][lenByte][2][handler:4]`.

| Length byte | SIDs | Request form |
|------------:|------|--------------|
| `FF` (handler checks) | `10 27 30 31 3b 2e 3e 29 28` | |
| 1 | `20`, `81`, `82` | `20` |
| 2 | `1a 21 33 11` | `1A 80`, `21 <lid>`, `33 <id>`, `11 01` |
| 3 | `14 17 22` | `14 FF FF`, `22 30 00` |
| 4 | `18` | `18 02 FF FF` |
| 6 | `23` | `23 00 <addr16> 03 <n>` |
| 7 | `09 3d` | |

**Handler layer:** handlers with variable-length SIDs compare the length against their own
expected size:

| Request | Required length | Form |
|---------|----------------:|------|
| `31` calibration/actuation routines `0x20`–`0x31` | **3** | `31 <id> 00` |
| `31 07` RequestForAuthentication | 7 | `31 07 03 <uid[4]>` |
| `31 0A` programming status | 2 | `31 0A` |
| **`2E 30 00` coding write** | **51** | `2E 30 00` + 48 coding bytes |
| **`30 10 07` valve/pump drive** | **8** | `30 10 07` + 5 bytes (§6 group A) |

> **Correction.** Earlier revisions of this doc called `0x409537` a "last-qualifying-operation
> token". On that reading each service needed a specific earlier service to "stamp" it: `81` or
> `27` for routines, `22 30 00` for coding. The stores those notes cited are response-length
> writes. A request that has the right length passes the check, whatever ran before it. No
> service needs another service run first to pass this check.

### 3a. SecurityAccess `27 03/04` — **not** required for service work  [fw: `kwp_27` `0xB14C2`]
`27 03` → `67 03 <seed16>`; `27 04 <key16>` → `67 04`. A correct key sets the coding level
`0x409513 = 3`. It also writes `0x409537 = 3` at `0xB1580` (the response length, §3). Granted only
inside ECUAdjustmentMode (`10 87`). `seed = (u16 @0x40095C) XOR 0x3008` (→ `0x53A1` if zero);
key = `ROR16(seed,3)` → bit swap/complement network → XOR image constant (full algorithm in
`analysis/7846816A_symbols.md`). None of the `31`, `30` or `2E 30 00` paths in this doc reads the
level.

### 3d. The real `31` gate and preconditions  [fw-verified: `kwp_31_start_routine` `0xB2B1C`]
The `31` handler does **not** call SecurityAccess. It runs two internal checks, then dispatches the
routine body through a second jump table. Both checks read the request's routine-id byte from
`0x409534` and its argument byte from `0x409535` (populated from the diag RX buffer).

**Check 1 — length/arg gate** (`0xB2B1C`→`0xB2C82`; jump table `0xB2B98`, index = `id − 5`) → **NRC `0x12`** on fail:
- routine id in table range (`5`–`49`);
- routines `0x20`/`0x22`/`0x24` share the handler at `0xB2C72`, which requires the **argument byte
  `0x409535 == 0`**;
- request length `0x409537 == 3`. Send the full 3-byte payload (`31 24 00`); a 2-byte `31 24`
  fails.

**Check 2 — per-sensor precondition** (`0xB2D08`–`0xB2D44`) → **NRC `0x22`** (conditionsNotCorrect) on
fail. Each routine requires its sensor's "ready/plausible" bit in RAM byte **`0x40200C`**:

| Routine | Calibrates | Required bit in `0x40200C` | checked at |
|--------:|-----------|:--------------------------:|-----------|
| `31 20` | brake pressure | bit 7 | `0xB2D0E` |
| `31 21` | steering angle | bit 5 | `0xB2D1C` |
| `31 22` | lateral accel | bit 6 | `0xB2D2A` |
| `31 24` | longitudinal accel | bit 0 | `0xB2D38` |

These bits are maintained by the chassis-sensor conditioning task (`~0x089E00`–`0x08A5xx`), a
register-heavy per-sensor state machine that does **not** linearise cleanly from static analysis, so
the exact per-bit set condition is **[cap] not yet pinned** — treat the following as the shape, not
gospel. A bit is set only when that sensor is **coded as fitted** (`sensor_fitted(n)`, ROM
`0xF6756[n]`: 5 pressure, 6 lateral, 8 steering, 9 ax) **and** currently reading **valid/plausible**
with no active fault, and no competing valve/sensor cal owning the state (`valve_cal_type
0x404970`). For brake pressure the documented validity chain is `0x408E6D` b6 = pressure valid,
which needs `0x408EB2` valid **and** the zero-pressure plausibility counter `0x408EBA < 50` — so a
sensor reading an implausible/non-zero value at rest (disconnected, mis-supplied, or reading rail)
saturates that counter, drops pressure validity, and leaves b7 clear → `7F 31 22`.

A pending NRC in `0x409538`, or the earlier all-routines fault query (`0xAF78C`, gated on
`0x409544 == 0x80`, affects ids `5/7/8/10`), can also stop it before this point. The speed gate
(NRC `0x33`) only applies to routine `31 31` (CCP).

**Bench discriminator** — run `31 21` (steering cal, needs b5): if steering *also* returns `0x22`,
the conditioning pass isn't producing ready bits at all (module not past start-up / a latched
failsafe / no valid chassis-sensor environment); if steering passes but pressure doesn't, the
pressure channel is the problem (not coded-fitted for the variant, or a sensor-circuit/plausibility
fault). Confirm by reading `0x40200C` directly and checking for pressure-sensor DTCs.

On pass the handler sets the response length (`0x409537 = 3`) and the response-ready flag
`0x409435 = 1`. The routine body then sets its own completion bit in `0x40200C`/`0x40200D` (e.g.
`31 24` sets `0x40200D` b7).

### 3b. Coding write — `2E 30 00`  [fw-verified, capture-verified]
Coding does **not** use SecurityAccess. This is the live-captured working path
(`~/source/wheelspeed/coding_write_dump.txt`):

```
22 30 00                 -> 62 30 00 <48 bytes>   ; read handler 0xB2610: reads NVM block 10 via
                                                   ; descriptor 0xF31FC
10 87 05                 -> 50 87                  ; coding session
2E 30 00 <48 bytes>      -> 6E 30 00               ; write handler 0xB2A16
```

The read is there to get the current block for the round trip. The firmware does not require it
before the write: the write handler's first check is on the write request's own length.

Write handler `0xB2A16` gate, in order:
1. Request length `0x409537 == 51` (`2E 30 00` + 48) else **NRC `0x12`** (`0xB2A1E`). A short or
   long block fails here.
2. `0x409544 == 16` else **NRC `0x22`** (`0xB2A26`). Normally already satisfied; note the
   ECUProgrammingMode (`10 85`) path sets `0x409544 = 4` (`0xB1332`), so do coding in `10 87 05`,
   not after entering `10 85`.
3. Field validator `0xCF432` over the 48-byte RX buffer `0x403320`; any out-of-range field →
   **NRC `0x31`** (`0xB2A42`; only a return of exactly 1 gives the NRC). The five validator
   stages and what each enforces: `CODING_BYTES_7846816A.md` (header and byte map).
   Exception: if `0x8E066(24, 1)` = 4 (a 3-bit state at `0x401FAC`, meaning not identified)
   `0xCF432` skips validation and returns 0xFE. The handler does not treat that as a failure: the
   raw bytes are still queued to block 10 and acknowledged, but nothing is checked, unpacked or
   saved to the active image (block 7), so the module keeps running on its old coding. Then the write is queued to NVM (descriptor `0xF3268`, block 10).

Rules for a correct write:
- **Block is exactly 48 bytes**, read and write the same NVM block (block 10, logical EEPROM
  `0x400`–`0x42F`). Round-trip: write back exactly what `22 30 00` returned, changing only target
  fields.
- **Byte 0 is a checksum**: `c[0] = (c[1] ^ c[2] ^ … ^ c[47]) + 1` (`0xCFDB8`). Any field edit
  must recompute it or the validator rejects the write. Field map: `analysis/CODING_BYTES_7846816A.md`.
- Nothing is appended on the wire; ISO-TP length `0x33` = 51 = 3 (`2E 30 00`) + 48. Trailing bytes
  in the last frame are CAN padding.

### 3c. Level-5 "Authentisierung" — `31 07` / `31 08`  [fw-verified, live]
Required for `10 85` (flash). Routines in §5 groups A–D do **not** need it; only the flash
jobs do. MD5 challenge/response, done inside ECUAdjustmentMode:

```
10 81 -> 10 87
31 07 03 <uid[4]>            -> 71 07 <ZUFALLSZAHL[8]>     ; uid tester-chosen (e.g. 27 3C 00 00)
31 08 <resp[16]>            -> 71 08 00                    ; 00 = accepted, level 5 granted
```

`ZUFALLSZAHL[8]` is the ECU PRNG output (`0x408C04`), returned directly — no reversal needed.

```
resp = MD5( KEY[16] ‖ uid[4] ‖ W564[4] ‖ ZUFALLSZAHL[8] ‖ KEY[16] )   ; 48-byte input
```

`KEY[16]` and `W564` (`@0x409564`) are flash-resident constants (values/derivation in
`FACTS.md` auth section). The ECU compares `resp` against its own MD5 (`md5_init 0xB3D74`,
IV confirmed standard MD5). Match → level 5 (`0x409545` path). Level persists until reset.

---

## 4. Response / negative-response codes  [fw: NRC byte `0x409538`]

Positive: `SID+0x40 …` (`70` for `30`, `71` for `31`, `73` for `33`). Negative: `7F <SID> <NRC>`.

| NRC | Meaning in this image | Typical cause |
|-----|----------------------|---------------|
| `12` | subFunction not supported / wrong length | request length `0x409537` wrong for the service (§3): `31` routine not sent as `31 <id> 00`, `30` not exactly `30 10 07` + 5 bytes, coding block not 48 bytes. Also: non-zero `31` argument byte `0x409535`, bad routine id, or `30` LID/control other than `10 07` |
| `21` | busyRepeatRequest | `30`: `0x40950B` b4 set (previous two-group request still in group A), or `0x8A906` busy |
| `22` | conditionsNotCorrect | `31` cal routines: the sensor's ready bit in `0x40200C` is clear (§3d) — sensor not coded-fitted for the variant, or not reading valid/plausible (e.g. brake-pressure validity `0x408E6D` b6 dropped: implausible zero-point, `0x408EBA ≥ 50`), or a competing valve/sensor cal active. Also: not standstill, ignition/supply, circuit self-check (`0x060100/0200/0400`), or subsystem busy (`0x8A906`) |
| `23` | routineNotComplete / routineNotStarted | result polled before the routine finished; keep polling |
| `33` | securityAccessDenied / speed-gate | level not granted, or road speed over the actuation limit (`0x409545` vs cal `0xF690C`) |
| `35` | invalidKey | wrong `27 04` key or `31 08` response |

Preconditions enforced in-handler for **every** actuation/calibration/bleed routine: **vehicle
stationary (0 km/h), ignition on (engine off for bleed), no blocking hydraulic/sensor fault,
and ECUAdjustmentMode**. Fail → `22` or `33`.

---

## 5. Generic routine lifecycle

```
start   : 31 <id> [args]      -> 71 <id> [data]     ; or 7F 31 <nrc>
poll    : 33 <id>             -> 73 <id> <status…>  ; repeat while status=in-progress / NRC 23
                                                    ; (calibration: loop up to ~20 s)
stop    : 31 <id> 00  or  leave by 20 / TesterPresent-timeout
```

`33` RequestRoutineResults is implemented for ids `21`, `28`, `29` (`kwp_33` `0xB3408`);
other routines report their result inline in the `71` response or via their matching status DID.

---

## 6. Routine catalog

### Group A — valve/pump actuation & brake bleed — SID `30` InputOutputControl  [fw-verified: `kwp_30_io_control` `0xB1702`, drive `0xB0154`]

This is the bleed / valve-drive path, **not** a `31` routine. The SGBD jobs `STEUERN_DIGITAL`,
`STEUERN_DIGITAL_DX`, `STEUERN_DIGITAL_BLS`, `NA_ENTLUEFTUNG_RE/LI/VA/HA_DX` and
`STEUERN_HYDRO_SPUELEN` all send this one telegram (their job comments name `$30,$10,$07`). The bleed
jobs differ only in which valve groups they send. There is no separate bleed service in the
firmware.

**Request** (exactly 8 bytes, response `70 10 07`):

```
30 10 07  A0 A1  T  B0 B1
          |  |   |  |  +- group B circuit valves + pump (bit map below)
          |  |   |  +---- group B wheel valves
          |  |   +------- wait time T (10 ms frames), 0 = single group
          |  +----------- group A circuit valves + pump
          +-------------- group A wheel valves
```

Read it as **two valve commands with a delay between them**: group A (`A0 A1`) is applied, then
after `T × 10 ms` the module switches to group B (`B0 B1`). Each command is a 2-byte block — a
**wheel byte** (inlets/outlets) and a **circuit byte** (USV/HSV/pump). With `T = 0` only group B
is used and group A is ignored, so a one-shot command sends `A0 A1 = 00 00` and the valves in
`B0 B1`.

**Group B is not held indefinitely — it times out.** When the module switches to group B it starts
a 200-frame (2.0 s) countdown; at 0 the drive zeroes both active bytes and every solenoid/pump
de-energises. So one telegram drives at most group A (~(T+1)×10 ms) then group B (2.0 s) then off.
This 2 s cap is the handler's safety: a tester that disconnects mid-sequence leaves the actuators
live for ≤ 2 s. To hold a state longer, resend the telegram before the 2 s elapses (it re-arms the
timer). A longer sequence is built from a series of these telegrams (see the SGBD bleed jobs and
§7). Full detail under **Timing** below.

**On the wire.** The payload is 8 bytes, which does not fit a single frame (§1 — 6 payload bytes
max once the byte-0 address is prepended), so every `30 10 07` request goes as an ISO-TP
first-frame + consecutive-frame pair, with the ECU's flow-control frame in between:

```
tester -> 6F1   29 10 08 30 10 07 A0 A1     ; FF: addr 29, total len 0x008, first 5 payload bytes
ECU    -> 629   F1 30 00 00                  ; FC clear-to-send (BS / STmin are the ECU's values)
tester -> 6F1   29 21 T  B0 B1               ; CF seq 1, last 3 payload bytes (rest is CAN padding)
ECU    -> 629   F1 03 70 10 07               ; positive response (single frame)
```

The all-off telegram `30 10 07 00 00 00 00 00` frames the same way (`FF 29 10 08 30 10 07 00 00` /
`CF 29 21 00 00 00`). `tools/mk60_can.py bleedcap` reassembles these pairs automatically.

**Gate, in order** (`0xB1702`):
1. Request length (`0x409537`, §3): `30 10 07` must be 8 bytes. The handler would accept 10 for
   `30 20 07` and 12 for anything else, but then requires LID/control == `10 07`. Any other
   length or LID gives **NRC `0x12`**. `30 20 07` (the `_DX` 10-byte form) is rejected by this
   image.
2. It sets the response length to 3 and the response-ready flag `0x409435 = 1`.
3. **NRC `0x22`** if `0x40288C` has b4 or b7 set, or if any of b1–b7 is set in failsafe byte
   `0x40287D`, or if any circuit self-check `0xB4312(0x60100 / 0x60200 / 0x60400)` returns non-zero.
4. **NRC `0x21`** if `0x40950B` b4 is set (a two-group request is still in group A), or if
   `0x8A906()` reports busy.
5. It writes 585 mA (`0x249`) to both `0x4094E6` slots. This is the USV current used when SV1/SV2
   are commanded.
6. It parses the payload from the diag buffer `0x40331D` (`[0]` = SID):
   - **T ≠ 0:** it sets `0x40950B` b4 and loads the active group (`0x40953F` ← A0,
     `0x409540` ← A1). It stores group B in `0x409557` ← B0 and `0x409558` ← B1, and sets the timer
     `0x409542 = T + 2`.
   - **T = 0:** it clears b4 and loads the active group from **B0/B1**. A0/A1 are ignored. The
     timer is 200.

   Each circuit byte is stored as `(x & 0x0F) | (x & 0x10 ? 0x40 : 0)`.

**Execution** runs every 10 ms in the main cycle (T3 `0x071040` → diag task `0xB00F4`, only while
`0x4094F7` b7 is set):
- `0xB0154`: while the timer is non-zero it counts down. At 0 it clears both active bytes, so all
  outputs go off. Every frame it drives each actuator from the active bytes:
  - Wheel byte bit *i* → `valve_pulse_set(0xF2EF0[i], bit ? 20 : 0)` (all 10 steps of the frame on
    or off). Order `0xF2EF0 = [0,4,1,5,2,6,3,7, 8,9,10,11, FF…]`.
  - Circuit byte bits 0–3 → channels 8–11.
  - Circuit byte stored bit 6 (wire bit 4) → `pump_motor_set_level(15)`, the maximum. Clear → 0.
  - For SV1/SV2 (bits 0/1) it also copies the 585 mA to `usv_current_set[c]` (`0x401D42`) unless
    `0x8AB46(1)` returns 2 or 3.
- `0xAFD10` (same task): when `0x40950B` b4 is set and the timer reaches 1, it copies group B into
  the active bytes, sets the timer to 200 and clears b4. If `0x4094F7` b7 drops, it clears b4, b3
  and b2. The running group then still times out within 2 s.

**Timing:**
- With T ≠ 0, group A runs for about (T + 1) × 10 ms, then group B runs for 2.0 s, then everything
  goes off.
- With T = 0, the one group runs for 2.0 s.
- To hold a state longer, resend the telegram before the 2 s runs out. Don't resend while a
  two-group request is still in group A, or you get NRC `0x21`.
- Send `30 10 07 00 00 00 00 00` to turn everything off at once.

The ±1-frame phase between the two counters is not pinned.

**Bit map.** These are firmware channels. The names match the SGBD's own `STEUER_I_O` table.
Wheel order is FL FR RL RR = wheel 0..3 (VL VR HL HR). Inlet channel = *w*, outlet = 4 + *w*.

| Wheel byte (A0/B0) | bit | ch | | Circuit byte (A1/B1) | bit | ch |
|---|---|---|---|---|---|---|
| `EVVL` inlet FL   | `0x01` | 0 | | `SV1` USV circuit 0 (front)  | `0x01` | 8 |
| `AVVL` outlet FL  | `0x02` | 4 | | `SV2` USV circuit 1 (rear)   | `0x02` | 9 |
| `EVVR` inlet FR   | `0x04` | 1 | | `EUV1` suction/HSV circuit 0 | `0x04` | 10 |
| `AVVR` outlet FR  | `0x08` | 5 | | `EUV2` suction/HSV circuit 1 | `0x08` | 11 |
| `EVHL` inlet RL   | `0x10` | 2 | | `PUMPE` return pump          | `0x10` | — |
| `AVHL` outlet RL  | `0x20` | 6 | | (bits 5–7 ignored)           |        |   |
| `EVHR` inlet RR   | `0x40` | 3 | | | | |
| `AVHR` outlet RR  | `0x80` | 7 | | | | |

What a set bit does:
- **Inlet bit:** the inlet is energised **closed** (`inlet_out_stage` = 229, about 1800 mA).
- **Outlet bit:** the outlet is energised **open**.
- **SV bit:** the USV is energised (585 mA setpoint).
- **EUV bit:** the suction valve is energised open.

How the circuit valves map to channels:
- ch 8/9 are the USVs. The drive writes their current to `usv_current_set[c]`.
- ch 10/11 are the circuit valves that `pump_circuit_demand(c)` (`0x88A18`) opens when the pump
  draws from the master side. That is consistent with HSV/suction valves.
- Circuit 0 = wheels 0/1 (front) per `circuit_wheel_map` `0xDA1B8`.
- The physical USV/HSV labels are inferred from these callers.

**Preconditions not in the handler:** run this at standstill, ignition on, in `10 87`, with
`3E` TesterPresent kept up. The handler itself has no speed check.

**Bleed procedure shape.** Repeat telegrams of this service with `3E` between them:
1. Close the inlets of the wheels you're not working on.
2. Run the pump.
3. Open outlets to push air out of the LPA/pump circuit while the bleed nipple is cracked.
4. End with all-off.

The fixed groups that the `NA_ENTLUEFTUNG_*` jobs send are not transcribed here.

### Group B — sensor & valve calibration (Abgleich) — SID `31` + `33`  [fw/sgbd]

Start with `31 <id>`, fetch result with `33 <id>` (loop up to ~20 s until final).

| Routine id | Job | Calibrates |
|-----------:|-----|-----------|
| `20` | `DRUCKSENSOR_DSC_ABGLEICHEN` | brake-pressure transducer(s) |
| `21` | `LENKWINKEL_DSC_ABGLEICHEN` | steering-angle sensor zero |
| `22` | `QUERBESCHLEUNIGUNG_DSC_ABGLEICHEN` | lateral-accel sensor |
| `24` | `LAENGSBESCHLEUNIGUNG_DSC_ABGLEICHEN` | longitudinal-accel sensor |
| `28` | `ABGLEICH_ANALOG_EV` | analog inlet valves |
| `29` | `ABGLEICH_ANALOG_MCI_V` | analog MCI (master-cyl isolation) valve |

```
10 81 -> 10 87                               ; no 27 needed (§3a)
31 <id> 00              -> 71 <id>            ; start; arg byte 0x409535 MUST be 0; sensor bit in 0x40200C must be set
                                              ;   else 7F 31 12 (length/arg) or 7F 31 22 (sensor not ready)
33 <id>                 -> 73 <id> <t1 v1 t2 v2>   ; STAT_ERGEBNIS_BYTE_TEXT/WERT pairs
   (repeat 33 until status leaves in-progress, max ~20 s; NRC 23 = keep polling)
20
```
Result text mapping: SGBD table `ABGLEICH_V_ERGEBNIS`. `33` is only valid for ids `21/28/29`;
pressure/accel ids report completion via their status DID / inline `71` data.

### Group C — RPA (tyre-pressure monitor) — SID `31`  [sgbd]

| Routine id | Job | Action |
|-----------:|-----|--------|
| `25` | `RPA_RESET` | reset/relearn tyre-pressure baseline |
| `26` | `RPA_EOL_PASSIV` | end-of-line passive |

```
31 25  -> 71 25        ; after a tyre change, at standstill
31 26  -> 71 26
```
Both are gated by a variant check (`0xCF478`) — NRC `22` on non-RPA variants.

### Group D — misc outputs & plausibility — SID `31`  [sgbd/fw]

| Routine id | Job | Action |
|-----------:|-----|--------|
| `27` | `DF_AUSGANG_AKTIVIEREN` | activate a diagnostic output (arg selects channel → `0x4033D8`) |
| `30` | `LAENGSBESCHLEUNIGUNG_PLAUSICHECK_PASSIV` | disable long-accel plausibility check |
| `31` | `_CCP_MODE` | enter CCP mode |

### Group E — authentication & flash — SID `31`  [fw-verified]

| Routine id | Job | Action |
|-----------:|-----|--------|
| `07` | `AUTHENTISIERUNG_ZUFALLSZAHL_LESEN` | §3c challenge |
| `08` | `AUTHENTISIERUNG_START` | §3c response → level 5 |

Flash jobs (`FLASH_LOESCHEN`, `FLASH_SIGNATUR_PRUEFEN`, `FLASH_PROGRAMMIER_STATUS_LESEN`) run in
`10 85` after level-5 auth, using the low routine local-ids (`31 02 …` erase, etc.) handled by
the bootloader. Full reflash sequence: `FACTS.md` flash section. **Out of scope for servicing;
listed for completeness — do not invoke casually.**

---

## 7. Worked byte sequences (KWP payloads; wrap per §1)

**Steering-angle calibration**
```
10 81 ; 10 87                         ; no 27 needed (§3a)
31 21 00              -> 71 21         ; arg byte must be 0; needs 0x40200C b5 (steering ready) else 7F 31 22
33 21                 -> 73 21 <result>     ; repeat until final
20
```

**Valve drive** (example built from the §6 group A bit map. It is not a BMW preset.)
```
10 81 ; 10 87
30 10 07 00 00 00 57 10  -> 70 10 07     ; T=0: all inlets closed + FL outlet open + pump, 2 s
3E                       -> 7E           ; keep the session up; resend the 30 within 2 s to hold
30 10 07 55 00 32 00 00  -> 70 10 07     ; all inlets closed for ~510 ms, then all off for 2 s
30 10 07 00 00 00 00 00  -> 70 10 07     ; everything off now
20
```

**Level-5 auth (only needed before flashing)**
```
10 81 ; 10 87
31 07 03 27 3C 00 00  -> 71 07 <rnd[8]>
31 08 <md5[16]>       -> 71 08 00
```

---

## 8. Open items

- The fixed valve groups the SGBD `NA_ENTLUEFTUNG_*` jobs send are not transcribed. The payload
  layout and bit map (§6 group A) are firmware-verified.
- `30` timing: the exact ±1-frame phase between the drive countdown (`0xB0154`) and the group-B
  switch (`0xAFD10`).
- Meaning of the `30` busy check `0x8A906`, the USV-current skip `0x8AB46(1) ∈ {2,3}`, the
  execution gate `0x4094F7` b7, and the `0x40288C` b4/b7 refusal.
- **[cap]** Exact BMW ISO-TP PCI nibbles for multi-frame (`0x6F1` address-byte framing) — confirm
  with any captured multi-frame exchange.
- `33` result byte semantics per calibration id (`ABGLEICH_V_ERGEBNIS` table) not yet transcribed.

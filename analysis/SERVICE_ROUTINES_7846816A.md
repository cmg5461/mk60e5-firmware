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
10 81            -> 50 81        ; StartCommunication; this ALSO writes 0x409537 = 3 (see §3)
10 87            -> 50 87        ; ECUAdjustmentMode (does NOT touch the token)
(…routine…)
20               -> 60
```

**SecurityAccess `27` is NOT required for the `31` service routines.** [fw-verified, capture-verified]
The token `0x409537` is set to **3 by the StartCommunication/connect handler itself** (`kwp_81_comm`
`0xB33B0`: `movi r6,3 / st.b r6,(0x409537)`), so after any normal connect the `31` gate is already
satisfied with no seed/key. A live bus capture confirms `31 22 00` succeeding straight after
`10 87 05` with no `27` anywhere in the session. Use `27 03/04` **only** to *restore* token 3 after
something else overwrote it in the same session (e.g. a `22 30 00` coding read stamps it to 51, §3b).

---

## 3. Access model — the `0x409537` sequence token

`0x409537` is **not** a monotonic security level. It is a single "last-qualifying-operation"
token: each privileged service requires the token to equal the specific value stamped by *its*
prerequisite step, and whatever ran last wins. Two layers check it.

**Dispatcher layer** (`0xB11B8`): before calling a handler, requires `0x409537 ==
serviceTable[SID].accessByte`, unless that byte is `0xFF` (wildcard). Service table `0xF30A0`,
12-byte records `[SID][accessByte][2][handler:4]`. Wildcard SIDs (run at any token): `10 27 30
31 3b 2e 3e 29 28`. Fixed-token SIDs: `20`→1, `81/82`→1, `1a 21 33 11`→2, `14 17 22`→3,
`18`→4, `23`→6, `09 3d`→7.

**Handler layer**: `31`, `2E` and others re-check the token inside, against a value specific to
the sub-function:

| Operation | Required `0x409537` | Set by (the prerequisite) |
|-----------|--------------------:|---------------------------|
| `31` calibration/actuation routines `0x20`–`0x31` | **3** | **StartCommunication `81` (`0xB33B0`)** — i.e. the connect itself; `27 03/04`, ClearDTC `14` and the `30/31/33` handlers also re-stamp 3 |
| `31 07` RequestForAuthentication | 7 | (flash elevation path) |
| `31 0A` | 2 | — |
| **`2E 30 00` coding write** | **51 (`0x33`)** | **reading `22 30 00` first** (`0xB2644`) |

So the token value that unlocks a `31` routine (3) is different from the one that unlocks a
coding write (51). They are reached by different prerequisites and **overwrite each other** — do
the coding read-stamp and the routine `0x27` in separate sessions, not interleaved.

Token 3 is also stamped by StartCommunication SID `0x81` (`0xB33B4`, the connect — but its own
gate needs token 1, so only from idle), ClearDTC `0x14`, and the `0x30/0x31/0x33` handlers. The
`10` session services (`10 81`, `10 87`, `10 87 05`) **never** change the token. `0x27` is the
robust choice because it is the only token-3 setter whose dispatcher byte is wildcard (runs from
any token, e.g. after a `22`-read has left 51). The dispatcher only *compares* the token; it never
stores the table byte. **Open (needs bench):** the fixed-token table can't be fully reconciled
with observed multi-service sessions (`1A`/`33`/`20`) from static analysis — probe `1A 80` as the
first request after connect, and `33 28` right after a good `31 28`, to pin the connect-layer token
dynamic.

### 3a. SecurityAccess `27 03/04` — one of several token-3 setters, **not** required for `31`  [fw: `kwp_27` `0xB14C2`]
`27 03` → `67 03 <seed16>`; `27 04 <key16>` → `67 04`, and on a correct key sets `0x409537 = 3`
(`0xB1580`) plus coding level `0x409513 = 3`. Granted only inside ECUAdjustmentMode (`10 87`).
`seed = (u16 @0x40095C) XOR 0x3008` (→ `0x53A1` if zero); key = `ROR16(seed,3)` → bit
swap/complement network → XOR image constant (full algorithm in `analysis/7846816A_symbols.md`).
It is redundant for the `31` service routines because StartCommunication already left the token at 3;
use it only to recover token 3 mid-session (see §2). Connect that works without it:
`10 81 → 10 87 → 31 <id> 00`.

### 3d. The real `31` gate and preconditions  [fw-verified: `kwp_31_start_routine` `0xB2B1C`]
The `31` handler does **not** call SecurityAccess. It runs two internal checks, then dispatches the
routine body through a second jump table. Both checks read the request's routine-id byte from
`0x409534` and its argument byte from `0x409535` (populated from the diag RX buffer).

**Check 1 — access/arg gate** (`0xB2B1C`→`0xB2C82`; jump table `0xB2B98`, index = `id − 5`) → **NRC `0x12`** on fail:
- routine id in table range (`5`–`49`);
- routines `0x20`/`0x22`/`0x24` share the handler at `0xB2C72`, which requires the **argument byte
  `0x409535 == 0`** — so send the full 3-byte payload (`31 24 00`), not a 2-byte `31 24`;
- `0x409537 == 3` (the connect already set this; see §2/§3).

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

On pass the handler re-stamps `0x409537 = 3`, sets the response-ready flag `0x409435 = 1`, and the
routine body sets its own completion bit in `0x40200C`/`0x40200D` (e.g. `31 24` sets `0x40200D` b7).

### 3b. Coding write — `2E 30 00`, unlocked by the read, **no `0x27`**  [fw-verified, capture-verified]
Coding does **not** use SecurityAccess. The unlock is the coding *read*, which stamps the token.
This is the live-captured working path (`~/source/wheelspeed/coding_write_dump.txt`):

```
22 30 00                 -> 62 30 00 <48 bytes>   ; read handler 0xB2610: reads NVM block 10 via
                                                   ; descriptor 0xF31FC AND stamps 0x409537 = 51
10 87 05                 -> 50 87                  ; coding session; only READS 0x409537, token survives
2E 30 00 <48 bytes>      -> 6E 30 00               ; write handler 0xB2A16
```

Write handler `0xB2A16` gate, in order:
1. `0x409537 == 51` else **NRC `0x12`** (`0xB2A1E`). This is why a session-then-write with no
   prior `22 30 00` fails — the token was never stamped.
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
- The token read need not be *immediately* before the write (the `10 87 05` session is
  token-transparent), but **nothing that re-stamps `0x409537` may run in between** — including a
  `31`-routine `0x27` (which would stamp 3) or another DID read. Keep coding and routine sessions
  separate.
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
| `12` | subFunction / sequence not supported | `31` access/arg gate (§3d): token `0x409537 ≠ 3` (no real connect), non-zero argument byte `0x409535`, bad routine id, or mis-framed request landing garbage in `0x409535` |
| `21` | busyRepeatRequest | `0x40950B` b4 set — prior routine still owns the actuators |
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

### Group A — valve/pump actuation & **brake bleed** — SID `30` InputOutputControl  [fw: `kwp_30` `0xB1702`]

This is the bleed / valve-drive path, **not** a `31` routine. Request form:

```
30 <LID> 07 <actuation payload>
   LID = 10  -> expected total len 8   (STEUERN_DIGITAL, one short group)
   LID = 20  -> expected total len 10  (STEUERN_DIGITAL_DX, two groups)
-> 70 <LID> 07 …     ; status in JOB_STATUS, NRC on fault
```

The handler sets routine state `0x409537=3`, runs the three circuit self-checks
(`0x060100/0200/0400` via `0xB4312`), then parses the actuation payload from the diag buffer
`0x40331D` (offset 5+): valve-select nibble, pump bit, changeover/high-pressure bits, and a
PWM/time word written to `0x4094E6`.

**Actuator vector** (SGBD order; firmware 12-solenoid map `0xD7634`, test order
`0xF2EF0 = [0,4,1,5,2,6,3,7,8,9,10,11]`):

| Token | Meaning | Firmware channel | Driver |
|-------|---------|------------------|--------|
| `EVVL EVVR EVHL EVHR` | Einlassventil (inlet), per corner | ch 0–3 | analog current, CS5 |
| `AVVL AVVR AVHL AVHR` | Auslassventil (outlet/dump) | ch 4–7 | digital latch, CS4 |
| `SV1 SV2` | circuit changeover (USV) | ch 8–9 | CS4 |
| `EUV1 EUV2` | inlet-changeover / high-pressure (HSV) | ch 10–11 | CS4 |
| `PUMPE` | return-pump motor | — | timer-PWM `0xF80000` |

Semantics **[sgbd]**: parameter `E` = send the session/diag-mode telegram **then** the
actuation sequence; `W` = actuation sequence only (session already open). A sequence is two
actuator groups separated by a wait time (Zeitglied, ms), plus a trailing job-status wait.
Example SGBD preset: `"E,EVVL,EVVR,SV1,800,PUMPE"` = open both front inlets + circuit-1
changeover, wait 800 ms, run pump.

Jobs on this path:

| Job | Routine | Meaning |
|-----|---------|---------|
| `STEUERN_DIGITAL`, `_DX` | `30 10/20 07` | generic valve+pump drive |
| `STEUERN_DIGITAL_BLS` | `30 10 07` | loop the sequence **until the brake-light switch releases** (max 200 cycles ≈ 8 s) — pedal-pump bleed |
| **`NA_ENTLUEFTUNG_RE/LI/VA/HA_DX`** | `30 10 07` wrappers | **service bleed**: Rechts / Links / Vorderachse / Hinterachse (right / left / front-axle / rear-axle), fixed per-corner valve preset + integrated `DIAGNOSE_MODE` |
| `STEUERN_HYDRO_SPUELEN` | `30 10 07` | flush HCU after fill (factory only) |

> **[cap]** The exact per-bit mapping inside the `<actuation payload>` and the fixed presets the
> `NA_ENTLUEFTUNG_*` jobs load are built in the SGBD BEST bytecode, not in strings. Confirm the
> wire bytes with one INPA/ISTA bleed capture before trusting a hand-built payload; the actuator
> *set* and ordering above are firmware-exact, the byte packing is not yet.

**Bleed procedure (per corner/axle):**
```
10 81 -> 10 87                     ; ECUAdjustmentMode, vehicle stationary, ignition on
30 10 07 <preset for corner>       ; = NA_ENTLUEFTUNG_xx ; opens inlet(s)+changeover, runs pump
  … operator cracks the caliper nipple while the pump cycles …
30 10 07 00…                       ; release / idle actuators
20                                  ; end session
```
Keep `3E` flowing throughout. Repeat for RL / RR / FL / FR (BMW sequence per the ISTA plan).

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
10 81 -> 10 87                               ; connect already set token 0x409537=3; NO 27 needed (§3d)
31 <id> 00              -> 71 <id>            ; start; arg byte 0x409535 MUST be 0; sensor bit in 0x40200C must be set
                                              ;   else 7F 31 12 (gate/arg) or 7F 31 22 (sensor not ready)
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
10 81 ; 10 87                         ; connect sets token 0x409537=3; no 27 needed (§3d)
31 21 00              -> 71 21         ; arg byte must be 0; needs 0x40200C b5 (steering ready) else 7F 31 22
33 21                 -> 73 21 <result>     ; repeat until final
20
```

**Front-axle bleed** (preset bytes = `[cap]`, structure firmware-exact)
```
10 81 ; 10 87
30 10 07 <VA preset>  -> 70 10 07 …          ; pump + front inlets/changeover cycling
   … crack FL then FR nipples …
30 10 07 00 …         -> 70 10 07 …          ; actuators off
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

- **[cap]** `30 10/20 07` actuation-payload bit layout, and the `NA_ENTLUEFTUNG_*` corner presets
  (in SGBD BEST bytecode). One INPA/ISTA bleed capture closes this.
- **[cap]** Exact BMW ISO-TP PCI nibbles for multi-frame (`0x6F1` address-byte framing) — confirm
  with any captured multi-frame exchange.
- `33` result byte semantics per calibration id (`ABGLEICH_V_ERGEBNIS` table) not yet transcribed.

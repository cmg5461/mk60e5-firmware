# Wheel-sensor type selector investigation (1M 7846411A; M3 7846816A compared)

> **Update 2026-10-06:** Conclusions here that non-VDA/E46 sensors need hardware are **superseded**. ASIC register 0x28C is a
> per-channel VDA/2-level mode mask, and with both-edge timer capture (mode 0xA1) E46 sensors read on all four
> wheels. See `docs/E46_SENSOR_FIRMWARE_PATCH.md` and FACTS.md.


Agent-derived (Sonnet), **key claims verified by main session**: BFU front/rear values identical in
both cars `[100,72,2073,2073,48,48]`; the `60F2` direction-mask literal present at 1M 0x0B91AC and
M3 0x0B93C4; invert mask 0xD79FC = `05 09 …` on 1M; `sub_075E94` confirmed. CPU addresses; file = CPU+0x8000.

## Summary answers (to the user's 3 questions)
1. **Per-axle sensor-type selector: NONE found [agent, high].** No calibration constant or coding/NVM
   parameter switches a channel between active-encoded (VDA) and passive (toothed-ring) handling. All
   four channels get identical ASIC init, poll, decode, and presence check. BFU (0x41F04) has identical
   front/rear values; M3's BFU (0x41CE4) is the same.
2. **Where it would be: n/a.** Nearest items:
   - **Direction-expected mask:** literal `60F2` (`movi r2,15`) at 0x0B91AC (M3: 0x0B93C4) = all four
     wheels expect direction. 0x075ABA accepts {0,1,2,3,15} and returns 15 for all.
   - **One coding bit reaching the decode path (0x075ADE):** flips **direction polarity only**. Chain:
     raw coding byte10 bit6 → word 0x4031F4 bit8 → getter 0x0D02EE → invert mask 0xD79FC[bit] = 05 or 09
     (wheel 0 plus wheel 2 or 3).
   - **ASIC constant tables** 0xD75A0/0xD75D2/0xD7607: written unconditionally, identical on all channels
     (regs 0x154/15C/164/16C = 0x1B), identical in M3. The only place a per-channel input mode *could*
     live. [needs-hw: ASIC datasheet]
3. **Front vs rear: no gate exists [agent, med].** Firmware has no front-only or rear-only passive concept.
   0x0B9118 tests `0x4029D6 & (1<<w)` per wheel and tolerates <4 expected wheels, so a partial mask would
   *work*, but the mask source is the constant 15 — a patch is required. A passive axle would need: a
   different ASIC input stage (HW; VDA is current-mode 7/14/28 mA), a patched direction mask, AND a patched
   presence check (below).

## New findings beyond the wss report
- **Variant word 0x4031F4/0x4031F6 = the packed BMW coding block.** Module 0x0D0000..0x0D0A00; installer
  0x0D0926 (XOR checksum 0x0D03F8, unpack/validate 0x0D0418, bit-packer 0x0D055A). NVM block-7 reload
  (0x0D0154 via 0x06E4CE) checked against 0x4030DC; mismatch → DTC 0xC0040. ~150 getter call sites at
  0x0D0240..0x0D03E2. **A.b8 = raw10.b6 is the only coding bit in the wheel-speed chain.** A.b4 (raw3.b6)
  and B.b4 (raw10.b4) enable the tooth monitor 0x0A9F7E (with cal words 0x41F68/6A, both 0 here) — look
  like platform bits, not sensor-type.
- **Sensor-presence check (0x075E94).** Popcounts the ASIC B word at 0x400F20+4*idx; ≥3 bits → `0x4010CE[w]=1`
  ("frame seen"). At cycle counter 0x400960 == 100, a wheel with no frame and no DTC gets `0x400952[w] |= 0x31`
  → 0x075D9A. Identical all four wheels, so an all-passive channel would be flagged as a sensor fault unless
  patched. Alt branch 0x075F1C is dead (0x075AA0 returns 4 for every wheel) — possibly a leftover build-time
  sensor-type variable [agent, low].
- **Air gap has no consumer [agent, med].** Quality bytes 0x400A3C/44/48 written by 0x075BD0, referenced
  nowhere → no air-gap fault in the app.
- **A wheel without direction keeps its speed [verified].** 0x0B9524 returns 0 when D6==0 or D9 bit w clear;
  0x0CE sign callbacks keep speed positive. Magnitude always from edge timing (0x0752B8), so **VDA data
  consumption is separable from edge timing in code.**
- Stock no-direction behaviour: counter 175 at 4.01..55 km/h → fault 0xF5A74[w], sets 0x4029DA bit4 (wss report).

## Conclusion for the user's hypothesis
Both 1M and M3 hard-configure **all four channels for VDA active-encoded sensors**. There is no parameter
to enable passive toothed-ring handling on either axle. The "325i passive rear by parameter" behaviour is
neither supported nor refuted by this binary beyond "no such selector here"; if it exists it would be a
different flash/variant (or ASIC-side). Edge *timing* is sensor-agnostic (would count toothed-ring edges),
but running passive would require HW input-stage changes plus patches to the direction mask (0x0B91AC) and
the presence check (0x075E94) — and still wouldn't flash without defeating the ROM self-test + BMY signature.

## Open / needs hardware or coding dump
1. ASIC register semantics — per-channel input-mode field? Best evidence: diff the user's E46-configured
   **E85 motorsport flash** at 0xD75A0/0xD75D2, the `60F2` literal, and the 0x075E94 presence check. [needs-hw]
2. Which diagnostic/NVM address block 7 maps to; a real coding dump (raw3/10/13/14/15). [needs-hw]
3. ASIC B-word contents for a non-VDA channel. [needs-hw]
4. Getter-to-bit matching for A.b11..b13, B.b2/b8 incomplete (none in the wheel-speed path).

---
name: firmware-system-analysis
description: Method for an end-to-end analysis of one MK60E5 firmware system (e.g. AYC, TCS, BCO, vref, a monitor) from the disassembly — locate it, read it, pin units, verify formulas by replaying the code, trace consumers, find numeric limits, and write it up as an analysis doc plus symbol entries. Use when asked to work out how a controller or subsystem works, what its parameters do, or to document it.
---

# Firmware system analysis

The goal is a document a reader can use to understand one system as it sits in the stock image: its inputs and
preconditions, its model or estimator, the decision logic and thresholds, the response, the modes, how other systems
consume it, its numeric limits, and what each calibration does. `analysis/AYC_7846816A.md` and
`analysis/DSC_STEERING_AND_VEHICLE_MODEL_7846816A.md` are worked examples of the bar.

Everything is read from code. Every claim carries a tag saying how it was established, and anything you did not
verify goes in an Open list rather than into the prose.

## Ground rules for this repo

- Addresses are **CPU addresses**. File offset in a bank-0 image = CPU + 0x8000. RAM is 0x400000–0x40C000.
- The listing is `analysis/7846816A_main.lst` (M3). `7846411A` is the 1M and `6862873A` the non-M; compare when useful.
- Tags: **[C]** read from code on this image, **[C-1M]** read on the 1M and carried over because the functions are
  opcode-identical, **[I]** inferred, **[U]** user-supplied, **[open]** not traced. Confidence in symbol tables:
  high / med / low (definitions at the top of `7846816A_symbols.md`).
- Bank images and scratch scripts go in the session scratchpad, never in the repo:
  `python tools/bmw_hex2bin.py fw/7846816A.0pa -o <scratch>/banks` gives `<scratch>/banks/7846816A_00000000.bin`.
- Don't regenerate `xdf/MK60E5_7846816A.xdf` with `make_xdf_m3.py`: the checked-in file has hand-added fields the
  generator would drop. Record new calibrations in the symbols file and say the XDF labels are stale.
- Don't commit unless asked. The sister repo `../mk60e5_patcher` must never receive firmware bytes.
- Docs describe the stock image. Keep car- or customer-specific findings out of `analysis/` docs (they go in memory
  or the patcher).

## 1. Start from what is known

Before reading any code, collect what earlier work established, and list it with its tag:

```
grep -n -i "<system>\|<key RAM>\|<key fn>" FACTS.md analysis/*.md analysis/7846816A_symbols.md
ls analysis/agents/                      # per-topic agent work dirs, e.g. m3ayc, yawmodel, abs_full
grep -n "<addr>" tools/make_xdf_m3.py    # calibration field notes
```

Also read the memory index for this project. Older entries can be wrong: earlier passes labelled the tracks "mm"
(they are Q10 m), and named a mid-function label as if it were a function entry. Treat old names as leads, and confirm
anything you build on.

## 2. Locate the code

- **Cross-references.** Literal-pool loads print the value as a comment, so every reference to an address is
  `grep -i "= 0x00<addr>\b" analysis/7846816A_main.lst`. A `lrw` followed by `ld` is a reader, and one followed by
  `st` is a writer.
- **Enclosing function** of a line:
  `n=$(grep -n "^  <ADDR>:" LST | cut -d: -f1); head -n $n LST | grep "^sub_" | tail -1`.
  Loop this over every xref to get a reader/writer map. It is the fastest way to see which systems touch a variable.
- **Calibration blocks.** The directory at 0x40300 lists the tagged blocks (ABS, CSI, TCS, AYC, BCO, COA, ...). Const
  tables also live in 0xD6xxx–0xF6xxx.
- **Indexing patterns.** Spotting these tells you a table's shape:
  - `ld.b rX,(coding,k)` then `lsli rX,1` → an s16 row with one entry per coding value.
  - `ixw` with the same index → 2-element pairs per entry (stride 4).
  - `+ 0x22·m` → `curve_t` records per mode.
- **Code is interleaved with literal pools.** The listing is a linear sweep, so pool data decodes as junk
  instructions. Follow branches; don't read straight down.

## 3. Read the arithmetic

M·CORE idioms that recur in this firmware:

| Pattern | Meaning |
|---|---|
| `mov r1,x; asri r1,N-1; lsri r1,32-N; addu x,r1; asri x,N` | signed x / 2^N, truncated toward zero |
| `btsti x,31; bf; addi x,2^N-1; asri x,N` | the same |
| `jsri 0x6D102` | `sat_s16` (clamp to s16) |
| `jsri 0x6D0CC` | `abs_sat16` |
| `jsri 0x919E2` | `div_sat16(num, den)`: clamp num to ±32767·den, then divide |
| `jsri 0x710FC` | `curve_interp_s16`, which reads `curve_t {lo, hi, n, x[n-1], c[n], k[n]}` |
| `jsri 0x7119E` | `interp_linear_xy`, an end-clamped xs/ys table |
| `mulsh` | 16 × 16 signed multiply |
| `mult` | 32-bit, wraps silently |
| `divu` | unsigned; a negative divisor gives garbage, not an error |
| `movi` | immediates only go to 127; larger constants come from `bseti`/`bmaski` or `lrw` |
| a value stored with plain `st.h` and no saturation call | wraps at s16 |

Write each output as a closed formula in the physical inputs. Note every truncation, saturation and wrap: they are
where the limits come from (§6).

## 4. Pin the units

A formula is not understood until its units close. Techniques that worked:

- **Round numbers.** Thresholds that come out round in a candidate unit confirm the LSB. For example, 1396 / 2792 /
  698 are exactly 4 / 8 / 2 °/s at 1/20000 rad/s.
- **Reproduce a known physical value.** Track 1575 → 1.538 m means Q10 m. 0x558C works out to 1.27 g. The loader's
  v_ch reproduces the known 1M value.
- **Match a constant to a physical formula exactly.** The divisor 65536·61317 equals 4e8·1024·9.81/1000, which
  identified the 446 row as the sensor's lateral offset (the ω²·y term).
- **Check against the rest of the system.** A reconstructed signal should agree with independent ones: the yaw from
  wheel speeds, from lateral accel and from the steering model should agree in steady cornering.

## 5. Verify by replaying the code

`tools/mcore_replay.py` executes listing lines against a bank image. It follows calls, keeps a stack, and reports
RAM writes plus numeric events: 32-bit multiply overflow, divide by zero, unsigned divide by a negative divisor, and
`sat_s16` clamping (with the caller's address).

```
python tools/mcore_replay.py <bank0.bin> analysis/7846816A_main.lst 0x5DE44 0x5E424 \
    --ram 0x4031AB=0:1 --rom 0xD6F72=1100*12 --show 0x400AA4-0x400AFA
```

Use it in this order:

1. **Stock replay.** Run with stock inputs and compare against values already known (FACTS, earlier docs). This
   validates both the replay and your reading.
2. **Formula check.** Write your closed formulas in Python, then import `Replayer` and compare them with the replay
   over a few hundred random, physically sensible inputs. Report "matches within N counts for K random cases". If they
   disagree, the formula is wrong (in this session a hex constant was misread) or a wrap or saturation is missing.
3. **Range sweep.** Push inputs toward the extremes and record which output wraps or saturates first. That gives
   safe parameter ranges and the real constraint. Find the quantity that actually controls the limit: here "v_ch
   below 194 km/h", not a proxy ratio that only happened to correlate in one sweep.

The replay suits leaf computations: loaders, converters, model and estimator updates. Preset the RAM those functions
read. Don't trust it across code that touches hardware, the OS or CAN.

## 6. Trace consumers, gates and limits

- **Consumers.** For every output, list its readers (§2) and follow at least one level. This answers "what is it
  for", and often turns up couplings nobody listed (e.g. ABS reading the AYC target at 14 sites).
- **Gates.** Record what has to hold for the code to run or the output to be used: validity bits, fault-reaction
  bits, driver mode, coding, speed thresholds.
- **Storage formats.** Many signals are copied into narrow types (s8 at 0.01 g caps at 1.27 g). Find every ceiling
  between the sensor and the decision, and say what happens to the system just past it, in both directions of
  error.
- **Mode- or variant-indexed tables.** Compare them across all related systems that share the index before
  interpreting one table on its own. For example, the AYC tables and the TCS drive-slip tables share the DSC mode
  index, and only together do they show what the mode is for.

## 7. Write it up

**Analysis doc:** `analysis/<SYSTEM>_7846816A.md`. Use this structure, dropping sections that don't apply:

1. Title, one-paragraph scope, source note ("read from the disassembly, not bench-tested", address convention,
   tags, units), links to related docs.
2. Overview: an ASCII diagram from inputs to outputs, with function addresses.
3. Preconditions and inhibits.
4. Model or estimator: the inputs as calibration rows, the formulas, the derived quantities, and the constraints
   found by replay.
5. Decision logic: the error or condition, thresholds, hysteresis, persistence, with tables in physical units.
6. Response: what is commanded, how it is distributed, its rates and caps.
7. Modes and variants, compared against the systems that share the index.
8. Coupling into other systems.
9. Numeric limits: a table of each limit, where it sits and its effect, plus what happens beyond it.
10. Parameters by effect: "to change X, use Y", with notes.
11. Open.

Use tables for calibrations: address, name, type and unit, stock value, meaning.

**Symbols** (`analysis/7846816A_symbols.md`), in the matching section:

- **Functions:** `| 0xADDR | \`ret name(type arg, ...)\` | conf | evidence |`, where the evidence is what the
  code does in one or two sentences, with key addresses.
- **RAM:** name, type (s16 / u8 / s8 and array size), unit or LSB, meaning, writer.
- **Calibrations:** name, type (`s16[12]`, `s16[3][4]`, `curve_t`), unit, stock value.
- Fix wrong earlier entries in place. Don't add a duplicate.

**Also update:**

- **FACTS.md:** a short dated entry only for verified, reusable facts, pointing to the doc.
- **Related docs:** a cross-link from the related doc. Leave the XDF alone, as in the ground rules.

**Report back:** what was verified and how, what is inferred, and what stays open. If an earlier statement (yours or
the repo's) turned out wrong, say so explicitly and fix it where it was written.

## Quality checklist

- [ ] Every formula has been checked against the code by replay, or is tagged [C-1M] / [I].
- [ ] Units close, with at least one physical sanity check per scaling.
- [ ] Each output has its consumers listed; each gate and mode dependency is stated.
- [ ] Saturations, wraps and storage-format ceilings are found, with the behaviour past them.
- [ ] Sign conventions are explicit, and both directions of error are discussed.
- [ ] Every calibration is listed with its address, type, stock value and effect.
- [ ] The Open list holds everything you did not trace; no guess appears as a fact.
- [ ] The symbols file is updated and stale earlier entries are corrected; there are no MR2- or customer-specific
      statements in `analysis/`.

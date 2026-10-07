#!/usr/bin/env python
"""MK60E5 (M3 7846816A) calibration <-> YAML, including the 12-entry per-variant
(coding-indexed) tables. `export` dumps a YAML you can edit; `apply` writes it back
to a copy of the image. Self-contained YAML (no PyYAML needed) for the fixed schema
below. XDF addr = CPU + 0x8000 = file offset. Edits change MISR + BMY -> use
--resign (or run tools/bmy_resign.py fix) before flashing.

The per-variant tables are 12 long, indexed 0..11 by the active EEPROM coding
variant (0 sedan, 1 Custom ESM, 3 coupe, 4 convertible, 5/8/9 Competition
sedan/coupe/convertible, 10 GTS coupe, 11 GTS sedan; 2/6/7 not identified). The ABS *entry-slip* target is intentionally SINGLE (one global curve) —
only the decel/threshold *shaping* (speed-term, g-term, decel floors) and the
chassis/DSC block are per-variant.

Usage:
  python tools/cal_yaml.py export --out cal.yaml
  python tools/cal_yaml.py apply cal.yaml --out flash/bin/7846816A_cal.bin --resign
"""
import argparse, os, re, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IMG = os.path.join(os.path.dirname(HERE), "flash", "bin", "7846816A_00000000.bin")

# group, name, addr, type, scale, unit, count   (count 1 = scalar, 12 = per-variant)
SCHEMA = [
    # --- single / global ---
    ("single", "circ_front",            0x49cf4, "u16", 1.0,   "mm",     1),
    ("single", "circ_rear",             0x49cf6, "u16", 1.0,   "mm",     1),
    ("single", "standstill",            0x49cf2, "u16", 0.01,  "km/h",   1),
    ("single", "abs_entry_debounce",    0x48db4, "u16", 1.0,   "frames", 1),
    ("single", "abs_entry_clamp_min",   0x48db6, "u16", 0.01,  "km/h",   1),
    ("single", "abs_entry_clamp_max",   0x48db8, "u16", 0.01,  "km/h",   1),
    ("single", "abs_entry_breakpt0",    0x48dbc, "u16", 0.01,  "km/h",   1),
    ("single", "abs_entry_intercept0",  0x48dbe, "u16", 0.01,  "km/h",   1),
    ("single", "abs_entry_intercept1",  0x48dc0, "u16", 0.01,  "km/h",   1),
    ("single", "abs_entry_slope0",      0x48dc2, "s16", 1/1024., "/km/h", 1),
    ("single", "abs_entry_slope1",      0x48dc4, "s16", 1/1024., "/km/h", 1),
    ("single", "abs_decel_base",        0x48620, "s16", 0.01,  "g",      1),
    ("single", "abs_decel_floor",       0x4861e, "s16", 0.01,  "g",      1),
    # --- 12-entry per-variant (coding index 0..11) ---
    ("variant", "decel_floor_lt20",     0x48644, "s16", 0.01,  "g",      12),
    ("variant", "decel_floor_lt60",     0x4865c, "s16", 0.01,  "g",      12),
    ("variant", "mass",                 0xdef72, "u16", 1.0,   "kg",     12),
    ("variant", "l_f_front_to_cg",      0xdef42, "u16", 1.0,   "mm",     12),
    ("variant", "l_r_cg_to_rear",       0xdef5a, "u16", 1.0,   "mm",     12),
    ("variant", "track_front",          0xdefa2, "u16", 1.0,   "mm",     12),
    ("variant", "track_rear",           0xdefba, "u16", 1.0,   "mm",     12),
    ("variant", "Jz_yaw_inertia",       0xdef8a, "u16", 1.0,   "kg.m2?", 12),
    ("variant", "Cf_front_cornering",   0xdeeca, "u16", 1.0,   "N/rad?", 12),
    ("variant", "Cr_rear_cornering",    0xdeee2, "u16", 1.0,   "N/rad?", 12),
]

# per-variant CURVE families: base addr, per-variant stride, nvar, sub-fields
#   sub = (name, rel_offset, count, type, scale, unit)
CURVES = [
    ("speed_term_front", 0x48412, 0x28, 12, [
        ("clampmin", 0x00, 1, "s16", 0.01,    "g"),
        ("clampmax", 0x02, 1, "s16", 0.01,    "g"),
        ("x",        0x06, 5, "u16", 0.01,    "km/h"),
        ("c",        0x10, 6, "s16", 0.01,    "g"),
        ("k",        0x1c, 6, "s16", 1/1024., "Q10"),
    ]),
    ("g_term", 0x48674, 0x40, 12, [
        ("clampmin", 0x00,  1, "s16", 0.01,    "g"),
        ("clampmax", 0x02,  1, "s16", 0.01,    "g"),
        ("x",        0x06,  9, "u16", 0.01,    "g"),
        ("c",        0x18, 10, "s16", 0.01,    "g"),
        ("k",        0x2c, 10, "s16", 1/1024., "Q10"),
    ]),
    # Cornering lateral-g PRESSURE term (ABS classify 0x51B54 -> code-32 exec 0x58FF4).
    # BOTH curves take x = |lateral accel| (byte 0x408ECA, ~0.01 g/count); curve output is
    # multiplied x100 -> 0.01 bar. Output RISES with lateral g (A 26->49 bar + 5 bar boost
    # >0.8 g; B 14->40 bar) = a lateral-LOAD pressure term, NOT a knockdown. (The code-32
    # rear knockdown uses a separate pct byte 0x408DE0, producer untraced.) Exact role of
    # these curves (per-wheel ceiling vs reference) UNCONFIRMED - confirm sign on a dynamic
    # trace before flashing. n=4: lo,hi @+0/+2; x[3] @+6; c[4] @+0xc; k[4] @+0x14.
    ("lat_g_press_a", 0x48e0a, 0x00, 1, [   # |lat g|; primary (+5 bar boost >0.8 g, hard-coded)
        ("clampmin", 0x00, 1, "s16", 1.0,     "bar"),
        ("clampmax", 0x02, 1, "s16", 1.0,     "bar"),
        ("x",        0x06, 3, "s16", 0.01,    "g"),
        ("c",        0x0c, 4, "s16", 1.0,     "bar"),
        ("k",        0x14, 4, "s16", 1/1024., "bar/.01g"),
    ]),
    ("lat_g_press_b", 0x48e26, 0x00, 1, [   # |lat g|; companion
        ("clampmin", 0x00, 1, "s16", 1.0,     "bar"),
        ("clampmax", 0x02, 1, "s16", 1.0,     "bar"),
        ("x",        0x06, 3, "s16", 0.01,    "g"),
        ("c",        0x0c, 4, "s16", 1.0,     "bar"),
        ("k",        0x14, 4, "s16", 1/1024., "bar/.01g"),
    ]),
]

# human note per curve family (for the export header comment)
CURVE_NOTES = {
    "speed_term_front": "deepens decel threshold vs vehicle speed",
    "g_term":           "adjusts decel threshold vs current decel",
    "lat_g_press_a":    "lateral-g pressure term vs |lat g| (0.01 bar); RISES with g, primary + boost",
    "lat_g_press_b":    "lateral-g pressure term vs |lat g| (0.01 bar); RISES with g, companion",
}

def _fmt(t): return ">h" if t == "s16" else ">H"
def _rng(t): return (-32768, 32767) if t == "s16" else (0, 65535)

def read_vals(buf, addr, t, n):
    f = _fmt(t)
    return [struct.unpack(f, buf[addr+2*i:addr+2*i+2])[0] for i in range(n)]

def cmd_export(buf, out):
    lines = [
        "# MK60E5 M3 7846816A calibration. addr = file offset (CPU+0x8000).",
        "# Edit the raw integer value(s); re-sign (MISR+BMY) before flashing.",
        "# per_variant tables are 12 long, coding index 0..11 (EEPROM-selected).",
        "# 0 M3 sedan, 1 Custom ESM, 2 ?, 3 coupe, 4 convertible, 5 Comp sedan, 6 ?, 7 ?,",
        "# 8 Comp coupe, 9 Comp convertible, 10 GTS coupe, 11 GTS sedan.",
        "# NOTE: abs_entry_* (the ABS entry-slip target) is SINGLE/global, not per-variant.",
        "",
        "single:",
    ]
    def emit(group):
        for g, name, addr, t, sc, unit, n in SCHEMA:
            if g != group:
                continue
            vals = read_vals(buf, addr, t, n)
            eng = [round(v*sc, 4) for v in vals]
            if n == 1:
                lines.append("  %s: {addr: 0x%05x, type: %s, scale: %s, unit: %s, value: %d}  # eng %s"
                             % (name, addr, t, sc, unit, vals[0], eng[0]))
            else:
                lines.append("  %s: {addr: 0x%05x, type: %s, scale: %s, unit: %s, values: [%s]}  # eng %s"
                             % (name, addr, t, sc, unit, ", ".join(str(v) for v in vals), eng))
    emit("single")
    lines.append("")
    lines.append("per_variant:   # index 0..11")
    emit("variant")
    lines.append("")
    lines.append("# per-variant CURVES (index 0..11). These + decel base/floor are the")
    lines.append("# wheel-DECEL-rate trigger (complement to the single entry-slip trigger).")
    lines.append("curves:")
    for fam, base, stride, nvar, subs in CURVES:
        note = CURVE_NOTES.get(fam, "")
        lines.append("  %s:   # %s" % (fam, note))
        for v in range(nvar):
            vb = base + v*stride
            parts = ["base: 0x%05x" % vb]
            for sname, roff, cnt, t, sc, unit in subs:
                vals = read_vals(buf, vb+roff, t, cnt)
                if cnt == 1:
                    parts.append("%s: %d" % (sname, vals[0]))
                else:
                    parts.append("%s: [%s]" % (sname, ", ".join(str(x) for x in vals)))
            lines.append("    %s[%d]: {%s}" % (fam, v, ", ".join(parts)))
    lines.append("")
    open(out, "w").write("\n".join(lines))
    print("wrote %s (%d scalar/variant params + %d curve families)" % (out, len(SCHEMA), len(CURVES)))

LINE = re.compile(r"^\s*(\w+):\s*\{addr:\s*(0x[0-9a-fA-F]+),\s*type:\s*(u16|s16),.*?"
                  r"(value|values):\s*(\[[^\]]*\]|-?\d+)\}", re.M)
CURVELINE = re.compile(r"^\s*(\w+)\[(\d+)\]:\s*\{base:\s*(0x[0-9a-fA-F]+),\s*"
                       r"clampmin:\s*(-?\d+),\s*clampmax:\s*(-?\d+),\s*"
                       r"x:\s*\[([^\]]*)\],\s*c:\s*\[([^\]]*)\],\s*k:\s*\[([^\]]*)\]\}", re.M)

def _ints(s):
    return [int(x) for x in s.split(",") if x.strip() != ""]

def cmd_apply(buf, yaml_path, out, resign, inplace, src):
    text = open(yaml_path).read()
    by_name = {s[1]: s for s in SCHEMA}
    changed = 0
    for m in LINE.finditer(text):
        name, addr_s, t, kind, valpart = m.groups()
        if name not in by_name:
            print("  skip unknown %s" % name); continue
        g, nm, addr, typ, sc, unit, n = by_name[name]
        if int(addr_s, 16) != addr or t != typ:
            print("  skip %s: addr/type mismatch vs schema" % name); continue
        if kind == "value":
            vals = [int(valpart)]
        else:
            vals = [int(x) for x in valpart.strip("[]").split(",") if x.strip() != ""]
        if len(vals) != n:
            sys.exit("%s: expected %d value(s), got %d" % (name, n, len(vals)))
        lo, hi = _rng(t); f = _fmt(t)
        for i, v in enumerate(vals):
            if not (lo <= v <= hi):
                sys.exit("%s[%d]=%d out of range %d..%d" % (name, i, v, lo, hi))
            off = addr + 2*i
            old = struct.unpack(f, buf[off:off+2])[0]
            if old != v:
                buf[off:off+2] = struct.pack(f, v); changed += 1
    # curve families
    cmap = {c[0]: c for c in CURVES}
    for m in CURVELINE.finditer(text):
        fam, var, base_s, cmin, cmax, xs, cs, ks = m.groups()
        if fam not in cmap:
            print("  skip unknown curve %s" % fam); continue
        _, base, stride, nvar, subs = cmap[fam]
        v = int(var); vb = base + v*stride
        if int(base_s, 16) != vb:
            print("  skip %s[%d]: base mismatch" % (fam, v)); continue
        want = {"clampmin": [int(cmin)], "clampmax": [int(cmax)],
                "x": _ints(xs), "c": _ints(cs), "k": _ints(ks)}
        for sname, roff, cnt, t, sc, unit in subs:
            vals = want[sname]
            if len(vals) != cnt:
                sys.exit("%s[%d].%s: expected %d, got %d" % (fam, v, sname, cnt, len(vals)))
            lo, hi = _rng(t); f = _fmt(t)
            for i, val in enumerate(vals):
                if not (lo <= val <= hi):
                    sys.exit("%s[%d].%s[%d]=%d out of range" % (fam, v, sname, i, val))
                off = vb + roff + 2*i
                if struct.unpack(f, buf[off:off+2])[0] != val:
                    buf[off:off+2] = struct.pack(f, val); changed += 1
    print("applied %d changed value(s)" % changed)
    dst = src if inplace else out
    open(dst, "wb").write(buf)
    print("wrote %s" % dst)
    if resign:
        r = subprocess.run([sys.executable, os.path.join(HERE, "bmy_resign.py"), "fix", dst, "-o", dst])
        if r.returncode != 0:
            sys.exit("resign failed")
    else:
        print("NOTE: not signed. Run `python tools/bmy_resign.py fix %s` before flashing." % dst)

def main():
    ap = argparse.ArgumentParser(description="MK60E5 M3 cal <-> YAML (incl. 12-variant tables)")
    ap.add_argument("--in", dest="img", default=DEFAULT_IMG)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export"); e.add_argument("--out", required=True)
    a = sub.add_parser("apply"); a.add_argument("yaml"); a.add_argument("--out")
    a.add_argument("--inplace", action="store_true"); a.add_argument("--resign", action="store_true")
    args = ap.parse_args()
    buf = bytearray(open(args.img, "rb").read())
    if args.cmd == "export":
        cmd_export(buf, args.out)
    else:
        if not args.inplace and not args.out:
            sys.exit("apply needs --out <path> (or --inplace)")
        cmd_apply(buf, args.yaml, args.out, args.resign, args.inplace, args.img)

if __name__ == "__main__":
    main()

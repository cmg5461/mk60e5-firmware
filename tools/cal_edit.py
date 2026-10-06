#!/usr/bin/env python
"""MK60E5 (M3 7846816A) ABS calibration editor — read/modify cal fields by index.

Fields are byte-verified against flash/bin/7846816A_00000000.bin. XDF address =
CPU + 0x8000 = file offset (what this tool uses). Values shown as RAW (what lands
in the bytes) and ENG (engineering units). Edits change MISR + the BMY signature,
so pass --resign (runs tools/bmy_resign.py fix) before flashing, or re-sign manually.

Usage:
  python tools/cal_edit.py list
  python tools/cal_edit.py get  <idx|name>
  python tools/cal_edit.py set  <idx|name>=<value> [more...] [--eng] [--out OUT] [--resign]
      <value> is RAW by default; with --eng it is engineering units (converted+rounded).
      Writes to --out (required unless --inplace); never clobbers the source silently.
"""
import argparse, struct, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IMG = os.path.join(os.path.dirname(HERE), "flash", "bin", "7846816A_00000000.bin")

# name, file offset, struct fmt, scale (eng = raw*scale), unit, note
FIELDS = [
    ("circ_front",          0x49cf4, ">H", 1.0,      "mm",        "front rolling circumference"),
    ("circ_rear",           0x49cf6, ">H", 1.0,      "mm",        "rear rolling circumference"),
    ("standstill",          0x49cf2, ">H", 0.01,     "km/h",      "standstill speed threshold"),
    ("abs_entry_debounce",  0x48db4, ">H", 1.0,      "frames",    "ABS entry debounce (10 ms frames)"),
    ("abs_entry_clamp_min", 0x48db6, ">H", 0.01,     "km/h",      "entry-slip threshold: clamp min"),
    ("abs_entry_clamp_max", 0x48db8, ">H", 0.01,     "km/h",      "entry-slip threshold: clamp max"),
    ("abs_entry_breakpt0",  0x48dbc, ">H", 0.01,     "km/h",      "entry-slip curve knee (vref)"),
    ("abs_entry_intercept0",0x48dbe, ">H", 0.01,     "km/h",      "entry-slip intercept seg0 (vref<knee)"),
    ("abs_entry_intercept1",0x48dc0, ">H", 0.01,     "km/h",      "entry-slip intercept seg1 (vref>knee)"),
    ("abs_entry_slope0",    0x48dc2, ">h", 1.0/1024, "/km/h",     "entry-slip slope seg0 (Q10, signed)"),
    ("abs_entry_slope1",    0x48dc4, ">h", 1.0/1024, "/km/h",     "entry-slip slope seg1 (Q10, signed)"),
    ("abs_decel_floor",     0x4861e, ">h", 0.01,     "g",         "decel threshold floor (deepest)"),
    ("abs_decel_base",      0x48620, ">h", 0.01,     "g",         "decel threshold base"),
]

def _rng(fmt):
    return (-32768, 32767) if fmt == ">h" else (0, 65535)

def _read(buf, f):
    name, off, fmt, scale, unit, note = f
    raw = struct.unpack(fmt, buf[off:off+2])[0]
    return raw, raw*scale

def resolve(key):
    """key is a numeric index or a field name -> return field index."""
    if key.isdigit():
        i = int(key)
        if not (0 <= i < len(FIELDS)):
            sys.exit("index %d out of range 0..%d" % (i, len(FIELDS)-1))
        return i
    for i, f in enumerate(FIELDS):
        if f[0] == key:
            return i
    sys.exit("unknown field %r (use `list`)" % key)

def cmd_list(buf):
    print("%-3s %-22s %-8s %-8s %-10s %-6s %s" % ("idx","name","offset","raw","eng","unit","note"))
    for i, f in enumerate(FIELDS):
        raw, eng = _read(buf, f)
        print("%-3d %-22s 0x%05X  %-8d %-10.4g %-6s %s" % (i, f[0], f[1], raw, eng, f[4], f[5]))

def cmd_get(buf, key):
    i = resolve(key); f = FIELDS[i]; raw, eng = _read(buf, f)
    print("[%d] %s = %d raw  (%.4g %s)  @0x%05X  %s" % (i, f[0], raw, eng, f[4], f[1], f[5]))

def cmd_set(buf, assigns, as_eng, out, resign, inplace, src):
    changed = []
    for a in assigns:
        if "=" not in a:
            sys.exit("bad assignment %r (want idx=value or name=value)" % a)
        key, val = a.split("=", 1)
        i = resolve(key.strip()); f = FIELDS[i]; name, off, fmt, scale, unit, note = f
        lo, hi = _rng(fmt)
        if as_eng:
            raw = int(round(float(val) / scale))
        else:
            raw = int(val, 0)
        if not (lo <= raw <= hi):
            sys.exit("[%d] %s: raw %d out of range %d..%d" % (i, name, raw, lo, hi))
        old = struct.unpack(fmt, buf[off:off+2])[0]
        buf[off:off+2] = struct.pack(fmt, raw)
        changed.append((i, name, off, old, raw, scale, unit))
    for i, name, off, old, raw, scale, unit in changed:
        print("[%d] %-22s @0x%05X  %d -> %d  (%.4g -> %.4g %s)"
              % (i, name, off, old, raw, old*scale, raw*scale, unit))
    dst = src if inplace else out
    with open(dst, "wb") as fh:
        fh.write(buf)
    print("wrote %s" % dst)
    if resign:
        print("re-signing (MISR + BMY) ...")
        r = subprocess.run([sys.executable, os.path.join(HERE, "bmy_resign.py"), "fix", dst, "-o", dst])
        if r.returncode != 0:
            sys.exit("resign failed")
    else:
        print("NOTE: not signed. Run `python tools/bmy_resign.py fix %s` before flashing." % dst)

def main():
    ap = argparse.ArgumentParser(description="MK60E5 M3 ABS cal editor (by index/name)")
    ap.add_argument("--in", dest="img", default=DEFAULT_IMG, help="source image")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    g = sub.add_parser("get");  g.add_argument("key")
    s = sub.add_parser("set")
    s.add_argument("assign", nargs="+", help="idx=value or name=value")
    s.add_argument("--eng", action="store_true", help="values are engineering units, not raw")
    s.add_argument("--out", help="output image path")
    s.add_argument("--inplace", action="store_true", help="overwrite the source image")
    s.add_argument("--resign", action="store_true", help="run bmy_resign.py fix on the output")
    a = ap.parse_args()
    buf = bytearray(open(a.img, "rb").read())
    if a.cmd == "list":
        cmd_list(buf)
    elif a.cmd == "get":
        cmd_get(buf, a.key)
    elif a.cmd == "set":
        if not a.inplace and not a.out:
            sys.exit("set needs --out <path> (or --inplace to overwrite the source)")
        cmd_set(buf, a.assign, a.eng, a.out, a.resign, a.inplace, a.img)

if __name__ == "__main__":
    main()

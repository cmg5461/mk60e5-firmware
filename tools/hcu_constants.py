"""Find the MK60E5 hydraulic-model constants (COA block) in BMW DSC flash images.

Works on .0pa files (parsed with bmw_hex2bin) and raw .bin dumps (file offset = address), for both
the M·CORE and the ARM controller families. Everything is located by data anchors and literal-pool
cross-references, not by fixed addresses:

  p-V axis   s16 {0, 400, 700, 1000, 1500, 2000, 3000, 6000, 12000, 32700} (0.01 bar), followed by
             the per-axle p-V volume sets (0.1 mm^3 counts)
  LPA curve  x {0, 100, 1000, 15000} (0.1 mm^3) and y {0, 130, 130, 500} (0.01 bar), found separately
  CPU offset the 32-bit literal holding the p-V axis address (0 for ARM dumps, 0x8000 for .0pa
             files whose addresses are CPU + 0x8000)
  fields     every 32-bit literal that sits within 0x60 bytes of a p-V-axis literal and points
             into the hydraulic-model area: the cal words that the p-V users load

Then two named groups, found by pattern:
  inlet      {k_in front, k_in rear, 219, x}: the first co-referenced field followed by 219.
             The next non-zero word is reported as k_vol (read by wheel_volume_delta on the M3)
  outlet     {k_out front, k_out rear}: the first pair after the inlet group (and before the p-V
             sets) with 300 <= rear < front <= 3000 and rear/front in 0.5..0.75 (every known HCU
             has 0.62..0.64). Co-referenced fields are tried first, then a word-by-word scan
  p-V sets   10-word sets starting at 0 and non-decreasing: the ones after the axis, plus any
             co-referenced set and the sets that follow it (a second set is often picked by coding)

Images with the older ARM valve model (per-level flow tables, no 219 group) report the inlet and
outlet as not found. Use -v to print every co-referenced field and decide by hand.

Usage:
  hcu_constants.py fw/*.0pa z4_gt3_6769162_0x000000_0x0a9bfe_merged.bin [-v]
"""
import argparse
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from bmw_hex2bin import parse  # noqa: E402

PV_AXIS = [0, 400, 700, 1000, 1500, 2000, 3000, 6000, 12000, 32700]
LPA_X = [0, 100, 1000, 15000]


def s16be(vals):
    return b"".join(struct.pack(">h", v) for v in vals)


def load(path):
    """Return (lowest address, memory bytearray, reference string)."""
    if path.suffix.lower() == ".bin":
        return 0, bytearray(path.read_bytes()), ""
    header, data = parse(path)
    lo, hi = min(data), max(data)
    mem = bytearray(b"\xff" * (hi - lo + 1))
    for a, v in data.items():
        mem[a - lo] = v
    ref = next((h.split(None, 1)[1] for h in header if h.startswith("$REFERENZ")), "")
    return lo, mem, ref


class Image:
    def __init__(self, path):
        self.path = path
        self.lo, self.mem, self.ref = load(path)

    def h(self, addr):
        """s16 at a file/.0pa address."""
        return struct.unpack_from(">h", self.mem, addr - self.lo)[0]

    def find(self, pat):
        i = self.mem.find(pat)
        return None if i < 0 else i + self.lo

    def literals(self, value):
        """Offsets (into mem) of word-aligned big-endian u32 literals equal to value."""
        key, out, i = struct.pack(">I", value), [], self.mem.find(struct.pack(">I", value))
        while i >= 0:
            if (i + self.lo) % 4 == 0:
                out.append(i)
            i = self.mem.find(key, i + 1)
        return out

    def cpu(self):
        arm = self.mem.count(bytes.fromhex("e12fff1e"))
        mcore = self.mem.count(bytes.fromhex("00cf"))
        thumb = self.mem.count(bytes.fromhex("4770"))
        if mcore > 1000:
            return "M·CORE"
        return "ARM" if arm > 300 else ("ARM/Thumb" if thumb > 1000 else "ARM?")


def analyse(img):
    pv = img.find(s16be(PV_AXIS))
    lpa = img.find(s16be(LPA_X))
    if pv is None:
        return None
    r = {"pv": pv, "lpa": lpa}

    # CPU address offset: which reading of the axis address has literal-pool references
    for off in (0, 0x8000):
        hits = img.literals(pv - off)
        if hits:
            break
    r["off"], r["pool_refs"] = off, len(hits)

    # p-V sets: 10-word, starting at 0, non-decreasing
    sets, a = [], pv + 20
    while len(sets) < 4:
        s = [img.h(a + 2 * i) for i in range(10)]
        if s[0] != 0 or any(y < x for x, y in zip(s, s[1:])) or s[-1] <= 0:
            break
        sets.append((a, s))
        a += 20
    r["sets"] = sets
    r["lpa_y"] = img.find(s16be([0, 130, 130, 500]))

    # cal fields loaded next to the p-V axis
    area = (min(pv, lpa or pv) - 0x300, (sets[-1][0] + 20) if sets else pv + 0x100)
    fields = set()
    for i in hits:
        for j in range(max(0, i - 0x60), min(len(img.mem) - 4, i + 0x60), 4):
            v = struct.unpack_from(">I", img.mem, j)[0] + off
            if area[0] <= v < area[1] and v != pv:
                fields.add(v)
    r["fields"] = sorted(fields)

    def pv_set(a):
        s = [img.h(a + 2 * i) for i in range(10)]
        return s if s[0] == 0 and s[-1] > 0 and all(y >= x for x, y in zip(s, s[1:])) else None

    seen = {a for a, _ in sets}
    for f in r["fields"]:
        a = f
        while a not in seen and pv_set(a):
            sets.append((a, pv_set(a)))
            seen.add(a)
            a += 20
    sets.sort()

    inlet = next((f for f in r["fields"] if img.h(f + 4) == 219), None)
    if inlet is None:  # the inlet word itself may not be loaded on its own: scan the area
        a = area[0]
        while a < area[1] and inlet is None:
            if img.h(a + 4) == 219 and 300 <= img.h(a) <= 3000 and 100 <= img.h(a + 2) <= 3000:
                inlet = a
            a += 2
    r["inlet"] = inlet
    if inlet is not None:
        a = inlet + 8
        while img.h(a) == 0 and a < inlet + 16:
            a += 2
        r["k_vol"] = (a, img.h(a))
        top = min([a for a, _ in sets if a > inlet] or [area[1]])

        def outlet_like(f):
            fr, rr = img.h(f), img.h(f + 2)
            return 300 <= rr < fr <= 3000 and 0.5 <= rr / fr <= 0.75

        cand = [f for f in r["fields"] if inlet + 8 < f < top] + list(range(inlet + 8, top, 2))
        r["outlet"] = next((f for f in cand if outlet_like(f)), None)
    else:
        r["k_vol"] = r["outlet"] = None
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=pathlib.Path)
    ap.add_argument("-v", "--verbose", action="store_true", help="print every co-referenced field")
    args = ap.parse_args()

    for path in args.files:
        img = Image(path)
        r = analyse(img)
        name = f"{path.name} [{img.cpu()}] {img.ref}".strip()
        if r is None:
            print(f"{name}: p-V axis not found\n")
            continue
        cpu = lambda a: a - r["off"]  # noqa: E731
        print(name)
        print(f"  CPU = file - {r['off']:#x}; p-V axis {cpu(r['pv']):#x} ({r['pool_refs']} literal refs); "
              f"LPA x {cpu(r['lpa']):#x} {LPA_X}, y "
              + (f"{cpu(r['lpa_y']):#x} [0, 130, 130, 500]" if r["lpa_y"] is not None else "not found"))
        if r["inlet"] is not None:
            i = r["inlet"]
            print(f"  inlet  {cpu(i):#x}: k_in front {img.h(i)}, rear {img.h(i + 2)}; "
                  f"next pair {img.h(i + 4)}, {img.h(i + 6)}; "
                  + (f"k_vol {img.h(r['k_vol'][0])} at {cpu(r['k_vol'][0]):#x}" if img.h(r['k_vol'][0]) <= 3000
                     else "k_vol n/a (older layout)"))
        else:
            print("  inlet  not found (older valve model?)")
        if r["outlet"] is not None:
            o = r["outlet"]
            print(f"  outlet {cpu(o):#x}: k_out front {img.h(o)}, rear {img.h(o + 2)}")
        else:
            print("  outlet not found")
        for a, s in r["sets"]:
            print(f"  p-V set {cpu(a):#x}: {s}")
        if args.verbose:
            print("  co-referenced fields (addr: s16, s16):")
            print("   " + ", ".join(f"{cpu(f):#x}: {img.h(f)},{img.h(f + 2)}" for f in r["fields"]))
        print()


if __name__ == "__main__":
    main()

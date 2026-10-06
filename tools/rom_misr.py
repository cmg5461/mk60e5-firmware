"""Recompute the in-ECU background ROM self-test (MISR) words for an MK60E5 image.

The DSC runs a hardware MISR (poly 0x00400007, seed 0, big-endian 32-bit word feed) over
three regions and compares against an expected word stored AT each region's end address.
After editing a calibration you must rewrite the expected word for the calibration range,
or the ECU raises error 0x10004. This tool reads the range table from the image, recomputes
each MISR, and reports (and optionally patches) the stored words.

The range table is self-describing: three {start, end} big-endian u32 pairs. It is located
automatically by scanning for a table whose first entry starts at the application base.
Verified addresses: 1M (7846411A) table 0xD7584, cal end 0x426BC; M3 (7846816A) table 0xD71F4,
cal end 0x4249C. File offset = CPU address + 0x8000 (pass CPU addresses).

This recomputes the MISR self-test ONLY. The 512-bit BMY RSA signature is a separate layer
(see tools/bmy_resign.py). Both must be valid for an edited image to load.

Usage:
  python tools/rom_misr.py flash/bin/7846816A_00000000.bin            # report
  python tools/rom_misr.py flash/bin/7846816A_00000000.bin --patch    # fix mismatches in place
"""
import argparse
import struct

APP_OFFSET = 0x8000
POLY = 0x00400007


def misr(data, start, end):
    """MISR over file bytes [start, end) fed as big-endian u32, CPU-addressed region."""
    s = 0
    for off in range(start + APP_OFFSET, end + APP_OFFSET, 4):
        w = struct.unpack(">I", data[off:off + 4])[0]
        s = ((s << 1) ^ (POLY if s >> 31 else 0)) & 0xFFFFFFFF
        s ^= w
    return s


def u32(data, cpu):
    o = cpu + APP_OFFSET
    return struct.unpack(">I", data[o:o + 4])[0]


def find_table(data):
    """Find the 3-entry {start,end} range table: first start == app base 0x40000,
    entries contiguous and ascending, each end holding a plausible expected word."""
    for cpu in range(0xD0000, 0xE0000, 4):
        try:
            if u32(data, cpu) != 0x40000:
                continue
            ends = [u32(data, cpu + 8 * i + 4) for i in range(3)]
            starts = [u32(data, cpu + 8 * i) for i in range(3)]
            if starts[0] == 0x40000 and starts[1] < starts[2] < ends[2] and ends[2] < 0x100000:
                return cpu
        except struct.error:
            continue
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--table", type=lambda s: int(s, 0), default=None,
                    help="CPU address of the range table (default: auto-detect)")
    ap.add_argument("--patch", action="store_true", help="write recomputed words into the image in place")
    args = ap.parse_args()
    data = bytearray(open(args.image, "rb").read())

    table = args.table or find_table(data)
    if table is None:
        raise SystemExit("could not locate the ROM self-test range table; pass --table 0x...")
    print(f"range table at {table:#x}")

    names = ["vectors/header", "calibration", "code+tables"]
    changed = False
    for i in range(3):
        start, end = u32(data, table + 8 * i), u32(data, table + 8 * i + 4)
        stored = u32(data, end)
        got = misr(data, start, end)
        ok = stored == got
        tag = "OK" if ok else "MISMATCH -> " + (f"{got:#010x}" if args.patch else "needs update")
        print(f"  [{start:#08x}, {end:#08x}) {names[i]:14s} stored@{end:#x}={stored:#010x} misr={got:#010x}  {tag}")
        if args.patch and not ok:
            data[end + APP_OFFSET:end + APP_OFFSET + 4] = struct.pack(">I", got)
            changed = True

    if args.patch and changed:
        open(args.image, "wb").write(data)
        print(f"patched {args.image} (MISR only; remember the BMY signature — tools/bmy_resign.py)")
    elif args.patch:
        print("nothing to patch")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""
parse_0pa.py - decode BMW WinKFP .0pa / .0da flash files (Intel HEX text) into a
raw image, and extract the MK60 level-5 auth key.

The .0pa files (e.g. in a BMW daten set data/DSCxx/<ZB>.0pa) are Intel HEX with a
small BMW header ($REFERENZ <coding-index>, $VALUE_UNUSED_BYTE, ...). Addresses
are FILE offsets (CPU address + 0x8000), matching our flash/bin dumps.

The MK60 level-5 Authentisierung key is the 16 bytes immediately preceding the
REFERENZ string in the data (verified: M3 7846816A key = F1CE23C6.. at file
0xFD6C8, directly before "01818I000900"). This key is shared across most MK60
variants (M3 + 4/5 E9x-335 variants); 4029563A is the known exception.

Usage:
  python tools/parse_0pa.py <file.0pa> [--out image.bin] [--key]
  python tools/parse_0pa.py --scan <daten_dir>      # list key for every DSC .0pa
"""
import argparse
import glob
import os
import sys

SHARED_KEY = bytes.fromhex("F1CE23C6CD24C8B7B8B3C653D9707BAC")  # M3/most MK60


def parse_ihex(path):
    """Return (lo_addr, bytes, referenz) for an Intel-HEX .0pa/.0da file."""
    mem, base, ref = {}, 0, None
    with open(path, "r", errors="replace") as fh:
        for ln in fh:
            s = ln.strip()
            if s.startswith("$REFERENZ"):
                ref = s.split()[1]
            if not s.startswith(":"):
                continue
            bc = int(s[1:3], 16)
            addr = int(s[3:7], 16)
            rt = int(s[7:9], 16)
            data = bytes.fromhex(s[9:9 + bc * 2])
            if rt == 0:
                for i, b in enumerate(data):
                    mem[base + addr + i] = b
            elif rt == 2:
                base = int(data.hex(), 16) << 4
            elif rt == 4:
                base = int(data.hex(), 16) << 16
            elif rt == 1:
                break
    if not mem:
        return 0, b"", ref
    lo, hi = min(mem), max(mem)
    buf = bytearray(b"\xff" * (hi - lo + 1))
    for a, b in mem.items():
        buf[a - lo] = b
    return lo, bytes(buf), ref


def extract_key(lo, buf, ref):
    """Key = 16 bytes before the first data occurrence of the REFERENZ string;
    fall back to the shared key if present at another offset."""
    if ref:
        j = buf.find(ref.encode())
        if j >= 16:
            k = buf[j - 16:j]
            if any(b != 0xFF for b in k):
                return k, lo + j - 16
    j = buf.find(SHARED_KEY)
    if j >= 0:
        return SHARED_KEY, lo + j
    return None, None


def main():
    p = argparse.ArgumentParser(description="decode BMW .0pa flash / extract MK60 key")
    p.add_argument("path", nargs="?")
    p.add_argument("--out", help="write the reconstructed raw image here")
    p.add_argument("--scan", metavar="DIR", help="scan a daten dir for all DSC .0pa keys")
    args = p.parse_args()

    if args.scan:
        files = sorted(glob.glob(os.path.join(args.scan, "data", "DSC*", "*.0pa")))
        for f in files:
            lo, buf, ref = parse_ihex(f)
            key, at = extract_key(lo, buf, ref)
            tag = os.path.relpath(f, args.scan)
            print("%-32s ref=%-14s key=%s%s"
                  % (tag, ref, key.hex() if key else "NOT FOUND",
                     "" if key != SHARED_KEY else "  (shared M3 key)"))
        return

    if not args.path:
        p.error("give a .0pa file or --scan DIR")
    lo, buf, ref = parse_ihex(args.path)
    key, at = extract_key(lo, buf, ref)
    print("file     : %s" % args.path)
    print("referenz : %s" % ref)
    print("addr span: 0x%X .. 0x%X (file offsets; CPU = offset - 0x8000)" % (lo, lo + len(buf) - 1))
    print("auth key : %s%s" % (key.hex() if key else "NOT FOUND",
                               "  (= shared M3 key)" if key == SHARED_KEY else ""))
    if key:
        print("key @    : file 0x%X  (CPU 0x%X)" % (at, at - 0x8000))
    if args.out:
        with open(args.out, "wb") as fh:
            fh.write(buf)
        print("wrote raw image (%d bytes, base file-offset 0x%X) -> %s" % (len(buf), lo, args.out))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Decode an MK60E5 logical-EEPROM dump (2 KiB, as written by `mk60_can.py eeprom`).

Input bytes are logical (un-inverted) — offset 0 = NVM 0x000. Field layouts and
checksum formulas are from analysis/EEPROM_MAP_7846816A.md and the valve-cal /
sensor-offset / coding docs. Confidence varies; see that doc for grades.

Usage:  eeprom_decode.py dump.bin [dump2.bin ...]
"""
from __future__ import annotations
import sys
from functools import reduce


def u16(b, o):   return (b[o] << 8) | b[o + 1]          # big-endian (M*CORE)
def s16(b, o):   v = u16(b, o); return v - 0x10000 if v & 0x8000 else v
def xor(bs):     return reduce(lambda a, c: a ^ c, bs, 0)
def cal_chk(bs): return reduce(lambda a, c: (a ^ ((c + 1) & 0xFF)), bs, 0)   # cal_checksum 0x86724
def bcd_part(b, o):  # packed BCD: 00 00 07 84 68 16 -> "7846816"
    return ("".join("%02X" % c for c in b[o:o + 6]).lstrip("0")) or "0"
def asc(b, o, n): return "".join(chr(c) if 0x20 <= c < 0x7F else "." for c in b[o:o + n])


def ok(flag):  return "\033[32mOK\033[0m" if sys.stdout.isatty() else "OK"
def bad(flag): return "\033[31mFAIL\033[0m" if sys.stdout.isatty() else "FAIL"
def mark(cond): return ok(cond) if cond else bad(cond)


def decode(b):
    print("  --- flash programming-cycle counters (block 24) ---")
    a0, a1 = b[0x37E], b[0x37F]
    print("    0x37E program-count A : %3d (0x%02X)%s" % (a0, a0, "   >= ~20 limit -> 31 02 erase fails 71 02 02" if a0 >= 20 else ""))
    print("    0x37F program-count B : %3d (0x%02X)" % (a1, a1))

    print("  --- programming status / session handshake (0x333-0x335) ---")
    st = {0x00: "Anlieferzustand", 0x01: "Normalbetrieb", 0x03: "Speicher geloescht",
          0x05: "Sig.pruefung PAF n/a", 0x07: "Prog.sitzung aktiv", 0x0C: "Programm fehlt/unvollst.",
          0x8C: "Zulieferer-reserviert (10 85 written)"}
    print("    0x333 handshake  : 0x%02X (%s)" % (b[0x333], "AA=app set / 55=BL ack" if b[0x333] in (0xAA, 0x55) else "?"))
    print("    0x334 handshake  : 0x%02X" % b[0x334])
    print("    0x335 prog status: 0x%02X (%s)  <- 31 0A reply" % (b[0x335], st.get(b[0x335], "?")))

    print("  --- coding ---")
    raw = b[0x400:0x430]
    rc = (xor(raw[1:]) + 1) & 0xFF
    print("    raw coding   0x400-0x42F : chk 0x%02X, computed 0x%02X  [%s]" % (raw[0], rc, mark(raw[0] == rc)))
    print("      bytes: %s" % raw.hex(" "))
    act = b[0x44B:0x4B0]
    ac = (xor(act[1:]) + 1) & 0xFF
    print("    active image 0x44B       : chk 0x%02X, computed 0x%02X  [%s]%s" % (
        act[0], ac, mark(act[0] == ac), "   (all-zero -> fault 0xC0040, needs coding)" if act[0] == 0 else ""))

    print("  --- valve self-calibration (block 16) ---")
    mci = b[0x283:0x2A3]
    mchk = cal_chk(mci)
    print("    MCI/USV record 0x281 : chk {0x%02X,0x%02X} computed 0x%02X  [%s]" % (
        b[0x281], b[0x282], mchk, mark(b[0x281] == mchk and b[0x282] == (mchk ^ 0xFF))))
    for c in range(2):
        p = [b[0x283 + c * 8 + i] for i in range(8)]                     # bar
        cur = [round(b[0x293 + c * 8 + i] * 2000 / 255) for i in range(8)]  # mA
        print("      circuit %d: P(bar)=%s" % (c, p))
        print("                 I(mA) =%s" % cur)
    inl = b[0x2A5:0x2CD]
    ichk = cal_chk(inl)
    print("    inlet record   0x2A3 : chk {0x%02X,0x%02X} computed 0x%02X  [%s]" % (
        b[0x2A3], b[0x2A4], ichk, mark(b[0x2A3] == ichk and b[0x2A4] == (ichk ^ 0xFF))))
    wheels = ["FL", "FR", "RL", "RR"]
    dp = [0, 20, 50, 90, 140]
    print("      hold current mA by wheel @ dp(bar) %s:" % dp)
    for w in range(4):
        vals = [s16(b, 0x2A5 + (w * 5 + k) * 2) for k in range(5)]
        print("        %s: %s" % (wheels[w], vals))

    print("  --- sensor zero-offset record (block 8, 0x160) ---")
    words = [s16(b, 0x160 + 2 * i) for i in range(17)]
    uw = [u16(b, 0x160 + 2 * i) for i in range(17)]
    xw = reduce(lambda a, c: a ^ c, uw[1:17], 0)       # xor16_checksum: w0 = ~XOR(w1..w16)
    valid = uw[0] == (~xw & 0xFFFF)
    print("    word0 chk 0x%04X, ~XOR(w1-16) 0x%04X  [%s]%s" % (
        uw[0], ~xw & 0xFFFF, mark(valid), "   (blank -> not yet learned)" if uw[0] == 0 else ""))
    if valid and uw[0] != 0:
        print("    steering offset (w2, Q6)  : %+d raw = %+.3f deg" % (words[2], words[2] / 64.0))
        print("    lateral  offset (w3)      : %+d" % words[3])
        print("    master-p offset (w4,w5)   : %+d, %+d" % (words[4], words[5]))

    print("  --- learned per-wheel tyre factors (block 22, 0x269) ---")
    print("    %s" % " ".join("%s=0x%02X(%d)" % (wheels[i], b[0x269 + i], b[0x269 + i]) for i in range(4)))

    print("  --- identity ---")
    print("    part number (1A 91) : %s   codier-idx 0x%02X  diag-idx %d" % (
        bcd_part(b, 0x3C3), b[0x3D6], u16(b, 0x3D7)))
    print("    VIN short  (1A 90)  : %s" % asc(b, 0x3A4, 7))
    print("    ident str  (1A 89)  : %s   (w564 auth tail = %s)" % (asc(b, 0x3B5, 9), asc(b, 0x3BA, 4)))
    print("    prog date  (1A 99)  : %s" % b[0x3AB:0x3AF].hex(" "))
    print("    ECU id tbl (1A 80)  : %s" % b[0x3CF:0x3CF + 29].hex(" "))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for path in sys.argv[1:]:
        b = open(path, "rb").read()
        if len(b) < 0x800:
            print("%s: too short (%d bytes, need 0x800)" % (path, len(b))); continue
        print("=" * 72)
        print(path)
        print("=" * 72)
        decode(b)
        print()


if __name__ == "__main__":
    main()

"""Replay M*CORE functions from a disassembly listing against a bank image, to check what code computes.

Executes the instructions printed in an `mcore_dis.py` listing (it does not decode bytes), starting at an entry
point and following calls until the outermost function returns. ROM reads come from the bank image (CPU address +
0x8000 = file offset), RAM starts zeroed unless preset. Reports every RAM write and numeric events: 32-bit multiply
overflow, divide by zero, unsigned divide by a negative-looking divisor, and calls to `sat_s16` (0x6D102 on
7846816A) whose input was out of range.

Use it to confirm a formula read from code, find the input range where a computation wraps or saturates, or see the
effect of a calibration change before patching. Calls into code that touches hardware or OS state will not mean
anything; replay leaf computations (loaders, converters, model updates).

Command line:
  python tools/mcore_replay.py BANK0.bin analysis/7846816A_main.lst 0x5DE44 0x5E424 \
      --ram 0x4031AB=0:1 --rom 0xD6F72=1100*12 --show 0x400AA4-0x400AFA

As a module (sweeps):
  from mcore_replay import Replayer
  r = Replayer(bank, lst)
  res = r.run([0x5DE44, 0x5E424], ram={0x4031AB: (0, 1)}, rom={0xD6F72: [1100] * 12})
  res.s16(0x400AE8), res.events

ROM overrides are s16 big-endian lists (the common calibration case); `--rom ADDR=v1,v2,...` or `ADDR=v*n`.
"""
import argparse
import re
import struct
import sys

M32 = 0xFFFFFFFF
RAM_LO, RAM_HI = 0x400000, 0x40C000
STACK_TOP = 0x7FF000            # fake stack outside every real region
RETURN_SENTINEL = 0xFFFFFFFE
SAT_S16 = 0x6D102               # 7846816A `sat_s16`; set Replayer.sat_probe to another address for other images

LINE = re.compile(r"^  ([0-9A-F]{6}):\s+[0-9A-F]{4}\s+(\S+)\s*([^;]*)(?:;\s*(.*))?$")
SPLIT = re.compile(r",(?![^()]*\))")


def s32(x):
    x &= M32
    return x - (1 << 32) if x & 0x80000000 else x


def sx(x, bits):
    x &= (1 << bits) - 1
    return x - (1 << bits) if x & (1 << (bits - 1)) else x


class Result:
    def __init__(self, mem, writes, events):
        self.mem, self.writes, self.events = mem, writes, events

    def u(self, addr, n):
        return int.from_bytes(bytes(self.mem.get(addr + i, 0) for i in range(n)), "big")

    def s16(self, addr):
        return sx(self.u(addr, 2), 16)

    def s8(self, addr):
        return sx(self.u(addr, 1), 8)


class Replayer:
    def __init__(self, bank_path, lst_path, file_offset=0x8000, sat_probe=SAT_S16):
        self.rom = bytearray(open(bank_path, "rb").read())
        self.off = file_offset
        self.sat_probe = sat_probe
        self.ins = {}
        for line in open(lst_path, errors="replace"):
            m = LINE.match(line.rstrip("\n"))
            if m:
                ops = [o.strip() for o in SPLIT.split(m.group(3))] if m.group(3).strip() else []
                self.ins[int(m.group(1), 16)] = (m.group(2), ops, m.group(4) or "")

    # memory -------------------------------------------------------------------------------------------------
    def _rd(self, a, n):
        if RAM_LO <= a < RAM_HI or a >= 0x700000:
            return int.from_bytes(bytes(self.mem.get(a + i, 0) for i in range(n)), "big")
        o = a + self.off
        if o + n > len(self.rom):
            raise RuntimeError(f"read outside image at 0x{a:06X}")
        return int.from_bytes(self.rom[o:o + n], "big")

    def _wr(self, a, n, v):
        for i, b in enumerate((v & ((1 << 8 * n) - 1)).to_bytes(n, "big")):
            self.mem[a + i] = b
        if RAM_LO <= a < RAM_HI:
            self.writes[a] = n

    # execution ----------------------------------------------------------------------------------------------
    def run(self, entries, ram=None, rom=None, max_steps=200000):
        """Run each entry in turn (shared memory). ram: {addr: (value, size)}; rom: {addr: [s16, ...]}."""
        saved = bytes(self.rom)
        try:
            for a, vals in (rom or {}).items():
                for i, v in enumerate(vals):
                    struct.pack_into(">h", self.rom, a + self.off + 2 * i, v)
            self.mem, self.writes, self.events = {}, {}, []
            for a, (v, n) in (ram or {}).items():
                self._wr(a, n, v)
            self.writes.clear()
            for e in entries:
                self._call(e, max_steps)
            return Result(dict(self.mem), dict(self.writes), list(self.events))
        finally:
            self.rom[:] = saved

    def _call(self, entry, max_steps):
        r = [0] * 16
        r[0], r[15] = STACK_TOP, RETURN_SENTINEL
        c = False
        pc = entry

        def note(kind, detail):
            self.events.append(f"{pc:06X} {kind} {detail}")

        for _ in range(max_steps):
            if pc == RETURN_SENTINEL:
                return
            if pc == self.sat_probe:
                v = s32(r[2])
                if not -32768 <= v <= 32767:
                    note("SAT16", f"{v} (called from 0x{(r[15] - 2) & M32:06X})")
            if pc not in self.ins:
                raise RuntimeError(f"no listing line at 0x{pc:06X}")
            mn, op, cm = self.ins[pc]
            nxt = pc + 2
            R = lambda i: int(op[i][1:])            # register number of operand i
            V = lambda i: r[R(i)]                   # unsigned value
            S = lambda i: s32(r[R(i)])              # signed value
            I = lambda i: int(op[i], 0)

            def put(i, v):
                r[R(i)] = v & M32

            if mn == "lrw":
                put(0, int(cm.split("=")[1], 16))
            elif mn in ("ld.b", "ld.h", "ld.w", "st.b", "st.h", "st.w"):
                rb, d = op[1].strip("()").split(",")
                a = (r[int(rb[1:])] + int(d)) & M32
                n = {"b": 1, "h": 2, "w": 4}[mn[-1]]
                if mn[0] == "l":
                    put(0, self._rd(a, n))
                else:
                    self._wr(a, n, V(0))
            elif mn in ("stm", "ldm"):
                first = int(op[0].split("-")[0][1:])
                a = r[0]
                for k in range(first, 16):
                    if mn == "stm":
                        self._wr(a, 4, r[k])
                    else:
                        r[k] = self._rd(a, 4)
                    a += 4
            elif mn == "mov": put(0, V(1))
            elif mn == "movi": put(0, I(1))
            elif mn == "bmaski": put(0, (1 << I(1)) - 1 if I(1) < 32 else M32)
            elif mn == "bgeni": put(0, 1 << I(1))
            elif mn == "bgenr": put(0, 1 << V(1) if V(1) < 32 else 0)
            elif mn == "bseti": put(0, V(0) | (1 << I(1)))
            elif mn == "bclri": put(0, V(0) & ~(1 << I(1)))
            elif mn == "andi": put(0, V(0) & I(1))
            elif mn == "and": put(0, V(0) & V(1))
            elif mn == "andn": put(0, V(0) & ~V(1))
            elif mn == "or": put(0, V(0) | V(1))
            elif mn == "xor": put(0, V(0) ^ V(1))
            elif mn == "not": put(0, ~V(0))
            elif mn == "abs": put(0, abs(S(0)))
            elif mn == "addu": put(0, V(0) + V(1))
            elif mn == "subu": put(0, V(0) - V(1))
            elif mn == "rsub": put(0, V(1) - V(0))
            elif mn == "addi": put(0, V(0) + I(1))
            elif mn == "subi": put(0, V(0) - I(1))
            elif mn == "rsubi": put(0, I(1) - V(0))
            elif mn == "ixh": put(0, V(0) + 2 * V(1))
            elif mn == "ixw": put(0, V(0) + 4 * V(1))
            elif mn == "mult":
                exact = S(0) * S(1)
                if not (-(1 << 31) <= exact < (1 << 32)):
                    note("MULT-OVF", exact)
                put(0, exact)
            elif mn == "mulsh":
                put(0, sx(V(0), 16) * sx(V(1), 16))
            elif mn in ("divs", "divu"):
                x, y = (S(0), S(1)) if mn == "divs" else (V(0), V(1))
                if y == 0:
                    note("DIV0", op)
                    put(0, 0)
                else:
                    if mn == "divu" and S(1) < 0:
                        note("DIVU-NEG", (V(0), S(1)))
                    q = abs(x) // abs(y)
                    put(0, q if (x < 0) == (y < 0) else -q)
            elif mn == "asri": put(0, S(0) >> I(1))
            elif mn == "lsri": put(0, V(0) >> I(1))
            elif mn == "lsli": put(0, V(0) << I(1))
            elif mn == "rotli": put(0, (V(0) << I(1)) | (V(0) >> (32 - I(1))))
            elif mn == "asr": put(0, S(0) >> min(V(1), 31))
            elif mn == "lsr": put(0, V(0) >> V(1) if V(1) < 32 else 0)
            elif mn == "lsl": put(0, V(0) << V(1) if V(1) < 32 else 0)
            elif mn == "sexth": put(0, sx(V(0), 16))
            elif mn == "sextb": put(0, sx(V(0), 8))
            elif mn == "zexth": put(0, V(0) & 0xFFFF)
            elif mn == "zextb": put(0, V(0) & 0xFF)
            elif mn.startswith("xtrb"):
                r[1] = (V(0) >> (8 * (3 - int(mn[-1])))) & 0xFF
            elif mn == "btsti": c = bool(V(0) >> I(1) & 1)
            elif mn == "cmplt": c = S(0) < S(1)
            elif mn == "cmplti": c = S(0) < I(1)
            elif mn == "cmpnei": c = V(0) != I(1)
            elif mn == "cmpne": c = V(0) != V(1)
            elif mn == "cmphs": c = V(0) >= V(1)
            elif mn == "tst": c = (V(0) & V(1)) != 0
            elif mn == "tstnbz": c = all((V(0) >> (8 * k)) & 0xFF for k in range(4))
            elif mn == "clrt":                      # clear rx if C set (C unchanged)
                if c: put(0, 0)
            elif mn == "clrf":                      # clear rx if C clear (C unchanged)
                if not c: put(0, 0)
            elif mn == "mvc": put(0, int(c))
            elif mn == "mvcv": put(0, int(not c))
            elif mn == "movt":
                if c: put(0, V(1))
            elif mn == "movf":
                if not c: put(0, V(1))
            elif mn == "inct":
                if c: put(0, V(0) + 1)
            elif mn == "incf":
                if not c: put(0, V(0) + 1)
            elif mn == "dect":
                if c: put(0, V(0) - 1)
            elif mn == "decf":
                if not c: put(0, V(0) - 1)
            elif mn == "bt":
                if c: nxt = int(op[0], 16)
            elif mn == "bf":
                if not c: nxt = int(op[0], 16)
            elif mn == "br": nxt = int(op[0], 16)
            elif mn == "bsr":
                r[15], nxt = pc + 2, int(op[0], 16)
            elif mn == "jsri":
                r[15], nxt = pc + 2, int(cm.split("->")[1], 16)
            elif mn == "jmpi":
                nxt = int(cm.split("->")[1], 16)
            elif mn == "jsr":
                r[15], nxt = pc + 2, V(0)
            elif mn == "jmp":
                nxt = V(0)
            else:
                raise RuntimeError(f"unhandled 0x{pc:06X}: {mn} {','.join(op)}")
            pc = nxt
        raise RuntimeError(f"no return after {max_steps} steps (last pc 0x{pc:06X})")


def _num(s):
    return int(s, 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bank", help="bank-0 image from tools/bmw_hex2bin.py")
    ap.add_argument("listing", help="mcore_dis.py listing, e.g. analysis/7846816A_main.lst")
    ap.add_argument("entries", nargs="+", type=_num, help="function entry points, run in order")
    ap.add_argument("--ram", action="append", default=[], metavar="ADDR=VAL:SIZE", help="preset RAM (size 1/2/4)")
    ap.add_argument("--rom", action="append", default=[], metavar="ADDR=V1,V2|V*N", help="override s16 ROM words")
    ap.add_argument("--show", metavar="LO-HI", help="print this RAM range as s16 (default: every write)")
    args = ap.parse_args()

    ram = {}
    for spec in args.ram:
        a, rest = spec.split("=")
        v, n = rest.split(":") if ":" in rest else (rest, "2")
        ram[_num(a)] = (_num(v), int(n))
    rom = {}
    for spec in args.rom:
        a, rest = spec.split("=")
        if "*" in rest:
            v, n = rest.split("*")
            rom[_num(a)] = [_num(v)] * int(n)
        else:
            rom[_num(a)] = [_num(x) for x in rest.split(",")]

    res = Replayer(args.bank, args.listing).run(args.entries, ram=ram, rom=rom)
    if args.show:
        lo, hi = (_num(x) for x in args.show.split("-"))
        for a in range(lo, hi, 2):
            print(f"0x{a:06X} {res.s16(a)}")
    else:
        for a, n in sorted(res.writes.items()):
            print(f"0x{a:06X} {sx(res.u(a, n), 8 * n)}  ({n} B)")
    for e in res.events:
        print("EVENT", e)
    return 1 if any(e.split()[1] in ("DIV0", "DIVU-NEG") for e in res.events) else 0


if __name__ == "__main__":
    sys.exit(main())

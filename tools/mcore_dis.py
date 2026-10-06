"""Minimal Motorola M*CORE (M200/M300) disassembler for raw big-endian images.

Opcode table follows GNU binutils opcodes/mcore-opc.h. All instructions are 16 bits.
r0 is the stack pointer, r15 the link register; "jmp r15" is the return.

Usage:
  mcore_dis.py IMAGE.bin --base 0x0 --start 0x48000 --end 0xFE78C > out.lst

Function entries are seeded from bsr targets and jsri/jmpi literal-pool targets and
printed as labels; lrw literal values are shown as comments.
"""
import argparse
import struct


def sx(v, bits):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


O0 = {0x0000: "bkpt", 0x0001: "sync", 0x0002: "rte", 0x0003: "rfi", 0x0004: "stop",
      0x0005: "wait", 0x0006: "doze", 0x0007: "idly4"}
O1 = {0x002: "mvc", 0x003: "mvcv", 0x008: "dect", 0x009: "decf", 0x00A: "inct", 0x00B: "incf",
      0x00C: "jmp", 0x00D: "jsr", 0x00E: "ff1", 0x00F: "brev", 0x014: "zextb", 0x015: "sextb",
      0x016: "zexth", 0x017: "sexth", 0x018: "declt", 0x019: "tstnbz", 0x01A: "decgt",
      0x01B: "decne", 0x01C: "clrt", 0x01D: "clrf", 0x01E: "abs", 0x01F: "not"}
XTRB = {0x010: "xtrb3", 0x011: "xtrb2", 0x012: "xtrb1", 0x013: "xtrb0"}
O2 = {0x02: "movt", 0x03: "mult", 0x05: "subu", 0x06: "addc", 0x07: "subc", 0x0A: "movf",
      0x0B: "lsr", 0x0C: "cmphs", 0x0D: "cmplt", 0x0E: "tst", 0x0F: "cmpne", 0x12: "mov",
      0x13: "bgenr", 0x14: "rsub", 0x15: "ixw", 0x16: "and", 0x17: "xor", 0x1A: "asr",
      0x1B: "lsl", 0x1C: "addu", 0x1D: "ixh", 0x1E: "or", 0x1F: "andn"}
OB = {0x28: "rsubi", 0x2A: "cmpnei", 0x2E: "andi", 0x30: "bclri", 0x34: "bseti", 0x36: "btsti"}
SHIFT = {0x38: ("xsr", "rotli"), 0x3A: ("asrc", "asri"), 0x3C: ("lslc", "lsli"), 0x3E: ("lsrc", "lsri")}
LS = {0x8: ("ld.w", 4), 0x9: ("st.w", 4), 0xA: ("ld.b", 1), 0xB: ("st.b", 1), 0xC: ("ld.h", 2), 0xD: ("st.h", 2)}
BR = {0: "bt", 1: "bf", 2: "br", 3: "bsr"}


def decode(h, pc, rd32):
    """Return (text, branch_target, call_target, literal_addr)."""
    rx = h & 15
    ry = (h >> 4) & 15
    top = h >> 8
    if h in O0:
        return O0[h], None, None, None
    if h & 0xFFFC == 0x0008:
        return f"trap {h & 3}", None, None, None
    if 0x0040 <= h <= 0x007F:
        op = {4: "ldq", 5: "stq", 6: "ldm", 7: "stm"}[h >> 4]
        regs = "r4-r7" if op in ("ldq", "stq") else f"r{rx}-r15"
        src = f"(r{rx})" if op in ("ldq", "stq") else "(r0)"
        return f"{op} {regs},{src}", None, None, None
    if h < 0x0200 and (h >> 4) in O1:
        name = O1[h >> 4]
        if h == 0x00CF:
            return "jmp r15            ; return", None, None, None
        return f"{name} r{rx}", None, None, None
    if h < 0x0200 and (h >> 4) in XTRB:
        return f"{XTRB[h >> 4]} r1,r{rx}", None, None, None
    if top == 0x04:
        return f"loopt r{ry},{pc + 2 - 2 * (16 - rx) if rx else pc:#x}", None, None, None
    if top in O2:
        return f"{O2[top]} r{rx},r{ry}", None, None, None
    if 0x10 <= top <= 0x11:
        if h & 0xFFF8 == 0x11F0:
            return f"psrclr {h & 7:#x}", None, None, None
        if h & 0xFFF8 == 0x11F8:
            return f"psrset {h & 7:#x}", None, None, None
        return f"mfcr r{rx},cr{(h >> 4) & 31}", None, None, None
    if 0x18 <= top <= 0x19:
        return f"mtcr r{rx},cr{(h >> 4) & 31}", None, None, None
    imm5 = (h >> 4) & 31
    if 0x20 <= top <= 0x25 or top in (0x22, 0x23):
        op = {0x20: "addi", 0x21: "addi", 0x22: "cmplti", 0x23: "cmplti", 0x24: "subi", 0x25: "subi"}[top]
        return f"{op} r{rx},{imm5 + 1}", None, None, None
    if top & 0xFE in OB:
        return f"{OB[top & 0xFE]} r{rx},{imm5}", None, None, None
    if top & 0xFE == 0x2C:
        if imm5 == 1:
            return f"divu r{rx},r1", None, None, None
        return f"bmaski r{rx},{imm5 or 32}", None, None, None
    if top & 0xFE == 0x32:
        if imm5 == 1:
            return f"divs r{rx},r1", None, None, None
        return f"bgeni r{rx},{imm5}", None, None, None
    if top & 0xFE in SHIFT:
        reg, imm = SHIFT[top & 0xFE]
        return (f"{reg} r{rx}" if imm5 == 0 else f"{imm} r{rx},{imm5}"), None, None, None
    if 0x60 <= top <= 0x67:
        return f"movi r{rx},{(h >> 4) & 0x7F}", None, None, None
    if 0x70 <= top <= 0x7F:
        rz = (h >> 8) & 15
        lit = (pc + 2 + (h & 0xFF) * 4) & ~3
        val = rd32(lit)
        vs = f"{val:#010x}" if val is not None else "?"
        if rz == 0:
            return f"jmpi [{lit:#x}]       ; -> {vs}", None, None, lit
        if rz == 15:
            return f"jsri [{lit:#x}]       ; -> {vs}", None, val, lit
        return f"lrw r{rz},[{lit:#x}]   ; = {vs}", None, None, lit
    if 0x8 <= h >> 12 <= 0xD:
        name, size = LS[h >> 12]
        rz = (h >> 8) & 15
        return f"{name} r{rz},(r{rx},{ry * size})", None, None, None
    if h >> 12 >= 0xE:
        kind = (h >> 11) & 3
        tgt = pc + 2 + sx(h & 0x7FF, 11) * 2
        if kind == 3:
            return f"bsr {tgt:#x}", None, tgt, None
        return f"{BR[kind]} {tgt:#x}", tgt, None, None
    return f".short {h:#06x}", None, None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--base", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--start", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--end", type=lambda s: int(s, 0), required=True)
    args = ap.parse_args()

    data = open(args.image, "rb").read()
    base = args.base

    def rd16(a):
        o = a - base
        return struct.unpack(">H", data[o:o + 2])[0]

    def rd32(a):
        o = a - base
        if 0 <= o <= len(data) - 4:
            return struct.unpack(">I", data[o:o + 4])[0]
        return None

    start, end = args.start & ~1, args.end

    def prologue(a):  # subi r0,N ; stm rX-r15,(r0)
        return start <= a < end - 2 and rd16(a) & 0xFE0F == 0x2400 and rd16(a + 2) & 0xFFF0 == 0x0070

    # The linear sweep also decodes data, so a bsr target only counts when it looks like a
    # function start. jsri literal targets and explicit prologues are trusted as-is.
    calls = set()
    for pc in range(start, end, 2):
        h = rd16(pc)
        _, _, call, lit = decode(h, pc, rd32)
        if prologue(pc):
            calls.add(pc)
        if call is None or not start <= call < end:
            continue
        if lit is not None or prologue(call) or (call - 2 >= start and rd16(call - 2) == 0x00CF):
            calls.add(call)

    for pc in range(start, end, 2):
        if pc in calls:
            print(f"\nsub_{pc:06X}:")
        h = rd16(pc)
        text, _, _, _ = decode(h, pc, rd32)
        print(f"  {pc:06X}:  {h:04X}   {text}")


if __name__ == "__main__":
    main()

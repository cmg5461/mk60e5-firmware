"""Dump the CAN message/signal/variable tables from an MK60E5 application image.

Layout found in 7846411A (1M), CPU addresses (file address - 0x8000):
  header      0xD82D5  (+0x10: n_tx, +0x11: n_rx; +0x0C: u16 offset of signal table from 0xD82E2)
  messages    0xD82F5  23-byte records, TX first then RX
                +2 u16 CAN id   +4 flags|DLC   +6 period (10 ms units, 0xFF = event / none)
                +10 n_signals   +11..12 u16 first signal index   +13 mailbox
  signals     header-derived, 5-byte records
                +0 flags|bit length   +1 position (bit<<4 | byte)   +3..4 u16 variable id
  variables   0xD8C34  8-byte records: +0 type (low 3 bits)  +1 default  +4 u32 callback
"""
import argparse
import struct

HDR, MSG, VAR = 0xD82D5, 0xD82F5, 0xD8C34
SIG_BASE = 0xD82E2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--base", type=lambda s: int(s, 0), default=-0x8000)
    args = ap.parse_args()
    data = open(args.image, "rb").read()

    def b(a, n=1):
        return data[a - args.base:a - args.base + n]

    def u16(a):
        return struct.unpack(">H", b(a, 2))[0]

    def u32(a):
        return struct.unpack(">I", b(a, 4))[0]

    n_tx, n_rx = b(HDR + 0x10)[0], b(HDR + 0x11)[0]
    sig_tab = SIG_BASE + u16(HDR + 0x0C)
    print(f"# CAN map\n\nheader {HDR:#x}: {n_tx} TX, {n_rx} RX; messages {MSG:#x}; "
          f"signals {sig_tab:#x}; variables {VAR:#x}\n")
    for i in range(n_tx + n_rx):
        m = MSG + 23 * i
        cid, fl, per = u16(m + 2), b(m + 4)[0], b(m + 6)[0]
        nsig, first, mbox = b(m + 10)[0], u16(m + 11), b(m + 13)[0]
        direction = "TX" if i < n_tx else "RX"
        period = "event" if per == 0xFF else f"{per * 10} ms"
        print(f"## {direction} 0x{cid:03X}  dlc {fl & 0x0F}  flags {fl >> 4:#x}  {period}  mailbox {mbox}")
        print("| sig | byte.bit | bits | flags | var | type | callback |")
        print("|---|---|---|---|---|---|---|")
        for s in range(first, first + nsig):
            sd = sig_tab + 5 * s
            f0, pos, var = b(sd)[0], b(sd + 1)[0], u16(sd + 3)
            v = VAR + 8 * var
            print(f"| {s} | {pos & 15}.{pos >> 4} | {f0 & 0x1F} | {f0 >> 5:#x} | 0x{var:03X} | "
                  f"{b(v)[0] & 7} | {u32(v + 4):#08x} |")
        print()


if __name__ == "__main__":
    main()

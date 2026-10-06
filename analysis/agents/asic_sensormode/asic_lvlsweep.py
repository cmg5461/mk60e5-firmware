#!/usr/bin/env python
"""Per-channel field sweep (regs 0x154/15C/164/16C, stock 0x1B = 27) with a precise
E46-like stimulus from the ESP32 rig on FL (pattern A, 7/14 mA square).

usage:  asic_lvlsweep.py check            -> just watch the observable ~3 s (controls)
        asic_lvlsweep.py sweep [lo hi]    -> sweep values lo..hi (hex, default 00..3F)

Observable (validated earlier with an E90 positive control): edge counters 0x40339A..9D
and interval words 0x40339E..A1 move when edges reach the MCU. Each candidate is
re-written continuously (no sleep) to beat the firmware's periodic re-init."""
import importlib.util, sys, time
spec = importlib.util.spec_from_file_location("m", r"C:\repos\e92_mk60e5\tools\mk60_can.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

CH_REGS = (0x154, 0x15C, 0x164, 0x16C)
STOCK = 0x1B

class A: pass
a = A(); a.channel = 0; a.bitrate = 500000; a.ecu = 0x29; a.req_id = 0x6F1; a.resp_id = 0x629; a.verbose = False
bus = m.open_bus(a); tp = m.IsoTp(bus, 0x6F1, 0x629, 0x29, m.TESTER_ADDR, verbose=False); uds = m.Uds(tp)

def peek(addr):
    r = uds.raw(bytes([0x23, 0x02, (addr >> 24) & 0xFF, (addr >> 16) & 0xFF, (addr >> 8) & 0xFF, addr & 0xFF]))
    return r[1:] if (r and r[0] != 0x7F) else None

def observe(seconds, value=None):
    mx = [0] * 8; seen = set(); n = 0
    t_end = time.time() + seconds
    while time.time() < t_end:
        if value is not None:
            for reg in CH_REGS:
                m._asic_xfer(uds, reg, value)
        w = peek(0x0040339A)
        if w and len(w) >= 8:
            b = w[:8]; n += 1
            for i in range(8): mx[i] = max(mx[i], b[i])
            seen.add(bytes(b[4:8]))
    hit = any(mx[:4]) or len(seen) > 1
    return mx, len(seen), n, hit

try:
    uds.start_session(0x81); uds.tester_present()
    if len(sys.argv) > 1 and sys.argv[1] == "sweep":
        lo = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x00
        hi = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x3F
        print("value(dec)  cnt(9A-9D)    intervals  samples  VERDICT")
        hits = []
        for v in range(lo, hi + 1):
            mx, nu, n, hit = observe(1.5, v)
            if hit: hits.append(v)
            print("0x%02X (%2d)   %-13s %-10d %-8d %s" % (v, v, " ".join("%02x" % x for x in mx[:4]), nu, n,
                                                      "*** HIT ***" if hit else ""))
        for reg in CH_REGS: m._asic_xfer(uds, reg, STOCK)
        print("\nrestored 0x%02X. hits:" % STOCK, ["0x%02X(%d)" % (h, h) for h in hits] or "none")
    else:
        mx, nu, n, hit = observe(3.0)
        print("stock regs: cnt=%s intervals=%d samples=%d -> %s" %
              (" ".join("%02x" % x for x in mx[:4]), nu, n, "EDGES SEEN" if hit else "no edges"))
finally:
    bus.shutdown()

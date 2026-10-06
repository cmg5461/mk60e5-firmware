"""Gentle sweep of the remaining global ASIC regs with the 7/14 stimulus on FL.
Restores to FIRMWARE INIT values (readback can differ). Stops at the first ECU hang."""
import importlib.util, time, sys
spec = importlib.util.spec_from_file_location("m", r"C:\repos\e92_mk60e5\tools\mk60_can.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
INIT = [(0x2FC, 0x0E5), (0x304, 0x0E5), (0x30C, 0x1FB), (0x314, 0x1FB), (0x264, 0x00E), (0x26C, 0x1AA),
        (0x274, 0x0C0), (0x284, 0x0FF), (0x28C, 0x00F), (0x2CC, 0x010), (0x2D4, 0x001), (0x2E4, 0x0E2),
        (0x2F4, 0x000), (0x24C, 0x090), (0x00C, 0x002)]
GENTLE_ONLY = {0x24C, 0x00C}
start = int(sys.argv[1], 16) if len(sys.argv) > 1 else None
class A: pass
a = A(); a.channel = 0; a.bitrate = 500000; a.ecu = 0x29; a.req_id = 0x6F1; a.resp_id = 0x629; a.verbose = False
bus = m.open_bus(a); tp = m.IsoTp(bus, 0x6F1, 0x629, 0x29, m.TESTER_ADDR, verbose=False); uds = m.Uds(tp)
def peek(addr):
    r = uds.raw(bytes([0x23, 0x02, (addr >> 24) & 0xFF, (addr >> 16) & 0xFF, (addr >> 8) & 0xFF, addr & 0xFF]))
    return r[1:] if (r and r[0] != 0x7F) else None
def observe(sec, write):
    mx = [0]*4; seen = set(); t_end = time.time() + sec
    while time.time() < t_end:
        m._asic_xfer(uds, *write)
        w = peek(0x0040339A)
        if w and len(w) >= 8:
            for i in range(4): mx[i] = max(mx[i], w[i])
            seen.add(bytes(w[4:8]))
    return mx, len(seen)
def cands(o, gentle):
    c = set()
    for f in (0.875, 1.125, 0.75, 1.25) + (() if gentle else (0.5, 1.5)):
        c.add(int(round(o * f)))
    c |= {o - 1, o + 1, o - 2, o + 2}
    if not gentle: c |= {0x000, 0x080, 0x200, 0x3FF}
    return [v for v in sorted(c) if 0 <= v <= 0x3FF and v != o and not (gentle and v == 0)]
try:
    uds.start_session(0x81); uds.tester_present()
    go = start is None
    for reg, o in INIT:
        if not go:
            go = (reg == start)
            if not go: continue
        hits = []
        for v in cands(o, reg in GENTLE_ONLY):
            try:
                mx, nu = observe(1.0, (reg, v))
            except Exception as e:
                print("!!! HANG/NO RESPONSE at reg 0x%03X value 0x%03X (%s) -- power-cycle, then resume with arg %03X"
                      % (reg, v, e, INIT[INIT.index((reg, o)) + 1][0] if (reg, o) != INIT[-1] else 0), flush=True)
                sys.exit(2)
            if any(mx) or nu > 1: hits.append("0x%03X" % v)
        m._asic_xfer(uds, reg, o)
        rx, _ = m._asic_xfer(uds, reg & ~7, 0)
        print("0x%03X init 0x%03X | tried %d values | hits: %s | restored, reads 0x%03X"
              % (reg, o, len(cands(o, reg in GENTLE_ONLY)), " ".join(hits) or "none", rx[1] & 0x3FF), flush=True)
    print("DONE", flush=True)
finally:
    bus.shutdown()

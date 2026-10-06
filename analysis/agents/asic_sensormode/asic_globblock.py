import importlib.util, time
spec = importlib.util.spec_from_file_location("m", r"C:\repos\e92_mk60e5\tools\mk60_can.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class A: pass
a = A(); a.channel = 0; a.bitrate = 500000; a.ecu = 0x29; a.req_id = 0x6F1; a.resp_id = 0x629; a.verbose = False
bus = m.open_bus(a); tp = m.IsoTp(bus, 0x6F1, 0x629, 0x29, m.TESTER_ADDR, verbose=False); uds = m.Uds(tp)
REGS = [0x174, 0x17C, 0x21C, 0x104, 0x10C, 0x224, 0x194, 0x1AC, 0x1C4, 0x1DC, 0x1E4, 0x1EC, 0x1F4, 0x1FC,
        0x23C, 0x24C, 0x264, 0x26C, 0x274, 0x284, 0x28C, 0x2CC, 0x2D4, 0x2E4, 0x2F4, 0x2FC, 0x304, 0x30C, 0x314, 0x00C]
def peek(addr):
    r = uds.raw(bytes([0x23, 0x02, (addr >> 24) & 0xFF, (addr >> 16) & 0xFF, (addr >> 8) & 0xFF, addr & 0xFF]))
    return r[1:] if (r and r[0] != 0x7F) else None
def rd(wreg): rx, _ = m._asic_xfer(uds, wreg & ~7, 0); return rx[1] & 0x3FF
def counting(sec, write=None):
    seen = set(); t_end = time.time() + sec
    while time.time() < t_end:
        if write: m._asic_xfer(uds, *write)
        w = peek(0x0040339A)
        if w and len(w) >= 8: seen.add(bytes(w[4:8]))
    return len(seen)
try:
    uds.start_session(0x81); uds.tester_present()
    base = counting(1.5)
    print("baseline distinct intervals/1.5s: %d (%s)" % (base, "COUNTING" if base > 1 else "NOT COUNTING - abort"), flush=True)
    if base > 1:
        for reg in REGS:
            o = rd(reg)
            z = counting(1.2, (reg, 0x000)); f = counting(1.2, (reg, 0x3FF))
            m._asic_xfer(uds, reg, o); r = counting(1.0)
            flag = "  <== AFFECTS COUNTING" if (z <= 1 or f <= 1) else ""
            print("0x%03X orig 0x%03X | @000: %2d  @3FF: %2d  restored: %2d (rb 0x%03X)%s" % (reg, o, z, f, r, rd(reg), flag), flush=True)
finally:
    bus.shutdown()

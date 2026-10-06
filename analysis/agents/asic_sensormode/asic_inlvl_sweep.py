import importlib.util, sys, time
spec = importlib.util.spec_from_file_location("m", r"C:\repos\e92_mk60e5\tools\mk60_can.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
REGS = [0x114 + 8*i for i in range(8)]          # 0x114..0x14C, inputs 0..7
class A: pass
a = A(); a.channel = 0; a.bitrate = 500000; a.ecu = 0x29; a.req_id = 0x6F1; a.resp_id = 0x629; a.verbose = False
bus = m.open_bus(a); tp = m.IsoTp(bus, 0x6F1, 0x629, 0x29, m.TESTER_ADDR, verbose=False); uds = m.Uds(tp)
def peek(addr):
    r = uds.raw(bytes([0x23, 0x02, (addr >> 24) & 0xFF, (addr >> 16) & 0xFF, (addr >> 8) & 0xFF, addr & 0xFF]))
    return r[1:] if (r and r[0] != 0x7F) else None
def readreg(reg):                                # write 0, take prior value, write it back
    rx, _ = m._asic_xfer(uds, reg, 0); prior = rx[1] & 0x3FF
    m._asic_xfer(uds, reg, prior); return prior
try:
    uds.start_session(0x81); uds.tester_present()
    stock = {r: readreg(r) for r in REGS}
    print("stock:", " ".join("0x%03X=0x%03X" % (r, v) for r, v in stock.items()), flush=True)
    hits = []
    for reg in REGS:
        line = []
        for v in range(0x000, 0x400, 0x10):
            mx = [0]*4; seen = set(); t_end = time.time() + 0.8
            while time.time() < t_end:
                m._asic_xfer(uds, reg, v)
                w = peek(0x0040339A)
                if w and len(w) >= 8:
                    for i in range(4): mx[i] = max(mx[i], w[i])
                    seen.add(bytes(w[4:8]))
            if any(mx) or len(seen) > 1:
                hits.append((reg, v, mx)); line.append("%03X*" % v)
        m._asic_xfer(uds, reg, stock[reg])
        print("reg 0x%03X swept, restored 0x%03X; hits: %s" % (reg, stock[reg], " ".join(line) or "none"), flush=True)
    print("TOTAL HITS:", [("0x%03X" % r, "0x%03X" % v, mx) for r, v, mx in hits] or "none")
finally:
    bus.shutdown()

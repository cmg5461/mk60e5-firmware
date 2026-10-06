import importlib.util, time
spec = importlib.util.spec_from_file_location("m", r"C:\repos\e92_mk60e5\tools\mk60_can.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class A: pass
a = A(); a.channel = 0; a.bitrate = 500000; a.ecu = 0x29; a.req_id = 0x6F1; a.resp_id = 0x629; a.verbose = False
bus = m.open_bus(a); tp = m.IsoTp(bus, 0x6F1, 0x629, 0x29, m.TESTER_ADDR, verbose=False); uds = m.Uds(tp)
def peek(addr):
    r = uds.raw(bytes([0x23, 0x02, (addr >> 24) & 0xFF, (addr >> 16) & 0xFF, (addr >> 8) & 0xFF, addr & 0xFF]))
    return r[1:] if (r and r[0] != 0x7F) else None
def rd(wreg): rx, _ = m._asic_xfer(uds, wreg & ~7, 0); return rx[1] & 0x3FF   # read cmd = low bits 000
def observe(sec, writes):
    mx = [0]*4; seen = set(); t_end = time.time() + sec
    while time.time() < t_end:
        for r, v in writes: m._asic_xfer(uds, r, v)
        w = peek(0x0040339A)
        if w and len(w) >= 8:
            for i in range(4): mx[i] = max(mx[i], w[i])
            seen.add(bytes(w[4:8]))
    return mx, len(seen)
try:
    uds.start_session(0x81); uds.tester_present()
    for ch in range(4):
        lm, mh = 0x184 + ch*0x18, 0x18C + ch*0x18
        o_lm, o_mh = rd(lm), rd(mh)
        print("ch%d regs 0x%03X/0x%03X orig 0x%03X/0x%03X" % (ch, lm, mh, o_lm, o_mh), flush=True)
        for (vl, vm) in [(o_lm, o_mh), (o_lm, 0x3FF), (0x3FF, 0x3FF), (0x000, 0x000), (o_lm, o_mh)]:
            mx, nu = observe(1.5, [(lm, vl), (mh, vm)])
            hit = any(mx) or nu > 1
            print("   LM=0x%03X MH=0x%03X  cnt=%s intervals=%d %s" % (vl, vm, " ".join("%02x" % x for x in mx), nu,
                  "*** HIT ***" if hit else ""), flush=True)
        m._asic_xfer(uds, lm, o_lm); m._asic_xfer(uds, mh, o_mh)
        print("   restored -> read back 0x%03X/0x%03X" % (rd(lm), rd(mh)), flush=True)
finally:
    bus.shutdown()

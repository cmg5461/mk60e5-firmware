import importlib.util
spec = importlib.util.spec_from_file_location("m", r"C:\repos\e92_mk60e5\tools\mk60_can.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class A: pass
a = A(); a.channel = 0; a.bitrate = 500000; a.ecu = 0x29; a.req_id = 0x6F1; a.resp_id = 0x629; a.verbose = False
bus = m.open_bus(a); tp = m.IsoTp(bus, 0x6F1, 0x629, 0x29, m.TESTER_ADDR, verbose=False); uds = m.Uds(tp)
REGS = [0x030, 0x050, 0x090, 0x098, 0x0A0, 0x0A8, 0x0B0, 0x0C8, 0x0E8, 0x0F0, 0x240, 0x248, 0x260, 0x290, 0x2F0]
try:
    uds.start_session(0x81); uds.tester_present()
    vals = {r: [] for r in REGS}
    for _ in range(12):
        for r in REGS:
            rx, _ = m._asic_xfer(uds, r, 0); vals[r].append(rx[1] & 0x3FF)
    for r in REGS:
        v = vals[r]; print("0x%03X  min 0x%03X max 0x%03X  %s" % (r, min(v), max(v), " ".join("%03X" % x for x in v)))
finally:
    bus.shutdown()

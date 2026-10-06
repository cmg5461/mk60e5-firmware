import importlib.util
spec = importlib.util.spec_from_file_location("m", r"C:\repos\e92_mk60e5\tools\mk60_can.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class A: pass
a = A(); a.channel = 0; a.bitrate = 500000; a.ecu = 0x29; a.req_id = 0x6F1; a.resp_id = 0x629; a.verbose = False
bus = m.open_bus(a); tp = m.IsoTp(bus, 0x6F1, 0x629, 0x29, m.TESTER_ADDR, verbose=False); uds = m.Uds(tp)
try:
    uds.start_session(0x81); uds.tester_present()
    rows = []
    for base in range(0x000, 0x400, 8):           # read command = low 3 bits 000 (non-destructive)
        rx, nrc = m._asic_xfer(uds, base, 0)
        rows.append((base, rx))
    for i in range(0, len(rows), 8):
        print("  ".join("%03X:%s" % (b, ("%03X" % (rx[1] & 0x3FF)) if rx else "NRC") for b, rx in rows[i:i+8]))
    rx0 = set(rx[0] for _, rx in rows if rx)
    print("RX0 values seen:", ["0x%04X" % v for v in sorted(rx0)])
finally:
    bus.shutdown()

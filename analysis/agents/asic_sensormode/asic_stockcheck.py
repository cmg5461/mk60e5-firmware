import importlib.util
spec = importlib.util.spec_from_file_location("m", r"C:\repos\e92_mk60e5\tools\mk60_can.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class A: pass
a = A(); a.channel = 0; a.bitrate = 500000; a.ecu = 0x29; a.req_id = 0x6F1; a.resp_id = 0x629; a.verbose = False
bus = m.open_bus(a); tp = m.IsoTp(bus, 0x6F1, 0x629, 0x29, m.TESTER_ADDR, verbose=False); uds = m.Uds(tp)
# expected stock values (read IDs) from the clean dump
EXP = {0x110:None,0x118:0x00B,0x120:0x00B,0x128:0x00B,0x130:0x00B,0x138:None,0x140:0x00B,0x148:0x00B,
       0x150:0x01B,0x158:0x01B,0x160:0x01B,0x168:0x01B,
       0x180:0x137,0x188:0x2C5,0x198:0x126,0x1A0:0x2CD,0x1B0:0x1E5,0x1B8:0x22F,0x1C8:0x1E5,0x1D0:0x22F}
try:
    uds.start_session(0x81); uds.tester_present()
    bad = []
    for r, e in EXP.items():
        rx, _ = m._asic_xfer(uds, r, 0); v = rx[1] & 0x3FF
        ok = (e is None and v in (0x00A, 0x00B)) or v == e
        if not ok: bad.append(r)
        print("0x%03X = 0x%03X %s" % (r, v, "" if ok else "<-- expected %s" % ("00A/00B" if e is None else "0x%03X" % e)))
    print("ALL STOCK" if not bad else "NOT STOCK: %s" % ["0x%03X" % b for b in bad])
finally:
    bus.shutdown()

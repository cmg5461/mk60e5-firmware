#!/usr/bin/env python
"""Phase-2 live sweep: input-threshold regs 0x114-0x14C and per-channel flag
0x224, watching 0x40339A..A1 (counters + interval). Spin E46 on FL throughout.
HIT = any counter nonzero OR interval word changes (nuniq>1)."""
import importlib.util, time
spec=importlib.util.spec_from_file_location("m", r"C:\repos\e92_mk60e5\tools\mk60_can.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

INPUT_REGS=[0x114,0x11C,0x124,0x12C,0x134,0x13C,0x144,0x14C]
FLAG_REG=0x224
THRESH_VALS=[0x000,0x020,0x040,0x060,0x080,0x0A0,0x0C0,0x0E0,0x100,0x140,0x180,0x200,0x280,0x300,0x3FF]
FLAG_VALS=[0x322,0x000,0x0FF,0x100,0x300,0x3FF]

class A: pass
a=A(); a.channel=0; a.bitrate=500000; a.ecu=0x29; a.req_id=0x6F1; a.resp_id=0x629; a.verbose=False
bus=m.open_bus(a); tp=m.IsoTp(bus,0x6F1,0x629,0x29,m.TESTER_ADDR,verbose=False); uds=m.Uds(tp)
def peek(addr):
    r=uds.raw(bytes([0x23,0x02,(addr>>24)&0xFF,(addr>>16)&0xFF,(addr>>8)&0xFF,addr&0xFF]))
    return r[1:] if (r and r[0]!=0x7F) else None
def test(label, writes):
    mx=[0]*8; seen=set()
    for _ in range(9):                       # ~2.7s
        for reg,val in writes: m._asic_xfer(uds,reg,val)
        w=peek(0x0040339A)
        if w and len(w)>=8:
            for i in range(8): mx[i]=max(mx[i],w[i])
            seen.add(bytes(w[4:8]))
        time.sleep(0.3)
    hit=any(mx) or len(seen)>1
    print("%-22s cnt %s  intv %s  nuniq %d  %s"%(label,
        " ".join("%02x"%x for x in mx[:4])," ".join("%02x"%x for x in mx[4:8]),
        len(seen),"*** HIT ***" if hit else ""))
    return hit
try:
    uds.start_session(0x81); uds.tester_present()
    hits=[]
    print("== input thresholds 0x114-0x14C (all 8 set to V) ==")
    for v in THRESH_VALS:
        if test("thresh=0x%03X"%v, [(r,v) for r in INPUT_REGS]): hits.append("thr%03X"%v)
    # restore stock-ish thresholds before flag phase
    for r in INPUT_REGS: m._asic_xfer(uds,r,0xBF)
    print("== per-channel flag 0x224 ==")
    for v in FLAG_VALS:
        if test("flag0x224=0x%03X"%v, [(FLAG_REG,v)]): hits.append("flag%03X"%v)
    m._asic_xfer(uds,FLAG_REG,0x322)
    print("\nhits:", hits or "none")
finally:
    bus.shutdown()

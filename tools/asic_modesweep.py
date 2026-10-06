#!/usr/bin/env python
"""Live sensor-mode sweep on the patched 0x23 probe. Spin the E46 on FL
continuously. For each candidate value V, write V to the four per-channel mode
regs 0x154/15C/164/16C (re-written every poll to beat the firmware's periodic
re-init), then poll the live edge counters 0x40339A (4 bytes) + snapshot
0x4033AE (4 bytes). Any nonzero => edges reached the MCU for that V = a HIT."""
import importlib.util, time
spec=importlib.util.spec_from_file_location("m", r"C:\repos\e92_mk60e5\tools\mk60_can.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

CH_REGS=(0x154,0x15C,0x164,0x16C)
# candidate values: control, extremes, single-bit flips of the stock 0x1B,
# and a few wider values (field may be up to 10 bits).
BASE=0x1B
CANDS=[0x1B,0x00,0x3F]+[BASE ^ (1<<b) for b in range(10)]+[0x1FF,0x3FF,0x0C0|BASE]

class A: pass
a=A(); a.channel=0; a.bitrate=500000; a.ecu=0x29; a.req_id=0x6F1; a.resp_id=0x629; a.verbose=False
bus=m.open_bus(a); tp=m.IsoTp(bus,0x6F1,0x629,0x29,m.TESTER_ADDR,verbose=False); uds=m.Uds(tp)

def peek(addr):
    r=uds.raw(bytes([0x23,0x02,(addr>>24)&0xFF,(addr>>16)&0xFF,(addr>>8)&0xFF,addr&0xFF]))
    return r[1:] if (r and r[0]!=0x7F) else None

try:
    uds.start_session(0x81); uds.tester_present()
    print("candidate  cnt(0x339A-9D)  interval(0x339E-A1)  nuniq  VERDICT")
    hits=[]
    for v in CANDS:
        mx=[0]*8; seen=set()                   # track 0x40339A..0x4033A1 (8 bytes)
        for _ in range(10):                    # ~3s per candidate
            for reg in CH_REGS: m._asic_xfer(uds,reg,v)   # (re)write all 4 channels
            w=peek(0x0040339A)
            if w and len(w)>=8:
                b=w[:8]
                for i in range(8): mx[i]=max(mx[i],b[i])
                seen.add(bytes(b[4:8]))         # distinct interval words = activity
            time.sleep(0.3)
        hit = any(mx) or len(seen)>1            # any counter nonzero OR interval word changing
        if hit: hits.append(v)
        print("0x%03X      %-15s %-20s %-5d %s" % (
            v, " ".join("%02x"%x for x in mx[:4]), " ".join("%02x"%x for x in mx[4:8]),
            len(seen), "*** HIT ***" if hit else ""))
    for reg in CH_REGS: m._asic_xfer(uds,reg,BASE)
    print("\nrestored channel regs to 0x%02X. hits:"%BASE, ["0x%03X"%h for h in hits] or "none")
finally:
    bus.shutdown()

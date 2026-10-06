import struct,collections
d=open('flash/bin/7846411A_00000000.bin','rb').read()
def lits(lo,hi):
    r=collections.defaultdict(list)
    for a in range(lo,hi,2):
        v=struct.unpack('>I',d[a+8000*0+0x8000:a+0x8000+4])[0] if False else struct.unpack('>I',d[a+0x8000:a+0x8004])[0]
        r[v].append(a)
    return r
L=lits(0x80000,0xB4000)
import sys
cal=collections.Counter()
for v,al in L.items():
    if al and (0x30000<=v<0x45000 or 0xDA000<=v<0xDC000) : cal[v]=len(al)
for v in sorted(cal): print(hex(v),cal[v],[hex(x) for x in L[v][:4]])

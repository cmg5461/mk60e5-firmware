import struct,re,collections,sys,bisect
d=open('flash/bin/7846411A_00000000.bin','rb').read()
subs=sorted(int(m.group(1),16) for m in re.finditer(r'^sub_([0-9A-F]+):',open('analysis/7846411A_main.lst').read(),re.M))
def fn(a): return subs[bisect.bisect_right(subs,a)-1]
lo,hi=int(sys.argv[1],16),int(sys.argv[2],16)
for a in range(0x40000,0xF0000,2):
    v=struct.unpack('>I',d[a+0x8000:a+0x8004])[0]
    if lo<=v<hi: print(hex(a),hex(v),'fn',hex(fn(a)))

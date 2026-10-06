import struct,re,collections,sys
d=open('flash/bin/7846411A_00000000.bin','rb').read()
# function starts from listing
subs=[int(m.group(1),16) for m in re.finditer(r'^sub_([0-9A-F]+):',open('analysis/7846411A_main.lst').read(),re.M)]
subs.sort()
import bisect
def fn(a): 
    i=bisect.bisect_right(subs,a)-1; return subs[i]
def w(a): return struct.unpack('>I',d[a+0x8000:a+0x8004])[0]
targets=[int(x,16) for x in sys.argv[1:]]
for a in range(0x70000,0xF0000,2):
    v=w(a)
    for t in targets:
        if t<=v<t+0x10 and v>=0x400000 or (v==t):
            print(hex(a),hex(v),'fn',hex(fn(a)))

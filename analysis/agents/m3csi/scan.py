import struct,sys
def scan(path,lo,hi,off=0x8000):
    d=open(path,'rb').read()
    out=[]
    for i in range(0,len(d)-3,2):
        v=struct.unpack('>I',d[i:i+4])[0]
        if lo<=v<hi: out.append((i-off,v))
    return out
for name,p,lo,n in(('M3','flash/bin/7846816A_00000000.bin',0x40EA8,0x114),('1M','flash/bin/7846411A_00000000.bin',0x40A04,0xB2)):
    print(name)
    for a,v in scan(p,lo,lo+n): print(hex(a),hex(v),hex(v-lo))

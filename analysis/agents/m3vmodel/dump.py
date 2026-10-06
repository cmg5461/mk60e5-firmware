import struct
d=open('flash/bin/7846816A_00000000.bin','rb').read()
a=0xD6E16
while a<0xD7100:
    v=struct.unpack('>12h',d[a+0x8000:a+0x8000+24])
    print(hex(a),v,sum(v[:1]))
    a+=24

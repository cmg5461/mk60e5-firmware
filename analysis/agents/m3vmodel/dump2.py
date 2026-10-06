import struct
d=open('flash/bin/7846816A_00000000.bin','rb').read()
a=0xD6ECA-0x18*8
while a<0xD7110:
    v=struct.unpack('>12h',d[a+0x8000:a+0x8000+24])
    print(hex(a),list(v))
    a+=24

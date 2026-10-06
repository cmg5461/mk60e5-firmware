import struct
a=open('flash/bin/7846816A_00000000.bin','rb').read()
def h(c,n): return list(struct.unpack('>%dh'%n,a[c+0x8000:c+0x8000+2*n]))
print('COA hdr',a[0x41978+0x8000:0x41978+0x8000+16].hex())
print('BCO hdr',a[0x41758+0x8000:0x41758+0x8000+16].hex())
COA=0x41978;BCO=0x41758
print('--BCO whole s16 (offset: values)')
b=h(BCO,0x110)
for i in range(0,0x110,8): print(hex(i*2),b[i:i+8])
print('--COA whole')
c=h(COA,0x1B6)
for i in range(0,0x1B6,8): print(hex(i*2),c[i:i+8])
print('--ROM idx tables (8 s16)')
for n,ad in [('d7156',0xd7156),('daa1c',0xdaa1c),('daa20',0xdaa20),('daa2c',0xdaa2c),('daa30',0xdaa30),('daa40',0xdaa40),('f672e',0xf672e),('f673a',0xf673a),('f6742',0xf6742),('f674a',0xf674a),('f6752',0xf6752),('f673e',0xf673e)]:
    print(n,h(ad,8))

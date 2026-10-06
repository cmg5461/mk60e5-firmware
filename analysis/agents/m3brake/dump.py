import struct
a=open('flash/bin/7846816A_00000000.bin','rb').read()
def h(c,n,s=True): return list(struct.unpack('>%d%s'%(n,'h' if s else 'H'),a[c+0x8000:c+0x8000+2*n]))
COA=0x41978
print('pressure axis COA+0x1D6',h(COA+0x1D6,10))
for nm,o in [('F0',0x1EA),('F1',0x1FE),('R0',0x212),('R1',0x226),('after',0x23A)]:
    print(nm,hex(o),h(COA+o,10))

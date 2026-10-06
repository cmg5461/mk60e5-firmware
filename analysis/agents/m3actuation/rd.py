import sys,struct
B=open('flash/bin/7846816A_00000000.bin','rb').read()
for a in sys.argv[1:]:
    a=int(a,16); o=a+0x8000 if False else a
    # CPU addr = file offset - 0x8000 -> offset=cpu+0x8000
    off=a+0x8000
    print(hex(a),'u16',struct.unpack('>H',B[off:off+2])[0],'s16',struct.unpack('>h',B[off:off+2])[0],B[off:off+16].hex())

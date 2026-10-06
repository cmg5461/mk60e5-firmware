"""Reproduction of MK60E5 background ROM self-test signature (HW unit 0xD50200).
Per 32-bit big-endian word w: s = ((s<<1) ^ (0x00400007 if s>>31 else 0)) & 0xFFFFFFFF ; s ^= w.  Seed 0, no xorout.
File offset = CPU + 0x8000. Expected value = BE u32 stored at range end address."""
import struct,sys
M=0xFFFFFFFF; POLY=0x00400007
def sig(img,start,end):
    s=0
    for (w,) in struct.iter_unpack('>I',img[start+0x8000:end+0x8000]):
        s=((s<<1)^(POLY if s>>31 else 0))&M
        s^=w
    return s
if __name__=='__main__':
    img=open(sys.argv[1] if len(sys.argv)>1 else '../../../flash/bin/7846411A_00000000.bin','rb').read()
    tab=0xD7584+0x8000
    for i in range(3):
        a,b=struct.unpack('>II',img[tab+8*i:tab+8*i+8])
        exp=struct.unpack('>I',img[b+0x8000:b+0x8004])[0]; got=sig(img,a,b)
        print(hex(a),hex(b),hex(exp),hex(got),'MATCH' if exp==got else 'NO')

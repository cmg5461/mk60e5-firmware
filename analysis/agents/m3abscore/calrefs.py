import re,struct,sys
from prof import ins,order,fm
B=open('../../../flash/bin/7846816A_00000000.bin','rb').read()
def raw(a,n=2): return B[a+0x8000:a+0x8000+n].hex()
def s16(a): return struct.unpack('>h',B[a+0x8000:a+0x8002])[0]
fns=[int(x,16) for x in sys.argv[1:]]
for a,n in fm:
    if a in fns:
        refs={}
        for x in order:
            if a<=x<a+n:
                m=re.search(r'lrw .*= 0x([0-9a-f]{8})',ins[x])
                if m:
                    v=int(m.group(1),16)
                    if 0x4039C<=v<0x40EAC: refs[v]=1
        print('%05X:'%a,' '.join('%X(+%X)=%d[%s]'%(v,v-0x4039C,s16(v),raw(v)) for v in sorted(refs)))

import struct,math
M=open('flash/bin/7846816A_00000000.bin','rb').read()
def row(a): return list(struct.unpack('>12h',M[a+0x8000:a+0x8000+24]))
lf=row(0xD6F42);lr=row(0xD6F5A);ms=row(0xD6F72);cf=row(0xD6ECA);cr=row(0xD6EE2)
def tdiv(a,b): 
    q=abs(a)//abs(b); return q if (a<0)==(b<0) else -q
def calc(lf,lr,m,cf,cr):
    L=lf+lr
    ae8=tdiv(L*675,1024)
    r7=(cr*cf)//m
    r4=tdiv(r7*L,128)
    den=cr*lr-cf*lf
    den=tdiv(den,32)
    r2=(383*r4)//den if den>0 else None
    return L,ae8,r2
for v in range(12):
    L,ae8,aea=calc(lf[v],lr[v],ms[v],cf[v],cr[v])
    vch2=32*aea*ae8 if aea else None
    print(v,lf[v],lr[v],ms[v],cf[v],cr[v],'L',L,'AE8',ae8,'AEA',aea,'32*AEA*AE8',vch2, math.sqrt(vch2)/100 if vch2 else None)
print('1M',calc(1331,1393,1739,7186,12857))
a=calc(1331,1393,1739,7186,12857);print(math.sqrt(32*a[2]*a[1]))

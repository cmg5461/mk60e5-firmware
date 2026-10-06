import struct
d=open('flash/bin/7846411A_00000000.bin','rb').read()
b=0x40AB8+0x8000
def w(o): return struct.unpack('>h',d[b+o:b+o+2])[0]
def curve(o):
    mn,mx,n=w(o),w(o+2),w(o+4)
    xs=[w(o+6+2*i) for i in range(n-1)]
    A=[w(o+6+2*(n-1)+2*i) for i in range(n)]
    B=[w(o+6+2*(n-1)+2*n+2*i) for i in range(n)]
    return mn,mx,n,xs,A,B
def ev(o,x):
    mn,mx,n,xs,A,B=curve(o)
    k=sum(1 for v in xs if v<x)   # segment index (x==break -> lower seg; equal anyway by continuity)
    y=A[k]+int(x*B[k]/1024)
    return max(mn,min(mx,y))
import sys
if __name__=='__main__':
    SP=[0,500,1000,1500,2000,2500,3000,4000,5000,6000,8000,10000,12000,15000,20000]
    for o in [0x86,0xa8,0xca,0xec,0x10e,0x130,0x5c6,0x5e2,0x5fe,0x180,0x19c,0x1b8,0x66e,0x690,0x6b2,0x6d4,0x6f6,0x718,0x534,0x550,0x56c]:
        print('+%03x'%o,' '.join('%d:%d'%(x//100,ev(o,x)) for x in SP))

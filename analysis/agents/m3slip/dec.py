import struct,sys
d=open('flash/bin/7846816A_00000000.bin','rb').read()
def s16(a): return struct.unpack('>h',d[a+0x8000:a+0x8002])[0]
def rec(a):
    lo,hi,n=s16(a),s16(a+2),s16(a+4)
    if not 1<=n<=20: return None
    x=[s16(a+6+2*i) for i in range(n-1)]
    c=[s16(a+6+2*(n-1)+2*i) for i in range(n)]
    k=[s16(a+6+2*(n-1)+2*n+2*i) for i in range(n)]
    return lo,hi,n,x,c,k,6+2*(3*n-1)
def ev(r,v):
    lo,hi,n,x,c,k,_=r
    i=sum(1 for b in x if v>b)
    p=v*k[i]; q=int(p/1024) if p>=0 else -int(-p/1024)
    return max(lo,min(hi,c[i]+q))
if __name__=='__main__':
    a=int(sys.argv[1],16)
    r=rec(a);print(hex(a),r)
    if r:
        for v in map(int,sys.argv[2:]): print(v,ev(r,v))

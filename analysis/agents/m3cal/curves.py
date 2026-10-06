import struct,sys
def load(bin,cpu,ln):
    d=open(bin,'rb').read(); b=cpu+0x8000
    return list(struct.unpack('>%dh'%(ln//2),d[b:b+ln]))
def ev(c,x):
    lo,hi,n=c[0],c[1],c[2]
    xs=c[3:3+n-1]; cs=c[3+n-1:3+n-1+n]; ks=c[3+2*n-1:3+3*n-1]
    i=0
    while i<n-1 and x>=xs[i]: i+=1   # reader: counts breakpoints < x? approximate
    y=cs[i]+((x*ks[i])>>10)
    return max(lo,min(hi,y))
def tryparse(w,o,tol=3):
    if o+3>len(w): return None
    lo,hi,n=w[o:o+3]
    if not(2<=n<=9) or lo>hi: return None
    L=3+(n-1)+2*n
    if o+L>len(w): return None
    c=w[o:o+L]
    xs=c[3:3+n-1]
    if any(xs[i]>=xs[i+1] for i in range(n-2)): return None
    cs=c[3+n-1:3+2*n-1]; ks=c[3+2*n-1:]
    if n>=2:
        for i in range(n-1):
            x=xs[i]
            a=cs[i]+((x*ks[i])>>10); b=cs[i+1]+((x*ks[i+1])>>10)
            # allow clamp
            a=max(lo,min(hi,a));b=max(lo,min(hi,b))
            if abs(a-b)>tol: return None

    return L
def scan(w):
    res=[];o=0
    while o<len(w):
        L=tryparse(w,o)
        if L and w[o+2]>=2:
            res.append((o,L)); o+=L
        else: o+=1
    return res
if __name__=='__main__':
    bin,cpu,ln=sys.argv[1],int(sys.argv[2],16),int(sys.argv[3],16)
    w=load(bin,cpu,ln)
    # body starts at word 6 (+0x0C)
    for o,L in scan(w):
        if o<6: continue
        c=w[o:o+L]
        print('+0x%03X len %2d lo=%d hi=%d n=%d x=%s c=%s k=%s'%(o*2,L,c[0],c[1],c[2],c[3:2+c[2]],c[2+c[2]:2+2*c[2]],c[2+2*c[2]:]))

import struct,json
d=open('flash/bin/7846411A_00000000.bin','rb').read()
b=0x40AB8+0x8000
W=[struct.unpack('>h',d[b+o:b+o+2])[0] for o in range(0,0x934,2)]
def w(o): return W[o//2]
refs=set(a[2] for a in json.load(open('analysis/agents/tcs/work/acc.json')))
found=[]
for o in range(0xC,0x930,2):
    mn,mx,n=w(o),w(o+2),w(o+4)
    if not(1<=n<=12) or mn>mx: continue
    L=3+(n-1)+2*n
    if o+2*L>0x934: continue
    xs=[w(o+6+2*i) for i in range(n-1)]
    if any(xs[i]>=xs[i+1] for i in range(len(xs)-1)): continue
    A=[w(o+6+2*(n-1)+2*i) for i in range(n)]
    B=[w(o+6+2*(n-1)+2*n+2*i) for i in range(n)]
    ok=True;err=0
    for i,x in enumerate(xs):
        y0=A[i]+x*B[i]/1024; y1=A[i+1]+x*B[i+1]/1024
        err=max(err,abs(y0-y1))
    if err>max(3,0.01*max(abs(mx),1)) : continue
    # nontrivial
    if n==1: continue
    found.append((o,n,L,mn,mx,xs,A,B,err))
for f in found: print('+%03x n=%d len=%d min=%d max=%d x=%s A=%s B=%s err=%.1f'%f)

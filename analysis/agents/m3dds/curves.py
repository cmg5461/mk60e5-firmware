import struct,sys
m=open('flash/bin/7846816A_00000000.bin','rb').read()
def scan(base,ln,name):
    a=base+0x8000
    x=struct.unpack('>%dh'%(ln//2),m[a:a+ln])
    res=[]
    i=6
    while i<len(x)-3:
        lo,hi,n=x[i],x[i+1],x[i+2]
        if 2<=n<=16 and lo<hi and i+3+(n-1)+2*n<=len(x):
            xs=x[i+3:i+3+n-1];cs=x[i+2+n:i+2+n+n];ks=x[i+2+2*n:i+2+3*n]
            xs=x[i+3:i+3+n-1];cs=x[i+3+n-1:i+3+2*n-1];ks=x[i+3+2*n-1:i+3+3*n-1]
            if all(xs[j]<xs[j+1] for j in range(len(xs)-1)) and all(abs(k)<20000 for k in ks):
                # continuity
                err=0
                for j in range(n-1):
                    xv=xs[j]
                    err=max(err,abs((cs[j]+ks[j]*xv/1024)-(cs[j+1]+ks[j+1]*xv/1024)))
                res.append((2*i,lo,hi,n,xs,cs,ks,err))
                i+=3+3*n-1; continue
        i+=1
    for r in res:
        print(name,'+0x%X'%r[0],'abs 0x%X'%(base+r[0]),'lo',r[1],'hi',r[2],'n',r[3],'x',r[4],'c',r[5],'k',r[6],'cont_err %.1f'%r[7])
scan(0x41E44,0x5E0,'LVC');scan(0x41D10,0x118,'DDS')

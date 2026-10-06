import struct,math
d=open('flash/bin/7846816A_00000000.bin','rb').read()
def tab(a): return struct.unpack('>12h',d[a+0x8000:a+0x8000+24])
lr=tab(0xD6F5A); lf=tab(0xD6F42); m=tab(0xD6F72); Cf=tab(0xD6ECA); Cr=tab(0xD6EE2)
def tdiv(a,b): 
    q=abs(a)//abs(b); return q if (a>=0)==(b>=0) else -q
for v in range(12):
    L=lr[v]+lf[v]
    AE8=tdiv(L*675,1024)
    r4=tdiv( ((Cr[v]*Cf[v])//m[v])*L + 0,1) ; 
    t=((Cr[v]*Cf[v])//m[v])*L
    r4=(t+ (((t>>6)&0x7f) if t<0 else 0))>>7
    den=Cr[v]*lr[v]-lf[v]*Cf[v]
    if den<0: den+=31
    den>>=5
    AEA=max(-32768,min(32767,tdiv(383*r4,den))) if den else None
    vch=math.sqrt(32*AE8*AEA)/100 if AEA and AEA>0 else None
    print(v,'L',L/1024,'AE8',AE8,'AEA',AEA,'vch km/h',vch)

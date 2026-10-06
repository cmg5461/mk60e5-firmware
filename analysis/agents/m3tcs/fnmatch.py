import re,struct,sys,collections
A=open('flash/bin/7846411A_00000000.bin','rb').read()
B=open('flash/bin/7846816A_00000000.bin','rb').read()
def mask(w):
    t=w>>12
    if t==7: return w&0xFF00
    if t==0xF: return w&0xF800
    return w
def fns(lst,lo,hi):
    r=[]
    for line in open(lst,errors='ignore'):
        m=re.match(r'^sub_([0-9A-F]{6}):',line)
        if m:
            a=int(m.group(1),16)
            if lo<=a<hi: r.append(a)
    return r
def grams(D,a,b,k=4):
    ws=struct.unpack('>%dH'%((b-a)//2),D[a+0x8000:b+0x8000])
    ws=[mask(w) for w in ws]
    return collections.Counter(tuple(ws[i:i+k]) for i in range(len(ws)-k+1))
f1=fns('analysis/7846411A_main.lst',0xC7400,0xD0000)
f3=fns('analysis/7846816A_main.lst',0xC7600,0xD0200)
def bounds(f,end):
    return [(f[i],f[i+1] if i+1<len(f) else end) for i in range(len(f))]
b1=bounds(f1,0xD0000);b3=bounds(f3,0xD0300)
g3=[(a,b,grams(B,a,b)) for a,b in b3]
for a,b in b1:
    g=grams(A,a,b)
    tot=sum(g.values())
    if tot<3: 
        continue
    best=None
    for a3,b3_,h in g3:
        s=sum((g&h).values())
        if best is None or s>best[0]: best=(s,a3,b3_)
    print(f"1M {a:06X}+{b-a:4X} -> M3 {best[1]:06X}+{best[2]-best[1]:4X} score {best[0]/tot:.2f}  d={best[1]-a:+X}")

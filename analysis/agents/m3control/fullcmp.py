import sys,re
sys.path.insert(0,'analysis/agents/m3control')
from fdiff import L1,L3
labels=sorted(int(m.group(1),16) for l in open('analysis/7846411A_main.lst',errors='ignore') for m in [re.match(r'sub_([0-9A-F]+):',l)] if m)
def end_of(a):
    nxt=[x for x in labels if x>a]; return nxt[0] if nxt else a+0x400
pool=set()
for a,(w,t) in L1.items():
    m=re.search(r'\[0x([0-9a-f]+)\]',t)
    if m and re.match(r'(lrw|jsri|jmpi)',t):
        p=int(m.group(1),16); pool.update([p,p+2])
def cmp(a1,a3):
    e=end_of(a1); bad=[];npool=0;n=0
    for o in range(0,e-a1,2):
        x=L1.get(a1+o);y=L3.get(a3+o)
        if x is None or y is None: bad.append((o,'missing'));continue
        n+=1
        if x[0]!=y[0]:
            if a1+o in pool: npool+=1
            else: bad.append((hex(o),x,y))
    return e-a1,n,npool,bad
if __name__=='__main__':
    for arg in sys.argv[1:]:
        a,b=[int(t,16) for t in arg.split(':')]
        ln,n,np_,bad=cmp(a,b)
        print(f'{a:06X}->{b:06X} len {ln:#x} words {n} pooldiff {np_} real-mismatch {len(bad)}', bad[:3])

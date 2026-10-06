import sys,json
sys.path.insert(0,'analysis/agents/m3control')
from fdiff import L1,L3
from fullcmp import labels,end_of,cmp
pm=json.load(open('analysis/agents/m3control/portmap.json'))
good={int(k,16):int(v[0],16) for k,v in pm.items() if len(v)==1}
deltas=sorted(set(v-k for k,v in good.items()))
out=dict(good)
for k,v in pm.items():
    a=int(k,16)
    if len(v)==1: continue
    if not (0x44000<=a<0x5E000): continue
    # nearest good neighbors deltas first
    cand=sorted(deltas,key=lambda d:min(abs(a-g) for g,x in good.items() if x-g==d))
    best=None
    for d in cand[:6]:
        ln,n,np_,bad=cmp(a,a+d)
        if n and len(bad)<=max(1,n//20): best=(d,len(bad),n);break
    print(hex(a),hex(end_of(a)-a),best)
    if best: out[a]=a+best[0]
json.dump({hex(k):hex(v) for k,v in out.items()},open('analysis/agents/m3control/portmap2.json','w'))

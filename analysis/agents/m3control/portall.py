import sys,re,json
sys.path.insert(0,'analysis/agents/m3control')
from port import find
from fdiff import L1,L3
from fullcmp import labels,end_of
res={}
for a in labels:
    if not (0x44000<=a<0x5E000 or 0x7B000<=a<0x8E000): continue
    n=min(40,end_of(a)-a)
    r=find(a,n)
    if len(r)>1 and n<40: r=[]
    res[a]=r
json.dump({hex(k):[hex(x) for x in v] for k,v in res.items()},open('analysis/agents/m3control/portmap.json','w'))
ok=sum(1 for v in res.values() if len(v)==1);print(len(res),ok)
for a,v in res.items():
    if len(v)!=1: print(hex(a),[hex(x) for x in v],hex(end_of(a)-a))

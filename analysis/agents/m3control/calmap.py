import sys,json,collections
sys.path.insert(0,'analysis/agents/m3control')
from fdiff import L1,L3
from fullcmp import end_of
from lits import lits
pm={int(k,16):int(v,16) for k,v in json.load(open('analysis/agents/m3control/portmap2.json')).items()}
m=collections.defaultdict(set); other=collections.defaultdict(set)
for a,b in pm.items():
    e=end_of(a)
    A=lits(L1,a,e);B=lits(L3,b,b+(e-a))
    for (x,v),(y,w) in zip(A,B):
        if 0x4039C<=v<0x4039C+0xC00: m[v].add(w)
        elif 0x40000<=v<0x43000 or 0xD0000<=v<0xF0000: other[v].add(w)
print('ABS cal refs: 1M addr(off) -> M3 addr(off)')
for v in sorted(m):
    print(f'{v:#x} (+{v-0x4039C:#x}) -> '+','.join(f'{w:#x} (+{w-0x4039C:#x})' for w in sorted(m[v])))
print('OTHER const/cal refs')
for v in sorted(other):
    print(f'{v:#x} -> '+','.join(f'{w:#x}' for w in sorted(other[v])))

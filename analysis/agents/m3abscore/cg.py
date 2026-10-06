import re
from prof import ins,order
fm=[]
for l in open('../m3control/abs_fnmap.txt'):
    m=re.match(r'(\w+) -> (\w+) d=(\S+) len=0x(\w+)',l)
    if m: fm.append((int(m.group(2),16),int(m.group(4),16)))
fm.sort()
starts={a for a,n in fm}
def owner(x):
    b=None
    for a,n in fm:
        if a<=x<a+n: b=a
    return b
callers={}
for x in order:
    t=ins[x]
    tg=None
    m=re.search(r'(?:=|->) 0x([0-9a-f]{8})',t)
    if t.startswith('jsri') and m: tg=int(m.group(1),16)
    mm=re.match(r'[jb]sr\s+0x([0-9a-f]+)',t)
    if mm: tg=int(mm.group(1),16)
    if tg in starts:
        callers.setdefault(tg,set()).add(owner(x))
import json
for a,n in fm:
    if n>=0x10:
        print('%05X len=%X callers: %s'%(a,n,' '.join('%X'%c for c in sorted(c for c in callers.get(a,[]) if c))))

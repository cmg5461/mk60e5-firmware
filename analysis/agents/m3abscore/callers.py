import re,sys
from prof import ins,order
want={int(x,16) for x in sys.argv[1:]}
fm=[]
for l in open('../m3control/abs_fnmap.txt'):
    m=re.match(r'(\w+) -> (\w+) d=(\S+) len=0x(\w+)',l)
    if m: fm.append((int(m.group(2),16),int(m.group(4),16)))
fm.sort()
def owner(x):
    best=None
    for a,n in fm:
        if a<=x<a+n: best=a
    return best
for x in order:
    t=ins[x]
    m=re.search(r'(?:=|->) 0x([0-9a-f]{8})',t)
    tg=None
    if 'jsri' in t and m: tg=int(m.group(1),16)
    mm=re.match(r'[jb]sr\s+0x([0-9a-f]+)',t)
    if mm: tg=int(mm.group(1),16)
    mm=re.match(r'(jmpi|jbr|br)\s+(?:\[0x\w+\]\s*)?',t)
    if tg in want:
        o=owner(x)
        print('%X calls %X  (in fn %s)'%(x,tg,'%X'%o if o else '?'))

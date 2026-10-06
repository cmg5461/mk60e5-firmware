import re,sys,collections
L=open('analysis/7846816A_main.lst').read().split('\n')
ins=[]
for l in L:
    m=re.match(r'\s+([0-9A-F]{6}):\s+([0-9A-F]{4})\s+(\S+)\s*(.*)',l)
    if m: ins.append((int(m[1],16),m[3],m[4]))
fm=[]
for l in open('analysis/agents/m3control/abs_fnmap.txt'):
    m=re.match(r'(\w+) -> (\w+) d=\S+ len=0x(\w+)',l)
    if m: fm.append((int(m[2],16),int(m[3],16)))
fm.sort()
starts=[a for a,_ in fm]
import bisect
def fn_of(a):
    i=bisect.bisect_right(starts,a)-1
    return starts[i] if i>=0 else None
calls=collections.defaultdict(set); ram=collections.defaultdict(collections.Counter); callees=collections.defaultdict(set)
sset=set(starts)
for a,mn,op in ins:
    if mn=='jsri':
        m=re.search(r'-> 0x([0-9a-f]+)',op)
        if m:
            t=int(m[1],16)
            if t in sset or 0x40000<=t<0xE0000:
                calls[t].add(a); callees[fn_of(a)].add(t)
    elif mn in('bsr','jmpi'):
        m=re.search(r'0x([0-9a-f]+)',op)
        if m:
            t=int(m[1],16)
            if t in sset and fn_of(a)!=t: calls[t].add(a); callees[fn_of(a)].add(t)
    m=re.search(r'= 0x([0-9a-f]{8})',op)
    if mn=='lrw' and m:
        v=int(m[1],16)
        if 0x400000<=v<0x410000:
            f=fn_of(a)
            if f: ram[f][v]+=1
if __name__=='__main__':
    lo,hi=int(sys.argv[1],16),int(sys.argv[2],16)
    for s,l in fm:
        if lo<=s<hi:
            cs=sorted({fn_of(c) for c in calls.get(s,())},key=lambda x:x or 0)
            print('%06X len=%X callers=%s callees=%s'%(s,l,[hex(c) for c in cs if c],[hex(c) for c in sorted(callees[s]) if c>=0x40000 and c<0x60000]))
            print('    ram:',' '.join('%X'%k+('x%d'%v if v>1 else '') for k,v in sorted(ram[s].items())))

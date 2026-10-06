import re,sys,collections
L=open('analysis/7846411A_main.lst').read().split('\n')
targets=[int(x,16) for x in sys.argv[1:]]
func=None;regs={}
res=collections.defaultdict(lambda: collections.defaultdict(set))
for l in L:
    m=re.match(r'^sub_([0-9A-F]+):',l)
    if m: func=m.group(1);regs={};continue
    m=re.match(r'^\s*([0-9A-F]{6}):\s+[0-9A-F]{4}\s+(.*)$',l)
    if not m: continue
    t=m.group(2)
    ml=re.match(r'lrw (r\d+),\[0x[0-9a-f]+\]\s+; = 0x([0-9a-f]{8})',t)
    if ml:
        v=int(ml.group(2),16)
        regs[ml.group(1)]=v if v in targets else None
        if v in targets: res[v]['lrw'].add(func)
        continue
    mm=re.match(r'(ld|st)\.([bhw]) (r\d+),\((r\d+),(-?\d+)\)',t)
    if mm:
        rw,sz,rz,rx,d=mm.groups()
        if regs.get(rx): res[regs[rx]][rw].add(func)
        if rw=='ld': regs[rz]=None
for v in targets:
    print('%X'%v,{k:sorted(x) for k,x in res[v].items() if k!='lrw'})

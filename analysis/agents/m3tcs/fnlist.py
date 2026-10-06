import re,sys,collections
lst='analysis/7846816A_main.lst'
lo=int(sys.argv[1],16);hi=int(sys.argv[2],16)
fn=None;info={}
rx=re.compile(r'^\s*([0-9A-F]{6}):\s+([0-9A-F]{4})\s+(.*)$')
for line in open(lst,errors='ignore'):
    m=re.match(r'^sub_([0-9A-F]{6}):',line)
    if m:
        fn=int(m.group(1),16)
        if lo<=fn<hi: info[fn]=dict(end=fn,cal=set(),ram=set(),calls=set(),n=0)
        continue
    if fn is None or fn not in info: continue
    m=rx.match(line)
    if not m: continue
    a=int(m.group(1),16);d=info[fn];d['end']=a;d['n']+=1
    t=m.group(3)
    c=re.search(r'; = 0x([0-9a-f]+)',t)
    if c:
        v=int(c.group(1),16)
        if 0x40000<=v<0x100000 and 'lrw' in t: d['cal'].add(v)
        elif 0x400000<=v<0x410000 and 'lrw' in t: d['ram'].add(v)
        elif 'jsri' in t or 'jmpi' in t:
            if 0x60000<=v<0xE0000: d['calls'].add(v)
    b=re.search(r'bsr 0x([0-9a-f]+)',t)
    if b: d['calls'].add(int(b.group(1),16))
for f in sorted(info):
    d=info[f]
    print(f"{f:06X} +{d['end']-f:4X} n={d['n']:3d} cal={sorted('%X'%x for x in d['cal'])[:6]} ram={sorted('%X'%x for x in d['ram'])[:10]} calls={sorted('%X'%x for x in d['calls'])[:8]}")

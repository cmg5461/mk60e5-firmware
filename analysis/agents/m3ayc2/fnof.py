import re,bisect,sys
subs=[]
for l in open('analysis/7846816A_main.lst',encoding='utf-8',errors='replace'):
    m=re.match(r'sub_([0-9A-F]{6}):',l)
    if m: subs.append(int(m[1],16))
subs.sort()
sym={}
for fn in ['analysis/7846816A_symbols.md','analysis/agents/m3absslip/symbols.txt']:
    for l in open(fn,encoding='utf-8',errors='replace'):
        m=re.match(r'\|?\s*0x([0-9A-Fa-f]+)\s*\|?\s*`?([A-Za-z_][\w()]*)',l)
        if m: sym.setdefault(int(m[1],16),m[2])
for a in sys.argv[1:]:
    a=int(a,16); i=bisect.bisect_right(subs,a)-1; f=subs[i]
    print('%X in sub_%06X %s'%(a,f,sym.get(f,'')))

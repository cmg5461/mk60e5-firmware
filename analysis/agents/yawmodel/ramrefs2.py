import re,sys,collections
L=open('analysis/7846411A_main.lst').read().split('\n')
pat=re.compile(r'^\s*([0-9A-F]{6}):\s+[0-9A-F]{4}\s+(.*)$')
targets=[int(x,16) for x in sys.argv[1:]]
for t in targets:
    W=[];R=[]
    for i,l in enumerate(L):
        m=re.search(r'lrw (r\d+),\[0x[0-9a-f]+\]\s+; = 0x([0-9a-f]{8})',l)
        if not m: continue
        v=int(m.group(2),16)
        if not (v<=t<v+0x40): continue
        reg=m.group(1); a=pat.match(l).group(1); off=t-v
        for j in range(i+1,min(i+16,len(L))):
            mm=pat.match(L[j])
            if not mm: continue
            s=mm.group(2)
            mo=re.match(r'(ld|st)\.(\w) (r\d+),\('+reg+r',(\d+)\)',s)
            if mo and int(mo.group(4))==off:
                (W if mo.group(1)=='st' else R).append(mm.group(1))
            if re.match(r'(lrw|mov|movi|ld\.\w+) '+reg+',',s) and not re.match(r'ld\.\w+ '+reg+r',\('+reg+r',',s): break
    print(hex(t),'W:',' '.join(sorted(set(W))),'| R:',' '.join(sorted(set(R))[:30]))

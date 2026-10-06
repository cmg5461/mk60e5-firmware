import re,sys,collections
L=open('analysis/7846411A_main.lst').read().split('\n')
pat=re.compile(r'^\s*([0-9A-F]{6}):\s+[0-9A-F]{4}\s+(.*)$')
lo=int(sys.argv[1],16); hi=int(sys.argv[2],16)
W=collections.defaultdict(list); Rd=collections.defaultdict(list)
for i,l in enumerate(L):
    m=re.search(r'lrw (r\d+),\[0x[0-9a-f]+\]\s+; = 0x([0-9a-f]{8})',l)
    if not m: continue
    v=int(m.group(2),16)
    if not (lo<=v<hi): continue
    reg=m.group(1); a=pat.match(l).group(1)
    for j in range(i+1,min(i+10,len(L))):
        t=L[j]
        mm=pat.match(t)
        if not mm: continue
        s=mm.group(2)
        mo=re.match(r'(ld|st)\.(\w) (r\d+),\('+reg+r',(\d+)\)',s)
        if mo:
            (W if mo.group(1)=="st" else Rd)[v+int(mo.group(4))].append(a); break
        if re.match(r'(lrw|mov|movi|ld\.\w+) '+reg+',',s): break
for v in sorted(set(W)|set(Rd)):
    print(hex(v),'W:',' '.join(sorted(set(W[v]))),'| R:',' '.join(sorted(set(Rd[v]))[:12]))

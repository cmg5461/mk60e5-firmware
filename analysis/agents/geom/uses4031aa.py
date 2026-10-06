import re,collections,sys
L=open('analysis/agents/geom/m3_main.lst').read().split('\n')
pat=re.compile(r'^\s*([0-9A-F]{6}):\s+[0-9A-F]{4}\s+(.*)$')
rows=[]
for i,l in enumerate(L):
    if '= 0x004031aa' in l:
        m=pat.match(l); reg=re.search(r'lrw (r\d+)',l).group(1)
        offs=[]
        for j in range(i+1,i+14):
            mm=pat.match(L[j])
            if not mm: continue
            t=mm.group(2)
            if re.match(r'lrw '+reg+r',',t) or re.match(r'(mov|movi|ld\.\w+|lrw) '+reg+',',t) and not t.startswith('st'):
                # reg overwritten
                mo=re.match(r'(ld\.\w+) '+reg+r',\((\w+),(\d+)\)',t)
                if not (mo and mo.group(2)==reg): break
            mo=re.match(r'(ld|st)\.(\w) (r\d+),\('+reg+r',(\d+)\)',t)
            if mo: offs.append((mo.group(1)+'.'+mo.group(2),int(mo.group(4)),mm.group(1)))
            elif re.search(r'\b'+reg+r'\b',t) and not t.startswith('lrw'):
                offs.append(('other:'+t,None,mm.group(1)))
        rows.append((int(m.group(1),16),offs))
cnt=collections.Counter()
for a,o in rows:
    for t,off,ad in o:
        cnt[(off,t.split(':')[0])]+=1
    print(hex(a),[(t,off) for t,off,ad in o])
print(sorted(cnt.items(),key=lambda x:(x[0][0] is None,x[0][0])))

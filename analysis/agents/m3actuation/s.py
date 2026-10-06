import re,sys
L=open('C:/repos/e92_mk60e5/analysis/7846816A_main.lst').read().split('\n')
idx={}
for i,l in enumerate(L):
    m=re.match(r'sub_([0-9A-Fa-f]+):',l)
    if m: idx[int(m.group(1),16)]=i
keys=sorted(idx)
def summ(a):
    s=idx[a]; nxt=[k for k in keys if k>a][0]; e=idx[nxt]
    lits=[];calls=[]
    for l in L[s:e]:
        m=re.search(r'; = (0x[0-9a-f]+)',l)
        if m: lits.append(m.group(1).lstrip('0x').lstrip('0') or '0')
        m=re.search(r'jsri.*-> (0x[0-9a-f]+)',l)
        if m: calls.append(m.group(1))
        m=re.search(r'\bbsr (0x[0-9a-f]+)',l)
        if m: calls.append('b'+m.group(1))
    print(f"== {a:06x} next {nxt:06x} len {nxt-a:#x} lines {e-s}")
    seen=[];[seen.append(x) for x in lits if x not in seen]
    print(" lits:"," ".join(seen))
    print(" calls:"," ".join(calls))
for a in sys.argv[1:]:
    summ(int(a,16))

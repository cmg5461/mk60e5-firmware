import re,sys,bisect
L=open('analysis/7846411A_main.lst',encoding='utf8',errors='ignore').read().split('\n')
subs=[];
for i,l in enumerate(L):
    m=re.match(r'sub_([0-9A-F]+):',l)
    if m: subs.append((int(m.group(1),16),int(m.group(1),16)))
addrs=[a for a,_ in subs]
def fn(a):
    k=bisect.bisect_right(addrs,a)-1
    return addrs[k] if k>=0 else 0
for pat in sys.argv[1:]:
    p=pat.lower()
    res={}
    for l in L:
        if re.search(r'= '+p+r'$',l.strip().lower()):
            a=int(l.split()[0].rstrip(':'),16); res.setdefault(fn(a),[]).append(hex(a))
    print(pat,{hex(k):len(v) for k,v in sorted(res.items())})

import re
L=open('7846816A_main.lst').read().split('\n')
fn=None;res=[]
for i,l in enumerate(L):
    m=re.match(r'sub_([0-9A-F]+):',l)
    if m: fn=m.group(1)
    if 'jsri' in l and '-> 0x000833da' in l:
        idv='?'
        for k in range(i-1,max(i-14,0),-1):
            mm=re.search(r'movi r3,(\d+)',L[k])
            if mm: idv=mm.group(1);break
        res.append((idv,fn))
for r in sorted(set(res),key=lambda x:(x[0].zfill(3),x[1])): print(*r)

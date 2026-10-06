import re,sys
L=open('7846816A_main.lst').read().split('\n')
idx={}
for i,l in enumerate(L):
    m=re.match(r'sub_([0-9A-F]+):',l)
    if m: idx[int(m.group(1),16)]=i
def summ(a):
    i=idx[a]; j=i+1
    while j<len(L) and not L[j].startswith('sub_'): j+=1
    body=L[i:j]
    ins=[l for l in body if re.match(r'\s+[0-9A-F]{6}:',l)]
    lits=[];calls=[]
    for l in ins:
        m=re.search(r'; = 0x([0-9a-f]+)',l)
        if m: lits.append(m.group(1).lstrip('0') or '0')
        m=re.search(r'jsri.*-> 0x([0-9a-f]+)',l)
        if m: calls.append(m.group(1).lstrip('0'))
    from collections import Counter
    print('== %X  insns=%d'%(a,len(ins)))
    print(' calls:',' '.join('%s x%d'%(k,v) for k,v in Counter(calls).items()))
    print(' lits:',' '.join(sorted(set(lits))))
for a in sys.argv[1:]: summ(int(a,16))

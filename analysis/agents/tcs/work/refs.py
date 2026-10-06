import re
L=open('analysis/7846411A_main.lst').read().split('\n')
pat=re.compile(r'lrw (r\d+),\[0x[0-9a-f]+\]\s+; = 0x([0-9a-f]{8})')
out=[]
for i,l in enumerate(L):
    m=pat.search(l)
    if m:
        v=int(m.group(2),16)
        if 0x40AB8<=v<0x413EC:
            out.append((i,v))
import sys
for i,v in out:
    print('=====',hex(v),'+%x'%(v-0x40AB8))
    for k in range(i-1,i+7): print(L[k])

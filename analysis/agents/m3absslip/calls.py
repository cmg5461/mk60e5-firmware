import re,sys
L=open('analysis/7846816A_main.lst').read().split('\n')
s=int(sys.argv[1],16); e=int(sys.argv[2],16)
for l in L:
    m=re.match(r'\s+([0-9A-F]{6}):\s+([0-9A-F]{4})\s+(jsri|bsr|jmpi)\s*(.*)',l)
    if m:
        a=int(m[1],16)
        if s<=a<e:
            t=re.search(r'-> 0x([0-9a-f]+)',m[4]) or re.search(r'(0x[0-9a-f]+)',m[4])
            print('%X %s'%(a,t.group(1).lstrip('0x') if t else m[4]), end=' | ')
print()

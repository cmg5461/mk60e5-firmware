import re,sys
sys.path.insert(0,'analysis/agents/m3ayc')
from fdiff import *
def consts(L,a):
    f=fn(L,a);r=[]
    for ad,w,t in f:
        m=re.search(r'= (0x[0-9a-f]+)',t) or re.search(r'-> (0x[0-9a-f]+)',t)
        if m: r.append(m[1])
    return r,len(f)
o,lo=consts(O,int(sys.argv[1],16));m,lm=consts(M,int(sys.argv[2],16))
import difflib
sm=difflib.SequenceMatcher(None,o,m,autojunk=False)
print(lo,lm,len(o),len(m),sm.ratio())
for t,i1,i2,j1,j2 in sm.get_opcodes():
    if t!='equal':print(t,o[i1:i2],m[j1:j2])

M=open('flash/bin/7846816A_00000000.bin','rb').read();O=open('flash/bin/7846411A_00000000.bin','rb').read()
m=M[0x41190+0x8000:0x41190+0x8000+0x5C6];o=O[0x413EC+0x8000:0x413EC+0x8000+0x5C6]
d=[i for i in range(len(m)) if m[i]!=o[i]]
print(len(d))
r=[];s=p=d[0]
for i in d[1:]:
    if i>p+8: r.append((s,p));s=i
    p=i
r.append((s,p));print([(hex(a),hex(b)) for a,b in r])
print(m[:16].hex(),o[:16].hex())
import sys
def hx(b,base=0):
    return ' '.join('%04x'%int.from_bytes(b[i:i+2],'big') for i in range(0,len(b),2))
for a,b in [(0xe0,0x120)]:
    print('M',hx(m[a:b]));print('O',hx(o[a:b]))
# try shift alignment
for sh in range(-16,17):
    c=sum(1 for i in range(0x100,0x5c0-20) if 0<=i+sh<len(o) and m[i]==o[i+sh])
    print(sh,c)
import difflib
mw=[int.from_bytes(m[i:i+2],'big') for i in range(0,len(m),2)]
ow=[int.from_bytes(o[i:i+2],'big') for i in range(0,len(o),2)]
sm=difflib.SequenceMatcher(None,mw,ow,autojunk=False)
print('=====DIFF')
for t,i1,i2,j1,j2 in sm.get_opcodes():
    if t!='equal': print(t,'M@%#x'%(i1*2),[hex(x) for x in mw[i1:i2]][:40],'O@%#x'%(j2*2 and j1*2),[hex(x) for x in ow[j1:j2]][:40])

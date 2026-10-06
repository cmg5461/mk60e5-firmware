import re,bisect
d=open('../../../flash/bin/7846411A_00000000.bin','rb').read()
BASE=0x4039C
b=d[BASE+0x8000:BASE+0x8000+0x668]
def u(o): return int.from_bytes(b[o:o+2],'big')
def s(o):
    v=u(o); return v-65536 if v>=32768 else v
L=open('../../7846411A_main.lst').read().split('\n')
subs=[int(m[1],16) for l in L for m in [re.match(r'sub_([0-9A-F]+):',l)] if m]
refs={}
for l in open('../SEED_cal_refs.md').read().split('## TCS')[0].split('\n'):
    m=re.search(r'cpu 0x([0-9a-f]+) -> field \+0x([0-9a-f]+)',l)
    if not m: continue
    p=int(m[1],16);f=int(m[2],16)
    if p<0x44000: continue
    fn=subs[bisect.bisect_right(subs,p)-1]
    refs.setdefault(f,set()).add(fn)
curves=[0x18,0x4a,0x76,0x9e,0xce,0xf4,0x134,0x144,0x154,0x17c,0x1a4,0x1c0,0x1dc,0x200,0x226,0x242,0x264,0x286,0x2a8,0x2d4,0x30c,0x330,0x352,0x36e,0x38a,0x3ca,0x400,0x41a,0x45e,0x488,0x4bc,0x4e4,0x554,0x576,0x598,0x5ae,0x5ca,0x5e6,0x602,0x634]
def cinfo(f):
    n=s(f+4);k=n-1
    return dict(lo=s(f),hi=s(f+2),n=n,x=[s(f+6+2*i) for i in range(k)],y=[s(f+6+2*k+2*i) for i in range(n)],sl=[s(f+6+2*k+2*n+2*i) for i in range(n)],end=f+6+2*k+4*n)
cv={f:cinfo(f) for f in curves}
cover=set()
for f,c in cv.items():
    for o in range(f,c['end'],2): cover.add(o)
def rd(f):
    return ', '.join('%06X'%x for x in sorted(refs.get(f,[]))) or '-'
def curve_readers(f):
    return rd(f)
out=[]
# scalar runs
runs=[];cur=[]
for o in range(0xc,0x668,2):
    if o in cover:
        if cur: runs.append(cur);cur=[]
    else: cur.append(o)
if cur: runs.append(cur)
from annot import SA,CA
rows=[]
for f,c in cv.items():
    rl,cf=CA.get(f,("no annotation",""))
    rows.append('| 0x%03X | %d..%d | %d | %s | %s | %s | %s | %s %s |'%(f,c['lo'],c['hi'],c['n'],c['x'],c['y'],c['sl'],rd(f),rl,cf))
sr=[]
for o in sorted(SA):
    m,cf=SA[o]
    sr.append('| 0x%03X | 0x%04X | %d | %s | %s %s |'%(o,u(o),s(o),rd(o),m,cf))
NL=chr(10)
open('_curves.txt','w').write(NL.join(rows))
open('_scalars.txt','w').write(NL.join(sr))
print('missing',[hex(m) for r in runs for m in r if m not in SA])

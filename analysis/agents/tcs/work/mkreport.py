import struct,sys
sys.path.insert(0,'analysis/agents/tcs/work')
from gen_curves import curve,ev,w
d=open('flash/bin/7846411A_00000000.bin','rb').read()
b=0x40AB8+0x8000
def u(o): return struct.unpack('>H',d[b+o:b+o+2])[0]
# (offset, name/role, x source, readers, conf)
T=[
(0x01e,'accel-limit vs slip A','x=0x403086[w] (filtered slip, 0.01 km/h); y compared with wheel record +0x22','C7CCA (call 0xC7D22)','low'),
(0x034,'accel-limit vs slip B','x=0x403086[w]; y compared with 0x40308e[w]','C7CCA (0xC7DA6)','low'),
(0x04e,'cross-wheel add to lower limit','x=-0x40308e[partner wheel]; y added to 0x40300c[w] before compare with 0x403086[w]','C7CCA (0xC7F1E)','low'),
(0x076,'low-speed offset','x=0x403066 (vref); y 9.92 km/h at 0 -> 0 at 8 km/h','C7600 (0xC773C)','low'),
(0x086,'BASE SLIP THRESHOLD set B, mode 0','x=0x403066 (vref, 0.01 km/h); y = threshold 0.01 km/h','C7746 -> C777E -> 0x402fc2','med'),
(0x0a8,'BASE SLIP THRESHOLD set B, mode 1','same','same','med'),
(0x0ca,'BASE SLIP THRESHOLD set B, mode 2','same','same','med'),
(0x0ec,'BASE SLIP THRESHOLD set A, mode 0','same','same (default set; set B used when 0x402F6C bit4)','med'),
(0x10e,'BASE SLIP THRESHOLD set A, mode 1','same','same','med'),
(0x130,'BASE SLIP THRESHOLD set A, mode 2','same','same','med'),
(0x160,'extra term (min-cap), single','x=0x403066; capped result','C77FC (0xC783E)','low'),
(0x170,'sibling of 0x160 (no direct reader found)','?','-','low'),
(0x180,'threshold extra vs vref, mode 0','x=0x403066 (only if >=2.50 km/h and 0x402F7E bit4 clear)','C7852 (0xC787C) -> C78D0 r12','low'),
(0x19c,'threshold extra vs vref, mode 1','same','same','low'),
(0x1b8,'threshold extra vs vref, mode 2','same','same','low'),
(0x1e4,'zero table (x=0x403098, all A=B=0)','x=0x403098 (20/40/60 km/h axis)','C7CCA (0xC7DFA/0xC7E06)','low'),
(0x200,'unread-by-lrw table? x=vref 60..100 km/h','x=0x403066','C9124 (0xC9130)','low'),
(0x240,'engine-term curve (set 0x402F6C bit4 clear)','x=byte 0x401142 (0..175); y 14.00..40.00','C9704 (0xC9726)','low'),
(0x25c,'engine-term curve (set 0x402F6C bit4 set)','x=byte 0x401142','C9704 (0xC9716)','low'),
(0x2f4,'gain % vs vref','x=0x403066; y 100 -> 166 %? /100 scale','C8E96 (0xC8F92)','low'),
(0x310,'excess term vs vref (all zero)','x=0x403066','C8E96 (0xC8ED4)','low'),
(0x3d4,'unknown curve vs 30/100/150 km/h','x=0x403066','CBD98 (0xCBF62)','low'),
(0x3f0,'unknown small-int curve vs 50/82/123 km/h','x=0x403066','CBD98 (0xCBE56)','low'),
(0x422,'triangle 0..150 (peak at 270)','x=?','CD490 (0xCD582)','low'),
(0x438,'curve vs vref 49.6/60 km/h','x=0x403066','CD490 (0xCD4A2)','low'),
(0x4a8,'ramp 5120/1024 (x 10,20)','x=signed byte 0x403096','CA7A4 (0xCA80C)','low'),
(0x4c4,'ramp 5120/1024 (x 10,20) twin','x=?','CA826 (0xCA86C)','low'),
(0x534,'ramp set mode 0 (x 22,50,78; y<=600)','x=signed byte 0x403096','CE54E (0xCE672)','low'),
(0x550,'ramp set mode 1 (identical to 0x534)','same','same','low'),
(0x56c,'ramp set mode 2 (identical to 0x534)','same','same','low'),
(0x588,'const 4500 (x 30/60/100 km/h)','x=0x403066','CE54E (0xCE65A)','low'),
(0x5a4,'const 200 (x 30/60/100 km/h)','x=0x403066','CE54E (0xCE71C)','low'),
(0x5c6,'factor vs vref, mode 0 (y 35.00->10.00 %?)','x=0x403066 (15/25/90 km/h)','CA058, CA518, CB3E4','low'),
(0x5e2,'factor vs vref, mode 1','same','same','low'),
(0x5fe,'factor vs vref, mode 2 (= mode 1)','same','same','low'),
(0x61c,'const 5 (x=8)','?','CA058 (0xCA1F4 region)','low'),
(0x63a,'const 200 (x 50/100/150 km/h)','x=0x403066','CA058 (0xCA1F4)','low'),
(0x66e,'17-word curve set mode 0 (y<=16000)','x=0x403066 (35/70/100/140 km/h)','CBAC6 (0xCBAF8)','low'),
(0x690,'17-word curve set mode 1','same (axis 50/75/100/180)','CBAC6','low'),
(0x6b2,'17-word curve set mode 2','same','CBAC6','low'),
(0x6d4,'17-word curve set 2nd bank mode 0','same','CBB72 (0xCBBCE)','low'),
(0x6f6,'17-word curve set 2nd bank mode 1','same','CBB72','low'),
(0x718,'17-word curve set 2nd bank mode 2','same','CBB72','low'),
(0x742,'zero table (x=0x403066 20/60/100 km/h)','x=0x403066','C9380 (0xC93A0/0xC93B2/0xC93E8)','low'),
(0x77e,'const curve 30.00 -> 15.00 (x 0.44/1.0/1.5/1.7)','x=byte 0x4030AF','C9BF4 (0xC9C46)','low'),
(0x7f0,'step 25/100 (x 0.25/0.75)','x=byte 0x4030B8','CA058 (0xCA186)','low'),
(0x806,'step 25/98 (x 25/75 %?)','x=0x4030B8*100','CB3E4 (0xCB522)','low'),
(0x826,'zero table (x 1.24/2.5)','x=byte 0x401142','CB648 (0xCB65A)','low'),
(0x83c,'ramp 5.00 -> 0 (x 15/50 km/h), mode 0','x=0x403066','CB66C (0xCB694)','low'),
(0x852,'ramp mode 1','x=0x403066','CB66C','low'),
(0x868,'ramp mode 2','x=0x403066','CB66C','low'),
(0x87e,'curve mode 0 (x 85.5/100 km/h)','x=0x403066','CB66C (0xCB682)','low'),
(0x894,'curve mode 1 (x 120/150 km/h)','x=0x403066','CB66C','low'),
(0x8aa,'curve mode 2 (x 100/150 km/h)','x=0x403066','CB66C','low'),
(0x8e4,'const 40.00 (x 20/40 km/h)','?','no reader found','low'),
]
out=[]
for o,name,xs,rd,cf in T:
    mn,mx,n,X,A,B=curve(o)
    out.append('| +%03X | %s | %d | %d..%d | %s | %s | %s | %s | [agent, %s] |'%(o,name,n,mn,mx,X,A,B,xs+'; reader '+rd,cf))
open('analysis/agents/tcs/work/tables.md','w').write('\n'.join(out))
# annotate dump
cov={}
for o,*_ in T:
    mn,mx,n,X,A,B=curve(o)
    L=3+(n-1)+2*n
    for k in range(o,o+2*L,2): cov[k]=o
lines=[]
for o in range(0,0x934,16):
    ws=[u(k) if k+2<=0x934 else None for k in range(o,min(o+16,0x934),2)]
    s=' '.join('%04X'%x for x in ws)
    tag=','.join(sorted({'%03X'%cov[k] for k in range(o,min(o+16,0x934),2) if k in cov}))
    lines.append('%03X: %-40s %s'%(o,s,('curves:'+tag) if tag else ''))
open('analysis/agents/tcs/work/dump.txt','w').write('\n'.join(lines))
print(len(out))

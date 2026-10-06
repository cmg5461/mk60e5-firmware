import re,struct
A=open('flash/bin/7846411A_00000000.bin','rb').read();B=open('flash/bin/7846816A_00000000.bin','rb').read()
def s16(D,a): return struct.unpack('>h',D[a+0x8000:a+0x8002])[0]
rows=[]
for l in open('analysis/agents/m3control/calmap.txt'):
    m=re.match(r'(0x[0-9a-f]+) \(\+(0x[0-9a-f]+)\) -> (0x[0-9a-f]+) \(\+(0x[0-9a-f]+)\)$',l.strip())
    if m:
        a=int(m.group(1),16);b=int(m.group(3),16)
        if 0x4039C<=b<0x4039C+0xB10: rows.append((int(m.group(2),16),a,int(m.group(4),16),b,s16(A,a),s16(B,b)))
dif=[r for r in rows if r[4]!=r[5]]
print(len(rows),'pairs;',len(dif),'value-differ')
for r in dif: print(f'1M+{r[0]:#x} {r[1]:#x}={r[4]}   M3+{r[2]:#x} {r[3]:#x}={r[5]}')
print('---key')
for off in (0xC,0x18,0x550,0x570,0x572,0x574,0x594,0x520,0x540,0x542,0x58E,0x590,0x592,0x61E,0x620,0x622,0x624,0x626,0x628,0x654,0x65C,0x65E,0x660,0x662,0x664,0x576):
    for r in rows:
        if r[0]==off: print(f'1M+{off:#x}={r[4]}  M3 +{r[2]:#x} ({r[3]:#x})={r[5]}')

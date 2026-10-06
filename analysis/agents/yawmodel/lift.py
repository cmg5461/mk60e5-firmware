import re,sys
BS=chr(92)
LST='analysis/7846411A_main.lst'
if len(sys.argv)>3: LST=sys.argv[3]
pat=re.compile(r'^\s*([0-9A-F]{6}):\s+([0-9A-F]{4})\s+(.*)$')
code={}; order=[]
for l in open(LST):
    m=pat.match(l.rstrip('\n'))
    if m:
        a=int(m.group(1),16); code[a]=(int(m.group(2),16),m.group(3)); order.append(a)
RND=re.compile(BS+"((.+) "+BS+"+ "+BS+"("+BS+"("+BS+"1 >> ("+BS+"d+)"+BS+") >>u ("+BS+"d+)"+BS+")"+BS+")")
CONST=re.compile(r'-?\d+|0x[0-9a-f]+')
def lift(start,end):
    addrs=[a for a in order if start<=a<=end]
    targets=set()
    for a in addrs:
        m=re.match(r'(bt|bf|br) 0x([0-9a-f]+)',code[a][1])
        if m: targets.add(int(m.group(2),16))
    env={}; cond='?'; out=[]; n=0; cur=[0]
    def R(r): return env.get(r,r)
    def setr(r,e):
        isc=CONST.fullmatch(e) is not None
        if not isc and r!='r1':
            out.append(f'  {cur[0]:05X}  {r} = {e}')
            if len(e)>70: e=r
        elif not isc and len(e)>70:
            out.append(f'  {cur[0]:05X}  {r} = {e}'); e=r
        env[r]=e
    for a in addrs:
        h,t=code[a]; cur[0]=a
        if a in targets:
            out.append(f'L{a:X}:'); env={k:v for k,v in env.items() if CONST.fullmatch(v)}
        cm=re.search(r';\s*=\s*(0x[0-9a-f]+)',t)
        t0=t.split(';')[0].strip()
        p=lambda s:out.append(f'  {a:05X}  {s}')
        if (h&0xFF00)==0x6800 and t0.startswith('.short'):
            rx=h&15; ry=(h>>4)&15
            setr(f'r{rx}',f'(s16({R("r%d"%rx)})*s16({R("r%d"%ry)}))'); continue
        mm=re.match(r'(\w[\w.]*)\s*(.*)',t0)
        if not mm: p('?? '+t); continue
        op=mm.group(1); args=mm.group(2)
        A=[x.strip() for x in re.split(r',(?![^(]*\))',args)] if args else []
        if op=='lrw':
            v=int(cm.group(1),16); s32=v-(1<<32) if v&0x80000000 else v
            setr(A[0], hex(v) if v>0x1000 and v<0xfff00000 else str(s32)); continue
        if op in('ld.w','ld.h','ld.b'):
            m=re.match(r'\((r\d+),(\d+)\)',A[1]); b=R(m.group(1)); off=int(m.group(2))
            ad=hex(int(b,16)+off) if re.fullmatch(r'0x[0-9a-f]+',b) else f'{b}+{off}'
            setr(A[0],f'M{ {"ld.w":"w","ld.h":"uh","ld.b":"ub"}[op] }[{ad}]'); continue
        if op in('st.w','st.h','st.b'):
            m=re.match(r'\((r\d+),(\d+)\)',A[1]); b=R(m.group(1)); off=int(m.group(2))
            ad=hex(int(b,16)+off) if re.fullmatch(r'0x[0-9a-f]+',b) else f'{b}+{off}'
            p(f'M{op[-1]}[{ad}] = {R(A[0])}'); continue
        d=A[0] if A else None
        if op=='mov': setr(d,R(A[1])); continue
        if op=='movi': setr(d,A[1]); continue
        if op in('addu','subu','mult','and','or','xor','andn'):
            sym={'addu':'+','subu':'-','mult':'*','and':'&','or':'|','xor':'^','andn':'&~'}[op]
            setr(d,f'({R(d)} {sym} {R(A[1])})'); continue
        if op=='addi': setr(d,f'({R(d)} + {A[1]})'); continue
        if op=='subi': setr(d,f'({R(d)} - {A[1]})'); continue
        if op=='rsubi': setr(d,f'({A[1]} - {R(d)})'); continue
        if op=='divs': setr(d,f'({R(d)} / {R(A[1])})'); continue
        if op=='divu': setr(d,f'udiv({R(d)}, {R("r1")})'); continue
        if op=='lsli': setr(d,f'({R(d)} << {A[1]})'); continue
        if op=='lsri': setr(d,f'({R(d)} >>u {A[1]})'); continue
        if op=='asri':
            c=R(d); mt=RND.fullmatch(c)
            if mt and 32-int(mt.group(3))==int(A[1]): setr(d,f'({mt.group(1)} /{1<<int(A[1])})'); continue
            setr(d,f'({c} >> {A[1]})'); continue
        if op=='andi': setr(d,f'({R(d)} & {A[1]})'); continue
        if op=='bseti': setr(d,f'({R(d)} | {1<<int(A[1])})'); continue
        if op=='bclri': setr(d,f'({R(d)} & ~{1<<int(A[1])})'); continue
        if op=='bmaski': setr(d,str((1<<int(A[1]))-1)); continue
        if op=='bgeni': setr(d,str(1<<int(A[1]))); continue
        if op=='sexth': setr(d,f's16({R(d)})'); continue
        if op=='zexth': setr(d,f'u16({R(d)})'); continue
        if op=='sextb': setr(d,f's8({R(d)})'); continue
        if op=='zextb': setr(d,f'u8({R(d)})'); continue
        if op=='ixh': setr(d,f'({R(d)} + 2*{R(A[1])})'); continue
        if op=='ixw': setr(d,f'({R(d)} + 4*{R(A[1])})'); continue
        if op=='lsl': setr(d,f'({R(d)} << {R(A[1])})'); continue
        if op=='asr': setr(d,f'({R(d)} >> {R(A[1])})'); continue
        if op=='lsr': setr(d,f'({R(d)} >>u {R(A[1])})'); continue
        if op=='rsub': setr(d,f'({R(A[1])} - {R(d)})'); continue
        if op=='abs': setr(d,f'abs({R(d)})'); continue
        if op=='btsti': cond=f'bit{A[1]}({R(d)})'; continue
        if op=='cmplt': cond=f'{R(d)} < {R(A[1])}'; continue
        if op=='cmphs': cond=f'{R(d)} >=u {R(A[1])}'; continue
        if op=='cmpne': cond=f'{R(d)} != {R(A[1])}'; continue
        if op=='cmpnei': cond=f'{R(d)} != {A[1]}'; continue
        if op=='cmplti': cond=f'{R(d)} < {A[1]}'; continue
        if op=='tst': cond=f'({R(d)} & {R(A[1])}) != 0'; continue
        if op=='bt': p(f'if ({cond}) goto L{int(A[0],16):X}'); continue
        if op=='bf': p(f'if (!({cond})) goto L{int(A[0],16):X}'); continue
        if op=='br': p(f'goto L{int(A[0],16):X}'); continue
        if op in('jsri','bsr','jsr'):
            tgt=re.search(r'-> (0x[0-9a-f]+)',t)
            tg=tgt.group(1) if tgt else A[0]
            n+=1
            p(f'R{n} = call {tg}({R("r2")}, {R("r3")}, {R("r4")}, {R("r5")})')
            for r in ('r1','r2','r3','r4','r5','r6','r7'): env.pop(r,None)
            env['r2']=f'R{n}'; continue
        if op=='jmp' and 'return' in t: p(f'return {R("r2")}'); continue
        p(t0)
    print(chr(10).join(out))
if __name__=='__main__':
    lift(int(sys.argv[1],16),int(sys.argv[2],16))

import re,struct
d=open('flash/bin/7846411A_00000000.bin','rb').read()
L=open('analysis/7846411A_main.lst').read().split('\n')
ins=[]
func=None
for l in L:
    m=re.match(r'^sub_([0-9A-F]+):',l)
    if m: func=m.group(1);continue
    m=re.match(r'^\s*([0-9A-F]{6}):\s+[0-9A-F]{4}\s+(.*)$',l)
    if m:
        a=int(m.group(1),16)
        if 0xC7000<=a<0xD9000: ins.append((a,func,m.group(2)))
out=[]
for i,(a,f,t) in enumerate(ins):
    m=re.match(r'jsri \[0x([0-9a-f]+)\]',t)
    if not m: continue
    p=int(m.group(1),16)
    v=struct.unpack('>I',d[p+0x8000:p+0x8004])[0]
    if v!=0x71158: continue
    # look back for r2 setup
    ctx=[]
    for j in range(max(0,i-14),i):
        aa,ff,tt=ins[j]
        if ff!=f: continue
        mm=re.search(r'; = 0x([0-9a-f]{8})',tt)
        ann=''
        if mm:
            v2=int(mm.group(1),16)
            if 0x40AB8<=v2<0x413EC: ann=' [TCS+%03x]'%(v2-0x40AB8)
            elif 0x400000<=v2<0x410000: ann=' [RAM %x]'%v2
        ctx.append('%X %s%s'%(aa,re.sub(r'\s*;.*','',tt),ann))
    out.append((a,f,ctx))
for a,f,ctx in out:
    print('#### call at %X in %s'%(a,f))
    print('\n'.join(ctx))

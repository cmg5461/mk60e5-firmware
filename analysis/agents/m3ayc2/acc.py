import re,sys
# usage: acc.py ADDR [ADDR2..]  -> lists accesses (st/ld) to RAM addresses by tracking lrw base regs
ins=[]
for l in open('analysis/7846816A_main.lst'):
    m=re.match(r'\s+([0-9A-F]{6}):\s+([0-9A-F]{4})\s+(\S+)\s*(.*)',l)
    if m: ins.append((int(m[1],16),m[3],m[4].strip()))
tg=[int(x,16) for x in sys.argv[1:]]
lo,hi=min(tg),max(tg)
base={}
out=[]
for i,(a,mn,op) in enumerate(ins):
    m=re.match(r'(r\d+),\[.*?\]\s*; = 0x([0-9a-f]{8})',op) if mn=='lrw' else None
    if m:
        v=int(m[2],16); base[m[1]]=(v,a); continue
    m=re.match(r'(ld|st)\.([bhw]) (r\d+),\((r\d+),(\d+)\)',mn+' '+op)
    if m:
        rb=m[4]
        if rb in base:
            ea=base[rb][0]+int(m[5])
            if ea in tg:
                out.append('%X %s.%s %s [0x%X]'%(a,m[1],m[2],m[3],ea))
        if m[1]=='ld' and m[3] in base and m[3]!=rb: del base[m[3]]
        continue
    if mn in('jmp','jsr','jsri','rts','bsr','jmpi'):
        # keep bases only in callee-saved? clear volatile r2-r7
        for r in list(base):
            if r in('r2','r3','r4','r5','r6','r7'): del base[r]
        continue
    # dest register overwritten
    d=op.split(',')[0]
    if d in base and mn not in('cmpnei','cmpeq','tst','cmplt','cmphs','cmpne') and not mn.startswith(('st','cmp','tst','br','bt','bf')): del base[d]
print('\n'.join(out))

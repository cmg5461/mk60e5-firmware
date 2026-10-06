import re,collections,json
L=open('analysis/7846411A_main.lst').read().split('\n')
ins=re.compile(r'^\s*([0-9A-F]{6}):\s+([0-9A-F]{4})\s+(\S+)\s*(.*?)(?:\s*;.*)?$')
lrw=re.compile(r'lrw (r\d+),\[0x[0-9a-f]+\]\s+; = 0x([0-9a-f]{8})')
func=None
regs={}
acc=[]  # (addr,func,off,size,rw,reg)
funcs=collections.defaultdict(list)
for l in L:
    m=re.match(r'^sub_([0-9A-F]+):',l)
    if m: func=m.group(1); regs={}; continue
    m=ins.match(l)
    if not m: continue
    a=int(m.group(1),16)
    if not(0xC7000<=a<0xD9000): continue
    mn,ops=m.group(3),m.group(4)
    ml=lrw.search(l)
    if ml:
        v=int(ml.group(2),16); r=ml.group(1)
        if 0x40AB8<=v<0x413EC: regs[r]=v-0x40AB8
        else: regs.pop(r,None)
        continue
    mm=re.match(r'(ld|st)\.([bhw]) (r\d+),\((r\d+),(-?\d+)\)',mn+' '+ops)
    if mm:
        rw,sz,rz,rx,d=mm.groups()
        if rx in regs:
            acc.append((a,func,regs[rx]+int(d),sz,rw,rz))
        if rw=='ld': regs.pop(rz,None)
        continue
    if mn in('jsr','jmp','bsr','jsri') : 
        if mn in('jsr','bsr','jsri'):
            for r in ('r2','r3','r4','r5','r6','r7','r1'): pass
        continue
    mo=re.match(r'(r\d+)',ops)
    if mo and not mn.startswith(('cmp','tst','bt','st','jm','js','b')):
        regs.pop(mo.group(1),None)
json.dump(acc,open('analysis/agents/tcs/work/acc.json','w'))
byf=collections.defaultdict(list)
for a,f,o,sz,rw,rz in acc: byf[f].append(o)
for f in sorted(byf): print(f,len(byf[f]),'%x-%x'%(min(byf[f]),max(byf[f])))

import re,sys
from prof import ins,order,fm
targets={int(x,16) for x in sys.argv[1].split(',')}
# taint: reg -> base symbol; linear scan per function
def regs(t):
    return re.findall(r'\br(\d+)\b',t)
for a,n in fm:
    if n<0x10: continue
    taint={}
    for x in order:
        if not (a<=x<a+n): continue
        t=ins[x]
        op=t.split()[0]
        m=re.search(r'= 0x([0-9a-f]{8})',t)
        if op=='lrw' and m:
            v=int(m.group(1),16)
            rd=int(re.match(r'lrw r(\d+)',t).group(1))
            # allow nearby offsets
            hit=None
            for tg in targets:
                if tg<=v<tg+8: hit=(tg,v-tg)
            if hit: taint[rd]=hit
            else: taint.pop(rd,None)
            continue
        r=regs(t)
        if op=='mov' and len(r)==2:
            if int(r[1]) in taint: taint[int(r[0])]=taint[int(r[1])]
            else: taint.pop(int(r[0]),None)
        elif op in('addu','ixh','ixw','subu') and len(r)==2:
            if int(r[1]) in taint and int(r[0]) not in taint: taint[int(r[0])]=taint[int(r[1])]
        elif op in('st.h','st.w','st.b'):
            # st rx,(ry,disp)
            mm=re.match(r'st\.\w r(\d+),\(r(\d+),(\d+)\)',t)
            if mm and int(mm.group(2)) in taint:
                tg,off=taint[int(mm.group(2))]
                print('%05X  fn %05X  %s  base %X+%d'%(x,a,t.split(';')[0].strip(),tg,off))
        else:
            if r and op not in('cmplt','cmphs','cmpne','cmpnei','cmplti','tst','btsti','jsri','bf','bt','br'):
                if int(r[0]) in taint and op.startswith(('ld','movi','mult','divs','sext','zext')) : taint.pop(int(r[0]),None)

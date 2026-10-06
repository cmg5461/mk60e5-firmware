import re,subprocess,sys
img='../../../flash/bin/7846816A_00000000.bin'
cbs=set()
for f in ['../m3can/m3_can_map.txt','m3_fcan_map.txt']:
    for l in open(f):
        m=re.search(r'\| (0x[0-9a-f]{6}) \|$',l.strip())
        if m: cbs.add(int(m.group(1),16))
cbs=sorted(c for c in cbs if c<0x400000)
for i,c in enumerate(cbs):
    end=cbs[i+1] if i+1<len(cbs) else c+0x80
    end=min(end,c+0x200)
    out=subprocess.run(['python','../../../tools/mcore_dis.py',img,'--base=-0x8000','--start=%#x'%c,'--end=%#x'%end],capture_output=True,text=True).stdout
    lines=[l for l in out.splitlines() if l.strip()]
    ram=[];ops=[]
    for l in lines:
        m=re.search(r'= (0x[0-9a-f]{8})',l)
        if m: ram.append(m.group(1)[2:].lstrip('0') or '0')
        m=re.search(r'\s(lsli|lsri|asri|mult|divs|divu|movi|addi|subi|andi|ixh|ixw|rsubi|sexth|sextb|btsti|cmpnei|cmplti|bgeni|bmaski|mulsh)\s+(.*)',l)
        if m: ops.append(m.group(1)+' '+m.group(2).split(';')[0].strip())
        if 'jmp r15' in l and len(lines)>0 and l is lines[-1]: pass
    print('%06x n=%d ram=%s ops=%s'%(c,len(lines),','.join(dict.fromkeys(ram)),'; '.join(ops[:14])))

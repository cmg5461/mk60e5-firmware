import re,sys
lo=int(sys.argv[1],16);hi=int(sys.argv[2],16)
lst='analysis/7846816A_main.lst'
rx=re.compile(r'^\s*([0-9A-F]{6}):\s+([0-9A-F]{4})\s+(\S+)\s*(.*)$')
lrw=re.compile(r'lrw r(\d+),\[.*?\]\s*;\s*=\s*0x([0-9a-f]+)')
mem=re.compile(r'(ld|st)\.(b|h|w)\s+r(\d+),\(r(\d+),(\d+)\)')
regs={};fn=None;R={};W={};C={}
def flush():
    if fn is not None and lo<=fn<hi:
        print(f"{fn:06X} W:{' '.join('%X'%a for a in sorted(W))} | R:{' '.join('%X'%a for a in sorted(set(R)-set(W)))}")
for line in open(lst,errors='ignore'):
    m=re.match(r'^sub_([0-9A-F]{6}):',line)
    if m:
        flush();fn=int(m.group(1),16);regs={};R={};W={};continue
    m=rx.match(line)
    if not m: continue
    t=line
    l=lrw.search(t)
    if l: regs[int(l.group(1))]=int(l.group(2),16);continue
    mm=mem.search(t)
    if mm:
        sz={'b':1,'h':2,'w':4}[mm.group(2)]
        b=regs.get(int(mm.group(4)))
        if b is not None:
            a=b+int(mm.group(5))*sz
            if 0x400000<=a<0x410000:
                (W if mm.group(1)=='st' else R)[a]=1
flush()

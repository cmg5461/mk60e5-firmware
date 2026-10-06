import re,sys
# usage: memref.py lo hi [lstpath] : find ld/st with base-reg+off in [lo,hi]
lo=int(sys.argv[1],16);hi=int(sys.argv[2],16)
lst=sys.argv[3] if len(sys.argv)>3 else 'analysis/7846816A_main.lst'
regs={}
rx=re.compile(r'^\s*([0-9A-F]{6}):\s+([0-9A-F]{4})\s+(\S+)\s*(.*)$')
lrw=re.compile(r'lrw r(\d+),\[.*?\]\s*;\s*=\s*0x([0-9a-f]+)')
mem=re.compile(r'(ld|st)\.(b|h|w)?\s*r(\d+),\(r(\d+),(\d+)\)')
for line in open(lst,errors='ignore'):
    m=rx.match(line)
    if not m:
        if line.startswith('sub_') or line.strip().endswith(':'): regs={}
        continue
    a=int(m.group(1),16)
    t=line
    l=lrw.search(t)
    if l:
        regs[int(l.group(1))]=int(l.group(2),16);continue
    mm=mem.search(t)
    if mm:
        sz={'b':1,'h':2,'w':4}.get(mm.group(2),4)
        off=int(mm.group(5))*sz
        b=regs.get(int(mm.group(4)))
        if b is not None and lo<=b+off<=hi:
            print(f"{a:06X} {mm.group(1)}.{mm.group(2)} r{mm.group(3)} [{b+off:X}]")
    # clobber dest regs crudely
    d=re.match(r'.*?\s(\w+)\s+r(\d+)',m.group(3)+' '+m.group(4))
    if d and not t.strip().split()[2].startswith(('st','cmp','tst','btst','bt','bf','br','jmp')):
        regs.pop(int(d.group(2)),None)

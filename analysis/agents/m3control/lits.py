import sys,re
sys.path.insert(0,'analysis/agents/m3control')
from fdiff import L1,L3
from fullcmp import end_of
def lits(L,a,e):
    out=[]
    for x in range(a,e,2):
        if x in L:
            m=re.match(r'lrw r\d+,\[0x[0-9a-f]+\]\s+; = 0x([0-9a-f]+)',L[x][1])
            if m: out.append((x,int(m.group(1),16)))
    return out
if __name__=='__main__':
  for arg in sys.argv[1:]:
    a,b=[int(t,16) for t in arg.split(':')]
    e=end_of(a)
    A=lits(L1,a,e);B=lits(L3,b,b+(e-a))
    print(f'== {a:06X}->{b:06X}: {len(A)} lrw, differing:')
    for (x,v),(y,w) in zip(A,B):
        if v!=w: print(f'   +{x-a:#x} 1M {v:#x}  M3 {w:#x}  d={w-v:+#x}')

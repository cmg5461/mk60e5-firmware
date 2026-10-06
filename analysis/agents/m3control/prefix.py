import sys
sys.path.insert(0,'analysis/agents/m3control')
from fdiff import L1,L3
def prefix(a1,a3):
    o=0
    while True:
        x=L1.get(a1+o);y=L3.get(a3+o)
        if x is None or y is None or x[0]!=y[0]: return o,x,y
        o+=2
if __name__=='__main__':
    for arg in sys.argv[1:]:
        a,b=[int(t,16) for t in arg.split(':')]
        o,x,y=prefix(a,b)
        print(f'{a:06X}->{b:06X} identical prefix {o:#x}  next 1M:{x} M3:{y}')

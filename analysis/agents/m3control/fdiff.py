import sys,re
def load(p):
    d={}
    for l in open(p,errors='ignore'):
        m=re.match(r'\s+([0-9A-F]{5,6}):\s+([0-9A-F]{4})\s+(.*)',l)
        if m: d[int(m.group(1),16)]=(m.group(2),m.group(3))
    return d
L1=load('analysis/7846411A_main.lst'); L3=load('analysis/7846816A_main.lst')
def diff(a1,a3,n):
    """compare n bytes of instructions; report opcode mismatches"""
    bad=[]
    for o in range(0,n,2):
        x=L1.get(a1+o);y=L3.get(a3+o)
        if x is None or y is None: bad.append((o,'missing'));continue
        if x[0]!=y[0]: bad.append((o,x,y))
    return bad
if __name__=='__main__':
    a1=int(sys.argv[1],16);a3=int(sys.argv[2],16);n=int(sys.argv[3],16)
    b=diff(a1,a3,n);print(hex(a1),'->',hex(a3),'len',hex(n),'mismatches',len(b))
    for x in b[:int(sys.argv[4]) if len(sys.argv)>4 else 8]:print(x)

import re,sys,difflib
def load(p):
    L=open(p,encoding='utf-8',errors='replace').read().split('\n');return L
O=load('analysis/7846411A_main.lst');M=load('analysis/7846816A_main.lst')
def fn(L,addr,maxn=100000):
    # find line with addr
    pat=re.compile(r'^\s*%06X:\s+([0-9A-F]{4})\s+(.*)$'%addr)
    for i,l in enumerate(L):
        if pat.match(l):break
    else: return None
    out=[]
    for l in L[i+1:] if False else L[i:]:
        if l.startswith('sub_') and out and len(out)>2: break
        m=re.match(r'^\s*([0-9A-F]{6}):\s+([0-9A-F]{4})\s+(.*)$',l)
        if m: out.append((int(m[1],16),m[2],m[3]))
        if len(out)>maxn:break
    return out
def cmp(oa,ma,show=40):
    a=fn(O,oa);b=fn(M,ma)
    if not a or not b: print('missing',hex(oa),hex(ma));return
    wa=[x[1] for x in a];wb=[x[1] for x in b]
    sm=difflib.SequenceMatcher(None,wa,wb,autojunk=False)
    n=0
    print('%x vs %x: lenO=%d lenM=%d ratio=%.4f'%(oa,ma,len(a),len(b),sm.ratio()))
    for t,i1,i2,j1,j2 in sm.get_opcodes():
        if t=='equal':continue
        if n<show:
            print(' ',t,[ '%x %s'%(x[0],x[2]) for x in a[i1:i2]][:6],'|',['%x %s'%(x[0],x[2]) for x in b[j1:j2]][:6])
        n+=1
    print(' ndiff',n)
if __name__=='__main__':
    cmp(int(sys.argv[1],16),int(sys.argv[2],16),int(sys.argv[3]) if len(sys.argv)>3 else 40)

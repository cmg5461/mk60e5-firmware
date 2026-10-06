import re,sys,collections
lst=open('../../7846816A_main.lst').read().split('\n')
ins={}
order=[]
for l in lst:
    m=re.match(r'\s*([0-9A-F]{6}):\s+([0-9A-F]{4})\s+(.*)',l)
    if m:
        a=int(m.group(1),16); ins[a]=m.group(3); order.append(a)
fm=[]
for l in open('../m3control/abs_fnmap.txt'):
    m=re.match(r'(\w+) -> (\w+) d=(\S+) len=0x(\w+)',l)
    if m: fm.append((int(m.group(2),16),int(m.group(4),16)))
fm.sort()
names={}
def prof(a,n):
    ram=collections.OrderedDict(); calls=[]
    for x in order:
        if a<=x<a+n:
            t=ins[x]
            m=re.search(r'(?:=|->) 0x([0-9a-f]{8})',t)
            if m:
                v=int(m.group(1),16)
                if 0x400000<=v<0x420000 and 'lrw' in t: ram[v]=1
                if 'jsri' in t and v<0x100000: calls.append(v)
            m=re.match(r'[jb]sr\s+0x([0-9a-f]+)',t)
            if m: calls.append(int(m.group(1),16))
    return list(ram),calls
if __name__=='__main__':
    lo=int(sys.argv[1],16);hi=int(sys.argv[2],16)
    for a,n in fm:
        if lo<=a<hi and n>=0x10:
            r,c=prof(a,n)
            print('%05X len=%X'%(a,n))
            print('   RAM:',' '.join('%X'%v for v in r))
            print('   CALL:',' '.join('%X'%v for v in dict.fromkeys(c)))

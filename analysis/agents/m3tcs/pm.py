import sys,struct
A=open('flash/bin/7846411A_00000000.bin','rb').read()
B=open('flash/bin/7846816A_00000000.bin','rb').read()
def words(D,start,n):
    o=start+0x8000
    return list(struct.unpack('>%dH'%n,D[o:o+2*n]))
def mask(w):
    t=w>>12
    if t==7: return w&0xFF00
    if t==0xF: return w&0xF800
    return w
def pat(a,n=30,skip=0):
    return [mask(w) for w in words(A,a+skip*2,n)]
# build masked B
BW=struct.unpack('>%dH'%(len(B)//2),B)
BM=[mask(w) for w in BW]
def find(a,n=30,lo=0x70000,hi=0xE0000):
    p=pat(a,n)
    res=[]
    for i in range((lo+0x8000)//2,(hi+0x8000)//2):
        if BM[i:i+n]==p: res.append(i*2-0x8000)
    return res
if __name__=='__main__':
    n=int(sys.argv[1])
    for a in sys.argv[2:]:
        a=int(a,16)
        r=find(a,n)
        print(hex(a),[hex(x) for x in r], [hex(x-a) for x in r])

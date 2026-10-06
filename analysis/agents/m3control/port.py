import sys
A=open('flash/bin/7846411A_00000000.bin','rb').read()
B=open('flash/bin/7846816A_00000000.bin','rb').read()
def find(addr,n=40,skip=0):
    w=A[addr+0x8000+skip:addr+0x8000+skip+n]
    res=[];i=-1
    while True:
        i=B.find(w,i+1)
        if i<0:break
        res.append(i-0x8000-skip)
    return res
if __name__=='__main__':
    for a in sys.argv[1:]:
        a=int(a,16)
        for n in (24,40,64):
            r=find(a,n)
            print(hex(a),n,[hex(x) for x in r][:6])
            if len(r)==1:break

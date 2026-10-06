import sys
M=open('flash/bin/7846816A_00000000.bin','rb').read();O=open('flash/bin/7846411A_00000000.bin','rb').read()
mb=0x41190+0x8000;ob=0x413EC+0x8000
def w(B,base,off,n): return [int.from_bytes(B[base+off+2*i:base+off+2*i+2],'big',signed=True) for i in range(n)]
def find(B,base,vals,ln=0x5d0):
    out=[]
    for off in range(0,ln,2):
        if w(B,base,off,len(vals))==vals: out.append(hex(off))
    return out
if __name__=='__main__':
    for v in ([3490,3490,3013],[2420,1861,1396],[1396,2792],[400,2000,330],[1,0,0]):
        print(v,'M3',find(M,mb,v),'1M',find(O,ob,v))

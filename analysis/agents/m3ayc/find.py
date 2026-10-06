import sys
M=open('flash/bin/7846816A_00000000.bin','rb').read();O=open('flash/bin/7846411A_00000000.bin','rb').read()
def find(cpu,n=24):
    pat=O[cpu+0x8000:cpu+0x8000+n]
    res=[];i=-1
    while True:
        i=M.find(pat,i+1)
        if i<0:break
        res.append(i-0x8000)
    return [hex(x) for x in res]
for a in [0x5ECB0,0x5F882,0x6514C,0x90C44,0xCF92A,0x60D68,0xD02D8,0x8E066]:
    print(hex(a),[find(a,n) for n in (16,32,48)])

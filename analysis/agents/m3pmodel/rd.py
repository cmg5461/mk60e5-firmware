import sys
d=open('/c/repos/e92_mk60e5/flash/bin/7846816A_00000000.bin','rb').read() if False else open('C:/repos/e92_mk60e5/flash/bin/7846816A_00000000.bin','rb').read()
def cpu(a,n): return d[a+0x8000:a+0x8000+n]
def s16(a): 
    v=int.from_bytes(cpu(a,2),'big'); return v-65536 if v>=32768 else v
def u32(a): return int.from_bytes(cpu(a,4),'big')
if __name__=='__main__':
    a=int(sys.argv[1],16); n=int(sys.argv[2]); w=int(sys.argv[3]) if len(sys.argv)>3 else 2
    print(cpu(a,n).hex())
    if w==2: print([s16(a+i) for i in range(0,n,2)])
    if w==1: print(list(cpu(a,n)))
    if w==4: print([hex(u32(a+i)) for i in range(0,n,4)])

import struct,sys
img,HDR,MSG,VAR=sys.argv[1],int(sys.argv[2],0),int(sys.argv[3],0),int(sys.argv[4],0)
data=open(img,'rb').read()
b=lambda a,n=1:data[a+0x8000:a+0x8000+n]
u16=lambda a:struct.unpack('>H',b(a,2))[0]
u32=lambda a:struct.unpack('>I',b(a,4))[0]
n_tx,n_rx=b(HDR+0x10)[0],b(HDR+0x11)[0]
sig=HDR+0xD+u16(HDR+0x0C)
print('tx',n_tx,'rx',n_rx,'sig',hex(sig))
for i in range(n_tx+n_rx):
    m=MSG+23*i
    cid,fl,per=u16(m+2),b(m+4)[0],b(m+6)[0]
    nsig,first,mbox=b(m+10)[0],u16(m+11),b(m+13)[0]
    print('%s 0x%03X dlc %d per %s mbox %d'%('TX' if i<n_tx else 'RX',cid,fl&15,per,mbox))
    for s in range(first,first+nsig):
        sd=sig+5*s
        f0,pos,var=b(sd)[0],b(sd+1)[0],u16(sd+3)
        v=VAR+8*var
        print('   sig %d byte.bit %d.%d len %d fl %x var 0x%03X type %d cb %#x raw %s'%(s,pos&15,pos>>4,f0&0x1f,f0>>5,var,b(v)[0]&7,u32(v+4),b(v,8).hex()))

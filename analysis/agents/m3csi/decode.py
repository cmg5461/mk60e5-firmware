import struct
M=open('flash/bin/7846816A_00000000.bin','rb').read()[0x40EA8+0x8000:0x40EA8+0x8000+0x114]
O=open('flash/bin/7846411A_00000000.bin','rb').read()[0x40A04+0x8000:0x40A04+0x8000+0xB2]
def interp(xs,ys,x):
    if x<=xs[0]: return ys[0]
    if x>=xs[-1]: return ys[-1]
    for i in range(1,len(xs)):
        if x<xs[i]:
            return ys[i-1]+int((ys[i]-ys[i-1])*(x-xs[i-1])/(xs[i]-xs[i-1]))
def sets(b,n):
    X=[struct.unpack('>4h',b[0xc+8*i:0x14+8*i]) for i in range(n)]
    Y=[struct.unpack('>4h',b[0xc+8*n+8*i:0x14+8*n+8*i]) for i in range(n)]
    return X,Y
for name,b,n in(('M3',M,3),('1M',O,1)):
    X,Y=sets(b,n)
    for s in range(n):
        print(name,'set',s,'x',X[s],'y',Y[s],'ratio',[round(y/1024,2) for y in Y[s]],'sw_deg@0.043',[round(x*0.04299,1) for x in X[s]])
        for x in (0,500,1000,2000,3383,5000,8000,10880):
            xc=min(x,X[s][3]); y=interp(X[s],Y[s],xc); 
            print('   raw',x,'ratio',round(y/1024,2),'delta_u',int(xc*29360/y), 'road_deg',round(int(xc*29360/y)/38400*57.2958,2))

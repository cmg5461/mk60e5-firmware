from curves import *
B3='../../../flash/bin/7846816A_00000000.bin'; B1='../../../flash/bin/7846411A_00000000.bin'
a3=load(B3,0x4039C,0xB0A); a1=load(B1,0x4039C,0x666)
def cv(w,off,n=None):
    o=off//2; nn=w[o+2]; L=3+(nn-1)+2*nn; return w[o:o+L]
print("== ABS decel threshold (raw units, g=0 second term), vref km/h ==")
V=[10,20,30,60,100,150,200,250,300]
def thr(w,fs_off,floor_lo,floor_60,base,floor,v,g=0,g_off=None):
    x=v*100
    t=base-ev(cv(w,fs_off),x)
    if g_off is not None: t-=ev(cv(w,g_off),g)
    t=max(t,floor)
    if x<6000: t=max(t,floor_60)
    if x<2000: t=max(t,floor_lo)
    return t
b1=a1[0xCC//2];f1=a1[0xCA//2];print('1M base',b1,'floor',f1,'lowfloors',a1[0x0F0//2] if False else '(-120,-132 scalars at +0xF0/+0xF2 per diff)')
print('M3 base',a3[0x284//2],'floor',a3[0x282//2],'gains',a3[0x27E//2],a3[0x280//2])
print('M3 20km/h-floor table +0x2A8:',a3[0x2A8//2:0x2A8//2+12]);print('M3 60km/h-floor table +0x2C0:',a3[0x2C0//2:0x2C0//2+12])
print('v    1M(front)  M3 front per mode 0..11')
for v in V:
    t1=thr(a1,0x76,-120,-132,-116,-240,v)
    row=[thr(a3,0x76+0x28*m,a3[0x2A8//2+m],a3[0x2C0//2+m],-116,-240,v) for m in range(12)]
    print('%3d  %5d   %s'%(v,t1,row))
print('rear curve (1M +0x9E == M3 +0x256), no mode dependence in M3 curve:')
for v in V: print(v, thr(a1,0x9E,-120,-132,-116,-240,v), thr(a3,0x256,a3[0x2A8//2],a3[0x2C0//2],-116,-240,v))
print('\nsecond term g(x) 1M vs M3 modes (x=0,20,50,100,127):')
for x in (0,20,50,100,127):
    print(x, ev(cv(a1,0xF4),x),[ev(cv(a3,0x2D8+64*m),x) for m in range(12)])
print('\nspeed-term differences per mode (front curve) - modes whose curve differs from mode 0:')
for m in range(12):
    print(m, cv(a3,0x76+0x28*m)[3:]==cv(a3,0x76)[3:], cv(a3,0x2D8+64*m)==cv(a3,0x2D8), cv(a3,0x76+0x28*m)==cv(a1,0x76))
for m in (10,11):
    print(m,'front curve',cv(a3,0x76+0x28*m)); 
print('1M front',cv(a1,0x76)); print('1M g',cv(a1,0xF4)); print('M3 g m0',cv(a3,0x2D8)); print('M3 g m10',cv(a3,0x2D8+640)); print('M3 g m11',cv(a3,0x2D8+704))

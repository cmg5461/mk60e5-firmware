# Integer replica of the linear-region bicycle observer sub_05ECB0 (1M 7846411A)
import math
def tdiv(a,b):
    q=abs(a)//abs(b); return q if (a<0)==(b<0) else -q
def sh(x,s): return tdiv(x,1<<s)
def cl16(x): return max(-32768,min(32767,x))
lf,lr,m,J,Cf,Cr=1331,1393,1739,3039,7186,12857
AA4=sh(tdiv(lr*-763548,J),7)
AAA=tdiv(0xdb6dac,m)
AAE=((Cf<<17)//24999)//3
AB2=(Cr<<17)//99999
AB4=sh(tdiv(572661*lf,J),7)
AB6=tdiv(19173933,m)
ABA=sh(-lf*0x2a3f,10); ABC=sh(lr*0x2a3f,10)
def curveR4(v):  # blend factor (needs ROM) ; read from ROM
    import struct
    d=open('flash/bin/7846411A_00000000.bin','rb').read()
    xs=[struct.unpack('>h',d[0xD7492+0x8000+2*i:0xD7492+0x8000+2*i+2])[0] for i in range(4)]
    ys=[struct.unpack('>h',d[0xD748A+0x8000+2*i:0xD748A+0x8000+2*i+2])[0] for i in range(4)]
    return xs,ys
def run(v,delta2,steps=4000):
    b=0;r=0;rd_prev=0;bd_prev=0;a50=0
    xs,ys=curveR4(0)
    # interpolate R4 (sub_071158 style simplified: linear between points)
    def R4(vv):
        if vv<=xs[0]: return ys[0]
        for i in range(1,4):
            if vv<=xs[i]:
                return ys[i-1]+(ys[i]-ys[i-1])*(vv-xs[i-1])/(xs[i]-xs[i-1])
        return ys[3]
    Fprev=0
    for k in range(steps):
        r9=tdiv(ABA*r,8)
        r11=tdiv(r9,v)
        af=cl16(delta2+2*b+r11)
        w=int(R4(v))
        a50=cl16((af*(8192-w)+a50*w)//8192) if True else af
        af_f=a50
        Ff=tdiv(AAE*af_f,16384)
        # rear
        r7=tdiv(ABC*r,8); r12=tdiv(r7,v)
        ar=2*b+r12
        Fr=tdiv(AB2*ar,16384)
        t1=tdiv(AAA*(-Ff),128); t1=tdiv(t1,v)
        t2=tdiv(AB6*(-Fr),128); t2=tdiv(t2,v)
        bd=cl16(2*t1+2*t2+tdiv(r,64))
        b=cl16(b+tdiv((bd+bd_prev)*0x2673,16384)); bd_prev=bd
        rd=cl16(tdiv(AB4*Ff,16384)+tdiv(AA4*Fr,16384))
        r=cl16(r+tdiv((rd+rd_prev)*10,14)); rd_prev=rd
    return r,b,rd,bd
if __name__=='__main__':
    for kmh in (30,50,80,100,150):
        v=kmh*100
        d2=1000
        r,b,rd,bd=run(v,d2)
        print(kmh,'km/h  2*delta=',d2,'r_code=',r,'beta=',b,'rd',rd,'bd',bd,'gain r/(2d)=',r/d2)

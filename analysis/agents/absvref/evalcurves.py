import struct,sys
d=open('flash/bin/7846411A_00000000.bin','rb').read()
def h(a,n=1):
    return [struct.unpack('>h',d[a+0x8000+2*i:a+0x8002+2*i])[0] for i in range(n)]
def curve(a):
    lo,hi,n=h(a,3)
    x=h(a+6,n-1); c=h(a+6+2*(n-1),n); k=h(a+6+2*(n-1)+2*n,n)
    return lo,hi,n,x,c,k
def ev(cv,xv):
    lo,hi,n,x,c,k=cv
    i=0
    while i<n-1 and xv>=x[i]: i+=1
    return max(lo,min(hi,c[i]+((xv*k[i])>>10)))
S={'T0 base 0x40468':0x40468,'floor 0x40466':0x40466,'lowspd -132 0x4048E':0x4048E,'lowspd -120 0x4048C':0x4048C,
 'L1 0x40664':0x40664,'L2 0x40666':0x40666,'L3 0x40668':0x40668,'L4 0x4066A':0x4066A,'c32E 0x406CA':0x406CA,
 'gate 0x40742':0x40742,'gate 0x40744':0x40744}
for k,a in S.items(): print(k,h(a)[0])
print('X-thresholds from 0x4048..: 0x4048E,0x4048C ok')
cur={'front 0x40412 (+0x76)':(0x40412,[0,5000,10000,15000,20000,25000,30000]),
'rear 0x4043A (+0x9E)':(0x4043A,[0,5000,10000,15000,20000,25000,30000]),
'2nd 0x40490 (+0xF4) x=decel':(0x40490,[0,20,40,60,80,100,120,127]),
'frac front 0x404F0 (+0x154)':(0x404F0,[0,500,1000,2000,4000,8000,16000]),
'frac rear 0x40518 (+0x17C)':(0x40518,[0,500,1000,2000,4000,8000,16000]),
'0x40726':(0x40726,[2000,3000,4000,5000,6000]),
'0x406EE slip%':(0x406EE,[0,5,10,15,20,30,50]),
'0x4070A spd':(0x4070A,[2000,3000,4000,5000,6000]),
'0x406CC L':(0x406CC,[0,500,1000,2000,4000]),
'0x406A8':(0x406A8,[0,50,100,200,300]),
'0x40670':(0x40670,[0,50,100,200,300]),
'0xD72A0 p':(0xD72A0,[0,500,1000,1500,2000,2499]),
'0xD728A L':(0xD728A,[0,500,1000,2000,4000,8000]),
'0xD7322 vref':(0xD7322,[0,1000,2000,5000,10000]),
}
for k,(a,xs) in cur.items():
    cv=curve(a); print(k,'lo,hi,n',cv[:3],'x',cv[3],'c',cv[4],'k',cv[5]); print('   ',[(x,ev(cv,x)) for x in xs])

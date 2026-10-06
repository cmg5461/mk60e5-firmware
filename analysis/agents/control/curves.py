import struct,sys
d=open('flash/bin/7846411A_00000000.bin','rb').read()
def h(a,n=1):
    return [struct.unpack('>h',d[a+0x8000+2*i:a+0x8002+2*i])[0] for i in range(n)]
def curve(a):
    lo,hi,n=h(a,3)
    if not(1<=n<=12): return None
    x=h(a+6,n-1); c=h(a+6+2*(n-1),n); k=h(a+6+2*(n-1)+2*n,n)
    return lo,hi,n,x,c,k,a+6+2*(n-1)+4*n
def ev(cv,xv):
    lo,hi,n,x,c,k,_=cv
    i=0
    while i<n-1 and xv>=x[i]: i+=1
    y=c[i]+((xv*k[i])>>10)
    return max(lo,min(hi,y))
if __name__=='__main__':
    for s in sys.argv[1:]:
        a=int(s,16); cv=curve(a)
        print(hex(a),cv[:6],'end',hex(cv[6]))
        xs=[0,100,200,500,1000,1500,2000,3000,5000,8000,10000,15000,20000,30000]
        print('   ',[(xv,ev(cv,xv)) for xv in xs])

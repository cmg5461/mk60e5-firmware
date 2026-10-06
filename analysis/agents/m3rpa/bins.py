# Recompute the DDS/RPA 40-tap bank bin frequencies from the Q12 tables (M3 image).
import struct,math
d=open('flash/bin/7846816A_00000000.bin','rb').read()
def tab(a,rows):
    o=a+0x8000
    return [[struct.unpack('>h',d[o+(r*40+k)*2:o+(r*40+k)*2+2])[0] for k in range(40)] for r in range(rows)]
A=tab(0xDAFD0,200);B=tab(0xDEE50,400);C=tab(0xE6B50,200);D=tab(0xEA9D0,400)
def cyc(S,Cc,N):
    return [round(((math.atan2(S[1][k],Cc[1][k])-math.atan2(S[0][k],Cc[0][k])+math.pi)%(2*math.pi)-math.pi)*N/(2*math.pi)) for k in range(40)]
ac=cyc(A,C,200); bd=cyc(B,D,400)
fs=400.0  # assumed: 2500 us resample interval
words=sorted([(2*c,'AC%d'%k) for k,c in enumerate(ac)]+[(c,'BD%d'%k) for k,c in enumerate(bd)])
# word order in RAM is interleaved (2k = AC k, 2k+1 = BD k); Hz = (cycles/400)*fs
print('AC cycles/200:',ac); print('BD cycles/400:',bd)
print('merged Hz (fs=400):',[ (w[0]*fs/400, w[1]) for w in words])

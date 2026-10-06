import struct,random
d=open('../../../flash/bin/7846411A_00000000.bin','rb').read()
M=0xFFFFFFFF
s,e,x=0x40000,0x402F8,0xB6EFCB77
W={k:struct.unpack(k+'%dI'%((e-s)//4),d[s+0x8000:e+0x8000]) for k in '<>'}
polys=[0x04C11DB7,0xEDB88320,0x04C11DB1,0x1EDC6F41,0x82F63B78,0xD5828281,0x80000057,0xC0000401,0x80200003,0x80000EA6,0xA0000001,0x80000062,0x8000000D,0x00400007,0x04C11DB7^1,0xA3000000,0x20000029, 0x82608EDB,0xB8000000,0x90000000,0xD0000001,0x80000AF,0xFA567D89,0x814141AB,0xF4ACFB13,0x32583499,0x992C1A4C,0x8F6E37A0,0x741B8CD7,0xA833982B,0x000000AF,0x00000001]
def steps(ws,poly,mode,inc):
    s_=0
    for w in ws:
        if mode==0: # galois left
            s_=((s_<<1)^(poly if s_>>31 else 0))&M
        elif mode==1: # galois right
            s_=(s_>>1)^(poly if s_&1 else 0)
        elif mode==2: # fibonacci left, feedback = parity(s&poly)
            fb=bin(s_&poly).count('1')&1; s_=((s_<<1)|fb)&M
        elif mode==3:
            fb=bin(s_&poly).count('1')&1; s_=(s_>>1)|(fb<<31)
        elif mode==4: # rotate left
            s_=((s_<<1)|(s_>>31))&M
        elif mode==5:
            s_=((s_>>1)|(s_<<31))&M
        s_^=w if inc!=1 else 0
        if inc==1: s_=(s_^w)  # same
    return s_
hits=0
for k in '<>':
  for p in polys:
    for mode in range(6):
      for pre in (0,1): # xor before or after step
        s_=0
        for w in W[k]:
            if pre: s_^=w
            if mode==0: s_=((s_<<1)^(p if s_>>31 else 0))&M
            elif mode==1: s_=(s_>>1)^(p if s_&1 else 0)
            elif mode==2: s_=((s_<<1)|(bin(s_&p).count('1')&1))&M
            elif mode==3: s_=(s_>>1)|((bin(s_&p).count('1')&1)<<31)
            elif mode==4: s_=((s_<<1)|(s_>>31))&M
            else: s_=((s_>>1)|(s_<<31))&M
            if not pre: s_^=w
        for name,v in (('v',s_),('~',s_^M),('rev',int(format(s_,'032b')[::-1],2)),('bs',int.from_bytes(s_.to_bytes(4,'big'),'little'))):
            if v==x: print('HIT',k,hex(p),mode,pre,name)
print('done')

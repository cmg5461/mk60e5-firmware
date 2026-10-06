import struct,zlib,itertools,binascii
d=open('../../../flash/bin/7846411A_00000000.bin','rb').read()
R=[(0x40000,0x402F8,0xB6EFCB77),(0x40300,0x426BC,0x03B09CDC),(0x426C0,0xF6684,0xD719D58D)]
for s,e,x in R: assert struct.unpack('>I',d[e+0x8000:e+0x8004])[0]==x
M=0xFFFFFFFF
def words(s,e,end='>'):
    return struct.unpack(end+'%dI'%((e-s)//4),d[s+0x8000:e+0x8000])
def rev(v,n=32): return int(format(v,'0%db'%n)[::-1],2)
def crc_bytes(data,poly,init,refl,xo):
    c=init
    if refl:
        p=rev(poly)
        for b in data:
            c^=b
            for _ in range(8): c=(c>>1)^p if c&1 else c>>1
    else:
        for b in data:
            c^=b<<24
            for _ in range(8): c=((c<<1)^poly if c&0x80000000 else c<<1)&M
    return c^xo
polys=[0x04C11DB7,0x04C11DB1,0x1EDC6F41,0x741B8CD7,0xA833982B,0x814141AB,0x8F6E37A0,0x000000AF,0x04C10DB7]
res={}
for s,e,x in R[:1]:
  for end in '><':
    raw=b''.join(struct.pack('>I',w) for w in words(s,e,end))
    for poly in polys:
      for init in (0,M):
        for refl in (0,1):
          for xo in (0,M):
            c=crc_bytes(raw,poly,init,refl,xo)
            for name,v in (('v',c),('rev',rev(c)),('bs',int.from_bytes(c.to_bytes(4,'big'),'little'))):
                if v==x: print('HIT',end,hex(poly),init,refl,xo,name)
    ws=words(s,e,end)
    print(end,'sum',hex(sum(ws)&M),'xor',hex(eval('__import__("functools").reduce(lambda a,b:a^b,ws)')),hex(x))

#!/usr/bin/env python
"""Build #3: repoint service 0x23 (ReadMemoryByAddress, table entry 21) to a
parametric peek handler. Request is EXACTLY 6 bytes (table len=0x06 enforced):

    23 <op> <a0 a1 a2 a3>

  op=0x01  ASIC xfer : r2=(a0<<24|a1<<16|a2<<8|a3); jsri 0xD4A30; return 4-byte
                       readback (RX0<<16|RX1), big-endian. (peek AND poke)
  op=0x02  RAM peek  : addr=a0..a3; read 32 bytes from CPU addr -> response.

Response convention mimics stock 0x23: data -> 0x40948A, length 0x409537 =
databytes+1, ready 0x409435=1 (dispatcher prepends 0x63 positive-response SID).
Handler is a clean subroutine (dispatcher calls via `jsr r7`); saves r15
because op=1 calls into the ASIC driver.

Hook: service table @ CPU 0xF30A0, entry 21 (0x23), handler ptr at entry+4
      = CPU 0xF31A0 / file 0xFB1A0 : 0x000B3112 -> 0x000D8F98.
Handler body @ CPU 0xD8F98 / file 0xE0F98 (zero-fill, inside BMY-signed seg).
"""
import struct

HANDLER_CPU = 0xD8F98
CPU2FILE    = 0x8000
TBL_CPU     = 0xF30A0
ENTRY       = 21
PTR_FILE    = (TBL_CPU + ENTRY*12 + 4) + CPU2FILE   # 0xFB1A0
ASICFN      = 0xD4A30

class Asm:
    def __init__(self, base): self.base=base; self.items=[]; self.labels={}
    def _a(self, fn): self.items.append([None, fn])
    # instructions
    def lrw (self,rd,l): self._a(lambda pc: 0x7000|(rd<<8)|self._o8(pc,l))
    def jsri(self,l):    self._a(lambda pc: 0x7F00|self._o8(pc,l))
    def ldb (self,rz,rx,d): self._a(lambda pc: 0xA000|(rz<<8)|((d&0xF)<<4)|rx)
    def stb (self,rz,rx,d): self._a(lambda pc: 0xB000|(rz<<8)|((d&0xF)<<4)|rx)
    def mov (self,rd,rs): self._a(lambda pc: 0x1200|(rs<<4)|rd)
    def movi(self,rd,i):  self._a(lambda pc: 0x6000|((i&0x7F)<<4)|rd)
    def addi(self,rd,i):  self._a(lambda pc: 0x2000|(((i-1)&0x1F)<<4)|rd)
    def subi(self,rd,i):  self._a(lambda pc: 0x2400|(((i-1)&0x1F)<<4)|rd)
    def orr (self,rd,rs): self._a(lambda pc: 0x1E00|(rs<<4)|rd)
    def lsli(self,rd,i):  self._a(lambda pc: 0x3C00|((i&0x1F)<<4)|rd)
    def lsri(self,rd,i):  self._a(lambda pc: 0x3E00|((i&0x1F)<<4)|rd)
    def cmpnei(self,rd,i):self._a(lambda pc: 0x2A00|((i&0x1F)<<4)|rd)
    def bf  (self,l):     self._a(lambda pc: 0xE800|(self._disp(pc,l)&0x7FF))
    def br  (self,l):     self._a(lambda pc: 0xF000|(self._disp(pc,l)&0x7FF))
    def ldm (self,n):     self._a(lambda pc: 0x0060|n)
    def stm (self,n):     self._a(lambda pc: 0x0070|n)
    def jmp (self,rx):    self._a(lambda pc: 0x00C0|rx)
    # directives
    def lbl (self,n):     self.items.append(['L',n])
    def al4 (self):       self.items.append(['A',None])
    def word(self,n,v):   self.items.append(['W',(n,v)])
    def _o8(self,pc,l):
        t=self.labels[l]; o=(t-((pc+2)&~3))//4
        assert 0<=o<=255,"off8 %d"%o; return o
    def _disp(self,pc,l):
        t=self.labels[l]; d=(t-(pc+2))//2
        assert -0x400<=d<0x400,"branch %d"%d; return d
    def asm(self):
        pc=self.base
        for it in self.items:
            if   it[0]=='A': pad=(4-(pc%4))%4; it.append(pad); pc+=pad
            elif it[0]=='L': self.labels[it[1]]=pc
            elif it[0]=='W': self.labels[it[1][0]]=pc; pc+=4
            else: it[0]=pc; pc+=2
        out=bytearray()
        for it in self.items:
            if   it[0]=='A': out+=b'\x00'*it[-1]
            elif it[0]=='L': pass
            elif it[0]=='W': out+=struct.pack(">I",it[1][1])
            else: out+=struct.pack(">H",it[1](it[0]))
        return bytes(out)

a=Asm(HANDLER_CPU)
# prologue: mirror the stock 0x23 handler's exact frame (subi r0,16; stm r13-r15)
# -- known-good encodings; preserves r13/r14 (we only clobber r1-r7) and r15.
a.subi(0,16); a.stm(13)
# r3 = &request ; r1 = op ; r4 = 32-bit arg
a.lrw(3,'REQ')
a.ldb(1,3,1)
a.ldb(4,3,2); a.lsli(4,8)
a.ldb(5,3,3); a.orr(4,5); a.lsli(4,8)
a.ldb(5,3,4); a.orr(4,5); a.lsli(4,8)
a.ldb(5,3,5); a.orr(4,5)
a.cmpnei(1,1); a.bf('ASIC')            # op==1 -> ASIC
# ---- RAM peek: 16 bytes from r4 -> 0x40948A (response 17B, safe vs ~31B buf) ----
a.lrw(7,'DST'); a.movi(6,16)
a.lbl('RL')
a.cmpnei(6,0); a.bf('RD')
a.ldb(5,4,0); a.stb(5,7,0)
a.addi(4,1); a.addi(7,1); a.subi(6,1)
a.br('RL')
a.lbl('RD')
a.movi(6,17); a.lrw(7,'LEN'); a.stb(6,7,0)   # length = 16+1
a.br('FIN')
# ---- ASIC xfer ----
a.lbl('ASIC')
a.mov(2,4); a.jsri('AFN')              # r2=arg; call 0xD4A30; r2=readback
a.lrw(7,'DST')
a.mov(4,2); a.lsri(4,24); a.stb(4,7,0)
a.mov(4,2); a.lsri(4,16); a.stb(4,7,1)
a.mov(4,2); a.lsri(4,8);  a.stb(4,7,2)
a.mov(4,2);               a.stb(4,7,3)
a.movi(6,5); a.lrw(7,'LEN'); a.stb(6,7,0)    # length = 4+1
# ---- finish ----
a.lbl('FIN')
a.lrw(7,'RDY'); a.movi(6,1); a.stb(6,7,0)    # ready=1
a.ldm(13); a.addi(0,16); a.jmp(15)           # epilogue (matches stock 0x23)
a.al4()
a.word('REQ',0x0040331D); a.word('DST',0x0040948A)
a.word('LEN',0x00409537); a.word('RDY',0x00409435); a.word('AFN',ASICFN)
code=a.asm()
print("0x23 handler @ CPU 0x%X (file 0x%X): %d bytes"%(HANDLER_CPU,HANDLER_CPU+CPU2FILE,len(code)))
print(" ",code.hex(" "))
print(" labels:",{k:"0x%X"%v for k,v in a.labels.items()})

img=bytearray(open("flash/bin/7846816A_00000000.bin","rb").read())
hoff=HANDLER_CPU+CPU2FILE
assert all(b==0 for b in img[hoff:hoff+len(code)]),"handler region not zero"
img[hoff:hoff+len(code)]=code
cur=struct.unpack(">I",img[PTR_FILE:PTR_FILE+4])[0]
print("svc-table 0x23 handler ptr @ file 0x%X: 0x%08X -> 0x%08X"%(PTR_FILE,cur,HANDLER_CPU))
assert cur==0x000B3112,"unexpected handler ptr 0x%X"%cur
img[PTR_FILE:PTR_FILE+4]=struct.pack(">I",HANDLER_CPU)
open("flash/bin/7846816A_probe.bin","wb").write(img)
print("wrote flash/bin/7846816A_probe.bin")

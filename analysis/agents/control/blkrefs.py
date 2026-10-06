import struct,re,sys,bisect,collections
d=open('flash/bin/7846411A_00000000.bin','rb').read()
subs=sorted(int(m.group(1),16) for m in re.finditer(r'^sub_([0-9A-F]+):',open('analysis/7846411A_main.lst').read(),re.M))
def fn(a): return subs[bisect.bisect_right(subs,a)-1]
blocks={'ABS':(0x4039C,0x40A04),'CSI':(0x40A04,0x40AB8),'TCS':(0x40AB8,0x413EC),'AYC':(0x413EC,0x41978),'BCO':(0x41978,0x41B98),'COA':(0x41B98,0x41F04),'BFU':(0x41F04,0x41F20),'VAR':(0x41F20,0x41F30),'DDS':(0x41F30,0x42048),'CSW':(0x42048,0x42064),'LVC':(0x42064,0x42644),'VMO':(0x42644,0x426BC),'SCAL':(0xDA2F0,0xDB300)}
res=collections.defaultdict(lambda: collections.defaultdict(int))
for a in range(0x40000,0xF0000,2):
    v=struct.unpack('>I',d[a+0x8000:a+0x8004])[0]
    for n,(lo,hi) in blocks.items():
        if lo<=v<hi: res[n][fn(a)]+=1
for n in blocks:
    fs=sorted(res[n]); 
    print(n,len(fs),'fns; range',hex(fs[0]) if fs else '',hex(fs[-1]) if fs else '')
    print('  ',' '.join('%x(%d)'%(f,res[n][f]) for f in fs))

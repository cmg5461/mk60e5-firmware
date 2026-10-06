import re,sys
d=open('flash/bin/7846816A_00000000.bin','rb').read()
d1=open('flash/bin/7846411A_00000000.bin','rb').read()
def find(a1,n=32):
    pat=d1[a1+0x8000:a1+0x8000+n]
    r=[m.start()-0x8000 for m in re.finditer(re.escape(pat),d)]
    return r
if __name__=='__main__':
    for a in sys.argv[1:]:
        a=int(a,16)
        for n in (40,24,16):
            r=find(a,n)
            if r: print(hex(a),n,[hex(x) for x in r]);break
        else: print(hex(a),'none')

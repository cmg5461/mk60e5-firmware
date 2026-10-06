import re
L=open('analysis/agents/geom/m3_main.lst').read().split('\n')
pat=re.compile(r'^\s*([0-9A-F]{6}):\s+[0-9A-F]{4}\s+(.*)$')
blocks=[('ABS',0x4039c,0xb0a),('CSI',0x40ea8,0x114),('TCS',0x40fbc,0x1d4),('AYC',0x41190,0x5c6),('BCO',0x41758,0x220),('COA',0x41978,0x36c),('BFU',0x41ce4,0x1c),('VAR',0x41d00,0xe),('DDS',0x41d10,0x118),('CSW',0x41e28,0x1a),('LVC',0x41e44,0x5e0),('VMO',0x42424,0x6c)]
def blk(v):
    for n,a,l in blocks:
        if a<=v<a+l: return '%s+%#x'%(n,v-a)
for i,l in enumerate(L):
    if '= 0x004031aa' in l:
        m=pat.match(l);reg=re.search(r'lrw (r\d+)',l).group(1)
        fld=None
        for j in range(i+1,i+6):
            mo=re.search(r'ld\.b r\d+,\('+reg+r',(\d+)\)',L[j])
            if mo: fld=int(mo.group(1));break
        if fld not in (1,2,3,4,7,0,9): continue
        refs=[]
        for j in range(i-12,i+16):
            mm=re.search(r'; = 0x([0-9a-f]{8})',L[j])
            if mm:
                v=int(mm.group(1),16)
                b=blk(v)
                if b and v not in (0x4031aa,): refs.append(b)
        print(m.group(1),'+%d'%fld,refs)

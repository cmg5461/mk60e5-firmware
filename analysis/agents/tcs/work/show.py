import sys,re
s=int(sys.argv[1],16); e=int(sys.argv[2],16)
L=open('analysis/7846411A_main.lst').read().split('\n')
for l in L:
    m=re.match(r'^\s*([0-9A-F]{6}):\s+[0-9A-F]{4}\s+(.*)$',l)
    if m:
        a=int(m.group(1),16)
        if s<=a<e:
            t=m.group(2)
            mm=re.search(r'; = 0x([0-9a-f]{8})',t)
            note=''
            if mm:
                v=int(mm.group(1),16)
                if 0x40AB8<=v<0x413EC: note='   <== TCS+%03x'%(v-0x40AB8)
                elif 0x400000<=v<0x410000: note='   <== RAM'
            t=re.sub(r'\s*;.*','',t) if not mm else t
            print('%06X %s%s'%(a,t,note))
    elif l.startswith('sub_'):
        a=int(l[4:10],16)
        if s<=a<e: print(l)

import re,sys
for f,tag in [('../m3can/m3_can_map.txt','MAIN'),('m3_fcan_map.txt','FCAN')]:
    print('#####',tag)
    cur=None;out=[]
    for l in open(f):
        m=re.match(r'## (TX|RX) 0x([0-9A-F]+)\s+dlc (\d+)\s+flags (\S+)\s+(\S+(?: ms)?)\s+mailbox',l)
        if m:
            if cur: print(cur+' '.join(out)); out=[]
            cur='%s %s dlc%s %s: '%(m.group(1),m.group(2),m.group(3),m.group(5).replace(' ',''))
            continue
        m=re.match(r'\| (\d+) \| (\d+)\.(\d+) \| (\d+) \| (0x\w+) \| (0x\w+) \| (\d) \| (0x[0-9a-f]+) \|',l)
        if m:
            s,by,bi,ln,fl,var,ty,cb=m.groups()
            if ty=='4' : out.append('[msg-cb %s]'%cb[2:].lstrip('0')); continue
            sg='s' if int(fl,16)&1 else ''
            t={'0':'','1':'R','2':'k'}.get(ty,ty)
            out.append('%s:%s.%s/%s%s%s v%s @%s;'%(s,by,bi,ln,sg,('!'+t if t else ''),var[2:],cb[2:].lstrip('0')))
    print(cur+' '.join(out))

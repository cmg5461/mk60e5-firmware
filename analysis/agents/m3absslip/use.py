import re,sys
tgt=int(sys.argv[1],16); W=int(sys.argv[2])
ins=[]
for l in open('analysis/7846816A_main.lst'):
    m=re.match(r'\s+([0-9A-F]{6}):\s+([0-9A-F]{4})\s+(\S+)\s*(.*)',l)
    if m: ins.append((int(m[1],16),m[3],m[4].strip()))
for i,(a,mn,op) in enumerate(ins):
    if mn=='lrw' and re.search(r'= 0x%08x'%tgt,op):
        reg=op.split(',')[0]
        for x in ins[i+1:i+W]:
            if re.match(r'(ld|st)\.[hbw]',x[1]) and ('(%s,'%reg) in x[2]:
                print('%X: %X %s %s'%(a,x[0],x[1],x[2]))

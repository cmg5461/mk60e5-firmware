import re,sys
tgt=int(sys.argv[1],16); W=int(sys.argv[2]) if len(sys.argv)>2 else 10
ins=[]
for l in open('analysis/7846816A_main.lst'):
    m=re.match(r'\s+([0-9A-F]{6}):\s+([0-9A-F]{4})\s+(\S+)\s*(.*)',l)
    if m: ins.append((int(m[1],16),m[3],m[4].strip()))
for i,(a,mn,op) in enumerate(ins):
    if mn=='lrw' and re.search(r'= 0x%08x'%tgt,op):
        reg=op.split(',')[0]
        win=ins[max(0,i-W//2):i+W]
        kind=[x for x in ins[i+1:i+W] if re.match(r'st\.[hbw]',x[1]) and ('(%s,'%reg) in x[2]]
        print('%X %s %s'%(a, 'STORE' if kind else 'read', ' | '.join('%X:%s %s'%x for x in ins[i-3:i+W//1+1] )) if (kind or len(sys.argv)>3) else '', end='\n' if (kind or len(sys.argv)>3) else '')

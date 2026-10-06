import re,sys
L=open('all.txt').read().split('\n')
fn=None;body={}
cur=None
for l in L:
    if l.startswith('sub_'): cur=l.strip(); body[cur]=[]; continue
    if cur: body[cur].append(l)
pat=sys.argv[1]; need=sys.argv[2] if len(sys.argv)>2 else '0x0040bf00'
for k,v in body.items():
    t='\n'.join(v)
    if re.search(pat,t) and need in t: print(k, len(v))

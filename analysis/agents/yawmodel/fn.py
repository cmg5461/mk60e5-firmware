import re,sys,subprocess,bisect
L=open('analysis/7846411A_main.lst').read().split('\n')
subs=[]
for l in L:
    m=re.match(r'^sub_([0-9A-F]{6}):',l)
    if m: subs.append(int(m.group(1),16))
subs.sort()
def bounds(a):
    i=bisect.bisect_right(subs,a)-1
    return subs[i], (subs[i+1]-1 if i+1<len(subs) else a+0x400)
if __name__=='__main__':
    a=int(sys.argv[1],16); s,e=bounds(a)
    print(f'# fn {s:X}..{e:X}')
    subprocess.run(['python','analysis/agents/yawmodel/lift.py',f'{s:X}',f'{e:X}'])

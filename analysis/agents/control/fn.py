import re,sys
L=open('analysis/7846411A_main.lst').read().split('\n')
name='sub_%06X:'%int(sys.argv[1],16)
on=False
for l in L:
    if l.startswith(name): on=True; print(l); continue
    if on and l.startswith('sub_'): break
    if on and not re.search(r'bkpt|trap |ldq|\.short|doze|stop\b|idly',l): print(l)

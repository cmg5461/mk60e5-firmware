import sys,bisect
a=int(sys.argv[1],16)
L=open('analysis/7846816A_main.lst').read().split('\n')
starts=[(int(l[4:10],16),i) for i,l in enumerate(L) if l.startswith('sub_')]
k=bisect.bisect_right([s for s,_ in starts],a)-1
i=starts[k][1];j=starts[k+1][1] if k+1<len(starts) else len(L)
print('\n'.join(x[:84] for x in L[i:j]))

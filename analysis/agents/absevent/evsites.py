import re
L=[l for l in open('d470.txt').read().split('\n') if l.strip()]
# find 'movi rX,28|29' followed by 'addu rX,r0' ; then track byte reg
ptr={}  # reg-> 28/29 ; also 
out=[]
bytereg={} # reg->(28/29)
for i,l in enumerate(L):
    m=re.search(r'movi (r\d+),(28|29)$',l)
    if m and i+1<len(L) and re.search(r'addu '+m.group(1)+r',r0',L[i+1]+L[i+2] if i+2<len(L) else L[i+1]):
        ptr[m.group(1)]=int(m.group(2)); continue
    # pointer reg overwritten
    m=re.search(r'^\s+\w+:\s+\w+\s+(?:movi|mov|lrw|addu|ld\.\w|addi|subi)\s+(r\d+),',l)
    if m and not re.search(r'movi (r\d+),(28|29)$',l):
        r=m.group(1)
        if r in ptr and not re.search(r'addu '+r+r',r0',l): del ptr[r]
        if r in bytereg and not re.search(r'ld\.b '+r,l): pass
    m=re.search(r'ld\.b (r\d+),\((r\d+),0\)',l)
    if m and m.group(2) in ptr: bytereg[m.group(1)]=ptr[m.group(2)]
    m=re.search(r'(bseti|bclri) (r\d+),(\d)',l)
    if m and m.group(2) in bytereg:
        out.append((l.split(':')[0].strip(),bytereg[m.group(2)],m.group(1),m.group(3)))
for o in out: print(*o)

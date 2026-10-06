import re
L=open('all.txt').read().split('\n')
fn=None
for i,l in enumerate(L):
    if l.startswith('sub_'): fn=l
    m=re.search(r'addi (r\d+),(32|34|33)$',l)
    if m:
        r=m.group(1)
        for j in range(i+1,min(i+14,len(L))):
            if re.search(r'st\.[hwb] \w+,\('+r+r',(0|2|4)\)',L[j]):
                print(fn,L[i].strip(),'|',L[j].strip()); break
            if re.search(r'^\s+\w+:\s+\w+\s+(mov|lrw|ld\.\w+|addu|ixh|ixw) '+r+',',L[j]) : break

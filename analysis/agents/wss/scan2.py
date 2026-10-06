import re,sys
L=open('analysis/7846411A_main.lst',encoding='utf8',errors='ignore').read().split('\n')
seen=set()
for i,l in enumerate(L):
    if '= 0x0040bf00' in l:
        for j in range(i+1,min(i+80,len(L))):
            m=re.search(r'st\.[hb] r\d+,\(r(\d+),(42|43)\)',L[j])
            if m and j not in seen: seen.add(j); print(l.split()[0],L[j].strip())
            if 'jmp r15' in L[j]: break

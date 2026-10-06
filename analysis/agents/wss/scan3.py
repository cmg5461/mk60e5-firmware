import re,sys
addr,bit=sys.argv[1].lower(),sys.argv[2]
L=open('analysis/7846411A_main.lst',encoding='utf8',errors='ignore').read().split('\n')
for i,l in enumerate(L):
    if l.strip().endswith('= '+addr):
        for j in range(i+1,min(i+8,len(L))):
            if re.search(r'(bseti|bclri) r\d+,'+bit+r'\b',L[j]):
                print(l.split()[0],'|',L[j].strip()); break

import sys
m=open('flash/bin/7846816A_00000000.bin','rb').read();o=open('flash/bin/7846411A_00000000.bin','rb').read()
for a in sys.argv[1:]:
    a=int(a,16);w=o[a+0x8000:a+0x8000+32]
    r=[hex(i-0x8000) for i in range(0,len(m)-32,2) if m[i:i+32]==w]
    print(hex(a),r)

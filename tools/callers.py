import struct,re,sys
d=open('fw/fwdc218b_dec.bin','rb').read()
B=0x10000000
for t in [int(x,16) for x in sys.argv[1:]]:
    imm=[hex(B+m.start()) for m in re.finditer(re.escape(struct.pack('>I',t)),d)]
    rel=[]
    for o in range(max(0,t-B-0x1000),min(len(d),t-B+0x1000),2):
        w=struct.unpack('>H',d[o:o+2])[0]
        if (w>>12)==0xd:
            r=w&0x7ff
            if r&0x400: r-=0x800
            if B+o+2+r*2==t: rel.append(hex(B+o))
    print(hex(t),'imm',imm,'relcall',rel)

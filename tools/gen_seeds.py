#!/usr/bin/env python3
"""Emit function entry seeds for the decrypted K-5 IIs image.

Seeds are targets of `LDI:32 #imm, Ri` immediately followed by
`CALL @Ri` / `CALL:D @Ri`, filtered to addresses that start with a typical
FR prologue (ST RP,@-R15 / ENTER / STM1).
"""
import re
import struct
import sys

BASE = 0x10000000


def main(path, out):
    d = open(path, "rb").read()
    seeds = set()
    for m in re.finditer(rb"\x9f([\x80-\x8f])(....)([\x97\x9f])", d, re.S):
        o = m.start()
        if o % 2:
            continue
        reg = m.group(1)[0] & 0xF
        if d[o + 7] != (0x10 | reg):
            continue
        t = struct.unpack(">I", m.group(2))[0] - BASE
        if not (0 <= t < len(d) - 2) or t % 2:
            continue
        b = d[t:t + 2]
        if b == b"\x17\x81" or b[0] in (0x0F, 0x8F):
            seeds.add(t + BASE)
    with open(out, "w") as f:
        for s in sorted(seeds):
            f.write("%08x\n" % s)
    print("%d seeds -> %s" % (len(seeds), out))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

#!/usr/bin/env python3
"""Find the FR function containing an address and create it in Ghidra via GhidraMCP.

Walks back from each address to the first prologue (ST RP,@-R15 / ENTER / STM1)
that directly follows a RET (97 20) or RET:D (9F 20 + delay slot).
Usage: mkfunc.py <addr> [...]
"""
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
import gh  # noqa: E402

BASE = 0x10000000
IMG = __import__("os").path.join(__import__("os").path.dirname(__file__), "..", "fw", "fwdc218b_dec.bin")


def is_prologue(b):
    return b == b"\x17\x81" or b[0] in (0x0F, 0x8F)


def find_start(d, addr):
    o = (addr - BASE) & ~1
    while o > 0:
        o -= 2
        if is_prologue(d[o:o + 2]) and (d[o - 2:o] == b"\x97\x20" or d[o - 4:o - 2] == b"\x9f\x20"):
            return o + BASE
    return None


def main():
    d = open(IMG, "rb").read()
    for a in sys.argv[1:]:
        s = find_start(d, int(a, 16))
        print(a, "->", hex(s) if s else None)
        if s:
            print(gh.post("create_function", address=hex(s), disassemble_first=True))


if __name__ == "__main__":
    main()

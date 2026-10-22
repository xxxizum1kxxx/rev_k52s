#!/usr/bin/env python3
"""Port function names between two decrypted FR80 images (e.g. K-5 IIs 1.07 -> K-5 1.16).

  port_names.py SRC_IMG DST_IMG NAMES_TSV OUT_TSV

Pass 1 (bytes): the leading code of every named SRC function (up to the first
RET, at most WINDOW bytes, grown to MAX_WINDOW while ambiguous) becomes a
pattern in which build-dependent fields are wildcards: the imm32 of
`LDI:32 #imm,Ri`, the imm20 of `LDI:20`, and the displacement of `CALL rel11`.
A unique hit in DST is accepted.

Pass 2 (delta): code moves by a nearly constant amount within a region, so each
unresolved name gets a predicted DST address from the nearest pass-1 matches
(by SRC address).  Among multiple byte hits the one within DELTA_TOL of the
prediction is taken if it beats the runner-up by NEAR_GAP (iterated, so new
matches become anchors); with no hits, the window around the prediction is scored
by the fraction of identical non-wildcard halfwords and the best spot is taken
if it scores at least MIN_SCORE.

Cross-check: every `LDI:32` in a matched SRC function that points at another
named function must hold the matched DST address of that name in DST.

Output columns: dst_addr, name, src_addr, method, window, ptr_check (ok/total).
"""
import bisect
import re
import struct
import sys

BASE = 0x10000000
WINDOW = 48
MAX_WINDOW = 192
DELTA_TOL = 0x400
NEAR_GAP = 0x20
SCAN = 0x800
MIN_SCORE = 0.85


def _rel11(w):
    r = w & 0x7FF
    return r - 0x800 if r & 0x400 else r


def tokens(d, off, size):
    """Split SRC code into (bytes, is_wild, kind, value) tokens until RET."""
    out, i = [], 0
    while i < size:
        w = struct.unpack_from(">H", d, off + i)[0]
        if (w & 0xFFF0) == 0x9F80:                      # LDI:32 #imm32,Ri
            out.append((d[off + i:off + i + 2], False, None, None))
            out.append((d[off + i + 2:off + i + 6], True, "imm32", struct.unpack_from(">I", d, off + i + 2)[0]))
            i += 6
            continue
        if (w & 0xFF00) == 0x9B00:                      # LDI:20 #imm20,Ri
            out.append((d[off + i:off + i + 4], True, "imm20", None))
            i += 4
            continue
        if (w & 0xF000) == 0xD000:                      # CALL / CALL:D rel11
            out.append((d[off + i:off + i + 2], True, "call", off + i + 2 + 2 * _rel11(w)))
            i += 2
            continue
        out.append((d[off + i:off + i + 2], False, None, None))
        i += 2
        if w in (0x9720, 0x9F20):                       # RET / RET:D (+ delay slot)
            if w == 0x9F20:
                out.append((d[off + i:off + i + 2], False, None, None))
                i += 2
            break
    return out, i


def regex(toks):
    parts = []
    for b, wild, kind, _ in toks:
        if not wild:
            parts.append(re.escape(b))
        elif kind == "call":
            parts.append(b"[\xd8-\xdf]." if b[0] & 0x08 else b"[\xd0-\xd7].")
        elif kind == "imm20":
            parts.append(re.escape(b[:1]) + b"...")
        else:
            parts.append(b"....")
    return b"".join(parts)


def score(toks, d, at):
    same = total = 0
    o = at
    for b, wild, _, _ in toks:
        if not wild:
            for k in range(0, len(b), 2):
                total += 1
                same += d[o + k:o + k + 2] == b[k:k + 2]
        o += len(b)
    return same / total if total else 0.0


def find_all(rx, d):
    return [m.start() for m in re.finditer(rx, d, re.S) if m.start() % 2 == 0]


def main(src_path, dst_path, names_path, out_path):
    src = open(src_path, "rb").read()
    dst = open(dst_path, "rb").read()
    names = []
    for line in open(names_path):
        line = line.strip()
        if line and not line.startswith("#"):
            a, n = line.split("\t")[:2]
            names.append((int(a, 16), n))

    found, method, cand, toks_of = {}, {}, {}, {}
    for addr, name in names:
        off = addr - BASE
        size = WINDOW
        while True:
            toks, used = tokens(src, off, size)
            hits = find_all(regex(toks), dst)
            if len(hits) <= 1 or used < size or size >= MAX_WINDOW:
                break
            size *= 2
        toks_of[name] = (toks, used)
        cand[name] = hits
        if len(hits) == 1:
            found[name] = hits[0] + BASE
            method[name] = "bytes"

    def predict(addr):
        anchors = sorted((a, found[n] - a) for a, n in names if n in found)
        keys = [a for a, _ in anchors]
        i = bisect.bisect_left(keys, addr)
        near = [anchors[j] for j in (i - 1, i) if 0 <= j < len(anchors)]
        a, delta = min(near, key=lambda t: abs(t[0] - addr))
        return addr + delta

    changed = True
    while changed and found:
        changed = False
        for addr, name in names:
            if name in found or not cand[name]:
                continue
            p = predict(addr)
            hits = sorted((abs(h + BASE - p), h + BASE) for h in cand[name])
            hits = [h for h in hits if h[0] <= DELTA_TOL]
            if hits and (len(hits) == 1 or hits[0][0] == 0 or hits[1][0] - hits[0][0] > NEAR_GAP):
                found[name], method[name] = hits[0][1], "bytes+delta"
                changed = True

    for addr, name in names:
        if name in found:
            continue
        p = predict(addr)
        if cand[name]:
            method[name] = f"ambiguous({len(cand[name])})"
            continue
        toks, used = toks_of[name]
        lo = max(0, p - BASE - SCAN) & ~1
        hi = min(len(dst) - used, p - BASE + SCAN)
        best = max(range(lo, hi, 2), key=lambda o: score(toks, dst, o))
        s = score(toks, dst, best)
        if s >= MIN_SCORE:
            found[name], method[name] = best + BASE, f"delta+score{s:.2f}"
        else:
            method[name] = f"none(best {s:.2f})"

    by_src = {a: n for a, n in names}
    rows, tally = [], [0, 0]
    for addr, name in names:
        toks, used = toks_of[name]
        ok = tot = 0
        if name in found:
            o = found[name] - BASE
            for b, wild, kind, val in toks:
                if kind == "imm32" and by_src.get(val) in found:
                    tot += 1
                    ok += struct.unpack_from(">I", dst, o)[0] == found[by_src[val]]
                o += len(b)
            tally[0] += ok
            tally[1] += tot
        dst_addr = f"{found[name]:08x}" if name in found else "-"
        rows.append(f"{dst_addr}\t{name}\t{addr:08x}\t{method.get(name, '-')}\t{used}\t{ok}/{tot}")

    with open(out_path, "w") as f:
        f.write("# dst_addr\tname\tsrc_addr\tmethod\twindow\tptr_check\n")
        f.write("\n".join(rows) + "\n")
    counts = {}
    for n in found:
        counts[method[n].split("score")[0]] = counts.get(method[n].split("score")[0], 0) + 1
    print(f"matched {len(found)}/{len(names)} {counts}; pointer cross-check {tally[0]}/{tally[1]}")
    for r in rows:
        if r.startswith("-"):
            print("  unmatched:", r.split("\t")[1], r.split("\t")[3])


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])

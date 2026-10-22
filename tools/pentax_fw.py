#!/usr/bin/env python3
"""Decode / encode the K-5 IIs firmware container (fwdc218b.bin, 0xAC0000 bytes).

Same XOR scheme as pfwtool (big-endian variant, "Copyright" at 0x24), extended
with the third section that pfwtool leaves encrypted:

  section  range                 IV at       contents
  main     [0x000100, 0xA00000)  0x000000    FR80 main firmware (maps to 0x10000000)
  sec2     [0xA00100, 0xA80000)  0xA00000    secondary image
  sub      [0xA80000, 0xABFF80)  0xABFF80    ARM Cortex-M sub-CPU firmware (little-endian)

The XOR is symmetric and every IV lies outside the range it protects, so
encode == decode.

  pentax_fw.py decode IN OUT
  pentax_fw.py encode IN OUT
  pentax_fw.py selftest IN        # decode->encode must reproduce IN byte for byte
  pentax_fw.py extract-sub IN OUT # write the decoded sub-CPU image
  pentax_fw.py checksum IN        # model markers + word sums (IN may be encoded or decoded)
  pentax_fw.py fix IN OUT [--section main|sub] [--at OFFSET]
                                  # rewrite one word so the section sums to 0 again;
                                  # OUT keeps the encoding of IN

Integrity (notes/firmware-checksum.md): the decoded main section [0, 0xA00000) and
the decoded sub section [0xA80000, 0xAC0000) each sum to 0 as big-endian 32-bit
words; sec2 has no simple sum. The updater checks the model markers
(model * 0x10001, 0xA55A5AA5) listed in MARKERS.
"""
import hashlib
import struct
import sys

M = 0xFFFFFFFF
SIZE = 0xAC0000
SECTIONS = [
    # (iv_offset, start, end)
    (0x000000, 0x000100, 0xA00000),
    (0xA00000, 0xA00100, 0xA80000),
    (0xABFF80, 0xA80000, 0xABFF80),
]
# 0xA80000-byte containers (K-5 fwdc209b, and the short FWDC218B the updater accepts)
# carry no sub-CPU section.
LAYOUTS = {SIZE: SECTIONS, 0xA80000: SECTIONS[:2]}

# Updater tables 0x107817E0 / 0x107817F8 (offsets stored as halfword indices):
# section -> (model-code word, marker offsets checked by FUN_104B4EAE).
MARKERS = {
    "main": (0x000010, [0x1F8, 0xFFFF0, 0x7FFFF8, 0x800008, 0x9FFFF8]),
    "sec2": (0xA00060, [0xA00070, 0xA77FF8, 0xA7FBF0]),
    "sub": (0xA80110, [0xA80100, 0xABFFF0]),
}
MARKER_TAG = 0xA55A5AA5
# section -> (start, end, default compensation word). The sub image ships its
# compensation in the last word; for main the word just before the 0x9FFFF0
# trailer sits in a 0x1A0B0-byte 0xFF padding run.
SUMS = {
    "main": (0x000000, 0xA00000, 0x9FFFEC),
    "sub": (0xA80000, 0xAC0000, 0xABFFFC),
}


def _key(iv):
    t0 = (iv[0] + (~iv[2] & M)) & M
    t1 = (iv[1] + (~iv[3] & M)) & M
    tmp = [t0, t1, ~t0 & M, ~t1 & M]
    k = [0] * 32
    for i in range(4):
        for j in range(4):
            k[i + 8 * j] = (tmp[i] + iv[j] - 1) & M
            k[i + 8 * j + 4] = (tmp[i] - iv[j] - 1) & M
    return k


def _section_base(iv_off, start):
    # pfwtool computes block offsets relative to the section base (the 1 MiB-aligned
    # region holding the IV) for the first two sections, and relative to the range
    # start for the trailing sub-CPU section.
    return start if iv_off > start else iv_off


def transform(data):
    if len(data) not in LAYOUTS or data[0x24:0x2D] != b"Copyright":
        raise SystemExit("unexpected container (size %#x)" % len(data))
    out = bytearray(data)
    for iv_off, start, end in LAYOUTS[len(data)]:
        k = _key(struct.unpack(">4I", data[iv_off:iv_off + 16]))
        base = _section_base(iv_off, start)
        rel0 = start - base
        for blk in range((end - start) // 0x80):
            rel = rel0 + blk * 0x80
            for i in range(32):
                o = base + rel + 4 * i
                v = struct.unpack_from(">I", out, o)[0] ^ ((k[i] - rel) & M)
                struct.pack_into(">I", out, o, v)
    return bytes(out)


def is_decoded(data):
    model_off, offs = MARKERS["main"]
    model = struct.unpack_from(">I", data, model_off)[0]
    return struct.unpack_from(">2I", data, offs[0]) == ((model * 0x10001) & M, MARKER_TAG)


def word_sum(data, start, end):
    return sum(struct.unpack_from(">%dI" % ((end - start) // 4), data, start)) & M


def check_markers(data, name):
    model_off, offs = MARKERS[name]
    model = struct.unpack_from(">I", data, model_off)[0]
    want = ((model * 0x10001) & M, MARKER_TAG)
    return model, [(o, struct.unpack_from(">2I", data, o) == want) for o in offs]


def sections_present(data):
    return [n for n in ("main", "sec2", "sub") if n != "sub" or len(data) == SIZE]


def cmd_checksum(data):
    dec = data if is_decoded(data) else transform(data)
    print("input:", "decoded" if dec is data else "encoded", "size %#x" % len(data))
    ok = True
    for name in sections_present(dec):
        model, res = check_markers(dec, name)
        bad = [hex(o) for o, good in res if not good]
        ok &= not bad
        print("  markers %-4s model %d: %s" % (name, model, "ok" if not bad else "BAD at " + ", ".join(bad)))
    for name, (start, end, _) in SUMS.items():
        if end > len(dec):
            continue
        s = word_sum(dec, start, end)
        ok &= s == 0
        print("  sum     %-4s [%#08x, %#08x): %#010x %s" % (name, start, end, s, "ok" if s == 0 else "BAD"))
    return ok


def cmd_fix(data, out, section, at):
    encoded = not is_decoded(data)
    dec = bytearray(transform(data) if encoded else data)
    start, end, default = SUMS[section]
    at = default if at is None else at
    if at % 4 or not start <= at < end:
        raise SystemExit("offset %#x is not a word inside %s" % (at, section))
    for name in sections_present(dec):
        for o in MARKERS[name][1]:
            if o <= at < o + 8:
                raise SystemExit("offset %#x overlaps a model marker" % at)
    old = struct.unpack_from(">I", dec, at)[0]
    struct.pack_into(">I", dec, at, (old - word_sum(dec, start, end)) & M)
    new = struct.unpack_from(">I", dec, at)[0]
    assert word_sum(dec, start, end) == 0
    open(out, "wb").write(transform(bytes(dec)) if encoded else bytes(dec))
    print("%s: word %#x %#010x -> %#010x, wrote %s output" % (
        section, at, old, new, "encoded" if encoded else "decoded"))


def main():
    cmd, src, *rest = sys.argv[1:]
    if cmd == "fix":
        out, opts = rest[0], rest[1:]
        section = opts[opts.index("--section") + 1] if "--section" in opts else "main"
        at = int(opts[opts.index("--at") + 1], 0) if "--at" in opts else None
        cmd_fix(open(src, "rb").read(), out, section, at)
        return
    if cmd == "checksum":
        sys.exit(0 if cmd_checksum(open(src, "rb").read()) else 1)
    data = open(src, "rb").read()
    if cmd in ("decode", "encode"):
        open(rest[0], "wb").write(transform(data))
    elif cmd == "selftest":
        dec = transform(data)
        enc = transform(dec)
        print("decoded sha256:", hashlib.sha256(dec).hexdigest())
        print("roundtrip identical:", enc == data)
        sys.exit(0 if enc == data else 1)
    elif cmd == "extract-sub":
        open(rest[0], "wb").write(transform(data)[0xA80000:0xAC0000])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()

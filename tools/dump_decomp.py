#!/usr/bin/env python3
"""Regenerate the raw decompiler dumps under notes/dec_*.c.

These dumps are derived from Ricoh's copyrighted firmware, so they are kept
out of git. Rebuild them locally after `firmware_setup.py import` and with the
GhidraMCP server running (tools/ghidra-mcp-headless.sh).

  dump_decomp.py            # all files below
  dump_decomp.py sysparam   # one file
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gh  # noqa: E402

NOTES = pathlib.Path(__file__).resolve().parent.parent / "notes"

DUMPS = {
    "1060f700": ["0x1060f700"],
    "1060f950": ["0x1060f950"],
    "1061000e": ["0x1061000e"],
    "autorun": ["0x10609d18", "0x10609d4a", "0x10609d56", "0x10609da4",
                "0x10609e4c", "0x10609f06", "0x10609f9a", "0x1060a064"],
    "autorun_users": ["0x1060925a", "0x1060940e", "0x106097e8"],
    "switch_test": ["0x10614978"],
    "sysparam": ["0x104a5ed2"],
}


def decompile(addr):
    out = json.loads(gh.get("force_decompile", function=addr))
    return out.get("decompiled", str(out))


def main():
    names = sys.argv[1:] or list(DUMPS)
    for name in names:
        addrs = DUMPS[name]
        parts = [decompile(a) if len(addrs) == 1 else f"######## {a}\n{decompile(a)}" for a in addrs]
        path = NOTES / f"dec_{name}.c"
        path.write_text("\n".join(parts))
        print(f"wrote {path.relative_to(NOTES.parent)}")


if __name__ == "__main__":
    main()

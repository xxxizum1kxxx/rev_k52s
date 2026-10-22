#!/usr/bin/env python3
"""Thin CLI over the GhidraMCP HTTP API (127.0.0.1:8089).

  gh.py dec <func-addr>              decompile
  gh.py xto <addr>                   xrefs to
  gh.py xfrom <addr>                 xrefs from
  gh.py str <substring>              search strings
  gh.py mem <addr> <len>             read memory
  gh.py lst <addr> [n]               listing of n code units (needs GHIDRA_MCP_ALLOW_SCRIPTS=1)
  gh.py get <endpoint> k=v ...       raw GET
  gh.py post <endpoint> k=v ...      raw POST (JSON body)
"""
import json
import sys
import urllib.parse
import urllib.request

URL = "http://127.0.0.1:8089"


def get(ep, **kw):
    q = urllib.parse.urlencode({k: v for k, v in kw.items() if v is not None})
    with urllib.request.urlopen(f"{URL}/{ep}?{q}", timeout=600) as r:
        return r.read().decode()


def post(ep, **kw):
    req = urllib.request.Request(f"{URL}/{ep}", data=json.dumps(kw).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read().decode()


LISTING_JAVA = """
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
public class McpListing extends GhidraScript {
  public void run() throws Exception {
    long a = Long.parseUnsignedLong("%s", 16); int n = %d;
    var cu = currentProgram.getListing().getCodeUnitAt(toAddr(a));
    var it = currentProgram.getListing().getCodeUnits(toAddr(a), true);
    for (int i = 0; i < n && it.hasNext(); i++) {
      CodeUnit c = it.next();
      Function f = getFunctionAt(c.getAddress());
      if (f != null) println("---- " + f.getName());
      String lbl = c.getLabel();
      println(c.getAddress() + "  " + (lbl != null ? lbl + ": " : "") + c.toString());
    }
  }
}
"""


def listing(addr, n):
    a = addr.lower().removeprefix("0x")
    out = json.loads(post("run_script_inline", code=LISTING_JAVA % (a, n)))
    text = out.get("console_output", str(out))
    return text.split("--- SCRIPT OUTPUT ---\n", 1)[-1].split("\n\n=== SCRIPT", 1)[0]


def _kv(args):
    return dict(a.split("=", 1) for a in args)


def main():
    cmd, *a = sys.argv[1:]
    if cmd == "dec":
        out = json.loads(get("force_decompile", function=a[0]))
        print(out.get("decompiled", out))
    elif cmd == "xto":
        print(get("get_xrefs_to", address=a[0], limit=a[1] if len(a) > 1 else 200))
    elif cmd == "xfrom":
        print(get("get_xrefs_from", address=a[0], limit=200))
    elif cmd == "str":
        print(get("search_strings", search_term=a[0], limit=a[1] if len(a) > 1 else 200))
    elif cmd == "mem":
        print(get("read_memory", address=a[0], length=a[1]))
    elif cmd == "lst":
        print(listing(a[0], int(a[1]) if len(a) > 1 else 40))
    elif cmd == "get":
        print(get(a[0], **_kv(a[1:])))
    elif cmd == "post":
        print(post(a[0], **_kv(a[1:])))


if __name__ == "__main__":
    main()

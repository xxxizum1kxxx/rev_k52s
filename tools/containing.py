#!/usr/bin/env python3
"""Print the function containing each address (GhidraMCP, needs GHIDRA_MCP_ALLOW_SCRIPTS=1).

  containing.py ADDR... [--create]

With --create, an address outside any function gets a function created at the
nearest preceding FR prologue (ST RP,@-R15 / ENTER / STM1) within 0x2000 bytes.
"""
import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import gh  # noqa: E402

JAVA = """
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
public class McpContaining extends GhidraScript {
  public void run() throws Exception {
    boolean create = %s;
    for (String s : "%s".split(",")) {
      var a = toAddr(Long.parseUnsignedLong(s, 16));
      Function f = getFunctionContaining(a);
      if (f == null && create) {
        for (long back = 0; back < 0x2000 && f == null; back += 2) {
          var p = a.subtract(back);
          if (getFunctionContaining(p) != null) break;
          int b0 = getByte(p) & 0xff, b1 = getByte(p.add(1)) & 0xff;
          if ((b0 == 0x17 && b1 == 0x81) || b0 == 0x0f || b0 == 0x8f) {
            disassemble(p);
            f = createFunction(p, null);
          }
        }
      }
      println(s + "\\t" + (f == null ? "-" : f.getEntryPoint() + "\\t" + f.getName()));
    }
  }
}
"""


def containing(addrs, create=False):
    hexes = ",".join(a.lower().removeprefix("0x") for a in addrs)
    out = json.loads(gh.post("run_script_inline", code=JAVA % ("true" if create else "false", hexes)))
    text = out.get("console_output", str(out))
    text = text.split("--- SCRIPT OUTPUT ---\n", 1)[-1].split("\n\n=== SCRIPT", 1)[0]
    rows = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append(parts)
    return rows


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--create"]
    for r in containing(args, "--create" in sys.argv):
        print("\t".join(r))

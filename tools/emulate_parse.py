#!/usr/bin/env python3
"""Run the firmware's own ScriptMode_parse_command (0x1060F950) under Ghidra's
P-code emulator for each token and report which cmd[] slot it sets.

  emulate_parse.py "DEBUG_MODE EN" "SW_DEBUG_MENU EN" ...
  emulate_parse.py --all        # every command string in the firmware table

Requires the GhidraMCP headless server with GHIDRA_MCP_ALLOW_SCRIPTS=1.
"""
import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import gh  # noqa: E402

PARSE = 0x1060F950
CMD_LEN = 0x30

ALL_COMMANDS = [
    "DEBUG_MODE EN", "DEBUG_MODE DIS", "CFDOOR_OPEN EN", "CFDOOR_OPEN DIS",
    "WRITE_CF_VNDR EN", "WRITE_CF_VNDR DIS", "SCRIPT_EN_MODE EN", "SCRIPT_EN_MODE DIS",
    "USR_DAT_CLEAR", "SWITCH_TEST", "DISPLAY_TEST", "MEMORY_TEST", "RELEASE_AGING",
    "LENS_COMUNICATION_CHECK", "CPU_ADJ_FLG_CLEAR", "CPU_ADJ_CSV_WRITE", "CPU_TST_CSV_WRITE",
    "CPU_ADJ_CSV_READ", "CPU_TST_CSV_READ", "CPU_ROM_STORE", "DSP_ROM_STORE", "AF_PINT_DISP",
    "ICCD_PINT_OFF_CLEAR", "COLOR_PINT_COR_CLEAR", "SI_ALL_ON", "CPU_ADJ_DAT_READ",
    "CPU_ADJ_DAT_WRITE", "DSP_ADJ_DAT_READ", "DSP_ADJ_DAT_WRITE", "ALL_ADJ_DAT_READ",
    "DSP_USR_DAT_READ", "DSP_USR_DAT_WRITE", "SR_BULB", "DIS_AF_F28", "ONLY_AF_F28",
    "VLENS_CTRL", "LENS_CPU_FIRMUP", "LENSROM_LOAD", "LENSROM_STORE", "OPEN_DEBUG_MENU",
    "SW_DEBUG_MENU EN", "SW_DEBUG_MENU DIS", "REGION_CODE 0", "REGION_CODE 1",
    "REGION_CODE 2", "REGION_CODE 3", "REGION_CODE 4", "REGION_CODE 5", "DISP_REGION_CODE",
    "CAM_LOG_DAT_READ", "CAM_LOG_DISP", "USR_CLEAR_CAM_DISP", "CRE_RECOVERY_FW", "G200_TEST",
    "LIVE_VIEW_TEST_MODE EN", "LIVE_VIEW_TEST_MODE DIS",
    # negative cases
    "debug_mode en", "DEBUG_MODE  EN", "DEBUG_MODE EN ", "",
]

JAVA = r"""
import ghidra.app.script.GhidraScript;
import ghidra.app.emulator.EmulatorHelper;
import ghidra.program.model.address.Address;
import java.math.BigInteger;
public class McpEmuParse extends GhidraScript {
  public void run() throws Exception {
    String[] toks = new String[] { %TOKENS% };
    long TOK = 0xC0F00000L, OUT = 0xC0F01000L, STK = 0xC0F80000L, RET = 0x10ABFFF0L;
    for (String t : toks) {
      EmulatorHelper emu = new EmulatorHelper(currentProgram);
      try {
        byte[] tb = (t + "\0").getBytes("ASCII");
        emu.writeMemory(toAddr(TOK), tb);
        byte[] out = new byte[%LEN%];
        out[0x25] = (byte)0xFF;
        emu.writeMemory(toAddr(OUT), out);
        emu.writeRegister("R4", BigInteger.valueOf(0xC0F02000L));
        emu.writeRegister("R5", BigInteger.valueOf(TOK));
        emu.writeRegister("R6", BigInteger.valueOf(OUT));
        emu.writeRegister("SP", BigInteger.valueOf(STK));
        emu.writeRegister("RP", BigInteger.valueOf(RET));
        emu.writeRegister(emu.getPCRegister(), BigInteger.valueOf(%PARSE%L));
        emu.setBreakpoint(toAddr(RET));
        boolean ok = emu.run(toAddr(%PARSE%L), null, monitor);
        long pc = emu.readRegister(emu.getPCRegister()).longValue();
        long r4 = emu.readRegister("R4").longValue();
        byte[] res = emu.readMemory(toAddr(OUT), %LEN%);
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < res.length; i++) {
          int v = res[i] & 0xff;
          if ((i == 0x25 && v != 0xff) || (i != 0x25 && v != 0)) sb.append(String.format("%02X=%02X ", i, v));
        }
        println("EMU|" + t + "|" + String.format("%08X", pc) + "|" + r4 + "|" + sb.toString().trim()
                + "|" + (emu.getLastError() == null ? "" : emu.getLastError()));
      } finally { emu.dispose(); }
    }
  }
}
"""


def emulate(tokens):
    lit = ", ".join(json.dumps(t) for t in tokens)
    code = (JAVA.replace("%TOKENS%", lit).replace("%LEN%", str(CMD_LEN))
            .replace("%PARSE%", str(PARSE)))
    out = json.loads(gh.post("run_script_inline", code=code))
    text = out.get("console_output", str(out))
    rows = []
    for line in text.splitlines():
        if "EMU|" in line:
            tok, pc, ret, slots, err = line.split("EMU|", 1)[1].split("|", 4)
            rows.append({"token": tok, "pc": pc, "ret": int(ret), "slots": slots, "err": err})
    if not rows:
        raise RuntimeError(text[-3000:])
    return rows


def main():
    toks = ALL_COMMANDS if sys.argv[1:] == ["--all"] else sys.argv[1:]
    for r in emulate(toks):
        status = "OK " if r["pc"] == "10ABFFF0" and not r["err"] else "ERR"
        print(f"{status} ret={r['ret']} {r['token']!r:32} -> {r['slots'] or '-'} {r['err']}")


if __name__ == "__main__":
    main()

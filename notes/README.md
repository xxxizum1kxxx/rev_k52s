English | [简体中文](README.zh-CN.md)

# PENTAX K-5 IIs firmware 1.07 analysis notes

## Samples

The firmware itself is **not** in this repository. Obtain it from Ricoh and prepare `fw/` with `tools/firmware_setup.py` (see the top-level README). The tool checks these hashes:

| File | SHA-256 |
| --- | --- |
| `k5_2s107.zip` (official download) | `c2352d91669c8dce47fe84298baa47dedaa438b156a834a8a8a130f84e14db1f` |
| `fw/fwdc218b.bin` (original, obfuscated) | `36b626a9ecd02e22161a1f3ef4e764f7641c2565bb82c866977aeb9eaad5ac97` |
| `fw/fwdc218b_dec.bin` (pfwtool-compatible decode) | `8379b15c058dfa6cb597ef159b3920c50722c033c7e83a0e8a55a46a91ffecd1` |

The container is 0xAC0000 bytes, with header `HOKKTKIYHTNTMU` and `Copyright` at 0x24, which selects pfwtool's big-endian branch.
- `[0x100, 0xA00000)` and `[0xA00100, 0xA80000)` are de-obfuscated with their IVs.
- The trailing section from `0xA80000` is the ARM sub-CPU image, decoded by `tools/pentax_fw.py`; see [memory-map.md](memory-map.md).

## Loading

- Language `fr81:BE:16:default`, compiler spec `fcc911` (FR81 = FR80 + FPU superset).
- Base: **file offset 0 maps to 0x10000000** (the whole image is mapped linearly).
  - Evidence 1: there are 128,493 sites of `LDI:32 #imm,Ri` followed by `CALL @Ri`. After subtracting 0x10000000, 99,755 of the targets (78%) land exactly on FR function prologues (`ST RP,@-R15` / `ENTER` / `STM1`). No other candidate base exceeds 20%.
  - Evidence 2: string references make sense, e.g. `0x10245F6A` references `"DEBUG MODE"` (0x10710AD8).
  - Candidates 0x0F87A000 / 0x0F86D000 score high but are false hits: those immediates really point to 0x102xxxxx functions and just happen to fall into the string-dense area around file offset 0x97xxxx.
- Rough layout by file offset:
  - `0x000000`: header
  - `0x100000–0x1FFFFF`: tables and data, mixed with what looks like compressed data
  - `0x200000–0x6FFFFF`: main code
  - `0x700000+`: strings and resources
- Peripherals and IO: the code is full of `0xFFFxxxxx` and `0xC000xxxx` addresses.
  - For example, `_DAT_c000468c` is a 0/1/2 mode value selecting the `DEBUG MODE` vs `PC VENDOR` label; it is not the debug flag, see section 5 of [debug-mode-consumers.md](debug-mode-consumers.md).

## Ghidra analysis (`notes/ghidra_report.txt`)

- 9514 seed functions (`tools/gen_seeds.py` → `notes/seed_functions.txt`). After auto-analysis: 33,927 functions and 1,537,956 instructions.
- 2,381 decode failures, of which 2,363 are in the 0x101xxxxx data area (data mistaken for code). The main code area 0x10200000–0x106FFFFF has only 2.
  **Conclusion: the existing FR81 SLEIGH covers FR80 code fully; no instructions need to be added for now.**
- Decompilation works, e.g.:
  - `FUN_10245f40`: `ui_show_debug_mode_label`, shows `"DEBUG MODE"` when `_DAT_c000468c` is 0, otherwise `"PC VENDOR"`
  - `FUN_1060f57a`: builds the debug script file name from `C:\%08d.%03d`

## Documents

- [memory-map.md](memory-map.md): container layout, address spaces, system flags
- [sd-file-entrypoints.md](sd-file-entrypoints.md): every SD-card entry file
- [debug-script.md](debug-script.md): factory script file name, entry conditions, command table, execution semantics
- `emulate_parse_all.txt`: P-code emulation results
- [../docs/debug-mode-guide.md](../docs/debug-mode-guide.md): user guide and hardware test log
- [debug-mode-consumers.md](debug-mode-consumers.md): every DEBUG_MODE read, the TEST MODE menu page, the in-menu exit
- [firmware-checksum.md](firmware-checksum.md): updater model-marker check, zero word-sum rule, `pentax_fw.py checksum/fix`
- [k5-vs-k5iis.md](k5-vs-k5iis.md): comparison with K-5 1.16 and function-name porting (`tools/port_names.py`)
- [fremulator-eval.md](fremulator-eval.md), `fremulator_parse_all.txt`: running `parse_command` on Nikon FrEmulator (`tools/fremu/`)
- Tools:
  - Card files and emulation: `tools/make_debug_card.py`, `tools/emulate_parse.py`
  - Firmware handling: `tools/firmware_setup.py`, `tools/pentax_fw.py`
  - Analysis helpers: `tools/port_names.py`, `tools/containing.py`, `tools/dump_decomp.py`
  - FrEmulator build: `tools/fremu/build.sh`

Raw decompiler output (`notes/dec_*.c`) is derived from the copyrighted firmware and is not committed. Regenerate it locally with `tools/dump_decomp.py`.

## Open leads

- `C:\%08d.bin` (0x1078F4CC), `C:\%08d.jpg` (0x1078F4D8).
- The AUTORUN interpreter's camera-command table (see [fremulator-eval.md](fremulator-eval.md) section 5).

## Environment

- Ghidra 12.1.4 with the `ghidra-fr60` extension (FR60 and FR81) and `GhidraMCP` 7.0.0, built from source for 12.1.4.
- The GhidraMCP source (`tools/ghidra-mcp`, tag v7.0.0-rc.3) has one local change in `build.gradle`: the Java 21 toolchain is replaced by `options.release = 21` so it builds with JDK 25. Keep that change when rebuilding.
- Ghidra project: `ghidra/K5IIs.gpr`, program `fwdc218b_dec.bin`. The project embeds firmware bytes and is git-ignored.
- AI integration (`.cursor/mcp.json` → `bridge-mcp-ghidra` → `127.0.0.1:8089`). Use one of:
  - Headless: `tools/ghidra-mcp-headless.sh`
  - GUI: run `ghidraRun`, open the project, enable GhidraMCPPlugin under `File > Configure > Utility`
  - The two cannot open the same project at once (project lock).
- Re-import and analyse (about 30 minutes):

```sh
GHIDRA_HEADLESS_MAXMEM=8G $GHIDRA_HOME/support/analyzeHeadless ghidra K5IIs \
  -import fw/fwdc218b_dec.bin -overwrite -loader BinaryLoader -loader-baseAddr 0x10000000 \
  -processor fr81:BE:16:default -cspec fcc911 -scriptPath tools/ghidra_scripts \
  -preScript SeedFunctions.java notes/seed_functions.txt \
  -postScript ReportStats.java notes/ghidra_report.txt -analysisTimeoutPerFile 7200
```

English | [简体中文](k5-vs-k5iis.zh-CN.md)

# K-5 1.16 vs K-5 IIs 1.07

The K-5 (2010) is the predecessor of the K-5 IIs (2013). Comparing their firmware has two purposes: cross-checking this project's function names, and confirming whether the factory-script mechanism is the same across both generations.

## Samples

| Item | K-5 1.16 | K-5 IIs 1.07 |
| --- | --- | --- |
| Source | Official Ricoh download `k5_v116m.zip` (`fwdc209b.bin`); the analysed copy came from [twang2218/pentax-firmware](https://github.com/twang2218/pentax-firmware) `k5/k5-v1.16-fwdc209b.bin` and is checked by hash in `tools/firmware_setup.py` | Official `k5_2s107.zip` |
| File | `fw/k5-v116-fwdc209b.bin`, 0xA80000 bytes | `fw/fwdc218b.bin`, 0xAC0000 bytes |
| Decoded | `fw/k5-v116_dec.bin`, SHA-256 `e9dac980fa20a19a9a08a70c355fcdfe319b10789e8b51fb95cc2e370fcb91d8` | `fw/fwdc218b_full_dec.bin` |
| Header model code @0x10 | 505 (`0x1F9`) | 541 (`0x21D`) |
| Header script id @0x14 | 77430 | 77681 |
| Version BCD @0x18 | `01 10 1A 1D` | `01 07 18 10` |
| Sub-CPU section | None | `0xA80000–0xABFF7F` |

The K-5 container has only the first two sections; `tools/pentax_fw.py` picks the layout by file size (`LAYOUTS`), and `selftest` reproduces the original byte for byte. After decoding, command strings and paths are plain text, so the XOR scheme did not change between generations.

## Factory script

- **The K-5 script file name is `00077430.505`**, and it also needs `DEVELOP.MOD`. The format string `C:\%08d.%03d` and the XOR-0x29 constant copy of `DEVELOP.MOD` are both present (around K-5 `0x10799540`).
- The command table is nearly identical.
  - The K-5 IIs only adds `DIS_AF_F28` and `ONLY_AF_F28`, for its new F2.8 AF sensor.
  - The other 54 command strings, the `KB%03d*.ADJ/CSV/BIN/USR/LOG` file names and the `WAIT...`/`COMPLETE...`/`ERROR...` prompts are all the same.
- So `make_debug_card.py` would work for the K-5 with just the file name changed. The command-table indices must still be checked against the K-5's `ScriptMode_parse_command` (`0x1060B526`): with two commands missing, later slots may shift. This project has no K-5 body, so no K-5 card files are provided.

## Other SD-card entry points

- 54 path strings are shared: `AUTORUN.541/505` (built from the model code), `CHKDAT`, `SYSPARAM.TXT`, `NOWAIT`, `KBCHG.BIN` and others.
- Paths found in only one firmware:
  - K-5 IIs only: `FWDC218B/C/D/S.BIN`, `KB541[B/C/S].BIN`, `SR%04d.bin`.
  - K-5 only: `FWDC209B/C/D.BIN`, `KB505[B/C].BIN`.
  - The differences are just the model number, plus the K-5 IIs sub-CPU section (`S`).
- SYSPARAM keys: of the K-5 IIs's 96 keys, the K-5 lacks only `ENABLE_RELEASE_LAP_TIME_DISPLAY` and `ENABLE_SR_EVALUATION`. The first SYSPARAM experiment suggested in the guide does not exist on the K-5.
- UI strings such as `DEBUG MODE` and `DISABLE DEBUG MODE` exist in both.

## Firmware integrity markers

Both images have, at the same offsets, the marker `0x10001 × model code` followed by `A55A5AA5` (`0x01F901F9` on the K-5): `0x1F8`, `0xFFFF0`, `0x7FFFF8`, `0x800008`, `0x9FFFF8`, `0xA00070`, `0xA77FF8`, `0xA7FBF0`. The K-5 IIs has one more at `0xABFFF0`, the end of the sub-CPU section. See [firmware-checksum.md](firmware-checksum.md).

## Porting function names

Tool: `tools/port_names.py fw/fwdc218b_dec.bin fw/k5-v116_dec.bin tools/names.tsv notes/k5-v116-names.tsv`. Pure Python, no Ghidra needed.

- Pass 1 matches byte patterns, wildcarding `LDI:32`/`LDI:20` immediates and `CALL` relative offsets: 34 unique hits.
- Pass 2 exploits the fact that code within a region shifts as a block.
  - It predicts each position from the nearest matched function and resolves multiple hits (34).
  - For functions with no hit, it scores candidates near the predicted position by the fraction of identical halfwords (3 hits, scores 0.85–0.94).
- Total **71/75**. Cross-check: inside matched functions, the `LDI:32` immediates that point to other named functions point to the corresponding ported addresses in the K-5, **30/30 consistent**.
- The shift grows monotonically with address, from `0x1E8` around `0x101F55xx` to `0x603C` around `0x106Exxxx`, with no jumps. This further supports the matches.
- The 4 unmatched functions are `ScriptMode_load_script` (best 0.72), `fwup_load_image` (0.81), `SysParam_load` (0.67) and `SwitchTest_draw` (0.50).
  - They changed materially between generations; for example, the K-5 lacks the LAP_TIME key and its SWITCH TEST lacks the F2.8-related keys.
  - They need manual confirmation from their callers in Ghidra.

Selected addresses (K-5 1.16):

| Function | K-5 IIs 1.07 | K-5 1.16 |
| --- | --- | --- |
| `Boot_special_poweron` | `0x105E81D8` | `0x105E3DD2` |
| `ScriptMode_files_present` | `0x1060F57A` | `0x1060B154` |
| `ScriptMode_parse_command` | `0x1060F950` | `0x1060B526` |
| `ScriptMode_execute` | `0x1061000E` | `0x1060BBA4` |
| `SysFlags_set_debug_mode` | `0x10615F40` | `0x10611980` |
| `SysFlags_is_debug_mode` | `0x10615F70` | `0x106119B0` |
| `ui_show_debug_mode_label` | `0x10245F40` | `0x10245ACC` |
| `AutoTest_load_autorun` | `0x1060940E` | `0x10604FF0` |
| `fs_stat` | `0x106C1D86` | `0x106BD40C` |

The full list is in `notes/k5-v116-names.tsv`.

## Ghidra project

The K-5 lives in its own project, `ghidra/K5/K5v116.gpr`: program `k5-v116_dec.bin`, FR81 big-endian, base `0x10000000`.
- Seeds come from `tools/gen_seeds.py` (`notes/k5-v116-seeds.txt`).
- Statistics are in `notes/k5-v116-ghidra-report.txt`; the analysis log is kept locally only.
- It is not merged into `K5IIs.gpr`, to avoid fighting the running GhidraMCP server for the project lock.

Full analysis took 1719 seconds and was saved successfully. Statistics side by side:

| Metric | K-5 1.16 | K-5 IIs 1.07 |
| --- | --- | --- |
| Functions | 30457 | 33927 |
| Instructions | 1453481 | 1537956 |
| Error bookmarks | 1928 (1902 in the `0x10100000` region) | 2381 (2363 in the `0x10100000` region) |
| Top unresolved opcodes | `0793`×129, `9F6F`×67, `9F2B`×37, `07A1`×33 | `0793`×205, `9F6F`×69, `07A1`×48, `0798`×44 |

Both concentrate their errors in `0x10100000–0x101FFFFF`, with essentially the same unresolved opcodes (`07xx`, `9Fxx`, `BExx`, `17xx`). So this region holds the same kind of code or data in both bodies that the FR81 language module cannot decode; it is not specific to the K-5 IIs. The K-5 has about 94% of the K-5 IIs's code.

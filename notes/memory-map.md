English | [简体中文](memory-map.zh-CN.md)

# Memory map and basic APIs

## Firmware container layout (`fw/fwdc218b.bin`, 0xAC0000 bytes)

| File range | IV at | Contents | Decoded |
| --- | --- | --- | --- |
| `0x000000–0x0000FF` | - | Plain header: magic `HOKKTKIYHTNTMU`, model code 541 (`0x21D`) at 0x10, script id 77681 (`0x12F71`) at 0x14, version BCD `01 07 18 10` at 0x18, copyright and model strings, `69FDABE0` at 0xFC | - |
| `0x000100–0x9FFFFF` | 0x000000 | FR80 main firmware | Mapped at `0x10000000` |
| `0xA00100–0xA7FFFF` | 0xA00000 | Second section (called the C section in the updater, size 0x80000, written at offset 0x500000×2) | - |
| `0xA80000–0xABFF7F` | 0xABFF80 | **Sub-CPU firmware**: ARM Cortex-M, little-endian, Thumb | `fw/subcpu_arm.bin` |
| `0xABFF80–0xABFFFF` | - | IV of the third section | - |

`tools/pentax_fw.py` decodes and encodes the container (`decode` / `encode` / `selftest` / `extract-sub`).
- Decoding and re-encoding reproduces the original byte for byte (`selftest`: `roundtrip identical: True`).
- The first two sections decode identically to pfwtool.
- The full decoded image `fw/fwdc218b_full_dec.bin` has SHA-256 `a31b6c8e88fefc634280235a3540486475aa349927b93137f0cfdf287eb4f4d3`.

The sub-CPU firmware starts with a vector table: initial SP `0x200037B8`, reset vector `0x00000231` (Thumb).
- Its strings include `NBADC0-init.`, `MSHS:Lo in TxRx`, `DUST-0 end.`, `PH-OFF !!!` and `CPU-VER %d`, so it probably handles shake reduction (SR) and dust removal.
- To analyse it, import it into Ghidra as `ARM:LE:32:Cortex` at base 0. This has not been done yet.

The update loader (`fwup_load_image` @ `0x104B6A0E`) checks file sizes:

| File | Expected size |
| --- | --- |
| `FWDC218D.BIN` | 0xA00000 |
| `FWDC218C.BIN` | 0x80000 |
| `FWDC218B.BIN` | 0xA80000 or 0xAC0000 |

## Runtime address space (main CPU, FR80)

| Address | Ghidra block | Description | Evidence |
| --- | --- | --- | --- |
| `0x00000000–0x00000FFF` | `IO_LO` | FR internal IO registers; symbols defined by the plugin pspec | FR architecture convention |
| `0x10000000–0x10ABFFFF` | `ram` (image) | Code and read-only data; the header is read directly at runtime (`DAT_10000010/14`) | 78% of indirect call targets land on function prologues |
| `0xC0000000–0xC0FFFFFF` | `SDRAM_WORK` | Globals and singletons, e.g. `0xC006C090` (ScriptMode) and `0xC000468C` (0/1/2 mode value that picks the `DEBUG MODE`/`PC VENDOR` label; not the debug flag) | LDI:32 references cluster at 0xC000–0xC00F |
| `0xFFF00000–0xFFFFFFFF` | `IO_HI` | Peripheral registers; references cluster at 0xFFFFFxxx (6858 sites) | LDI:32 reference distribution |

## RTOS and base library

- The firmware does **not** use `INT #0x40` (the Fujitsu μITRON calling convention), so the plugin's `ResolveUTronSyscalls` does not apply. System services are plain function calls, for example `mutex_lock` / `mutex_unlock` (`0x101F5510` / `0x101F5524`).
- The code is C++-style: vtables are `{int16 this_adj, int16 0, fnptr}` and singletons are lazily created by `*_instance()`.
- Named functions (from `tools/names.tsv`, applied to the Ghidra project):
  - Memory and strings: `op_new`, `op_delete`, `sprintf`, `strcmp`
  - File system: `fs_stat`, `FileSystem_instance`
  - Keys: `key_is_pressed` and `key_lookup` (key code → byte index + mask, table at `0x1077C7B0`)
  - Firmware header: `fwhdr_get_model_code`, `fwhdr_get_script_id`
  - Boot flow: `Boot_*`
  - Script mode: `ScriptMode_*`
  - System flags: `SysFlags_*` / `flags_*`

## System flags (persistent)

All flags live in one settings object. `0x5AA5A55A` means on and `0xFFFFFFFF` means off. `SysFlags_commit` writes changes back to storage.

| Offset | Flag | Script command |
| --- | --- | --- |
| +0x04 | DEBUG_MODE | `[DEBUG_MODE EN/DIS]` |
| +0x08 | CFDOOR_OPEN | `[CFDOOR_OPEN EN/DIS]` |
| +0x0C | WRITE_CF_VNDR (presumed) | `[WRITE_CF_VNDR EN/DIS]` |
| +0x10 | SCRIPT_EN_MODE | `[SCRIPT_EN_MODE EN/DIS]` |
| +0x18 | SW_DEBUG_MENU | `[SW_DEBUG_MENU EN/DIS]` |

## Helper tools

| Tool | Purpose |
| --- | --- |
| `tools/gh.py` | Calls the GhidraMCP HTTP API: decompile, xrefs, strings, listings (`lst` needs `GHIDRA_MCP_ALLOW_SCRIPTS=1`) |
| `tools/mkfunc.py` | Walks back from any address to a function prologue and creates the function in Ghidra |
| `tools/callers.py` | Finds callers via 32-bit immediates and relative CALLs, compensating for missing Ghidra xrefs |

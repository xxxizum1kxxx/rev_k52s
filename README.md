English | [简体中文](README.zh-CN.md)

# PENTAX K-5 IIs firmware 1.07: factory debug mode research

> [!IMPORTANT]
> **AI-generated content.** Almost all of the analysis, tooling and documentation here was produced by AI coding agents (LLMs in Cursor driving Ghidra through GhidraMCP), under the direction of the repository owner.
> - Conclusions come from static analysis and emulation and **have not yet been verified on a real camera**. They may be wrong.
> - Read the code before running it, and treat every claim as a hypothesis until hardware tests confirm it.

> [!IMPORTANT]
> **No license.** This repository deliberately has no license file. All rights are reserved by the author.
> - Under GitHub's Terms of Service you may view and fork it on GitHub.
> - No other permission to use, copy, modify or redistribute the contents is granted.
> - Third-party projects referenced here keep their own licenses.

> [!WARNING]
> **No Ricoh / PENTAX firmware is included.** The repository contains none of:
> - the firmware images (`fwdc218b.bin` and the like), or decrypted or decompressed versions of them;
> - Ghidra projects built from them, or raw decompiler output;
> - ROM or calibration dumps.
>
> Those files are Ricoh's copyrighted property; Ricoh's download page says "転載禁止" (no redistribution).
> - What *is* here: original notes, address tables, short identifier strings quoted for interoperability, and tools that work on a firmware file **you download yourself** from Ricoh's official site.
> - See [Getting the firmware](#getting-the-firmware).
> - Do not commit or share firmware, decoded images or camera dumps (`KB541*.BIN`, `*.ADJ`, …).

> [!CAUTION]
> **Use at your own risk.** Factory modes can wipe calibration data, wear out the shutter or make the camera unusable.
> - This is an independent project, not affiliated with or endorsed by RICOH IMAGING COMPANY, LTD.
> - PENTAX and RICOH are trademarks of their respective owners.
> - Nothing here modifies firmware, but you alone are responsible for what you do to your camera.

## What this is

The K-5 IIs firmware (and, by comparison, the K-5 firmware) contains a factory script mode, inherited by much later Ricoh bodies such as the GR IV. It is driven by two files on the SD card:

- `00077681.541`: a text script with commands such as `[DEBUG_MODE EN]` or `[OPEN_DEBUG_MENU]`
- `DEVELOP.MOD`: a marker file

With the card door open at power-on, the camera runs the script. From there you can reach:

- the hidden **Development Menu 1–5**: switch test, shutter count, version info, calibration and ROM backup;
- a **TEST MODE** page in the normal menu;
- **`SYSPARAM.TXT`** image-pipeline debug switches;
- a BASIC-like **AUTORUN** test language.

Everything was found by static reverse engineering, and the script parser was checked by running the firmware's own code in two emulators. Hardware testing is the next step.

## Quick start (testers)

You need a K-5 IIs on firmware 1.07, a full battery, an SD card formatted in the camera, and Python 3.

1. Read [docs/debug-mode-guide.md](docs/debug-mode-guide.md) in full.
2. Copy the two files from `sdcard/devmenu/` to the root of the card. They are generated files, not firmware.
   - The other presets are under `sdcard/`, or can be generated with `python3 tools/make_debug_card.py write <card-root> --preset <name>`.
3. With the card door **open**, power on. The Development Menu should appear; leave with `[MENU]` without changing anything.
4. Fill in the test log in section 6 of the guide and report back. Report file sizes only; never send dump files.

No firmware download is needed for this; the card files are self-contained.

## Getting the firmware

Only needed to reproduce the analysis, run the emulators or regenerate the card files. Ricoh only allows owners of the camera to download it, after accepting its software license agreement.

1. Open Ricoh's official page and read the license agreement:
   - K-5 IIs 1.07: <https://www.ricoh-imaging.co.jp/english/support/digital/k-5_2_s.html> (Japanese: <https://www.ricoh-imaging.co.jp/japan/support/download/digital/k5_2_s.html>)
   - K-5 1.16 (comparison only): <https://www.ricoh-imaging.co.jp/english/support/digital/k-5_s.html>
   - `python3 tools/firmware_setup.py open` opens the K-5 IIs page in your browser.
2. Download `k5_2s107.zip` (Windows/Mac zip; for the K-5, `k5_v116m.zip`) yourself.
3. Let the helper verify, extract and decode it locally:

```bash
python3 tools/firmware_setup.py info                 # official URLs and expected SHA-256
python3 tools/firmware_setup.py import ~/Downloads/k5_2s107.zip
python3 tools/firmware_setup.py status
```

`import` checks the SHA-256 of the archive and of `fwdc218b.bin`, then writes these files to `fw/`, which is git-ignored:
- `fwdc218b.bin`
- `fwdc218b_dec.bin` (pfwtool-compatible)
- `fwdc218b_full_dec.bin`
- `subcpu_arm.bin`

Each output is verified against reference hashes, so your analysis lines up byte for byte with the addresses in `notes/`. The tool never downloads anything and never uploads anything.

To update the camera itself to 1.07, follow Ricoh's own procedure on that page: copy `fwdc218b.bin` to a formatted card and power on while holding MENU. Never flash files produced by this repository's tools.

## Repository layout

| Path | Contents |
| --- | --- |
| [docs/](docs/debug-mode-guide.md) | User guide and hardware test log |
| [notes/](notes/README.md) | Analysis notes: memory map, SD entry points, script command table, debug-mode consumers, integrity checks, K-5 comparison, emulator evaluation |
| `sdcard/` | Ready-made SD-card script presets (`devmenu`, `enable`, `disable`, `camlog`, `sysparam-laptime`) |
| `tools/firmware_setup.py` | Verify, extract and decode the official firmware you downloaded |
| `tools/make_debug_card.py` | Generate and check SD-card scripts (refuses dangerous commands by default) |
| `tools/pentax_fw.py` | Firmware container codec, self-test, integrity check/fix (offline use) |
| `tools/emulate_parse.py`, `tools/fremu/` | Run the firmware's script parser in Ghidra P-code emulation or Nikon FrEmulator |
| `tools/gh.py`, `mkfunc.py`, `callers.py`, `containing.py`, `port_names.py`, `dump_decomp.py`, `ghidra_scripts/` | Ghidra / GhidraMCP helpers |
| `tools/names.tsv`, `notes/*.tsv` | Address → name tables |

Every document exists in English (`*.md`, default) and Simplified Chinese (`*.zh-CN.md`).

## Analysis environment (optional)

Each of the following is cloned or installed separately and is not part of this repository:

- [Ghidra](https://github.com/NationalSecurityAgency/ghidra) 12.1.x
- [desrdev/ghidra-fr60](https://github.com/desrdev/ghidra-fr60): FR60/FR81 processor
- [bethington/ghidra-mcp](https://github.com/bethington/ghidra-mcp): GhidraMCP
- [twang2218/pentax-firmware-tool](https://github.com/twang2218/pentax-firmware-tool): pfwtool, reference decoder
- [simeonpilgrim/nikon-firmware-tools](https://github.com/simeonpilgrim/nikon-firmware-tools): FrEmulator

Setup details are in [notes/README.md](notes/README.md).

## Related work

- [radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion](https://github.com/radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion): the same factory-script mechanism on the GR IV / GR IIIx
- [i-am-shodan/PHDK](https://github.com/i-am-shodan/PHDK), [i-am-shodan/PentaxFirmwareTool](https://github.com/i-am-shodan/PentaxFirmwareTool): PENTAX K-30 firmware work

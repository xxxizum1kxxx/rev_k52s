English | [简体中文](debug-script.zh-CN.md)

# Factory debug script (K-5 IIs, firmware 1.07)

## 1. Required files (SD card root)

| File | Origin | Content |
| --- | --- | --- |
| `00077681.541` | `sprintf("C:\\%08d.%03d", hdr[0x14]=77681, hdr[0x10]=541)` | Command script (text) |
| `DEVELOP.MOD` | Name rebuilt on the stack byte by byte with XOR 0x29, so a plain-text grep will not find it | The K-5 IIs **only checks that it exists**. The tool writes the 10 bytes the GR series requires: `07 01 2C 1F 10 03 1E 16 05 2D` |

The check is `ScriptMode_files_present` @ `0x1060F57A`: both files must pass `fs_stat`.

Re-check of `DEVELOP.MOD` (2026-10-21):

- `ScriptMode_files_present` pushes the encoded bytes of `C:\DEVELOP.MOD` with 15 `LDI:8` instructions and decodes them with `c ^ 0xFF ^ 0xD6` (equivalent to XOR 0x29). It then only calls `fs_stat`; it never opens or reads the file.
- A whole-image scan for the same `LDI:8` sequence finds only `0x1060F5FA`. A second hit at `0x10A8F1B4` lies in the sub-CPU section and is coincidental.
- `0x1079FF40` holds a constant copy of the same encoded string, right after the format string `C:\%08d.%03d`. Nothing references it; it is leftover compiler init data.
- Neither the plain nor the XOR-0x29 form of `DEVELOP.MOD` appears anywhere else.
- Conclusion: K-5 IIs 1.07 does not check content or length.
  - The GR IV and GR IIIx 1.60 were found on hardware to require exactly these 10 fixed bytes.
  - They do not decode to readable text with single-byte XOR, addition or chained XOR, so their meaning is unknown.
  - `make_debug_card.py` always writes them for compatibility with other bodies and firmware versions.

## 2. Power-on conditions

When `Boot_classify` @ `0x105E815A` decides the power-on is not a "normal" one, it takes the special branch `Boot_special_poweron` @ `0x105E81D8`:

```
if (SW_DEBUG_MENU && OK(6) + DISP(10) held)              -> Development Menu1..5
else if (SCRIPT_EN_MODE || DEBUG_MODE || DOOR(0x1E) active):
    if (SCRIPT_EN_MODE && AUTORUN.541 on card)            -> AUTORUN self test
    else if (00077681.541 and DEVELOP.MOD both on card)   -> factory script mode (this document)
```

The key codes come from the SWITCH TEST draw function at `0x10614978`, which pairs each key code with a name:

| Key code | Name | Probable physical control |
| --- | --- | --- |
| 0 | SWS | Shutter half press |
| 1 | SWR | Shutter full press |
| 3 | CARD | Card inserted |
| 5 | AF | AF button |
| 6 | 4WOK | OK in the 4-way pad |
| 7 | MENU | MENU button |
| 9 | INFO | INFO button |
| 10 | DISP | DISP (physical button to be confirmed) |
| 0x11–0x14 | 4WU/4WD/4WR/4WL | 4-way pad |
| 0x15 | AEL | AE-L |
| 0x16 | GREEN | Green button |
| 0x17 | XVAVSET | Unidentified |
| 0x18 | PRV | Preview |
| 0x1D | FLPOP | Flash pop-up |
| **0x1E** | **DOOR** | **Card-door switch** |
| 0x20 | GP | Unidentified |
| 0x21 | ISO | ISO button |
| 0x22 | LIVE | Live view |
| 0x23 | 36 | Unidentified |
| 0x25 | RAW | RAW button |
| 0x26 | ERASE | Erase button |

**Conclusion:** on a fresh camera (all flags off), entering script mode **requires powering on with the card door open**, so that the DOOR switch is active.

Insert the card, leave the door open and switch on. If that does not work, press the switch under the door latch with a finger at the moment of power-on.

Once `DEBUG_MODE` or `SCRIPT_EN_MODE` is on, every power-on takes this branch and the script runs again whenever it is on the card. After setting things up you **must delete or rename the script file**.

## 3. Script format

The reader is `ScriptMode_load_script` @ `0x1060F700`; lines are split by `script_readline` @ `0x10616BDA`.

- The whole file is read into memory and processed line by line, at most 0x400 bytes per line.
- A line may contain several `[...]` commands. The text between the brackets (at most 0x7F bytes) is passed unchanged to `ScriptMode_parse_command`.
- At `!` or `;` **the rest of the line is ignored**, so these characters start comments.
- Commands are compared with `strcmp`: case-sensitive, and the spacing must match exactly, for example `[DEBUG_MODE EN]`.
- Unknown commands are silently ignored.

## 4. Command table (`ScriptMode_parse_command` @ `0x1060F950`)

Results go into an array `cmd[index]`: EN writes 1, DIS writes 2, and single-word actions write 1. `cmd[0x25]` holds the region code and starts at 0xFF.

| Index | Command | Handler / effect | Risk |
| --- | --- | --- | --- |
| 0x00 | `DEBUG_MODE EN` / `DEBUG_MODE DIS` | `SysFlags_set_debug_mode`, offset +0x04. Switching from off to EN also calls `0x106162C6` | Low, reversible |
| 0x01 | `CFDOOR_OPEN EN/DIS` | Offset +0x08; allows operation with the card door open | Low |
| 0x02 | `WRITE_CF_VNDR EN/DIS` | Offset +0x0C | Unknown |
| 0x03 | `SCRIPT_EN_MODE EN/DIS` | Offset +0x10; enables AUTORUN | Low |
| 0x04 | `USR_DAT_CLEAR` | **Clears user data** (highest priority, runs immediately) | Medium, equivalent to a factory reset |
| 0x05 | `SWITCH_TEST` | Key test screen | Read-only |
| 0x06 | `DISPLAY_TEST` | Display test | Read-only |
| 0x07 | `MEMORY_TEST` | Memory test | Read-only |
| 0x08 | `RELEASE_AGING` | Shutter aging test (**uses up shutter life**) | High |
| 0x09 | `LENS_COMUNICATION_CHECK` | Lens communication check | Read-only |
| 0x0A | `CPU_ADJ_FLG_CLEAR` | Clears CPU calibration flags | **High** |
| 0x0B / 0x0C | `CPU_ADJ_CSV_WRITE` / `CPU_TST_CSV_WRITE` | Loads `KB541ADJ/TST.CSV` from the card | **High** |
| 0x0D / 0x0E | `CPU_ADJ_CSV_READ` / `CPU_TST_CSV_READ` | Exports calibration values to CSV | Read-only |
| 0x0F | `CPU_ROM_STORE` | Dumps the CPU ROM to `KB541CPU.BIN` | Read-only; **recommended first, as a backup** |
| 0x10 | `DSP_ROM_STORE` | Dumps the DSP ROM to `KB541DSP.BIN` | Read-only |
| 0x11 | `AF_PINT_DISP` | Shows AF focus offsets | Read-only |
| 0x12 | `ICCD_PINT_OFF_CLEAR` | Clears focus calibration | **High** |
| 0x13 | `COLOR_PINT_COR_CLEAR` | Clears focus colour correction | **High** |
| 0x14 | `SI_ALL_ON` | Lights all viewfinder superimpose segments | Read-only |
| 0x15 / 0x16 | `CPU_ADJ_DAT_READ` / `CPU_ADJ_DAT_WRITE` | `KB541CPU.ADJ` export (READ) and load (WRITE) | READ read-only, WRITE high |
| 0x17 / 0x18 | `DSP_ADJ_DAT_READ` / `DSP_ADJ_DAT_WRITE` | `KB541.ADJ` | Same as above |
| 0x19 | `ALL_ADJ_DAT_READ` | Exports all calibration data | Read-only; recommended backup |
| 0x1A / 0x1B | `DSP_USR_DAT_READ` / `DSP_USR_DAT_WRITE` | `KB541.USR` | READ read-only |
| 0x1C | `SR_BULB` | Shake-reduction bulb test | Medium |
| 0x1D | `DIS_AF_F28` | Disables the F2.8 AF sensor | Medium, test only |
| 0x1E | `ONLY_AF_F28` | Uses only the F2.8 AF sensor | Medium |
| 0x1F | `VLENS_CTRL` | Virtual lens control | Medium |
| 0x20 | `LENS_CPU_FIRMUP` | Lens firmware update (`LENSCPU.bin`) | **High** |
| 0x21 / 0x22 | `LENSROM_LOAD` / `LENSROM_STORE` | Lens EEPROM load and dump | STORE read-only, LOAD high |
| 0x23 | `OPEN_DEBUG_MENU` | Opens Development Menu 1–5 directly | Low |
| 0x24 | `SW_DEBUG_MENU EN/DIS` | Offset +0x18; enables OK+DISP at power-on for the dev menu | Low |
| 0x25 | `REGION_CODE 0`…`REGION_CODE 5` | Rewrites the region code (language, video standard) | Medium |
| 0x26 | `DISP_REGION_CODE` | Shows the region code | Read-only |
| 0x27 | `CAM_LOG_DAT_READ` | Dumps the camera log to `KB541CAM.LOG` | Read-only |
| 0x28 | `CAM_LOG_DISP` | Shows shutter count, wireless channel, focus offset | Read-only |
| 0x29 | `USR_CLEAR_CAM_DISP` | Clears user data and shows the result | Medium |
| 0x2A | `CRE_RECOVERY_FW` | Creates recovery firmware | Medium, writes flash |
| 0x2B | `G200_TEST` | Test; needs `G200STEP.DAT` | Unknown |
| 0x2C | `LIVE_VIEW_TEST_MODE EN/DIS` | Live-view test mode | Low |

## 5. Execution semantics (`ScriptMode_execute` @ `0x1061000E`)

1. **Exclusive actions**: only one runs, chosen by priority, after which the screen waits for a key.
   - Priority: `USR_DAT_CLEAR` → `USR_CLEAR_CAM_DISP` → the CSV/ROM/ADJ commands → `LENS_CPU_FIRMUP` → `CRE_RECOVERY_FW` → `LENSROM_*` → `G200_TEST`.
   - The screen shows `WAIT...`, then `COMPLETE...` or `ERROR...`.
2. With no exclusive action, **flag commands** are processed.
   - They can be combined: `DEBUG_MODE`, `CFDOOR_OPEN`, `WRITE_CF_VNDR`, `SCRIPT_EN_MODE`, `SW_DEBUG_MENU`, `REGION_CODE`, `LIVE_VIEW_TEST_MODE` and the two `*_CLEAR`.
   - If any of them changed, `SysFlags_commit` is called once to persist them.
3. Then **one UI command** runs, by priority: `OPEN_DEBUG_MENU` → `SWITCH_TEST` → `DISPLAY_TEST` → `MEMORY_TEST` → `RELEASE_AGING` → `LENS_COM…` → `AF_PINT_DISP` → `CAM_LOG_DISP` → `SI_ALL_ON` → `SR_BULB` / `AF F2.8` → `VLENS` → `DISP_REGION_CODE`.

## 5.1 Line endings and emulation check

- `script_readline` @ `0x10616BDA` **treats only `\r` as end of line** and skips the byte after it, so **CRLF is mandatory**.
  - With LF only, the whole file becomes one line; the 0x400-byte buffer is not bounds-checked, and every command after the first `;` is lost.
  - With CR only, the first character of each following line is eaten.
- `tools/emulate_parse.py --all` runs the **firmware's own** `ScriptMode_parse_command` in Ghidra's P-code emulator.
  - All 56 command strings land in the expected slots; see `notes/emulate_parse_all.txt`.
  - All 4 negative cases are rejected: lower case, double space, trailing space and the empty string.
- `tools/make_debug_card.py` self-checks generated files with a Python port of the firmware tokenizer. `check --emulate` then feeds the tokens to the emulator.
- Pre-generated card files are in `sdcard/devmenu/`, `sdcard/enable/`, `sdcard/disable/` and `sdcard/camlog/`.

## 5.2 Related bodies

Public research on the Ricoh GR IV and GR IIIx ([radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion](https://github.com/radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion)) shows that the K-5 IIs factory-script mechanism lives on in 2020s models. The GR column below comes from that repository's documents and its `tools/create_factory_entry.py`.

| Item | K-5 IIs 1.07 (this project) | GR IV 1.11 / GR IIIx 1.60 |
| --- | --- | --- |
| Script file name | `00077681.541`, `%08d.%03d` (script id, model code) | `00078560.636` / `00078490.609`, same format |
| `DEVELOP.MOD` | Existence only | Must be the 10 bytes `07 01 2C 1F 10 03 1E 16 05 2D` |
| Menu command | `[OPEN_DEBUG_MENU]` | `[OPEN_FACTORY_DEBUG_MENU]`; one line suffices (verified on hardware) |
| Entry condition | Power on with card door open, or flags already on | Power on holding MENU |
| Debug flag | Settings object `+0x04`, on `0x5AA5A55A` / off `0xFFFFFFFF` | CameraModeData `+4`, identical values |
| Auto-run script | `AUTORUN.541`, BASIC-like, results in `CHKDAT.541` | `script/startup.ttl`, Tera Term language with `filecopy`; `C:` is the SD card, `A:` internal resources |
| Debug UI consumers | Four-part version numbers, extra TEST MODE page (with `DEBUG MODE DISABLE`); no hidden key sequence found. See [debug-mode-consumers.md](debug-mode-consumers.md) | `Camera Mode` text, four-part version numbers, timed four-key sequence into `DevelopmentMenuController` |

Earlier K-30 research from the same company ([i-am-shodan/PHDK](https://github.com/i-am-shodan/PHDK), [i-am-shodan/PentaxFirmwareTool](https://github.com/i-am-shodan/PentaxFirmwareTool)) also matches the K-5 IIs on firmware integrity checks; see [firmware-checksum.md](firmware-checksum.md).

## 6. Recommended first script

Start with `devmenu` (`[OPEN_DEBUG_MENU]`) to confirm that script mode works; it writes no flags. Then:

```
; K-5 IIs: enable debug mode + dev menu (safe flags only)
[DEBUG_MODE EN]
[SW_DEBUG_MENU EN]
```

To switch off:

```
[DEBUG_MODE DIS]
[SW_DEBUG_MENU DIS]
[SCRIPT_EN_MODE DIS]
```

## 7. Effects once enabled (confirmed statically)

- With `DEBUG_MODE` on:
  - The capture pipeline reads `SYSPARAM.TXT` at init; keys are in [sd-file-entrypoints.md](sd-file-entrypoints.md).
  - The setup menu gains a TEST MODE page (0x0D) after setup page 0x0C: CAPTURE/SYSTEM TEST, AF TEST, STRINGS DISP TEST, Icon Test, DEBUG MODE DISABLE.
  - The factory version page switches from two-part to four-part DSP/CPU version numbers.
  - Details are in [debug-mode-consumers.md](debug-mode-consumers.md). `0xC000468C` is not the debug flag; it only selects the `DEBUG MODE` / `PC VENDOR` label text.
- With `SW_DEBUG_MENU` on, holding OK+DISP at power-on opens **Development Menu1–5**:
  - Menu1: flag toggles, `USR DAT CLEAR`, `REGION CODE`
  - Menu2: `SWITCH TEST`, `RELEASE AGING`, `LENS COM CHECK`, `AF PINT DISP`, `CAMERA LOG DISP`
  - Menu3: calibration data transfer between camera and SD
  - Menu4: lens ROM read/write/edit and lens firmware update
  - Menu5: board version, DSP chip version, dust removal test, media test, display test, memory test, live-view test
- With `SCRIPT_EN_MODE` on, an `AUTORUN.541` on the card at power-on runs a BASIC-style test script whose results go to `CHKDAT.541`.

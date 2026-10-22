English | [简体中文](debug-mode-consumers.zh-CN.md)

# Where DEBUG_MODE is read (K-5 IIs 1.07)

Goal: find what actually changes in the firmware once `DEBUG_MODE` is on (SysFlags +0x04, persistent value `0x5AA5A55A`/`0xFFFFFFFF`), and find a way to leave debug mode on the camera itself. The reference is the GR IV's debug behaviour: a four-part version page, hidden menus and so on.

Method: enumerate every `LDI:32 #getter` load site through GhidraMCP, then decompile each caller.
- Some callers were not recognised as functions by Ghidra; they were created with `tools/containing.py --create`.
- Vtable entries point 2 bytes before the entries Ghidra created automatically, so those functions were rebuilt at the vtable addresses.

## 1. The three getters

| Function | Address | Notes |
| --- | --- | --- |
| `SysFlags_is_debug_mode` | `0x10615F70` | Reads SysFlags object +0x04. Load sites: `104BB3A0`, `105DD3E8`, `1060D212`, `10610F6A`, `10611682`, `10611720`, `10618D1A/2A/36` |
| `flags_is_debug_mode` | `0x10483F1C` | Persistent-storage getter. Called by `FUN_105EC2A2` (the wrapper used by boot classification, see [debug-script.md](debug-script.md) section 2) and `FUN_104840AE` (reads all flags into an array) |
| `flags_is_debug_mode_2` | `0x10483EF0` | Used via `FUN_104F7936`; reads persistent area 3 |

The same group has getters and setters for the other flags:
- Getters: `FUN_10483F48/F74/FCC`, `FUN_10484012`.
- Setters: `FUN_10483F5C/FB4/ECA`, `FUN_10484018`, `FUN_1048400C`.
- `FUN_10484046` writes all flags back from an array.

## 2. Behaviour changes

| Location | Change in debug mode | GR IV counterpart |
| --- | --- | --- |
| `FUN_1060D1FA` (version page of the factory screen chain) | Version changes from two-part `VER %d.%02d` to four-part `DSP VER %d.%02d.%02d.%02d` and `CPU VER %d.%02d.%02d.%02d`, plus an extra main-CPU version line | Four-part version page, **exact match** |
| `FUN_10618CBC` | Also calls `FUN_106182D2(obj, debug?2:0, debug)`, shown for 5 seconds | Same as above |
| Setup menu (init table `0x1000AD2C`, navigation `FUN_10230824`) | An extra TEST MODE page (page 0x0D), see section 3 | Hidden factory menu |
| `FUN_104BA894` line 731 | If `FUN_1049E2F8(…,2)==2` and debug mode, forces output struct +0x5A to 1; otherwise uses setting 0xDE. Meaning unconfirmed | — |
| `FUN_105EC9D8` | Outside debug mode calls `FUN_104A8B6C()` and `FUN_104A946C(1,0)`; debug mode skips both. Meaning unconfirmed | — |
| `FUN_105DD34C` | Builds a status bitmap; debug mode is bit 0 of the first word (probably queried over USB/PC) | — |
| `FUN_1061167A` | Snapshots all flags to struct +0x5E..+0x68 for Development Menu1 to show and edit | — |
| `FUN_106116DE` (Development Menu1 screen) | Shows `DEBUG MODE <EN>/<DIS>`, `CARDDOOR OPEN`, `WRITE CARD VNDR`, `SCRIPT EN MODE`, `AUTO TEST MODE`, `USR DAT CLEAR`, `REGION CODE`; writes the flags back on confirm | GR IV factory debug menu |
| `ScriptMode_execute` `0x10610F6A`, `0x10610F96` | Debug branches while running script commands, see [debug-script.md](debug-script.md) | — |

The `mode` argument of `FUN_106182D2(obj, mode, debug)`:
- 0 shows only the DSP version, 1 only the CPU version, 2 both.
- 3 shows the DSP chip version (used by Development Menu5).
- A true third argument selects the four-part format.

The factory screen runner `FUN_1060C1BA(obj, n)` picks the starting screen from `n`:
- 0: version page (singleton `FUN_1060D15A`, object `0xC006BCF0`)
- 1: ScriptMode
- 2: SwitchTest
- 3: Development Menu1 (`FUN_1061149E`)

`FUN_1060C402` links the screens into a list. The version page is followed by Menu1, and Menu1 to Menu5 (`1061149E` → `10611C62` → `10612234` → `10612898` → `10612D0C`) form a ring.

## 3. TEST MODE page in the setup menu

The setup page sequence comes from the ROM init table at `0x1000AD2C`:

- Normal: `1 2 3 4 5 8 9 A B C E F 10 11`, 14 pages.
- Debug mode: `D` is inserted after `C`, 15 pages. The short sequence `6..C` likewise becomes `6..D`.
- Navigation is `FUN_10230824`. A further condition, `FUN_104FB7EA`, always returns 0 in this firmware.

Page 0x0D:

- Layout table `0x10707F58`, draw function `FUN_10227D32` (vtable `0x1070DDF4`, slot at `0x1070DF20`), key handler `FUN_102282BC`. OK is key code 7; key 0xE returns via `FUN_102301CE(…,0x18)`.
- Strings start in the localisation table at `0x1002B75C`, each byte encoded as +9.

| Row | Opens screen |
| --- | --- |
| CAPTURE/SYSTEM TEST | 0x67 |
| AF TEST | 0x65 |
| STRINGS DISP TEST | 0x66 |
| Icon Test | 0x68 |
| **DEBUG MODE DISABLE** | 0x69 |

## 4. Ways out of debug mode

### 4.1 Menu: DISABLE DEBUG MODE ?

`DEBUG MODE DISABLE` on the TEST MODE page opens a confirmation dialog:

- Constructor `FUN_104309D2`, vtable `0x1076194C`. Draw slot 37 = `0x10430AD4`, layout `0x10761370` (`DISABLE DEBUG MODE ?` / `DISABLE` / `CANCEL`); key slot 45 = `0x10430DA4`.
- `FUN_102A6CE6` stores the instance at screen manager +0x244.
- Choosing `DISABLE` (ID `0x1FF0002`) calls `FUN_10430E9E` → `FUN_104F786A(obj, 0)`.
  - If debug mode is on, it clears, in order: `DEBUG_MODE`, `CFDOOR_OPEN`, `WRITE_CF_VNDR`, `SCRIPT_EN_MODE`, the flag behind `0x10483FB4`, `SW_DEBUG_MENU` and the flag behind `0x10483ECA`.
  - It then commits to persistent storage with `FUN_1048BD74`.

This exit path needs **no card and no script**, and serves as a fallback to the `disable` card.

### 4.2 SYSPARAM: DAC_DEBUG_MODE_BREAK

The DA calibration loop `FUN_102AFB2E` starts by checking `FUN_104A5ACE(0x22)`, which is `DO_DA_CALIB` (object +0xF4). On one exit path it checks `FUN_104A5ACE(0x2A)`, which is `DAC_DEBUG_MODE_BREAK` (+0x114), and if set calls the same `FUN_104F786A`.

So `[DAC_DEBUG_MODE_BREAK]1@` in `SYSPARAM.TXT` clears debug mode once the DA calibration flow runs. How to enter that flow is unconfirmed; not recommended.

### 4.3 BOARD TEST 36: FLASH INIT (the opposite, beware)

The BOARD TEST list (strings from `0x10798790`, `COMMAND: %02X HEX`, tests 10–38, entry reference at `0x105D23FA`) includes `36 : FLASH INIT` (`FUN_105D3AD8`, called by `FUN_105D2C46` at `0x105D2D7E`). It does the following:

1. `FUN_1061619E` clears all flags and commits;
2. then `SysFlags_set_debug_mode(1)` and `set_cfdoor_open(1)`;
3. finally `FUN_10616168`.

After FLASH INIT the camera is in the factory state with **debug mode on**. Do not mistake it for an exit path.

## 5. Correction: `0xC000468C` is not DEBUG_MODE

Earlier notes treated `_DAT_C000468C` as the DEBUG label switch. That was wrong:

- It is a 0/1/2 mode value, written only by `FUN_1023019C`, whose caller `FUN_102B29C2` copies obj+0x70.
- `ui_show_debug_mode_label` (`0x10245F40`) shows `DEBUG MODE` when it is 0 and `PC VENDOR` otherwise. It only picks the label text and does not decide whether debug mode is on.
- `FUN_102301CE` skips an action when it is 1 and the argument is 1.

The real debug state lives only in SysFlags +0x04 and its persistent storage.

## 6. Hidden key sequences

On the GR IV in debug mode, a timed four-key sequence opens `DevelopmentMenuController`. No equivalent sequence was found in K-5 IIs 1.07: every debug-mode read is listed in section 2, and none is in key-event counting or timing logic.

The only key combination for the Development Menu is still OK+DISP held at power-on, which needs `SW_DEBUG_MENU`; see [debug-script.md](debug-script.md) section 2.

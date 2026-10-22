English | [简体中文](debug-mode-guide.zh-CN.md)

# PENTAX K-5 IIs (firmware 1.07) factory debug mode guide

> This guide is derived entirely from static reverse engineering and P-code emulation. It has **not yet been verified on a real camera**. Section 6 is a test log; please run the steps in order and fill it in.
> Nothing here **modifies the firmware**. You only put files on the SD card. The only things that change are flags the camera stores persistently, and the `disable` script turns them back off.
> You use this guide entirely at your own risk (see the disclaimer in the top-level README).

## 0. Preparation

- The camera must be on firmware **1.07**. To check, power on while holding MENU; the version appears in the middle of the LCD.
  - Other versions may use a different script number. `make_debug_card.py` reads the number from the firmware header.
  - If you are not on 1.07, update with Ricoh's official procedure first (top-level README, "Getting the firmware").
- Use a fully charged battery and an SD card formatted in this camera, in **slot 1**.
- Generate the card files on a computer, or copy the pre-generated ones from `sdcard/`:

```bash
python3 tools/make_debug_card.py presets
python3 tools/make_debug_card.py write /run/media/$USER/SDCARD --preset devmenu
python3 tools/make_debug_card.py check /run/media/$USER/SDCARD/00077681.541 --emulate   # optional, needs GhidraMCP + firmware
```

The card root should then contain:
- `00077681.541`: the command script, with CRLF line endings.
- `DEVELOP.MOD`: the 10 bytes `07 01 2C 1F 10 03 1E 16 05 2D`.
  - The K-5 IIs only checks that this file exists.
  - These bytes are what the GR IV / GR IIIx were found to require. Including them does no harm on the K-5 IIs.

## 1. Entering script mode (first time)

Start with the `devmenu` card, which contains only `[OPEN_DEBUG_MENU]`. It does not write any persistent flag. If you reach the Development Menu, the file name, `DEVELOP.MOD` and the card-door power-on condition are all correct; only then use the `enable` card to set flags.

On Ricoh's GR IV, a single `[OPEN_FACTORY_DEBUG_MENU]` line plus `DEVELOP.MOD` opens the factory menu, verified on hardware ([radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion](https://github.com/radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion)). The K-5 IIs `OPEN_DEBUG_MENU` matches it in name and purpose.

1. Power off, insert the SD card, and **leave the card door open**.
2. Power on.
   - At power-on the firmware checks the card-door switch (key code 0x1E, named DOOR). With the door open, it takes the "special power-on" branch and looks for the script files.
   - If nothing happens, power off and try again while pressing the card-door detection switch with a finger at the moment of power-on.
3. The script screen should appear.
   - Flag commands such as `DEBUG_MODE EN` are written and committed.
   - Display or dump commands show `WAIT...`, then `COMPLETE...` or `ERROR...`. Press any key to continue.
   - The `devmenu` card should go straight to Development Menu1. Leave with `[MENU]` and do not change anything there.
4. Power off, switch to the `enable` card, and power on once more with the door open.
5. Power off and **delete or rename `00077681.541` on the computer**.
   - Once `DEBUG_MODE` is on, every power-on takes the special branch. If the script is still on the card, it runs again on every boot.
6. Close the door, power on normally, and confirm the camera is in debug mode (section 3).

## 2. Presets

| Preset | Contents | Purpose | Risk |
| --- | --- | --- | --- |
| `enable` | `[DEBUG_MODE EN]` `[SW_DEBUG_MENU EN]` | Turn on debug mode and the dev-menu key combo | Low, reversible |
| `disable` | `[DEBUG_MODE DIS]` `[SW_DEBUG_MENU DIS]` `[SCRIPT_EN_MODE DIS]` | Turn everything off | None |
| `devmenu` | `[OPEN_DEBUG_MENU]` | Open the development menu directly | Low |
| `camlog` | `[CAM_LOG_DISP]` | Show shutter count, wireless channel, focus offset | Read-only |
| `backup-cpu-rom` | `[CPU_ROM_STORE]` | Dump `KB541CPU.BIN` | Read-only |
| `backup-dsp-rom` | `[DSP_ROM_STORE]` | Dump `KB541DSP.BIN` | Read-only |
| `backup-adj` | `[ALL_ADJ_DAT_READ]` | Dump all calibration data `KB541*.ADJ` | Read-only |
| `backup-camlog` | `[CAM_LOG_DAT_READ]` | Dump `KB541CAM.LOG` | Read-only |

**Only one "exclusive action" (a dump, clear and so on) runs per power-on**, so do backups one at a time.

**Strongly recommended:** after enabling debug mode, run the four `backup-*` presets first and keep the files on your computer. If calibration data is ever wiped, these backups are the only way to restore it.

Do **not** publish or share these dumps. They contain Ricoh's copyrighted firmware and your camera's individual calibration data.

The tool refuses to generate dangerous commands by default, for example `USR_DAT_CLEAR`, `*_WRITE`, `*_CLEAR`, `RELEASE_AGING`, `LENS_CPU_FIRMUP` and `REGION_CODE n`. Pass `--allow-dangerous` only if you really mean it. The full risk table is in [notes/debug-script.md](../notes/debug-script.md).

## 3. What becomes available

### 3.1 Development Menu (needs `SW_DEBUG_MENU EN`)

Hold **OK and DISP** (key codes 6 and 10) while powering on. Use the 4-way pad to select, `[OK]` to run, and `[MENU]` to cancel or go back.

| Menu | Items | Advice |
| --- | --- | --- |
| Menu1 | DEBUG MODE / CARDDOOR OPEN / WRITE CARD VNDR / SCRIPT EN MODE / AUTO TEST MODE toggles, USR DAT CLEAR, REGION CODE | Touch only the first two. **Never** run USR DAT CLEAR or change the region code |
| Menu2 | SWITCH TEST, RELEASE AGING (MAN/AUTO), LENS COM CHECK, AF PINT DISP, CAMERA LOG DISP | All read-only except RELEASE AGING, which **fires the shutter continuously** |
| Menu3 | CPU/DSP ADJ DAT transfer between camera and SD (CAMERA=>SD or SD=>CAMERA), CAMERA LOG CAMERA=>SD | Use only the `CAMERA=>SD` direction |
| Menu4 | LENS ROM DAT transfer, LENS ROM EDIT R/W, LENS CPU FWUP | Use only `CAMERA=>SD`. **Do not** edit or update lenses |
| Menu5 | BOARD VER, DSP CHIP VER, DUST REDUCTION TEST, MEDIA TEST, DISPLAY TEST, MEMORY TEST, LIVEVIEW TEST | Mostly read-only. MEDIA TEST may write to the card |

The physical button behind DISP is not confirmed yet; the K-5 IIs INFO button is a different key code, 9. If OK+DISP does not work, use the `devmenu` preset instead.

### 3.2 TEST MODE page in the setup menu (needs `DEBUG_MODE EN`)

In debug mode, the normal MENU gains a TEST MODE page (page 0x0D) after setup page 0x0C. No key combination is needed:

| Item | Description | Advice |
| --- | --- | --- |
| CAPTURE/SYSTEM TEST | Capture and system test | Not reverse engineered yet; do not enter |
| AF TEST | AF test | Same as above |
| STRINGS DISP TEST | Shows UI strings one by one | Read-only, safe to look at |
| Icon Test | Shows icons | Read-only, safe to look at |
| **DEBUG MODE DISABLE** | Opens `DISABLE DEBUG MODE ?`; choose `DISABLE` to leave debug mode | Fallback exit path, see section 4 |

The version page of the factory screens also changes from `VER x.yy` to the four-part `DSP VER x.yy.zz.ww` and `CPU VER x.yy.zz.ww`. This matches what the GR IV shows in debug mode. No timed four-key sequence like the GR IV's was found. Details are in [notes/debug-mode-consumers.md](../notes/debug-mode-consumers.md).

### 3.3 Key names shown in SWITCH TEST

`SWS` (half press), `SWR` (full press), `PRV`, `AF`, `LIVE`, `GREEN`, `FLPOP`, `DOOR`, `CARD`, `GP`, `36`, `RAW`, `MENU`, `ERASE`, `INFO`, `4WU/D/L/R/OK`, `DISP`, `XVAVSET`, `AEL`, `ISO`, `AEMD`, `AFMD`, `AFAREA`, `MODE`, `FDL/RDL` (front/rear dial counters), `AC:ON/OFF`.

Use this screen to find out which physical controls DISP and DOOR are.

### 3.4 SYSPARAM.TXT (needs `DEBUG_MODE EN`)

In debug mode, the capture pipeline reads `SYSPARAM.TXT` from the card root when it initialises.

Format:
- Each entry is `[KEY]value1,value2@`; `@` ends an entry.
- Spaces, CR and LF are ignored.
- `#` ends the file.
- Numbers are parsed as decimal, `atoi` style; a minus sign is allowed.

The safest first experiment is `sdcard/sysparam-laptime/SYSPARAM.TXT`:

```
[ENABLE_RELEASE_LAP_TIME_DISPLAY]1@
#
```

Expected effect: the release time is shown after a shot.

The other keys are listed in section 3 of [notes/sd-file-entrypoints.md](../notes/sd-file-entrypoints.md).
- Some keys change image output, such as `DISABLENR` and `CAPTURE_ALL_PIXEL`.
- Others write large intermediate RAW data to the card, such as the `STORE*` family.

Try those only after lap-time works, one key at a time.

### 3.5 AUTORUN scripts (needs `SCRIPT_EN_MODE EN`, advanced)

If the card holds `AUTORUN.541` at power-on, the camera runs a BASIC-like test script of up to 20000 bytes and appends results to `CHKDAT.541`.

Known control-flow keywords include `PRINT WAIT GOTO GOSUB IF WHILE FILEOUT FSEARCH TIMERON`. The camera-operation commands have not been reverse engineered yet, so this is not recommended for now.

## 4. Exit and recovery

1. Run the `disable` preset once using the procedure in section 1.
2. Delete `00077681.541`, `DEVELOP.MOD`, `SYSPARAM.TXT` and `AUTORUN.541` from the card.
3. Power on normally and confirm the debug-only items are gone.

Fallback exit without a card: MENU → TEST MODE page in the setup section → `DEBUG MODE DISABLE` → choose `DISABLE` in `DISABLE DEBUG MODE ?`. This clears `DEBUG_MODE`, `CARDDOOR_OPEN`, `WRITE_CF_VNDR`, `SCRIPT_EN_MODE`, `SW_DEBUG_MENU` and related flags in one go and saves them (`FUN_104F786A`).

Warning: Menu5's BOARD TEST contains `36 : FLASH INIT`. It clears all flags and then **turns debug mode and the card-door flag back on**. It is not an exit path; do not run it.

## 5. Risks and rules

- Use only read-only or reversible commands. Every `WRITE`, `CLEAR`, `LOAD`, `FIRMUP` and `REGION_CODE` operation needs its own assessment.
- Do not run dumps or tests on a low battery.
- If the camera will not boot normally or keeps entering the script screen, remove the card and use a card holding only the `disable` script plus `DEVELOP.MOD`, entering as in section 1.
- Modifying firmware is only an option if the SD-card route fails. It needs separate confirmation and is not part of this guide.

## 6. Hardware test log

| # | Action | Expected | Actual | Notes |
| --- | --- | --- | --- | --- |
| 0 | `devmenu` card, power on with door open | Development Menu1 appears directly | | If not, debug the door condition before continuing |
| 1 | `enable` card, power on with door open | Script screen, or completes silently | | Photo or description |
| 2 | Delete script, close door, power on normally | Setup section of MENU gains a TEST MODE page | | Most reliable sign that debug mode is on |
| 3 | Hold OK+DISP while powering on | Development Menu1 | | If not, try OK+INFO, or use the `devmenu` script |
| 4 | Menu2 → SWITCH TEST | Key names highlight as keys are pressed | | Note which physical controls DISP and DOOR are |
| 5 | `camlog` card | TOTAL COUNT (shutter count) shown | | |
| 6 | `backup-cpu-rom`, `backup-dsp-rom`, `backup-adj`, `backup-camlog` | Files appear on the card | | File sizes (do not share the files) |
| 7 | `sysparam-laptime`, take a shot in debug mode | Release time shown | | |
| 8 | TEST MODE page → STRINGS DISP TEST / Icon Test | String or icon list shown | | Read-only |
| 9 | TEST MODE page → DEBUG MODE DISABLE → DISABLE | TEST MODE page disappears | | Menu exit path; `enable` card can turn it back on |
| 10 | `disable` card | Back to normal | | Card exit path |

Please report the results of this table (file sizes only for the dumps, not the files), so the guide can be corrected.

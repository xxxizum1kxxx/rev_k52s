English | [简体中文](sd-file-entrypoints.zh-CN.md)

# SD-card file entry points

The full list of path strings and where they are used is in `notes/sd_paths_raw.txt`, produced by scanning `LDI:32` immediates. The `541` in file names is the model code from firmware header offset 0x10.

## 1. Entry points that change camera behaviour

| File | When | Precondition | Handler | Purpose |
| --- | --- | --- | --- | --- |
| `C:\00077681.541` **plus** `C:\DEVELOP.MOD` | Power-on | Both files exist and the power-on branch conditions hold ([debug-script.md](debug-script.md)) | `ScriptMode_files_present` → `ScriptMode_load_script` → `ScriptMode_parse_command` → `ScriptMode_execute` | Factory command script: `[DEBUG_MODE EN]` and 45 other commands |
| `C:\AUTORUN.541` | Power-on | `SCRIPT_EN_MODE` is on and the file exists (`FUN_105e4a42` → `FUN_1060925a`) | `FUN_1060940e` reads it (max 20000 bytes) and hands it to the interpreter (`this+0x60`) | BASIC-like test script language (section 2) |
| `C:\CHKDAT.541` | While AUTORUN runs | Same as above | `FUN_10609da4` (open and append) | AUTORUN result log |
| `C:\SYSPARAM.TXT` | Capture pipeline init (`FUN_104a5a78`) | **DEBUG_MODE is on** (`FUN_10483ef0`) | `FUN_104a5ed2` | Image-pipeline debug parameters, about 90 keys (section 3) |
| `C:\FWDC218B.BIN` / `C\D\S.BIN` | Power-on holding MENU (official update flow) | File size must match exactly | `fwup_load_image` | Firmware update |
| `C:\KB541[B/C/S].BIN`, `C:\KB541.BIN` | Update flow | - | `0x104b3bae` and others | Probably service full or partial images |
| `C:\KBCHG.BIN` | Update flow | - | `FUN_104b3ac8` | Reads one parameter (`sscanf`) and passes it to the updater |
| `C:\NOWAIT` | Update flow | If the file is **absent**, the updater waits for a key | `FUN_104b6f3e` | When present, skips waits and confirmations during update |

## 2. AUTORUN script language (control-flow keywords)

The keyword table is at 0x1079F067:

```
END EXIT PAUSE WAIT GOTO IFGOTO ALLCLR CLS PRINT LANGUAGE COLOR
GOSUB IFGOSUB RETURN IF ELSE WHILE INTERVAL CYCLE FILEOUT FSEARCH TIMERON TIMEROFF
```

Error messages: `Command Error / Command Not Support / Command is Rejected / Illegal Parameter / Syntax Error / Data Over Flow / Script is Finished`.

This is the same kind of mechanism as the "factory scripts" in the GR IV research. Camera-function commands (not in the table above) are forwarded by the interpreter to the camera command layer. That command table has not been extracted yet and is left for future work.

## 3. SYSPARAM.TXT

Format rules:
- Each entry is `[KEY]value1,value2@`; `@` ends an entry.
- `#` or `0x1A` ends the file.
- Spaces, CR and LF are ignored.
- At most 0x400 bytes are read.

Keys by category:

| Category | Keys |
| --- | --- |
| Data dumps | `STOREPREBAYER STOREBAYER STOREPREDARK STOREGEN STORE_CIS_INFO STORECPU STOREAE STOREAF STOREIQWD STOREDP STOREDEFECTPIXELDATA STOREVFPNDATA STORE_CAF STORE_LVAE` |
| Noise reduction and defect pixels | `DISABLENR FORCENR DISABLE_ALL_NR DISABLEDPC DISABLE_HW_DPC DISABLE_EX_DPC FORCE_EX_DPC FORCE_LEXP_DPC FORCE_HW_DPC DISABLE_BLACK_DPC DISABLEVFPNCOR ENABLE_SUPER_HIGH_ISO_NR` |
| Bayer filters | `DISABLEBAYFLT DISABLEBAYPREFLT FORCEBAYFLT FORCEBAYPREFLT DISABLE_BAYER_ALL_FILTER FORCE_FINE_SHARPNESS` |
| Sensor (CIS) | `CAPTURE_ALL_PIXEL CAPTURE_ALL_PIXEL_V CIS_DIRECT_GAIN CIS_CLAMP_OFF CIS_SELECT_OFF CIS_READOUT_UPSIDEDOWN CIS_STILL_BLACK_DUMMY CIS_SVR_SHR_SETTING CHANGE_CIS_AD_TIMING SET_CIS_STILL_HD_CYCLE SET_STILL_CLAMP_AREA SET_STILL_CLAMP_LEVEL` |
| Dark frame and OB correction | `DISABLE_SUBSTRACT_OB DISABLE_ACT_OB_CORRECT ENABLE_FORCE_ACT_OB_CORRECT ENABLE_DARK_FRAME_TV_RATIO ENABLE_STORE_DFS_FRAME ENABLE_SET_ADD_DFS_OFFSET ENABLE_SET_ADDTIONAL_OB` |
| Shading correction | `DISABLE_H_SHADING_CORR DISABLE_V_SHADING_CORR ENABLE_V_SHADING_COEF_FIXED` |
| Gain | `DIS_ISO_ADJ_GAIN DIS_RGB_ADJ_GAIN DISABLE_CIS_GAIN_DOWN ENABLE_SET_CIS_GAIN_DOWN DIRECT_GAIN` |
| Shutter and bulb | `BULB_DEBUG DISABLE_BULB_ALG WAIT_CLOSING_CURTAIN ENABLE_DUMMY_RELEASE ENABLE_RELEASE_LAP_TIME_DISPLAY ENABLE_ROLLING_CAPTURE ENABLE_ROLLING_STILL ENABLE_STILL_WINDOW_MODE ENABLE_SVD_1EV_UP` |
| Live view | `LV_MODE LV_DEBUG_SW KILL_LV_AE LV_INVALID_OFFSET_V LIVEVIEW_TEMPERATURE_FREE ENABLE_PHASE_CTL_GUI` |
| DAC and DA | `DAC_* DA_* DO_DA_CALIB PM_PARAM` |
| Shake reduction (SR) | `ENABLE_SR_TRIGGER_26KHZ` |

**Risk:** many keys change image output or dump large RAW data to the card. Start with display-only keys such as `ENABLE_RELEASE_LAP_TIME_DISPLAY`.

## 4. Service and calibration files (read or written by factory commands)

| File | Command | Nature |
| --- | --- | --- |
| `KB541ADJ.CSV` / `KB541TST.CSV` | `CPU_ADJ/TST_CSV_WRITE/READ` | CPU calibration export and import |
| `KB541CPU.BIN` / `KB541DSP.BIN` | `CPU_ROM_STORE` / `DSP_ROM_STORE` | **ROM dumps** (read-only, usable as backup; do not redistribute) |
| `KB541.ADJ` / `KB541CPU.ADJ` | `*_ADJ_DAT_READ/WRITE`, `ALL_ADJ_DAT_READ` | Calibration data; READ means camera → card |
| `KB541.USR` | `DSP_USR_DAT_READ/WRITE` | User data |
| `KB541CAM.LOG` | `CAM_LOG_DAT_READ` | Camera log (shutter count and more) |
| `LENSEEP.LNS` / `BACKUP.LNS` | `LENSROM_LOAD/STORE` | Lens EEPROM |
| `G200STEP.DAT` | `G200_TEST` | Test data |
| `LENSCPU.bin` | `LENS_CPU_FIRMUP` | Lens firmware update |

## 5. Other dump-only paths

There are also debug dump paths for RAW, JPEG and CSV data (`Resu%04d.raw`, `Dfct_*.raw`, `AF%04d.srm`, `DacLog.csv`, `%08d.bin/.jpg`, `MOV%04d.RAW` and others). They are only written when the corresponding debug switch is on and do not affect how the camera boots.
